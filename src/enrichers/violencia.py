"""
Violência municipal via ISP-RJ (DuckDB) + Atlas da Violência (IPEA).

Uso:
    python3 -m src.enrichers.violencia [--dry-run] [--limit N] [--uf UF] [--ano ANO]

Fontes:
    1. ISP-RJ: dados criminais mensais por CISP/município (RJ apenas)
       → Dataset DuckDB (~3MB, 26.316 registros, 2003-2026)
       → Cobre 46 municípios do RJ com código IBGE válido
    2. Atlas da Violência: API IPEA (se disponível) para demais UFs

Cria: violencia_municipios (auto-DDL se não existir)
"""

from __future__ import annotations

import argparse
import asyncio
import time

from src.db_utils import get_connection

# ── Fontes ─────────────────────────────────────────────────────────────────────

_HAS_ISP = False
_HAS_ATLAS = False

try:
    from mcp_brasil._shared.datasets import executar_query, get_registry

    _HAS_ISP = True
except ImportError:
    pass

try:
    from mcp_brasil._shared.http_client import http_get

    _HAS_ATLAS = True
except ImportError:
    pass

# ── Mapeamento ISP-RJ → colunas DB ─────────────────────────────────────────────

# ISP-RJ colunas criminais agregáveis por ano
COLUNAS_ISP: dict[str, str] = {
    "hom_doloso": "homicidios",
    "total_roubos": "roubos",
    "total_furtos": "furto",
    "feminicidio": "violencia_genero",
    "lesao_corp_morte": "mortes_transito",
}

# CISP combinados (mcirc >= 9900000) → lista de municípios IBGE
# Extraído manualmente dos nomes no ISP-RJ dataset
CISP_COMBINADO: dict[int, list[int]] = {
    9999985: [3300704, 3300258],  # Cabo Frio;Arraial do Cabo (pré-2011)
    9999995: [3301157, 3301918],  # Cardoso Moreira;Italva
    9999998: [
        3301504,
        3302007,
    ],  # Cordeiro;Macuco — Macuco=3302007? Não, é 3302007=Itaguaí. Macuco=3302056
    9999999: [3302908, 3303401],  # Miguel Pereira;Paty dos Alferes
}

# Correção: Macuco IBGE = 3302056
CISP_COMBINADO[9999998] = [3301504, 3302056]


