#!/usr/bin/env python3
"""Push dos polígonos das RAs + impacto dos deputados distritais (CLDF) ao CARTO DW.

Estende ``push_ra_poligonos_carto.py`` com dados de
``src.enrichers.deputado_ra_impacto`` (proposições por deputado × RA e emendas
orçamentárias por RA), criando a tabela
``transferegov_df_ra_deputados_cldf`` no CARTO DW: mesma geometria/demografia
da tabela base, mais resumo de emendas e os 5 deputados mais atuantes por RA
(colunas achatadas ``dep1``..``dep5`` para uso direto em tooltips/Builder).

Pré-requisito: rodar antes ``python3 -m src.enrichers.deputado_ra_impacto``
para popular ``cldf_deputado_ra_impacto`` e ``cldf_ra_emendas_resumo``.

Uso:
    .venv/bin/python scripts/push_ra_deputados_carto.py [--dry-run]

Requer ``CARTO_API_KEY`` no ``.env``. Idempotente: pode rodar múltiplas vezes.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER
from scripts.push_ra_poligonos_carto import (
    carregar_geojson,
    run_sql,
    simplificar_geometria,
    sql_literal,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("push_ra_deputados_carto")

TABLE_FQN = (
    "carto-dw-ac-xx7br32v.private_andreabenathar_a5f83fac.transferegov_df_ra_deputados_cldf"
)
MAX_DEPUTADOS = 5

ALIASES: dict[str, str] = {
    "SOBRADINHO I": "SOBRADINHO",
    "SOL NASCENTE/POR DO SOL": "SOL NASCENTE E POR DO SOL",
    "SETOR DE INDUSTRIAS": "SIA",
}


def norm(texto: str | None) -> str:
    """Normaliza nome de RA: remove acentos, caixa alta, espaços extras."""
    import unicodedata

    sem_acento = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(limpo.upper().split())


def carregar_dados_cruzados() -> dict[str, dict[str, Any]]:
    """Carrega demografia + emendas + top deputados por RA, indexado por nome normalizado."""
    import psycopg2

    dsn = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ra.ra_codigo, ra.nome_ra, ra.populacao_est, ra.area_km2,
                   ra.densidade, ra.latitude, ra.longitude,
                   COALESCE(res.total_emendas, 0), COALESCE(res.vl_emenda, 0),
                   COALESCE(res.vl_empenhado, 0), COALESCE(res.vl_liquidado, 0)
            FROM df_regioes_administrativas ra
            LEFT JOIN cldf_ra_emendas_resumo res ON res.ra_codigo = ra.ra_codigo
            """
        )
        base = cur.fetchall()

        cur.execute(
            """
            SELECT ra_codigo, nome_candidato, sigla_partido, total_proposicoes,
                   ROW_NUMBER() OVER (
                       PARTITION BY ra_codigo ORDER BY total_proposicoes DESC
                   ) AS posicao,
                   COUNT(*) OVER (PARTITION BY ra_codigo) AS total_deputados
            FROM cldf_deputado_ra_impacto
            """
        )
        deputados_por_ra: dict[int, list[tuple]] = {}
        totais_por_ra: dict[int, int] = {}
        for ra_codigo, nome, partido, props, posicao, total in cur.fetchall():
            if posicao <= MAX_DEPUTADOS:
                deputados_por_ra.setdefault(ra_codigo, []).append((nome, partido, props))
            totais_por_ra[ra_codigo] = total

    resultado: dict[str, dict[str, Any]] = {}
    for row in base:
        (
            ra_codigo,
            nome_ra,
            populacao_est,
            area_km2,
            densidade,
            latitude,
            longitude,
            total_emendas,
            vl_emenda,
            vl_empenhado,
            vl_liquidado,
        ) = row
        registro: dict[str, Any] = {
            "ra_codigo": ra_codigo,
            "nome_ra": nome_ra,
            "populacao_est": populacao_est,
            "area_km2": float(area_km2) if area_km2 is not None else None,
            "densidade": float(densidade) if densidade is not None else None,
            "latitude": float(latitude) if latitude is not None else None,
            "longitude": float(longitude) if longitude is not None else None,
            "total_emendas": total_emendas,
            "vl_emenda": float(vl_emenda),
            "vl_empenhado": float(vl_empenhado),
            "vl_liquidado": float(vl_liquidado),
            "total_deputados_atuantes": totais_por_ra.get(ra_codigo, 0),
        }
        deputados = deputados_por_ra.get(ra_codigo, [])
        for i in range(1, MAX_DEPUTADOS + 1):
            if i <= len(deputados):
                nome, partido, props = deputados[i - 1]
            else:
                nome, partido, props = None, None, None
            registro[f"dep{i}_nome"] = nome
            registro[f"dep{i}_partido"] = partido
            registro[f"dep{i}_proposicoes"] = props
        resultado[norm(nome_ra)] = registro

    return resultado


