"""
Enriquecimento de municípios via API de Agregados do IBGE.

Uso: python3 -m src.enrichers.ibge_agregados [--dry-run] [--uf UF] [--limit N]

Busca dados demográficos/econômicos dos municípios mapeados:
  - População residente estimada (tabela 6579, variável 9324)
  - PIB a preços correntes (tabela 5938, variável 37)
  - Área territorial (tabela 1301, variável 615)

Requer: tabela municipios_ibge populada (via ibge.py) e migration_004 aplicada.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from typing import TypedDict
import requests

from src.db_utils import get_connection

from config.settings import (
    ENRICH_RATE_LIMIT,
)

# ---------------------------------------------------------------------------
# API de Agregados do IBGE (v3)
# ---------------------------------------------------------------------------
IBGE_AGGREGADOS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"


# Tipagem da resposta IBGE (JSON heterogêneo — tipos explícitos necessários)
class _ResultadoIBGE(TypedDict):
    series: list[dict[str, object]]


class _AgregadoIBGE(TypedDict):
    id: str
    variavel: str
    resultados: list[_ResultadoIBGE]


# Tabelas e variáveis de interesse
# Formato: chave -> (tabela_id, variavel_id, descricao)
AGREGADOS: dict[str, tuple[int, int, str]] = {
    "populacao": (6579, 9324, "População residente estimada"),
    "pib": (5938, 37, "PIB a preços correntes em R$ mil"),
    "area": (1301, 615, "Área territorial em km²"),
}




def _parse_agregado_response(resp_json: list[_AgregadoIBGE]) -> float | None:
    """Extrai o primeiro valor numérico da resposta de agregados IBGE.

    Estrutura: [{"id": "9324", "resultados": [{"series": [{"serie": {"2024": "12345"}}]}]}]
    """
    if not resp_json:
        return None

    resultados = resp_json[0].get("resultados", [])
    if not resultados:
        return None

    series = resultados[0].get("series", [])
    if not series:
        return None

    serie = series[0].get("serie", {})
    if not serie or not isinstance(serie, dict):
        return None

    # Chaves são anos/periódos — pegar a primeira (mais recente)
    valor_str = next(iter(serie.values()), None)
    if valor_str is None or not isinstance(valor_str, str):
        return None

    try:
        return float(valor_str)
    except (ValueError, TypeError):
        return None


def buscar_agregado_municipio(
    tabela: int,
    variavel: int,
    municipio_id: int,
    timeout: int = 15,
) -> float | None:
    """Busca um agregado IBGE para um município específico.

    API: /v3/agregados/{tabela}/periodos/-1/variaveis/{variavel}?localidades=N6[{municipio_id}]
    - periodos/-1 = último período disponível
    - localidades/N6 = nível município
    """
    url = (
        f"{IBGE_AGGREGADOS_URL}/{tabela}"
        f"/periodos/-1/variaveis/{variavel}"
        f"?localidades=N6[{municipio_id}]"
    )
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            return None

        data: list[_AgregadoIBGE] = resp.json()
        return _parse_agregado_response(data)
    except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError):
        return None


def buscar_todos_agregados(
    municipio_id: int,
    timeout: int = 15,
) -> dict[str, float | None]:
    """Busca todos os agregados configurados para um município."""
    resultados: dict[str, float | None] = {}
    for chave, (tabela, variavel, _desc) in AGREGADOS.items():
        resultados[chave] = buscar_agregado_municipio(tabela, variavel, municipio_id, timeout)
    return resultados


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquecer municípios com agregados IBGE (população, PIB, área)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Mostrar sem escrever no DB")
    parser.add_argument("--uf", type=str, default="", help="UF específica (vazio=todas)")
    parser.add_argument("--limit", type=int, default=0, help="Máx. municípios (0=todos)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Buscar municípios que já estão na tabela ibge (com código)
    uf_filtro: str = str(args.uf).upper() if args.uf else ""
    if uf_filtro:
        cur.execute(
            "SELECT municipio_id, nome, uf FROM municipios_ibge WHERE uf = %s ORDER BY nome",
            (uf_filtro,),
        )
    else:
        cur.execute("SELECT municipio_id, nome, uf FROM municipios_ibge ORDER BY uf, nome")

    municipios: list[tuple[int, str, str]] = cur.fetchall()
    limite: int = int(args.limit) if args.limit else 0
    if limite > 0:
        municipios = municipios[:limite]

    print(f"Municípios para enriquecer: {len(municipios)}")
    dry_run: bool = bool(args.dry_run)
    if dry_run:
        print("  [DRY-RUN] Nenhum dado será escrito no banco")

    total_atualizados = 0
    total_erros = 0
    inicio = time.time()

    for i, (mun_id, nome, uf) in enumerate(municipios):
        # Buscar todos os agregados
        agg = buscar_todos_agregados(mun_id)

        pop = agg.get("populacao")
        pib = agg.get("pib")
        area = agg.get("area")

        tem_dados = any(v is not None for v in [pop, pib, area])

        if dry_run:
            pop_str = f"{int(pop):,}" if pop else "—"
            pib_str = f"R$ {pib:,.0f} mil" if pib else "—"
            area_str = f"{area:,.2f} km²" if area else "—"
            status = "✓" if tem_dados else "✗"
            print(f"  {status} {mun_id} - {nome} ({uf}) | Pop: {pop_str} | PIB: {pib_str} | Área: {area_str}")
        elif tem_dados:
            cur.execute(  # noqa: E501
                """
                UPDATE municipios_ibge SET
                    populacao = %s,
                    pib = %s,
                    area_km2 = %s,
                    atualizado_em = %s
                WHERE municipio_id = %s
                """,
                (
                    int(pop) if pop else None,
                    pib,
                    area,
                    datetime.now(UTC),
                    mun_id,
                ),
            )
            total_atualizados += 1
        else:
            total_erros += 1

        # Rate limit
        if i < len(municipios) - 1:
            time.sleep(ENRICH_RATE_LIMIT)

        # Progresso a cada 50 municípios
        if (i + 1) % 50 == 0:
            elapsed = time.time() - inicio
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  ... {i + 1}/{len(municipios)} ({rate:.1f} mun/s)")

    if not dry_run:
        conn.commit()

    conn.close()

    elapsed = time.time() - inicio
    print(f"\nConcluído em {elapsed:.1f}s")
    if dry_run:
        print(f"  Municípios: {len(municipios)} (dry-run, sem escrita)")
    else:
        print(f"  Atualizados: {total_atualizados} | Sem dados: {total_erros}")


if __name__ == "__main__":
    main()
