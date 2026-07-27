"""
Indexer para base do Qdrant — v2 com votos, dados financeiros e batch embedding.

Fontes de dados indexadas:
  1. perfil         — Nome, partido, UF do deputado
  2. proposicao     — PLs e proposições legislativas
  3. emenda         — Emendas Pix (planos_acao) com dados financeiros do município
  4. voto           — Padrão de voto em votações nominais (NOVO)
  5. diario_oficial — Atos do Diário Oficial

Model: nomic-embed-text-v1.5 (768d) | Metric: Cosine

Uso:
    ./run.sh cron-qdrant --limit 10
    ./run.sh cron-qdrant --nome "Afonso Florence"
    python3 -m src.enrichers.rag_qdrant_indexer --rebuild  # limpa e reindexa tudo
"""

import argparse
import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from config.settings import (
    EMBEDDER_MODEL,
    EMBEDDING_DIM,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from src.db_utils import get_connection
from src.localai_client import LocalAIClient
from src.localai_manager import manager as localai_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------


def ensure_collection(client: QdrantClient, recreate: bool = False) -> None:
    """Cria ou recria a coleção Qdrant com configurações otimizadas e payload indexes."""
    try:
        collections = [c.name for c in client.get_collections().collections]
        if recreate and QDRANT_COLLECTION in collections:
            log.info(f"Recriando coleção {QDRANT_COLLECTION} (--rebuild)...")
            client.delete_collection(QDRANT_COLLECTION)

        if QDRANT_COLLECTION not in collections or recreate:
            log.info(f"Criando coleção {QDRANT_COLLECTION} ({EMBEDDING_DIM}d, cosine)...")
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=qdrant_models.VectorParams(
                    size=EMBEDDING_DIM,
                    distance=qdrant_models.Distance.COSINE,
                ),
                hnsw_config=qdrant_models.HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                    full_scan_threshold=10000,
                ),
            )
            log.info("Coleção criada com sucesso.")

        # Garantir payload indexes para busca filtrada ultra-rápida (deputado_id, type, uf)
        log.info("Garantindo payload indexes no Qdrant (deputado_id, type, uf)...")
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="deputado_id",
            field_schema=qdrant_models.PayloadSchemaType.INTEGER,
        )
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="type",
            field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="uf",
            field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
        )
    except Exception as e:
        log.error(f"Erro ao verificar/criar coleção Qdrant: {e}")
        raise


# ---------------------------------------------------------------------------
# Batch embedding via LocalAIClient (com retry + cache)
# ---------------------------------------------------------------------------

_embed_client: LocalAIClient | None = None


def _get_embed_client() -> LocalAIClient:
    global _embed_client
    if _embed_client is None:
        _embed_client = LocalAIClient(model=EMBEDDER_MODEL)
    return _embed_client


def embed_text_batch(texts: list[str]) -> list[list[float]]:
    """Gera embeddings em batch via LocalAIClient (1 request para N textos)."""
    if not texts:
        return []
    client = _get_embed_client()
    try:
        return client.embed(texts)
    except Exception as e:
        log.error(f"Erro no batch embedding ({len(texts)} textos): {e}")
        return []


def embed_text(text: str) -> list[float] | None:
    """Embedding de um único texto (wrapper para compatibilidade)."""
    results = embed_text_batch([text])
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Extração de dados do banco — cada fonte retorna lista de chunks
# ---------------------------------------------------------------------------