def _create_table(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS violencia_municipios (
            id SERIAL PRIMARY KEY,
            municipio_id INTEGER REFERENCES municipios_ibge(municipio_id),
            ano_referencia INTEGER NOT NULL,
            homicidios INTEGER DEFAULT 0,
            taxa_homicidios REAL,
            mortes_transito INTEGER DEFAULT 0,
            roubos INTEGER DEFAULT 0,
            furto INTEGER DEFAULT 0,
            violencia_genero INTEGER DEFAULT 0,
            extracted_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(municipio_id, ano_referencia)
        )""")


def _upsert_violencia(cur, mun_id: int, ano: int, dados: dict) -> None:
    cur.execute(
        """
        INSERT INTO violencia_municipios
            (municipio_id, ano_referencia, homicidios, taxa_homicidios,
             mortes_transito, roubos, furto, violencia_genero, extracted_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (municipio_id, ano_referencia) DO UPDATE SET
            homicidios = EXCLUDED.homicidios,
            taxa_homicidios = EXCLUDED.taxa_homicidios,
            mortes_transito = EXCLUDED.mortes_transito,
            roubos = EXCLUDED.roubos,
            furto = EXCLUDED.furto,
            violencia_genero = EXCLUDED.violencia_genero,
            extracted_at = NOW()
        """,
        (
            mun_id,
            ano,
            dados.get("homicidios", 0),
            dados.get("taxa_homicidios"),
            dados.get("mortes_transito", 0),
            dados.get("roubos", 0),
            dados.get("furto", 0),
            dados.get("violencia_genero", 0),
        ),
    )


def _estimar_taxa_homicidios(homicidios: int, populacao: int | None) -> float | None:
    """Calcula taxa de homicídios por 100 mil habitantes."""
    if populacao and populacao > 0 and homicidios > 0:
        return round(homicidios / populacao * 100_000, 2)
    return None


# ── Fonte 1: ISP-RJ ────────────────────────────────────────────────────────────


async def _processar_isp_rj(
    cur,
    anos: list[int],
    municipios_filter: set[int] | None,
    dry_run: bool,
) -> dict:
    """Processa dados criminais do ISP-RJ para municípios do RJ.

    Retorna estatísticas: {processados, com_dados, total_anual_rows, combinados}
    """
    if not _HAS_ISP:
        return {"processados": 0, "com_dados": 0, "total_anual_rows": 0, "combinados": 0}

    reg = get_registry()
    specs = {s.id: s for s in reg.all_specs()}
    spec = specs.get("isp_rj")
    if not spec:
        return {"processados": 0, "com_dados": 0, "total_anual_rows": 0, "combinados": 0}

    stats: dict = {"processados": 0, "com_dados": 0, "total_anual_rows": 0, "combinados": 0}

    for ano in anos:
        # 1. Municípios com código IBGE direto
        rows = await executar_query(
            spec,
            """
            SELECT
                mcirc,
                SUM(hom_doloso) AS homicidios,
                SUM(total_roubos) AS roubos,
                SUM(total_furtos) AS furtos,
                SUM(feminicidio) AS feminicidio,
                SUM(lesao_corp_morte) AS mortes_transito
            FROM isp_rj_cisp_mensal
            WHERE ano = ? AND mcirc < 9900000
            GROUP BY mcirc
            ORDER BY mcirc
            """,
            params=[ano],
        )

        for r in rows:
            mun_id = r["mcirc"]
            if municipios_filter and mun_id not in municipios_filter:
                continue
            pop = _get_populacao(cur, mun_id)
            dados = {
                "homicidios": r["homicidios"],
                "roubos": r["roubos"],
                "furto": r["furtos"],
                "violencia_genero": r["feminicidio"] or 0,
                "mortes_transito": r["mortes_transito"] or 0,
                "taxa_homicidios": _estimar_taxa_homicidios(r["homicidios"], pop),
            }
            if not dry_run:
                _upsert_violencia(cur, mun_id, ano, dados)
            stats["processados"] += 1
            if r["homicidios"] > 0 or r["roubos"] > 0:
                stats["com_dados"] += 1

        # 2. CISP combinados (um posto atende 2+ municípios)
        for fake_mcirc, mun_ids in CISP_COMBINADO.items():
            rows = await executar_query(
                spec,
                """
                SELECT
                    SUM(hom_doloso) AS homicidios,
                    SUM(total_roubos) AS roubos,
                    SUM(total_furtos) AS furtos,
                    SUM(feminicidio) AS feminicidio,
                    SUM(lesao_corp_morte) AS mortes_transito,
                    COUNT(*) AS num_cisps
                FROM isp_rj_cisp_mensal
                WHERE ano = ? AND mcirc = ?
                """,
                params=[ano, fake_mcirc],
            )
            if not rows or rows[0]["homicidios"] is None:
                continue
            r = rows[0]
            # Distribui igualmente entre os municípios do CISP
            n = len(mun_ids)
            for mun_id in mun_ids:
                if municipios_filter and mun_id not in municipios_filter:
                    continue
                pop = _get_populacao(cur, mun_id)
                # Rateia os totais entre os municípios
                hom = max(0, round(r["homicidios"] / n))
                dados = {
                    "homicidios": hom,
                    "roubos": max(0, round(r["roubos"] / n)),
                    "furto": max(0, round(r["furtos"] / n)),
                    "violencia_genero": max(0, round((r["feminicidio"] or 0) / n)),
                    "mortes_transito": max(0, round((r["mortes_transito"] or 0) / n)),
                    "taxa_homicidios": _estimar_taxa_homicidios(hom, pop),
                }
                if not dry_run:
                    _upsert_violencia(cur, mun_id, ano, dados)
                stats["combinados"] += 1
                if r["homicidios"] > 0:
                    stats["com_dados"] += 1

    return stats


# ── Fonte 2: Atlas da Violência ────────────────────────────────────────────────


async def _processar_atlas(
    cur,
    uf: str | None,
    anos: list[int],
    dry_run: bool,
) -> dict:
    """Tenta processar dados do Atlas da Violência (IPEA) para UFs não-RJ.

    ATENÇÃO: API do Atlas pode estar indisponível (retorna 404 desde meados 2026).
    """
    if not _HAS_ATLAS:
        return {"processados": 0, "api_ok": False}

    # Verifica se API está no ar
    try:
        temas = await http_get("https://www.ipea.gov.br/atlasviolencia/api/v1/temas")
        if not temas:
            return {"processados": 0, "api_ok": False}
    except Exception:
        return {"processados": 0, "api_ok": False}

    # API disponível — implementar consulta por UF
    stats: dict = {"processados": 0, "api_ok": True}

    # Mapear séries de interesse
    # Tema 1 = Homicídios | Tema 12 = Violência Trânsito | Tema 61 = Violência Gênero
    # Ideal: buscar série municipal (abrangência=4) filtrando por código IBGE
    # Como a API está instável, registro apenas o placeholder.

    return stats


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _get_populacao(cur, mun_id: int) -> int | None:
    cur.execute("SELECT populacao FROM municipios_ibge WHERE municipio_id = %s", (mun_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def _listar_municipios(cur, uf: str | None) -> list[tuple[int, str, str, int | None]]:
    if uf:
        cur.execute(
            """SELECT m.municipio_id, m.nome, m.uf, m.populacao
               FROM municipios_ibge m
               WHERE m.uf = %s
               ORDER BY m.nome""",
            (uf.upper(),),
        )
    else:
        cur.execute(
            """SELECT m.municipio_id, m.nome, m.uf, m.populacao
               FROM municipios_ibge m
               ORDER BY m.uf, m.nome"""
        )
    return cur.fetchall()  # type: ignore[return-value]


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquecer municípios com dados de violência criminal"
    )
    parser.add_argument("--dry-run", action="store_true", help="Mostrar sem escrever no DB")
    parser.add_argument("--limit", type=int, default=0, help="Máx. municípios (0=todos)")
    parser.add_argument("--uf", type=str, default=None, help="Filtrar por UF (ex: RJ)")
    parser.add_argument(
        "--ano",
        type=int,
        default=0,
        help="Ano de referência (0=todos disponíveis)",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Determinar anos
    anos = [args.ano] if args.ano else list(range(2019, 2027))  # 2019-2026

    municipios = _listar_municipios(cur, args.uf)
    if args.limit > 0:
        municipios = municipios[: args.limit]

    mun_ids = {m[0] for m in municipios}
    print(f"Municípios alvo: {len(municipios)} | Anos: {anos}")
    if args.dry_run:
        print("  [DRY-RUN] Nenhum dado será escrito no banco")
    else:
        _create_table(cur)
        conn.commit()

    inicio = time.time()

    # ── Fonte 1: ISP-RJ ──
    if args.uf is None or args.uf.upper() == "RJ":
        print("\n── ISP-RJ ──")
        stats_rj = asyncio.run(_processar_isp_rj(cur, anos, mun_ids, args.dry_run))
        print(
            f"  ISP-RJ: {stats_rj['processados']} registros processados, "
            f"{stats_rj['com_dados']} com dados, "
            f"{stats_rj['combinados']} via CISP combinado"
        )
        if not args.dry_run:
            conn.commit()

    # ── Fonte 2: Atlas da Violência (outras UFs) ──
    if args.uf is None or args.uf.upper() != "RJ":
        print("\n── Atlas da Violência ──")
        stats_atlas = asyncio.run(_processar_atlas(cur, args.uf, anos, args.dry_run))
        if stats_atlas.get("api_ok"):
            print(f"  Atlas: {stats_atlas['processados']} registros")
        else:
            print("  API do Atlas da Violência indisponível (404)")
        if not args.dry_run and stats_atlas.get("processados", 0) > 0:
            conn.commit()

    elapsed = time.time() - inicio
    print(f"\nConcluído em {elapsed:.1f}s")


if __name__ == "__main__":
    main()
