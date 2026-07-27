"""
tse_vereadors — Enriquecedor de Vereadores (Dados TSE / Eleições Municipais)

Sincroniza candidatos a vereador (2020 e 2024) com o banco PostgreSQL.
Coleta: nome, partido, município, situação (eleito/não eleito), votos, coligação.

Uso:
  python3 -m src.enrichers.tse_vereadors [--dry-run] [--uf UF] [--ano ANO]
"""

from __future__ import annotations

import argparse
import asyncio
import unicodedata

from src.db_utils import get_connection


def normalize(text: str) -> str:
    """Remove acentos, uppercase e prefixos de nomes de municípios."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.upper().strip()
    for prefix in [
        "MUNICIPIO DE ",
        "MUNICÍPIO DE ",
        "ESTADO DE ",
        "ESTADO DA ",
        "ESTADO DO ",
    ]:
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.strip()


async def sync_vereadors(
    dry_run: bool = False,
    target_uf: str | None = None,
    ano: int = 2024,
) -> None:
    conn = get_connection()
    cur = conn.cursor()

    # ── 1. Carregar municípios IBGE ──────────────────────────────────
    query_ibge = "SELECT municipio_id, nome, uf FROM municipios_ibge"
    if target_uf:
        query_ibge += f" WHERE UPPER(uf) = '{target_uf.upper()}'"
    cur.execute(query_ibge)
    ibge_rows = cur.fetchall()
    print(f"📍 Municípios IBGE carregados: {len(ibge_rows)}")

    ibge_index: dict[tuple[str, str], tuple[int, str, str]] = {}
    for mun_id, nome, uf in ibge_rows:
        key = (normalize(nome), (uf or "").upper())
        ibge_index[key] = (mun_id, nome, uf)

    # ── 2. Consultar candidatos a vereador no TSE (DuckDB local) ─────
    from mcp_brasil._shared.datasets import executar_query
    from mcp_brasil.datasets.tse_candidatos import DATASET_SPEC as CAND_SPEC

    where_parts = [
        "UPPER(ds_cargo) = 'VEREADOR'",
        f"CAST(ano_eleicao AS INTEGER) = {ano}",
    ]
    if target_uf:
        where_parts.append(f"UPPER(sg_uf) = '{target_uf.upper()}'")

    where_sql = " AND ".join(where_parts)
    sql_cand = f"""
        SELECT
            sq_candidato, ano_eleicao, nm_candidato, nm_urna_candidato,
            sg_partido, sg_uf, nm_ue, ds_cargo,
            ds_sit_tot_turno, nm_coligacao, nm_tipo_destinacao_votos
        FROM "{CAND_SPEC.table}"
        WHERE {where_sql}
    """

    print(f"🔎 Consultando candidatos a vereador ({ano})...")
    tse_cand = await executar_query(CAND_SPEC, sql_cand, [])
    print(f"📊 Candidatos retornados do TSE: {len(tse_cand)}")

    # ── 3. Consultar votos por candidato (tse_votacao) ────────────────
    votos_map: dict[int, int] = {}
    try:
        from mcp_brasil.datasets.tse_votacao import DATASET_SPEC as VOT_SPEC

        sql_votos = f"""
            SELECT sq_candidato,
                   SUM(CAST(qt_votos_nominais AS BIGINT)) AS total_votos
            FROM "{VOT_SPEC.table}"
            WHERE CAST(ano_eleicao AS INTEGER) = {ano}
            GROUP BY sq_candidato
        """
        print("🔎 Consultando votos por candidato (tse_votacao)...")
        tse_votos = await executar_query(VOT_SPEC, sql_votos, [])
        votos_map = {int(r["sq_candidato"]): int(r.get("total_votos") or 0) for r in tse_votos}
        print(f"🗳️  Votos mapeados para {len(votos_map)} candidatos")
    except Exception as e:
        print(f"⚠️  Aviso: não foi possível consultar votos (tse_votacao): {e}")
        print("    Os votos ficarão zerados. O enriquecedor continua normalmente.")

    # ── 4. Mapear candidatos → municípios IBGE ────────────────────────
    matched_records: list[
        tuple[int, int, str, str, str, str, str, str, int, int, str, str]
    ] = []
    unmatched_count = 0

    for r in tse_cand:
        sq_cand = int(r.get("sq_candidato") or 0)
        nome_completo = r.get("nm_candidato") or ""
        nome_urna = r.get("nm_urna_candidato") or ""
        partido = r.get("sg_partido") or ""
        uf = (r.get("sg_uf") or "").upper()
        cidade_tse = r.get("nm_ue") or ""
        situacao = r.get("ds_sit_tot_turno") or ""
        coligacao = r.get("nm_coligacao") or ""
        votos = votos_map.get(sq_cand, 0)

        key = (normalize(cidade_tse), uf)
        ibge_match = ibge_index.get(key)

        if ibge_match:
            mun_id, mun_nome, mun_uf = ibge_match
            matched_records.append(
                (
                    sq_cand,  # sq_candidato (PK)
                    mun_id,  # municipio_id
                    mun_nome,  # municipio_nome
                    mun_uf,  # uf
                    nome_completo,  # nome_completo
                    nome_urna,  # nome_urna
                    partido,  # sigla_partido
                    "",  # numero_candidato (not in DuckDB dataset)
                    ano,  # ano_eleicao
                    votos,  # votos
                    situacao,  # situacao_candidatura
                    coligacao,  # coligacao
                )
            )
        else:
            unmatched_count += 1
            if dry_run and unmatched_count <= 5:
                print(f"  ⚠️  Sem match IBGE: {cidade_tse} ({uf}) — {nome_completo}")

    print(f"✅ Vereadores mapeados: {len(matched_records)} | Sem match: {unmatched_count}")

    # ── 5. Calcular percentual de votos por município ──────────────────
    votos_por_municipio: dict[int, int] = {}
    for rec in matched_records:
        m_id: int = rec[1]
        votos_por_municipio[m_id] = votos_por_municipio.get(m_id, 0) + rec[9]

    # Atualizar records com percentual
    final_records: list[
        tuple[int | str, int, str, str, str, str, str, str, int, int, float, str, str]
    ] = []
    for rec in matched_records:
        (
            sq_cand,
            mun_id,
            mun_nome,
            mun_uf,
            nome_completo,
            nome_urna,
            partido,
            numero,
            ano_eleicao,
            votos,
            situacao,
            coligacao,
        ) = rec
        total_municipio = votos_por_municipio.get(mun_id, 0)
        pct = round(votos / total_municipio * 100, 2) if total_municipio > 0 else 0.0
        final_records.append(
            (
                sq_cand,
                mun_id,
                mun_nome,
                mun_uf,
                nome_completo,
                nome_urna,
                partido,
                numero,
                ano_eleicao,
                votos,
                pct,
                situacao,
                coligacao,
            )
        )

    # ── 6. UPSERT no PostgreSQL ───────────────────────────────────────
    if not dry_run and final_records:
        insert_sql = """
            INSERT INTO vereadores_dados (
                sq_candidato, municipio_id, municipio_nome, uf,
                nome_completo, nome_urna, sigla_partido, numero_candidato,
                ano_eleicao, votos, percentual_votos,
                situacao_candidatura, coligacao, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (sq_candidato) DO UPDATE SET
                municipio_nome = EXCLUDED.municipio_nome,
                uf = EXCLUDED.uf,
                nome_completo = EXCLUDED.nome_completo,
                nome_urna = EXCLUDED.nome_urna,
                sigla_partido = EXCLUDED.sigla_partido,
                numero_candidato = EXCLUDED.numero_candidato,
                ano_eleicao = EXCLUDED.ano_eleicao,
                votos = EXCLUDED.votos,
                percentual_votos = EXCLUDED.percentual_votos,
                situacao_candidatura = EXCLUDED.situacao_candidatura,
                coligacao = EXCLUDED.coligacao,
                updated_at = NOW()
        """
        # Executar em batch para performance
        batch_size = 5000
        for i in range(0, len(final_records), batch_size):
            batch = final_records[i : i + batch_size]
            cur.executemany(insert_sql, batch)
            conn.commit()
            print(f"  💾 Batch {i // batch_size + 1}: {len(batch)} registros salvos")

        print(
            f"💾 Total: {len(final_records)} vereadores sincronizados "
            f"na tabela 'vereadores_dados'!"
        )
    elif dry_run and final_records:
        print(f"🔍 DRY-RUN: {len(final_records)} vereadores seriam inseridos")
        # Mostrar exemplos
        eleitos = [r for r in final_records if "ELEITO" in (r[11] or "").upper()]
        print(f"    Eleitos: {len(eleitos)} | Não eleitos: {len(final_records) - len(eleitos)}")
        if eleitos:
            print("    Exemplos de eleitos:")
            for r in eleitos[:5]:
                print(f"      {r[4]} ({r[6]}) — {r[9]} votos ({r[10]}%) — {r[3]}")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar candidatos a vereador via TSE")
    parser.add_argument("--dry-run", action="store_true", help="Não salvar alterações no banco")
    parser.add_argument("--uf", type=str, help="Filtrar por UF específica (ex: AL, SP, BA)")
    parser.add_argument("--ano", type=int, default=2024, help="Ano da eleição (padrão: 2024)")
    args = parser.parse_args()

    asyncio.run(
        sync_vereadors(
            dry_run=args.dry_run,
            target_uf=args.uf,
            ano=args.ano,
        )
    )


if __name__ == "__main__":
    main()