def _extract_perfil(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk 1: Perfil básico do deputado."""
    cur.execute(
        "SELECT nome, sigla_partido, uf FROM parlamentares_dados WHERE deputado_id = %s",
        (deputado_id,),
    )
    row = cur.fetchone()
    if not row:
        return []
    nome_full, partido, uf = row
    return [
        {
            "text": (
                f"Deputado Federal: {nome_full}. "
                f"Partido: {partido}. Estado: {uf}. "
                f"Atuação legislativa na Câmara dos Deputados."
            ),
            "type": "perfil",
            "deputado_id": deputado_id,
        }
    ]


def _extract_proposicoes(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Proposições legislativas (PLs, PLPs, PECs)."""
    cur.execute(
        "SELECT sigla_tipo, numero, ano, ementa FROM parlamentar_proposicoes "
        "WHERE deputado_id = %s",
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for sigla, num, ano, ementa in cur.fetchall():
        if not ementa:
            continue
        docs.append(
            {
                "text": (f"Proposição do deputado {nome}: {sigla} {num}/{ano}. Ementa: {ementa}"),
                "type": "proposicao",
                "deputado_id": deputado_id,
                "ref": f"{sigla} {num}/{ano}",
            }
        )
    return docs


def _extract_emendas(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Emendas Pix com dados financeiros do município (SICONFI)."""
    cur.execute(
        """
        SELECT b.nome, b.uf, o.descricao, pa.valor_total,
               mf.receitas_orcamentarias, mf.despesas_totais, mf.divida_passiva
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN objetos o ON pa.objeto_id = o.objeto_id
        JOIN parlamentares_dados pd
            ON pa.parlamentar_nome = pd.nome_urna OR pa.parlamentar_nome = pd.nome
        LEFT JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        LEFT JOIN municipios_financeiro mf
            ON bm.municipio_id = mf.municipio_id
            AND mf.exercicio = EXTRACT(YEAR FROM COALESCE(pa.data_atualizacao_plano_acao, NOW()))
        WHERE pd.deputado_id = %s
        ORDER BY pa.valor_total DESC NULLS LAST
        LIMIT 20
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for row in cur.fetchall():
        municipio, emp_uf, obj, valor, receita, despesa, divida = row
        txt = (
            f"Emenda do deputado {nome} para {municipio}-{emp_uf}. "
            f"Objeto: {obj}. Valor: R$ {valor:,.2f}."
        )
        # Enriquecer com dados financeiros do município (se disponíveis)
        if receita and despesa:
            txt += (
                f" Dados financeiros do município: receita orçamentária R$ {receita:,.2f}, "
                f"despesas totais R$ {despesa:,.2f}."
            )
            if divida:
                txt += f" Dívida passiva R$ {divida:,.2f}."
        docs.append(
            {
                "text": txt,
                "type": "emenda",
                "deputado_id": deputado_id,
                "ref": f"Emenda para {municipio}",
            }
        )
    return docs


def _extract_votos(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Padrão de voto em votações nominais (NOVO v2)."""
    # 1. Resumo agregado: quantos SIM/NÃO/ABSTENÇÃO
    cur.execute(
        """
        SELECT v.tipo_voto, COUNT(*) as n
        FROM votos_camara v
        WHERE v.deputado_id = %s
        GROUP BY v.tipo_voto
        ORDER BY n DESC
    """,
        (deputado_id,),
    )
    votos_agg: list[tuple[str, int]] = cur.fetchall()
    if not votos_agg:
        return []

    total_votos: int = sum(n for _, n in votos_agg)
    partes: list[str] = [f"'{tv}': {n} vezes ({n * 100 // total_votos}%)" for tv, n in votos_agg]
    resumo_text: str = (
        f"Padrão de voto do deputado {nome} em {total_votos} votações nominais em 2026: "
        f"{', '.join(partes)}."
    )

    docs: list[dict[str, Any]] = [
        {"text": resumo_text, "type": "voto", "deputado_id": deputado_id}
    ]

    # 2. Votos em destaque: votações onde votou contra a maioria (dissenso)
    cur.execute(
        """
        SELECT v.tipo_voto, vc.descricao, vc.aprovacao
        FROM votos_camara v
        JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id
        WHERE v.deputado_id = %s
          AND v.tipo_voto IS NOT NULL
        ORDER BY v.id DESC
        LIMIT 30
    """,
        (deputado_id,),
    )
    for tipo_voto, descricao, aprovacao in cur.fetchall():
        if not descricao or not tipo_voto:
            continue
        # Detectar dissenso: se o deputado votou Não mas a proposição foi aprovada
        # (ou vice-versa)
        dissenso: bool = False
        if (
            aprovacao is True
            and tipo_voto in ("Não", "Obstrução")
            or aprovacao is False
            and tipo_voto == "Sim"
        ):
            dissenso = True

        prefixo: str = "[DISSENSO] " if dissenso else ""
        desc_trunc: str = descricao[:200] + ("..." if len(descricao) > 200 else "")
        txt = f"{prefixo}Deputado {nome} votou '{tipo_voto}' em: {desc_trunc}"
        docs.append({"text": txt, "type": "voto", "deputado_id": deputado_id})

    return docs


def _extract_diario_oficial(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Atos do Diário Oficial (via alertas)."""
    cur.execute(
        """
        SELECT da.orgao, da.tipo_ato, da.resumo_ia, da.valor_financeiro,
               da.entidades_citadas
        FROM parlamentar_alertas pa
        JOIN diario_oficial_atos da ON pa.ato_id = da.ato_id
        WHERE pa.parlamentar_nome = %s
           OR pa.parlamentar_nome = (
               SELECT nome_urna FROM parlamentares_dados
               WHERE deputado_id = %s LIMIT 1
           )
    """,
        (nome, deputado_id),
    )
    docs: list[dict[str, Any]] = []
    for orgao, tipo_ato, resumo, valor, entidades in cur.fetchall():
        txt = f"Ato Oficial ({tipo_ato}) em {orgao}. Resumo: {resumo}."
        if entidades and entidades != "[]":
            txt += f" Entidades citadas: {entidades}."
        if valor:
            txt += f" Valor associado: R$ {valor:,.2f}."
        docs.append(
            {
                "text": txt,
                "type": "diario_oficial",
                "deputado_id": deputado_id,
                "ref": f"Ato: {tipo_ato}",
            }
        )
    return docs


def _extract_prefeitos_aliados(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Cruzamento partidário entre Deputado x Prefeitos Receptores de Emendas (TSE)."""
    cur.execute(
        """
        SELECT b.nome as municipio, pd_dep.sigla_partido as partido_deputado,
               pr.prefeito_nome, pr.sigla_partido as partido_prefeito, pr.coligacao,
               SUM(pa.valor_total) as valor_total
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd_dep
            ON pa.parlamentar_nome = pd_dep.nome_urna OR pa.parlamentar_nome = pd_dep.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN prefeitos_dados pr ON bm.municipio_id = pr.municipio_id
        WHERE pd_dep.deputado_id = %s
        GROUP BY b.nome, pd_dep.sigla_partido, pr.prefeito_nome, pr.sigla_partido, pr.coligacao
        ORDER BY valor_total DESC
        LIMIT 15
    """,
        (deputado_id,),
    )

    docs: list[dict[str, Any]] = []
    for muni, part_dep, pref_nome, part_pref, coligacao, valor in cur.fetchall():
        mesmo_partido: bool = part_dep == part_pref
        em_coligacao: bool = bool(part_dep and coligacao and part_dep in coligacao)

        relacao: str = (
            "MESMO PARTIDO DO DEPUTADO"
            if mesmo_partido
            else ("ALIANÇA/COLIGAÇÃO" if em_coligacao else "OPOSIÇÃO/OUTRO PARTIDO")
        )

        txt = (
            f"Conexão política local em {muni}: Prefeito {pref_nome} ({part_pref}). "
            f"Relação com o deputado {nome} ({part_dep}): {relacao}. Total emendas recebidas: R$ {valor:,.2f}."
        )
        docs.append(
            {
                "text": txt,
                "type": "conexao_politica",
                "deputado_id": deputado_id,
                "ref": f"Prefeito de {muni}",
            }
        )
    return docs


# ---------------------------------------------------------------------------
# Orchestrador: extrai todos os chunks de um deputado
# ---------------------------------------------------------------------------


def get_deputado_texts(deputado_id: int) -> list[dict[str, Any]]:
    """Extrai chunks de TODAS as fontes para um deputado."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT nome FROM parlamentares_dados WHERE deputado_id = %s",
            (deputado_id,),
        )
        row = cur.fetchone()
        if not row:
            return []
        nome = row[0]

        docs: list[dict[str, Any]] = []
        docs.extend(_extract_perfil(cur, deputado_id, nome))
        docs.extend(_extract_proposicoes(cur, deputado_id, nome))
        docs.extend(_extract_emendas(cur, deputado_id, nome))
        docs.extend(_extract_votos(cur, deputado_id, nome))
        docs.extend(_extract_diario_oficial(cur, deputado_id, nome))
        docs.extend(_extract_prefeitos_aliados(cur, deputado_id, nome))
        return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Popula o Qdrant com dados dos Deputados para RAG (v2)"
    )
    parser.add_argument("--limit", type=int, default=10, help="Número de deputados a processar")
    parser.add_argument("--nome", type=str, help="Nome do deputado (busca exata por ILIKE)")
    parser.add_argument("--rebuild", action="store_true", help="Recriar coleção do zero")
    args = parser.parse_args()

    # 1. Carregar embedder
    log.info("Carregando modelo de embeddings...")
    localai_manager.ensure_model_loaded(EMBEDDER_MODEL)

    # 2. Conectar Qdrant
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, recreate=args.rebuild)

    # 3. Buscar deputados para indexar
    with get_connection() as conn, conn.cursor() as cur:
        if args.nome:
            cur.execute(
                """
                SELECT deputado_id, nome
                FROM parlamentares_dados
                WHERE nome ILIKE %s OR nome_urna ILIKE %s
            """,
                (f"%{args.nome}%", f"%{args.nome}%"),
            )
        else:
            # Priorizar deputados com mais dados (alertas DO + votos)
            cur.execute(
                """
                SELECT pd.deputado_id, pd.nome,
                    (SELECT COUNT(*) FROM parlamentar_alertas pa
                     WHERE pa.parlamentar_nome IN (pd.nome, pd.nome_urna)) as n_alertas,
                    (SELECT COUNT(*) FROM votos_camara vc
                     WHERE vc.deputado_id = pd.deputado_id) as n_votos
                FROM parlamentares_dados pd
                ORDER BY n_alertas DESC, n_votos DESC, pd.deputado_id ASC
                LIMIT %s
            """,
                (args.limit,),
            )
        deputados = cur.fetchall()

    if not deputados:
        log.info("Nenhum deputado encontrado para indexar.")
        return

    log.info(f"Indexando {len(deputados)} deputados no Qdrant...")
    total_points = 0

    for idx, dep_row in enumerate(deputados, 1):
        deputado_id = dep_row[0]
        nome = dep_row[1]

        # Extrair chunks
        docs = get_deputado_texts(deputado_id)
        if not docs:
            log.warning(f"  [{idx}/{len(deputados)}] {nome}: sem dados, pulando.")
            continue

        # Batch embedding (1 request para todos os chunks)
        texts = [d["text"] for d in docs]
        vectors = embed_text_batch(texts)

        # Montar points
        points: list[qdrant_models.PointStruct] = []
        for doc, vector in zip(docs, vectors):
            if not vector or len(vector) != EMBEDDING_DIM:
                continue
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{deputado_id}_{doc['text']}"))
            points.append(
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=doc,
                )
            )

        # Upsert
        if points:
            client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            total_points += len(points)

        if idx % 10 == 0 or idx == len(deputados):
            log.info(
                f"  [{idx}/{len(deputados)}] {nome}: {len(docs)} chunks, "
                f"{len(points)} vetores → total {total_points}"
            )

    log.info(
        f"Indexação concluída: {len(deputados)} deputados, "
        f"{total_points} vetores inseridos no Qdrant."
    )


if __name__ == "__main__":
    main()
