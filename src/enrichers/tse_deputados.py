"""
tse_deputados — Enriquecedor de Deputados Federais (Dados TSE / Eleições 2022)

Sincroniza perfil eleitoral dos deputados federais (TSE) com a tabela parlamentares_dados do PostgreSQL.

Uso:
  python3 -m src.enrichers.tse_deputados [--dry-run] [--ano 2022]
"""

from __future__ import annotations

import argparse
import asyncio
import unicodedata

import psycopg2

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER


def normalize(text: str) -> str:
    """Remove acentos, lowercase e caracteres especiais de nomes para comparação fuzzy."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.upper().strip()


async def sync_tse_deputados(dry_run: bool = False, ano: int = 2022) -> None:
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )
    cur = conn.cursor()

    # 1. Carregar deputados do banco local
    cur.execute("SELECT deputado_id, nome, nome_urna, sigla_partido, uf FROM parlamentares_dados")
    deputados_db = cur.fetchall()
    print(f"👥 Deputados carregados do PostgreSQL: {len(deputados_db)}")

    # 2. Consultar candidatos a deputado federal no TSE (DuckDB mcp-brasil)
    from mcp_brasil._shared.datasets import executar_query
    from mcp_brasil.datasets.tse_candidatos import DATASET_SPEC as CAND_SPEC
    from mcp_brasil.datasets.tse_bens import DATASET_SPEC as BENS_SPEC

    sql_candidatos = f"""
        SELECT sq_candidato, ano_eleicao, nm_candidato, nm_urna_candidato, 
               sg_partido, sg_uf, ds_cargo, ds_sit_tot_turno, nm_coligacao
        FROM "{CAND_SPEC.table}"
        WHERE UPPER(ds_cargo) LIKE '%DEPUTADO FEDERAL%'
          AND CAST(ano_eleicao AS INTEGER) = {ano}
          AND UPPER(ds_sit_tot_turno) LIKE '%ELEITO%'
          AND UPPER(ds_sit_tot_turno) NOT LIKE '%NÃO%'
    """
    print(f"🔎 Consultando deputados federais eleitos em {ano} no TSE...")
    tse_candidatos = await executar_query(CAND_SPEC, sql_candidatos, [])
    print(f"📊 Candidatos retornados do TSE: {len(tse_candidatos)}")

    # Indexar candidatos TSE por (nome_norm, uf) e (nome_urna_norm, uf)
    tse_index = {}
    for c in tse_candidatos:
        uf = (c.get("sg_uf") or "").upper()
        nome = normalize(c.get("nm_candidato") or "")
        nome_urna = normalize(c.get("nm_urna_candidato") or "")
        
        tse_index[(nome, uf)] = c
        if nome_urna:
            tse_index[(nome_urna, uf)] = c

    # 3. Consultar bens declarados por candidato (TSE Bens)
    print("💰 Consultando bens declarados no TSE...")
    sql_bens = f"""
        SELECT sq_candidato, SUM(TRY_CAST(REPLACE(vr_bem_candidato, ',', '.') AS DOUBLE)) AS total_bens
        FROM "{BENS_SPEC.table}"
        WHERE CAST(ano_eleicao AS INTEGER) = {ano}
        GROUP BY sq_candidato
    """

    try:
        tse_bens_rows = await executar_query(BENS_SPEC, sql_bens, [])
        bens_map = {r["sq_candidato"]: float(r.get("total_bens") or 0.0) for r in tse_bens_rows}
        print(f"💵 Mapeados patrimônios de {len(bens_map)} candidatos!")
    except Exception as e:
        print(f"⚠️ Aviso ao consultar bens TSE: {e}")
        bens_map = {}

    matched_count = 0
    updates = []

    for dep_id, nome, nome_urna, partido, uf in deputados_db:
        uf_upper = (uf or "").upper()
        key_nome = (normalize(nome), uf_upper)
        key_urna = (normalize(nome_urna), uf_upper)

        match = tse_index.get(key_nome) or tse_index.get(key_urna)

        # Fallback de busca sem UF se não encontrar com UF
        if not match:
            for (k_nome, k_uf), cand in tse_index.items():
                if k_nome == key_nome[0] or (key_urna[0] and k_nome == key_urna[0]):
                    match = cand
                    break

        if match:
            matched_count += 1
            sq_cand = match.get("sq_candidato")
            situacao = match.get("ds_sit_tot_turno") or "ELEITO"
            coligacao = match.get("nm_coligacao") or "Partido Isolado"
            patrimonio = bens_map.get(sq_cand, 0.0)

            updates.append((
                ano, situacao, coligacao, patrimonio, dep_id
            ))

    print(f"✅ Deputados vinculados com sucesso ao TSE: {matched_count}/{len(deputados_db)}")

    if not dry_run and updates:
        update_sql = """
            UPDATE parlamentares_dados SET
                ano_eleicao = %s,
                situacao_eleitoral = %s,
                coligacao = %s,
                patrimonio_total = %s
            WHERE deputado_id = %s
        """
        cur.executemany(update_sql, updates)
        conn.commit()
        print(f"💾 {len(updates)} perfis de deputados atualizados com dados do TSE!")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar dados TSE de deputados federais")
    parser.add_argument("--dry-run", action="store_true", help="Não salvar no banco")
    parser.add_argument("--ano", type=int, default=2022, help="Ano eleitoral (padrão: 2022)")
    args = parser.parse_args()

    asyncio.run(sync_tse_deputados(dry_run=args.dry_run, ano=args.ano))


if __name__ == "__main__":
    main()
