"""Cross-analysis: TransfereGov emendas + TSE voting data."""

from __future__ import annotations

import asyncio
import os
import time

import psycopg2

os.environ["MCP_BRASIL_DATASETS"] = "tse_candidatos,tse_votacao"

DB_URL = "postgresql://cognee:cognee@127.0.0.1:5432/transferegov_db"


class FakeCtx:
    async def info(self, msg: str) -> None:
        print(f"  [info] {msg}")


def get_pi_deputies_with_emendas() -> list[dict]:
    """Get PI deputies and their emenda totals from TransfereGov DB."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            parlamentar_nome AS nome,
            sigla_partido,
            uf,
            SUM(valor_total) AS valor_total
        FROM v_parlamentar_municipio
        WHERE UPPER(uf) = 'PI'
        GROUP BY parlamentar_nome, sigla_partido, uf
        HAVING SUM(valor_total) > 0
        ORDER BY valor_total DESC
        LIMIT 15
    """)
    rows = []
    for row in cur.fetchall():
        rows.append(
            {
                "nome": row[0] or "",
                "sigla_partido": row[1] or "",
                "uf": row[2] or "",
                "valor_total": float(row[3] or 0),
            }
        )
    conn.close()
    return rows


async def cross_analyze() -> None:
    print("=" * 70)
    print("  CROSS-ANALYSIS: TransfereGov emendas × TSE voting (PI)")
    print("=" * 70)

    # 1. Get PI deputies from TransfereGov
    print("\n--- TransfereGov: PI deputies with emendas ---")
    deputies = get_pi_deputies_with_emendas()
    for d in deputies:
        print(f"  {d['nome']:<30} {d['sigla_partido']:<6} R$ {d['valor_total']:>15,.2f}")

    # 2. For each top deputy, find them in TSE and get voting data
    from mcp_brasil.datasets.tse_candidatos.tools import buscar_candidatos

    ctx = FakeCtx()
    results = []

    for dep in deputies[:10]:
        nome = dep["nome"]
        print(f"\n--- Looking up {nome} in TSE ---")
        t0 = time.time()

        # Find candidate in TSE
        cand_result = await buscar_candidatos(
            ctx, nome=nome, uf="PI", cargo="DEPUTADO FEDERAL", limite=5
        )
        time.time() - t0
        print(cand_result)

        # Extract sq_candidato from the result (we need to parse it)
        # Since tools return markdown, let's query DuckDB directly
        from mcp_brasil._shared.datasets import executar_query
        from mcp_brasil.datasets.tse_candidatos import DATASET_SPEC as CAND_SPEC

        sql = (
            "SELECT sq_candidato, ano_eleicao, nm_urna_candidato, sg_partido, "
            "ds_sit_tot_turno "
            f'FROM "{CAND_SPEC.table}" '
            "WHERE UPPER(sg_uf) = 'PI' "
            "AND UPPER(ds_cargo) LIKE '%DEPUTADO FEDERAL%' "
            "AND strip_accents(UPPER(nm_candidato)) LIKE strip_accents(?) "
            "AND CAST(ano_eleicao AS INTEGER) = 2022 "
            "LIMIT 1"
        )
        rows = await executar_query(CAND_SPEC, sql, [f"%{nome}%"])
        if not rows:
            print("  → Not found in TSE 2022")
            continue

        sq = rows[0]["sq_candidato"]
        nome_urna = rows[0]["nm_urna_candidato"]
        resultado = rows[0]["ds_sit_tot_turno"]
        print(f"  → sq_candidato={sq}, nome_urna={nome_urna}, resultado={resultado}")

        # Get voting details
        from mcp_brasil.datasets.tse_votacao import DATASET_SPEC as VOT_SPEC

        votos_sql = (
            "SELECT SUM(TRY_CAST(qt_votos_nominais AS BIGINT)) AS total_votos "
            f'FROM "{VOT_SPEC.table}" '
            "WHERE CAST(sq_candidato AS VARCHAR) = ? "
            "AND CAST(ano_eleicao AS INTEGER) = 2022"
        )
        votos_rows = await executar_query(VOT_SPEC, votos_sql, [str(sq)])
        votos = int(votos_rows[0]["total_votos"] or 0) if votos_rows else 0

        results.append(
            {
                "nome": nome,
                "partido": dep["sigla_partido"],
                "valor_total": dep["valor_total"],
                "votos_2022": votos,
                "resultado": resultado,
            }
        )
        print(f"  → Emendas: R$ {dep['valor_total']:,.2f} | Votos 2022: {votos:,}")

    # 3. Final summary table
    if results:
        print("\n" + "=" * 70)
        print("  CROSS-ANALYSIS RESULTS")
        print("=" * 70)
        print(
            f"{'Nome':<25} {'Partido':<8} {'Valor Total':>16} {'Votos 2022':>12} {'Resultado':<20}"
        )
        print("-" * 85)
        for r in results:
            print(
                f"{r['nome']:<25} {r['partido']:<8} "
                f"R$ {r['valor_total']:>13,.2f} {r['votos_2022']:>12,} "
                f"{r['resultado']:<20}"
            )

        # Correlation hint
        vals = [(r["valor_total"], r["votos_2022"]) for r in results if r["votos_2022"] > 0]
        if len(vals) >= 3:
            # Simple Pearson correlation
            n = len(vals)
            sum_x = sum(v for v, _ in vals)
            sum_y = sum(v for _, v in vals)
            sum_xy = sum(x * y for x, y in vals)
            sum_x2 = sum(x**2 for x, _ in vals)
            sum_y2 = sum(y**2 for _, y in vals)
            denom = ((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2)) ** 0.5
            corr_r = (n * sum_xy - sum_x * sum_y) / denom if denom else 0
            print(f"\n📊 Pearson correlation (emendas valor × votos): {corr_r:.3f}")
            if corr_r > 0.5:
                print(
                    "   → Strong positive: deputies with higher emenda values tend to have more votes"
                )
            elif corr_r > 0.2:
                print("   → Moderate positive: some relationship between emenda values and votes")
            elif corr_r > -0.2:
                print("   → Weak/none: emenda values and votes are largely independent")
            else:
                print("   → Negative: deputies with lower emenda values tend to have more votes")


async def main() -> None:
    try:
        await cross_analyze()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 70)
    print("  DONE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
