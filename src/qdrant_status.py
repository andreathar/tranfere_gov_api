#!/usr/bin/env python3
"""qdrant-status: Painel de status da indexação Qdrant.

Uso:
    python3 src/qdrant_status.py
    ./run.sh qdrant-status
"""

from collections import Counter

from qdrant_client import QdrantClient
from qdrant_client.http import models

from config.settings import QDRANT_COLLECTION, QDRANT_URL
from src.db_utils import get_connection
from src.enrichers.rag_qdrant_indexer import check_payload_index_health


def main():
    # trust_env=False: httpx 0.28.1 quebra URLPattern com no_proxy CIDR IPv6
    qdrant = QdrantClient(url=QDRANT_URL, trust_env=False)
    conn = get_connection()
    cur = conn.cursor()

    # Total
    count_all = qdrant.count(QDRANT_COLLECTION)
    print(f"📊 Qdrant: {count_all.count:,} vetores")

    # Saúde dos payload indexes — pega índice ausente ou com tipo errado
    # (achado real 2026-08-17: municipio_ibge_id indexado como KEYWORD com
    # dados INTEGER, nunca casava com nenhum ponto; docs/decision_reviews.md)
    problemas_index = check_payload_index_health(qdrant)
    if problemas_index:
        print("\n⚠️  Payload index com problema:")
        for p in problemas_index:
            print(f"  {p}")
    else:
        print("✅ Payload indexes: todos presentes e com o tipo certo")

    # Por tipo
    chunk_types = [
        ("voto", "Votações"),
        ("proposicao", "Proposições"),
        ("emenda", "Emendas PIX"),
        ("beneficiario", "Beneficiários"),
        ("perfil", "Perfil"),
        ("parlamentar_resumo", "Resumo"),
        ("conexao_politica", "Conexões"),
        ("indicadores_sociais", "Indic. Sociais"),
        ("prefeito", "Prefeitos"),
        ("vereadores_resumo", "Vereadores"),
        ("demografia_municipio", "Demografia"),
        ("municipio_financeiro", "SICONFI Municipal"),
        ("estado_financeiro", "SICONFI Estadual"),
        ("emenda_discricionaria", "Discricionárias"),
        ("discurso_plenario", "Discursos"),
        ("compras_municipio", "Compras"),
        ("indicadores_municipal", "Indic. Municipais"),
        ("fnde_repasses", "FNDE"),
        ("diario_oficial", "Diário Oficial"),
        ("risco_judicial", "Risco Judicial"),
        ("senador", "Senadores"),
        ("parlamentar_alertas", "Alertas"),
    ]
    for ct, label in chunk_types:
        c = qdrant.count(
            QDRANT_COLLECTION,
            count_filter=models.Filter(
                must=[models.FieldCondition(key="type", match=models.MatchValue(value=ct))]
            ),
        )
        if c.count > 0:
            print(f"  {label:25s} {c.count:>7,}")

    # Mapear deputados
    dep_counts: Counter = Counter()
    offset = None
    while True:
        records, offset = qdrant.scroll(
            QDRANT_COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for r in records:
            did = r.payload.get("deputado_id")
            if did:
                dep_counts[did] += 1
        if offset is None:
            break

    cur.execute(
        """SELECT d.deputado_id, d.nome, d.sigla_partido
           FROM parlamentares_dados d WHERE d.deputado_id = ANY(%s)""",
        (list(dep_counts.keys()),),
    )
    id_map = {r[0]: r for r in cur.fetchall()}
    dep_sorted = sorted(dep_counts.items(), key=lambda x: -x[1])

    print(f"\n🏛️  Deputados indexados: {len(dep_counts)}")
    print("\nTop 10:")
    for did, count in dep_sorted[:10]:
        info = id_map.get(did)
        if info:
            print(f"  {info[1]:30s} ({info[2]}) → {count:3d} chunks")

    # Discricionárias
    print("\n📋 Discricionárias:")
    cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(valor_total::numeric),0) FROM emendas_discricionarias"
    )
    total, vlr = cur.fetchone()
    # Total no Qdrant
    c_disc = qdrant.count(
        QDRANT_COLLECTION,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type", match=models.MatchValue(value="emenda_discricionaria")
                )
            ]
        ),
    )
    print(f"  Banco: {total:,} emendas | R$ {vlr:,.0f}")
    print(f"  Qdrant: {c_disc.count:,} chunks")

    # Deputados com discursos mas sem indexação
    cur.execute(
        """SELECT DISTINCT d.deputado_id, p.nome
           FROM parlamentar_discursos d
           JOIN parlamentares_dados p ON p.deputado_id = d.deputado_id
           WHERE d.deputado_id != ALL(%s)
           ORDER BY p.nome""",
        (list(dep_counts.keys()),),
    )
    missing = cur.fetchall()
    if missing:
        print(f"\n⚠️  Deputados com discursos NÃO indexados: {len(missing)}")
        for r in missing[:5]:
            print(f"  Dep {r[0]} ({r[1]})")
        print("  (rode ./run.sh cron-qdrant --diff para incluir)")

    # Última indexação
    cur.execute(
        "SELECT MAX(data_analise)::text FROM parlamentares_personas "
        "WHERE data_analise >= NOW() - INTERVAL '7 days'"
    )
    ultimo = cur.fetchone()[0]
    print(f"\n🕐 Último dossiê gerado: {ultimo or 'N/A'}")

    print("\n✅ Para atualizar:  ./run.sh cron-qdrant --diff")
    print("✅ Para gerar dossiês: ./run.sh cron-dossie --lote 50")
    conn.close()


if __name__ == "__main__":
    main()
