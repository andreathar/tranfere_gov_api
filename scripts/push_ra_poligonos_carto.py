#!/usr/bin/env python3
"""Push dos polígonos das Regiões Administrativas (RAs) do DF para o CARTO DW.

Fluxo:
1. Lê o GeoJSON oficial de limites das RAs (GDF/IBRAM, camada 2025) já baixado em
   ``data/carto_exports/ra_boundaries_raw.geojson``.
2. Cruza com a demografia local da tabela ``df_regioes_administrativas``
   (PostgreSQL), casando nomes normalizados (sem acento/caixa) + aliases.
3. Cria (CREATE OR REPLACE) a tabela BigQuery
   ``transferegov_df_ra_poligonos`` no dataset privado do CARTO DW com coluna
   ``geom GEOGRAPHY`` e insere linha a linha via SQL API.
4. Verifica contagem de linhas/polígonos ao final.

Uso:
    .venv/bin/python scripts/push_ra_poligonos_carto.py [--dry-run]

Requer ``CARTO_API_KEY`` no ``.env``. Idempotente: pode rodar múltiplas vezes.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import psycopg2
import requests
from dotenv import load_dotenv

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("push_ra_poligonos_carto")

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
CARTO_SQL_URL = "https://gcp-us-east1.api.carto.com/v3/sql/carto_dw/query"
TABLE_FQN = "carto-dw-ac-xx7br32v.private_andreabenathar_a5f83fac.transferegov_df_ra_poligonos"
GEOJSON_PATH = Path("data/carto_exports/ra_boundaries_raw.geojson")

# Fonte oficial dos polígonos (documentada em docs/CARTO_INTEGRATION.md):
# https://onda.ibram.df.gov.br/server/rest/services/Territorio/
#   Regioes_Administrativas_DF_2025/MapServer/0 (GDF, camada 2025, 35 RAs)

# Casamentos especiais: nome normalizado na base local -> nome no GeoJSON GDF.
ALIASES: dict[str, str] = {
    "SOBRADINHO I": "SOBRADINHO",
    "SOL NASCENTE/POR DO SOL": "SOL NASCENTE E POR DO SOL",
    "SETOR DE INDUSTRIAS": "SIA",
}

# Precisão das coordenadas enviadas ao BigQuery (6 casas ~ 11 cm).
COORD_NDIGITS = 6


def norm(texto: str | None) -> str:
    """Normaliza nome de RA: remove acentos, caixa alta, espaços extras."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(limpo.upper().split())


def carregar_geojson() -> list[dict[str, Any]]:
    """Lê o GeoJSON em disco e valida estrutura mínima."""
    if not GEOJSON_PATH.exists():
        log.error("GeoJSON não encontrado: %s", GEOJSON_PATH)
        log.error("Baixe com curl -o %s '<url da camada IBRAM 2025 f=geojson>'", GEOJSON_PATH)
        sys.exit(1)
    with GEOJSON_PATH.open(encoding="utf-8") as arq:
        dados = json.load(arq)
    features = dados.get("features", [])
    if not 30 <= len(features) <= 40:
        log.error("GeoJSON inválido: %d features (esperado ~35).", len(features))
        sys.exit(1)
    log.info("GeoJSON OK: %d features de %s", len(features), GEOJSON_PATH)
    return features


