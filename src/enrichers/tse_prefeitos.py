"""
tse_prefeitos — Enriquecedor de Prefeitos (Dados TSE / Eleições)

Sincroniza prefeitos eleitos no TSE (2020 e 2024) com o banco de dados PostgreSQL.

Uso:
  python3 -m src.enrichers.tse_prefeitos [--dry-run] [--uf UF] [--ano ANO]
"""

from __future__ import annotations

import argparse
import asyncio
import unicodedata

import psycopg2

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER


def normalize(text: str) -> str:
    """Remove acentos, lowercase e prefixos de nomes de municípios."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.upper().strip()
    for prefix in ["MUNICIPIO DE ", "MUNICÍPIO DE ", "ESTADO DE ", "ESTADO DA ", "ESTADO DO "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip()


async def sync_prefeitos(dry_run: bool = False, target_uf: str | None = None, ano: int = 2024) -> None:
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )
    cur = conn.cursor()

    # 1. Carregar municípios IBGE
    query_ibge = "SELECT municipio_id, nome, uf FROM municipios_ibge"
    if target_uf:
        query_ibge += f" WHERE UPPER(uf) = '{target_uf.upper()}'"

    cur.execute(query_ibge)
    ibge_rows = cur.fetchall()
    print(f"📍 Municípios IBGE carregados: {len(ibge_rows)}")

    ibge_index = {}
    for mun_id, nome, uf in ibge_rows:
        key = (normalize(nome), uf.upper())
        ibge_index[key] = (mun_id, nome, uf)

    # 2. Consultar candidatos eleitos a prefeito e vice-prefeito no TSE (DuckDB mcp-brasil)
    from mcp_brasil._shared.datasets import executar_query
    from mcp_brasil.datasets.tse_candidatos import DATASET_SPEC as CAND_SPEC

    where_clauses = [
        "CAST(ano_eleicao AS INTEGER) = " + str(ano),
        "UPPER(ds_sit_tot_turno) LIKE '%ELEITO%'",
        "UPPER(ds_sit_tot_turno) NOT LIKE '%NÃO%'"
    ]
    if target_uf:
        where_clauses.append(f"UPPER(sg_uf) = '{target_uf.upper()}'")

    sql_prefeitos = f"""
        SELECT sq_candidato, ano_eleicao, nm_candidato, nm_urna_candidato, sg_partido, 
               sg_uf, nm_ue, ds_cargo, ds_sit_tot_turno, nm_coligacao, st_reeleicao
        FROM "{CAND_SPEC.table}"
        WHERE UPPER(ds_cargo) = 'PREFEITO' AND {" AND ".join(where_clauses)}
    """
    sql_vices = f"""
        SELECT sq_candidato, nm_candidato, sg_partido, sg_uf, nm_ue
        FROM "{CAND_SPEC.table}"
        WHERE UPPER(ds_cargo) = 'VICE-PREFEITO' AND {" AND ".join(where_clauses)}
    """

    print(f"🔎 Executando busca de prefeitos e vice-prefeitos eleitos ({ano}) no TSE...")
    tse_rows = await executar_query(CAND_SPEC, sql_prefeitos, [])
    tse_vices = await executar_query(CAND_SPEC, sql_vices, [])
    print(f"📊 Prefeitos eleitos retornados: {len(tse_rows)} | Vice-prefeitos eleitos: {len(tse_vices)}")

    vices_index = {}
    for v in tse_vices:
        v_key = (normalize(v.get("nm_ue") or ""), (v.get("sg_uf") or "").upper())
        vices_index[v_key] = v.get("nm_candidato") or ""

    matched_records = []
    unmatched_count = 0

    for r in tse_rows:
        nome_candidato = r.get("nm_candidato") or r.get("nm_urna_candidato") or ""
        partido = r.get("sg_partido") or ""
        uf = (r.get("sg_uf") or "").upper()
        cidade_tse = r.get("nm_ue") or ""
        coligacao = r.get("nm_coligacao") or ""
        situacao = r.get("ds_sit_tot_turno") or "ELEITO"

        key = (normalize(cidade_tse), uf)
        ibge_match = ibge_index.get(key)
        vice_nome = vices_index.get(key, "")

        if ibge_match:
            mun_id, mun_nome, mun_uf = ibge_match
            matched_records.append((
                mun_id, mun_nome, mun_uf, nome_candidato,
                partido, ano, situacao, coligacao, vice_nome
            ))
        else:
            unmatched_count += 1
            if dry_run and unmatched_count <= 5:
                print(f"  ⚠️ Sem match IBGE: {cidade_tse} ({uf}) — Prefeito: {nome_candidato}")

    print(f"✅ Prefeitos mapeados com sucesso: {len(matched_records)} | Sem match: {unmatched_count}")

    if not dry_run and matched_records:
        insert_sql = """
            INSERT INTO prefeitos_dados (
                municipio_id, municipio_nome, uf, prefeito_nome,
                sigla_partido, ano_eleicao, situacao_candidatura, coligacao, vice_prefeito_nome, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (municipio_id) DO UPDATE SET
                prefeito_nome = EXCLUDED.prefeito_nome,
                sigla_partido = EXCLUDED.sigla_partido,
                ano_eleicao = EXCLUDED.ano_eleicao,
                situacao_candidatura = EXCLUDED.situacao_candidatura,
                coligacao = EXCLUDED.coligacao,
                vice_prefeito_nome = EXCLUDED.vice_prefeito_nome,
                updated_at = NOW()
        """
        cur.executemany(insert_sql, matched_records)
        conn.commit()
        print(f"💾 {len(matched_records)} prefeitos sincronizados na tabela 'prefeitos_dados'!")

    conn.close()



def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar prefeitos eleitos via TSE")
    parser.add_argument("--dry-run", action="store_true", help="Não salvar alterações no banco")
    parser.add_argument("--uf", type=str, help="Filtrar por UF específica (ex: PI, SP, BA)")
    parser.add_argument("--ano", type=int, default=2024, help="Ano da eleição (padrão: 2024)")
    args = parser.parse_args()

    asyncio.run(sync_prefeitos(dry_run=args.dry_run, target_uf=args.uf, ano=args.ano))


if __name__ == "__main__":
    main()