def montar_linhas(
    features: list[dict[str, Any]], dados: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Casa features do GeoJSON com os dados cruzados (mesma lógica de aliases)."""
    linhas: list[dict[str, Any]] = []
    for feat in features:
        nome_gdf = feat.get("properties", {}).get("ra_nome", "")
        chave = norm(nome_gdf)
        registro = dados.get(chave)
        if registro is None:
            for alias_chave, destino in ALIASES.items():
                if destino == chave and alias_chave in dados:
                    registro = dados[alias_chave]
                    break
        geom_str = simplificar_geometria(feat["geometry"])
        linha = dict(registro) if registro else {"nome_ra": nome_gdf.title()}
        linha["geojson"] = geom_str
        linhas.append(linha)
    return linhas


def publicar(api_key: str, linhas: list[dict[str, Any]]) -> None:
    """Cria a tabela cruzada no BigQuery e insere as linhas uma a uma."""
    colunas_dep = []
    for i in range(1, MAX_DEPUTADOS + 1):
        colunas_dep.append(f"dep{i}_nome STRING")
        colunas_dep.append(f"dep{i}_partido STRING")
        colunas_dep.append(f"dep{i}_proposicoes INT64")

    quebra_linha = ",\n        "
    ddl = f"""
    CREATE OR REPLACE TABLE `{TABLE_FQN}` (
        ra_codigo INT64,
        nome_ra STRING,
        populacao_est INT64,
        area_km2 FLOAT64,
        densidade FLOAT64,
        latitude FLOAT64,
        longitude FLOAT64,
        geom GEOGRAPHY,
        total_emendas INT64,
        vl_emenda FLOAT64,
        vl_empenhado FLOAT64,
        vl_liquidado FLOAT64,
        total_deputados_atuantes INT64,
        {quebra_linha.join(colunas_dep)}
    )
    """
    run_sql(api_key, ddl)
    log.info("Tabela criada/substituída: %s", TABLE_FQN)

    campos_base = [
        "ra_codigo",
        "nome_ra",
        "populacao_est",
        "area_km2",
        "densidade",
        "latitude",
        "longitude",
    ]
    campos_emendas = ["total_emendas", "vl_emenda", "vl_empenhado", "vl_liquidado"]
    campos_dep = ["total_deputados_atuantes"]
    for i in range(1, MAX_DEPUTADOS + 1):
        campos_dep += [f"dep{i}_nome", f"dep{i}_partido", f"dep{i}_proposicoes"]

    for i, linha in enumerate(linhas, start=1):
        geom_literal = f"ST_GEOGFROMGEOJSON({sql_literal(linha['geojson'])}, make_valid=>TRUE)"
        valores = [sql_literal(linha.get(c)) for c in campos_base]
        valores.append(geom_literal)
        valores += [sql_literal(linha.get(c, 0)) for c in campos_emendas]
        valores += [
            sql_literal(linha.get(c, 0 if c == "total_deputados_atuantes" else None))
            for c in campos_dep
        ]
        run_sql(api_key, f"INSERT INTO `{TABLE_FQN}` VALUES ({', '.join(valores)})")
        if i % 10 == 0 or i == len(linhas):
            log.info("Inseridas %d/%d linhas...", i, len(linhas))


def verificar(api_key: str) -> None:
    """Confere contagens finais na tabela publicada."""
    res = run_sql(
        api_key,
        f"SELECT COUNT(*) AS total, COUNT(geom) AS com_geom, "
        f"SUM(vl_emenda) AS emendas_total, SUM(total_deputados_atuantes) AS deps_total "
        f"FROM `{TABLE_FQN}`",
    )
    linhas = res.get("rows") or []
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
    dados = carregar_dados_cruzados()
    log.info("Dados cruzados locais: %d RAs", len(dados))

    linhas = montar_linhas(features, dados)
    com_dep = sum(1 for linha in linhas if linha.get("total_deputados_atuantes"))
    log.info("Linhas preparadas: %d (%d com deputados atuantes)", len(linhas), com_dep)

    if args.dry_run:
        log.info("--dry-run: nada foi publicado.")
        return

    publicar(api_key, linhas)
    verificar(api_key)
    log.info("Concluído: %s", TABLE_FQN)


if __name__ == "__main__":
    main()