def carregar_demografia() -> dict[str, dict[str, Any]]:
    """Carrega demografia local indexada por nome normalizado."""
    dsn = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ra_codigo, nome_ra, populacao_est, area_km2,
                   densidade, latitude, longitude
            FROM df_regioes_administrativas
            """
        )
        registros = cur.fetchall()
    colunas = [
        "ra_codigo",
        "nome_ra",
        "populacao_est",
        "area_km2",
        "densidade",
        "latitude",
        "longitude",
    ]
    return {norm(reg[1]): dict(zip(colunas, reg)) for reg in registros}


def _arredondar_coords(coords: Any, ndigits: int = COORD_NDIGITS) -> Any:
    """Arredonda recursivamente pares [lng, lat] para reduzir payload."""
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), ndigits), round(float(coords[1]), ndigits)]
    if isinstance(coords, list):
        return [_arredondar_coords(c, ndigits) for c in coords]
    return coords


def simplificar_geometria(geometry: dict[str, Any]) -> str:
    """Arredonda coordenadas e devolve GeoJSON serializado."""
    geometria = {
        "type": geometry["type"],
        "coordinates": _arredondar_coords(geometry["coordinates"]),
    }
    return json.dumps(geometria, ensure_ascii=False, separators=(",", ":"))


def sql_literal(valor: Any, force_string: bool = False) -> str:
    """Converte valor Python em literal SQL do BigQuery."""
    if valor is None:
        return "NULL"
    if force_string:
        texto = str(valor).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{texto}'"
    if isinstance(valor, (int, float)):
        return repr(valor)
    texto = str(valor).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{texto}'"


def run_sql(api_key: str, query: str, max_tentativas: int = 5) -> dict[str, Any]:
    """Executa uma consulta na SQL API do CARTO DW com retry exponencial.

    Reprocessa falhas transitórias de rede (DNS/conexão/timeout), erros HTTP
    5xx e 429. Erros 4xx definitivos falham imediatamente.
    """
    ultima_exc: Exception | None = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = requests.post(
                CARTO_SQL_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"q": query},
                timeout=120,
            )
            if resp.status_code in (429, *range(500, 600)):
                raise requests.exceptions.HTTPError(f"HTTP {resp.status_code} transitório")
            if not resp.ok:
                raise RuntimeError(f"SQL API HTTP {resp.status_code}: {resp.text[:300]}")
            return resp.json()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as exc:
            ultima_exc = exc
            espera = min(2**tentativa, 30)
            log.warning(
                "Falha transitória (tentativa %d/%d): %s — nova tentativa em %ds",
                tentativa,
                max_tentativas,
                exc.__class__.__name__,
                espera,
            )
            time.sleep(espera)
    raise RuntimeError(f"Rede indisponível após {max_tentativas} tentativas") from ultima_exc


def _campo_float(registro: dict[str, Any] | None, campo: str) -> float | None:
    """Lê um campo numérico de um registro opcional, tolerando None/ausente."""
    valor = registro.get(campo) if registro else None
    return float(valor) if valor is not None else None


def montar_linhas(
    features: list[dict[str, Any]], demografia: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Casa features do GeoJSON com demografia local.

    Retorna (linhas, db_sem_poligono, geojson_sem_demografia).
    """
    linhas: list[dict[str, Any]] = []
    db_usados: set[str] = set()

    for feat in features:
        props = feat.get("properties", {})
        nome_gdf = props.get("ra_nome", "")
        chave = norm(nome_gdf)
        registro = demografia.get(chave)
        if registro is None:
            # Procura alias apontando para este nome do GeoJSON.
            for alias_chave, destino in ALIASES.items():
                if destino == chave and alias_chave in demografia:
                    registro = demografia[alias_chave]
                    break
        if registro is not None:
            db_usados.add(norm(registro["nome_ra"]))
        geom_str = simplificar_geometria(feat["geometry"])
        linhas.append(
            {
                "ra_codigo": registro["ra_codigo"] if registro else None,
                "nome_ra": registro["nome_ra"] if registro else nome_gdf.title(),
                "populacao_est": registro["populacao_est"] if registro else None,
                "area_km2": _campo_float(registro, "area_km2"),
                "densidade": _campo_float(registro, "densidade"),
                "latitude": _campo_float(registro, "latitude"),
                "longitude": _campo_float(registro, "longitude"),
                "geojson": geom_str,
            }
        )

    db_sem_poligono = sorted(r["nome_ra"] for k, r in demografia.items() if k not in db_usados)
    geojson_sem_demografia = sorted(
        linha["nome_ra"] for linha in linhas if linha["populacao_est"] is None
    )
    return linhas, db_sem_poligono, geojson_sem_demografia


def publicar(api_key: str, linhas: list[dict[str, Any]]) -> None:
    """Cria a tabela no BigQuery e insere as linhas uma a uma."""
    ddl = f"""
    CREATE OR REPLACE TABLE `{TABLE_FQN}` (
        ra_codigo INT64,
        nome_ra STRING,
        populacao_est INT64,
        area_km2 FLOAT64,
        densidade FLOAT64,
        latitude FLOAT64,
        longitude FLOAT64,
        geom GEOGRAPHY
    )
    """
    run_sql(api_key, ddl)
    log.info("Tabela criada/substituída: %s", TABLE_FQN)

    for i, linha in enumerate(linhas, start=1):
        valores = ", ".join(
            [
                sql_literal(linha["ra_codigo"]),
                sql_literal(linha["nome_ra"]),
                sql_literal(linha["populacao_est"]),
                sql_literal(linha["area_km2"]),
                sql_literal(linha["densidade"]),
                sql_literal(linha["latitude"]),
                sql_literal(linha["longitude"]),
                f"ST_GEOGFROMGEOJSON({sql_literal(linha['geojson'])}, make_valid=>TRUE)",
            ]
        )
        run_sql(api_key, f"INSERT INTO `{TABLE_FQN}` VALUES ({valores})")
        if i % 10 == 0 or i == len(linhas):
            log.info("Inseridas %d/%d linhas...", i, len(linhas))


def verificar(api_key: str) -> None:
    """Confere contagens finais na tabela publicada."""
    res = run_sql(
        api_key,
        f"SELECT COUNT(*) AS total, COUNT(geom) AS com_geom, "
        f"SUM(populacao_est) AS pop_total FROM `{TABLE_FQN}`",
    )
    linhas = res.get("rows") or res.get("data", {}).get("rows") or []
    if linhas:
        log.info("Verificação: %s", linhas[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Não publica no CARTO.")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("CARTO_API_KEY", "")
    if not api_key and not args.dry_run:
        log.error("CARTO_API_KEY ausente no ambiente/.env.")
        sys.exit(1)

    features = carregar_geojson()
    demografia = carregar_demografia()
    log.info("Demografia local: %d RAs", len(demografia))

    linhas, db_sem_poligono, geojson_sem_demo = montar_linhas(features, demografia)
    com_geom = sum(1 for linha in linhas if linha["geojson"])
    log.info("Linhas preparadas: %d (%d com polígono)", len(linhas), com_geom)

    if db_sem_poligono:
        log.warning("RAs locais SEM polígono no GeoJSON: %s", "; ".join(db_sem_poligono))
    if geojson_sem_demo:
        log.warning(
            "Polígonos SEM demografia local (serão inseridos com NULL): %s",
            "; ".join(geojson_sem_demo),
        )

    if args.dry_run:
        log.info("--dry-run: nada foi publicado.")
        return

    publicar(api_key, linhas)
    verificar(api_key)
    log.info("Concluído: %s", TABLE_FQN)


if __name__ == "__main__":
    main()
