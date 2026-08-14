"""
Modulo RAG v7: Geracao de Personas/Dossies de Deputados (Multi-Analista).

Melhorias v7 (vs. v6):
  - 7 analistas especialistas independentes (cada um com prompt focado)
  - Roteador de chunks: cada analista recebe apenas dados relevantes
  - Quality check proprio por analista + score global ponderado
  - Tolerancia a falhas: se um analista falha, os demais continuam
  - Assembly final concatena secoes na ordem correta

v6 (base):
  - Modelo padrao gemma-4-e2b-it (36.8 tok/s, melhor PT-BR)
  - Retry automatico com fallback (llama-3.2-3b) se quality check reprovar
  - ensure_model_loaded() chamado 1x no lote (eliminada duplicacao)
  - Prompt mais estruturado com secoes "I. EXECUTIVO / OPOSICAO"
  - RAG_FALLBACK_MODEL e RAG_MAX_RETRIES via settings.py

v5 (base):
  - Multi-query RAG (15 queries tematicas, batch embedding)
  - Reciprocal Rank Fusion (RRF) para re-ranking de chunks
  - Dedup via MD5 (nao por prefixo) para evitar falsos positivos
  - Validacao de tamanho do prompt (janela de contexto ~8K)
  - Quality check: validacao de secoes obrigatorias na analise
  - QdrantClient reutilizado por lote (nao 1 por query)
  - ThreadPoolExecutor para processamento paralelo em lote
  - Context_list retornado por generate (elimina busca duplicada)

Fluxo v7:
  1. search_context_multiquery() -> batch embed + RRF -> chunks do Qdrant
  2. run_analyst_pipeline() -> 7 analistas independentes (com tolerancia a falhas)
  3. assemble_dossier() -> concatena secoes na ordem
  4. calculate_global_score() -> score ponderado das secoes
  5. _save_persona() -> salva no DB com contexto_rag + fontes_usadas

Uso:
    ./run.sh cron-dossie --nome "Afonso Florence"
    ./run.sh cron-dossie --lote 50 --modelo gemma-4-e2b-it
    python3 -m src.enrichers.rag_persona --nome "Afonso Florence" --regerar
"""

import argparse
import concurrent.futures
import hashlib
import logging
import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from config.settings import (
    CLOUD_PROXY_MODEL_NAMES,
    QDRANT_COLLECTION,
    QDRANT_URL,
    RAG_LLM_MODEL,
    RAG_MAX_CHUNKS,
    RAG_MIN_CHUNKS,
    RAG_PERSONA_VERSION,
    USE_MODAL_VLLM,
)
from src.analysts import (
    assemble_dossier,
    calculate_global_score,
    run_analyst_pipeline,
)
from src.db_utils import get_connection
from src.enrichers.rag_qdrant_indexer import (
    embed_text_batch,
    text_to_sparse_vector,
    texts_to_sparse_vectors,
)
from src.localai_manager import manager as localai_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Último resultado de qualidade (score global + por analista) exposto para
# consumidores como scripts/dossier_bench.py — preenchido a cada chamada de
# generate_persona_analysis() sem alterar a assinatura da função.
LAST_RUN_SCORE: dict = {"global": None, "analistas": {}}
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes para RRF e validacao de prompt
# ---------------------------------------------------------------------------

RRF_K = 60  # Constante de suavizacao do Reciprocal Rank Fusion
RAG_TOKEN_CHARS = 4  # Estimativa: ~4 caracteres por token
# Limite de tokens adaptativo: 32k para Modal (Llama-3-70B), 7k para local
RAG_MAX_TOKENS = 32000 if USE_MODAL_VLLM else 7000
EMBEDDING_DIM = 768  # Dimensao do embeddinggemma-300m

# ---------------------------------------------------------------------------
# Mapa: query_tematica_index -> chunk_types para filtro no Qdrant
# Cada query busca apenas chunks do tipo relevante, melhorando o recall
# e reduzindo ruido no RRF fusion.
# ---------------------------------------------------------------------------

QUERY_CHUNK_FILTER: dict[int, list[str]] = {
    0: ["VOTO"],
    1: ["PROPOSICAO"],
    2: ["EMENDA", "BENEFICIARIO"],
    3: ["EMENDA_DISCRICIONARIA"],
    4: ["PARLAMENTAR_RESUMO", "PERFIL", "PERSONA_EXISTENTE"],
    5: ["MUNICIPIO_FINANCEIRO"],
    6: ["DEMOGRAFIA_MUNICIPIO"],
    7: ["INDICADORES_SOCIAIS", "INDICADORES_MUNICIPAL"],
    8: ["FNDE_REPASSES"],
    9: ["CONEXAO_POLITICA", "PREFEITO", "VEREADORES_RESUMO", "SENADOR"],
    10: ["RISCO_JUDICIAL", "DIARIO_OFICIAL", "PARLAMENTAR_ALERTAS"],
    11: ["COMPRAS_MUNICIPIO", "BENEFICIARIO"],
    12: ["DISCURSO_PLENARIO"],
    13: ["DISCURSO_PLENARIO"],
    # FIX 2026-07-31: antes, 7 dos 22 chunk types (perfil, beneficiario,
    # diario_oficial, senador, indicadores_municipal, parlamentar_alertas,
    # persona_existente) NUNCA eram buscados pelas queries tematicas — ficavam
    # fora do contexto do dossier mesmo quando indexados. Agora todos os tipos
    # sao alcancaveis por pelo menos uma query.
}

# ---------------------------------------------------------------------------
# Multi-Query RAG -- 14 queries tematicas (cobrindo todos os 22 chunk types)
# ---------------------------------------------------------------------------

QUERIES_TEMATICAS = [
    # === Comportamento Legislativo ===
    "Padrao de voto e alinhamento politico do deputado em votacoes nominais, "
    "dissenso partidario, obstrucao e abstencao no plenario",
    "Proposicoes legislativas apresentadas: PLs, PECs, PDLs, areas tematicas, "
    "produtividade legislativa e coerencia com emendas",
    # === Emendas e Transferencias ===
    "Emendas parlamentares Pix: municipios beneficiarios, valores transferidos, "
    "situacao dos planos de acao, objetos de execucao",
    "Emendas discricionarias e transferencias convencionais do Portal Transparencia: "
    "convenios, status de execucao orcamentaria, beneficiarios CNPJ",
    "Resumo consolidado do deputado: total de emendas, beneficiarios unicos, "
    "municipios atendidos e valor global alocado",
    # === Contexto Municipal/Estadual Financeiro e Demografico ===
    "Dados financeiros municipais SICONFI: receita orcamentaria, despesas totais, "
    "divida passiva, arrecadacao FPM, ICMS e ISS dos municipios receptores",
    "Dados financeiros do governo estadual SICONFI: receitas, despesas, resultado "
    "orcamentario, divida, ICMS, IPVA, ITCD, IRRF, FPE, FUNDEB e RCL do estado "
    "onde o deputado atua",
    "Dados demograficos IBGE dos municipios receptores: populacao, PIB per capita, "
    "IDHM, area territorial, densidade demografica",
    # === Indicadores Sociais e Transparencia ===
    "Indicadores de saude e educacao nos municipios: leitos SUS, hospitais, UBS, "
    "IDEB anos iniciais e finais, taxa de aprovacao e matriculas escolares",
    "Repasses FNDE e programas educacionais (FUNDEB, PNAE, PNLD, PNATE) "
    "nos municipios receptores de emendas parlamentares",
    # === Rede Politica e Riscos ===
    "Conexao politica local: partido dos prefeitos beneficiados, relacao partidaria, "
    "vereadores aliados, apadrinhamento eleitoral, fisiologismo municipal",
    "Risco judicial e compliance: processos judiciais dos beneficiarios via DataJud, "
    "fraudes, irregularidades e acoes contra entidades receptoras",
    # === Compras, Beneficiarios e Transparencia ===
    "Compras publicas e licitacoes nos municipios receptores, fornecedores, "
    "contratos homologados e beneficiarios diretos com CNPJ",
    # === Discursos e Retorica ===
    "Ideologia e posicionamento politico do deputado nos discursos de plenario: "
    "pautas de costumes, conservadorismo, progressismo, polarizacao, retorica partidaria",
    "Topicos recorrentes, palavras-chave e bandeiras publicas do deputado nos "
    "discursos: saude, educacao, seguranca, economia, corrupcao, direitos humanos, meio ambiente",
]

# Secoes obrigatorias que a analise gerada deve conter (v6 com CLASSIFICAÇÂO)
SECOES_OBRIGATORIAS = [
    "CLASSIFICACAO POLITICA",
    "PERFIL",
    "AREAS TEMATICAS",
    "CRUZAMENTO DE DADOS",
    "ALINHAMENTO POLITICO",
    "ANOMALIAS E FISIOLOGISMO",
]

# Secoes opcionais (dependem dos dados disponiveis)
SECOES_OPCIONAIS = [
    "PADRAO DE VOTO",
    "EMENDAS PIX",
    "PROPOSICOES LEGISLATIVAS",
    "FISIOLOGISMO E ALINHAMENTO MUNICIPAL",
]


# ---------------------------------------------------------------------------
# Busca Qdrant -- com client reutilizavel e vector pre-computado
# ---------------------------------------------------------------------------


def search_context_qdrant(
    deputado_id: int,
    query_text: str,
    limit: int = 10,
    client: QdrantClient | None = None,
    query_vector: list[float] | None = None,
    query_sparse_vector: qdrant_models.SparseVector | None = None,
    chunk_types: list[str] | None = None,
    tipo_politico: str = "deputado",
) -> list[tuple[str, float]]:
    """Busca chunks relevantes no Qdrant usando hybrid search (dense + BM25 sparse + RRF).

    Args:
        client: QdrantClient reutilizado (None = criar novo).
        query_vector: Dense vector pré-embeddado (None = embed agora).
        query_sparse_vector: Sparse vector BM25 pré-computado (None = computa agora).
        chunk_types: Filtrar por tipos específicos de chunk (ex: ["VOTO", "EMENDA"]).
                     Se None, retorna todos os tipos (mantém compatibilidade).

    Returns:
        Lista de (texto_formatado, score_qdrant).
    """
    # 1.4: Nao chamar ensure_model_loaded aqui (chamado 1x no caller)
    if query_vector is None:
        from src.enrichers.rag_qdrant_indexer import embed_text

        query_vector = embed_text(query_text)
    if not query_vector:
        log.error(f"Falha ao embeddar query: '{query_text[:60]}...'")
        return []

    # Sparse query vector (BM25) — gerado localmente
    if query_sparse_vector is None:
        query_sparse_vector = text_to_sparse_vector(query_text)

    # 1.2: Reutilizar client quando fornecido
    should_close = False
    if client is None:
        # trust_env=False: evita falha de URLPattern do httpx 0.28.1 com
        # no_proxy contendo CIDR IPv6 (ex.: fd00::/8) -> Invalid port ':'
        client = QdrantClient(url=QDRANT_URL, trust_env=False)
        should_close = True

    # Filtro base: por cargo + id do político.
    # Deputados: tipo_politico/politico_id (uniforme com os demais cargos),
    # com fallback para deputado_id (pontos criados antes do backfill Fase 3).
    if tipo_politico == "deputado":
        id_conditions: list[Any] = [
            qdrant_models.FieldCondition(
                key="politico_id",
                match=qdrant_models.MatchValue(value=deputado_id),
            ),
            qdrant_models.FieldCondition(
                key="deputado_id",
                match=qdrant_models.MatchValue(value=deputado_id),
            ),
        ]
    else:
        id_conditions = [
            qdrant_models.FieldCondition(
                key="politico_id",
                match=qdrant_models.MatchValue(value=deputado_id),
            )
        ]

    conditions: list[
        qdrant_models.FieldCondition
        | qdrant_models.IsEmptyCondition
        | qdrant_models.IsNullCondition
        | qdrant_models.HasIdCondition
        | qdrant_models.HasVectorCondition
        | qdrant_models.NestedCondition
        | qdrant_models.Filter
    ] = [
        qdrant_models.FieldCondition(
            key="tipo_politico",
            match=qdrant_models.MatchValue(value=tipo_politico),
        ),
        qdrant_models.Filter(should=id_conditions),
    ]

    # Filtro opcional por chunk type
    # IMPORTANTE: payloads do Qdrant usam tipos em MINÚSCULAS
    # (ex: "proposicao", "voto") — normalizar para lowercase,
    # pois MatchValue é case-sensitive.
    if chunk_types:
        chunk_types = [ct.lower() for ct in chunk_types]
        if len(chunk_types) == 1:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="type",
                    match=qdrant_models.MatchValue(value=chunk_types[0]),
                )
            )
        else:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="type",
                    match=qdrant_models.MatchAny(any=chunk_types),
                )
            )

    filtro = qdrant_models.Filter(must=conditions)

    try:
        # Hybrid search: prefetch dense + sparse, fuse with RRF
        hits = client.query_points(
            collection_name=QDRANT_COLLECTION,
            prefetch=[
                qdrant_models.Prefetch(
                    query=query_vector,
                    using="dense",
                    limit=limit * 3,
                ),
                qdrant_models.Prefetch(
                    query=query_sparse_vector,
                    using="bm25",
                    limit=limit * 3,
                ),
            ],
            query=qdrant_models.FusionQuery(fusion=qdrant_models.Fusion.RRF),
            query_filter=filtro,
            search_params=qdrant_models.SearchParams(hnsw_ef=128),
            limit=limit,
        )
    except Exception as e:
        log.error(f"Erro na busca Qdrant para deputado {deputado_id}: {e}")
        return []
    finally:
        if should_close:
            client.close()

    results: list[tuple[str, float]] = []
    for hit in hits.points:
        if hit.payload and "text" in hit.payload:
            tipo = hit.payload.get("type", "info").upper()
            text = f"[{tipo}] {hit.payload['text']}"
            results.append((text, hit.score))
    return results


# ---------------------------------------------------------------------------
# Multi-Query com batch embed + RRF + MD5 dedup
# ---------------------------------------------------------------------------


def _buscar_resumos_por_area(
    deputado_id: int,
    tipo_politico: str = "deputado",
    client: QdrantClient | None = None,
) -> list[tuple[str, float]]:
    """Busca chunks 'Distribuição por área' (fonte canônica de R$ literais).

    Os resumos por área de emendas/emendas discricionárias trazem os TOTAIS
    EXATOS por área/município — a fonte que o llama-3.2-3b deve transcrever
    literalmente (data-first). O RRF normal pode deixá-los de fora quando há
    muitos chunks; aqui usamos filtro por tipo + scroll e selecionamos os
    chunks cujo texto contém 'Distribuição por área'.

    Retorna lista de (texto_formatado, score_ficticio) — score 1.0 apenas
    para manter o contrato de (texto, score).
    """
    should_close = False
    if client is None:
        client = QdrantClient(url=QDRANT_URL, trust_env=False)
        should_close = True
    try:
        # Filtro por tipo de chunk de emenda (o resumo vive em um destes)
        conditions: list[Any] = [
            qdrant_models.FieldCondition(
                key="tipo_politico",
                match=qdrant_models.MatchValue(value=tipo_politico),
            ),
            qdrant_models.FieldCondition(
                key="type",
                match=qdrant_models.MatchAny(any=["emenda", "emenda_discricionaria"]),
            ),
        ]
        if tipo_politico == "deputado":
            conditions.append(
                qdrant_models.Filter(
                    should=[
                        qdrant_models.FieldCondition(
                            key="politico_id",
                            match=qdrant_models.MatchValue(value=deputado_id),
                        ),
                        qdrant_models.FieldCondition(
                            key="deputado_id",
                            match=qdrant_models.MatchValue(value=deputado_id),
                        ),
                    ]
                )
            )
        else:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="politico_id",
                    match=qdrant_models.MatchValue(value=deputado_id),
                )
            )

        hits, _next = client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=qdrant_models.Filter(must=conditions),
            limit=100,
            with_payload=True,
        )
        out: list[tuple[str, float]] = []
        for hit in hits:
            pl = hit.payload or {}
            text = pl.get("text") or ""
            if "Distribuição por área" in text or "distribuicao_por_area" in text:
                tipo = str(pl.get("type", "info")).upper()
                out.append((f"[{tipo}] {text}", 1.0))
        return out
    except Exception as exc:
        log.warning(f"Falha ao buscar resumos por área: {exc}")
        return []
    finally:
        if should_close:
            client.close()


def search_context_multiquery(
    deputado_id: int,
    top_k_per_query: int = 8,
    tipo_politico: str = "deputado",
) -> tuple[list[str], list[tuple[str, float]]]:
    """Executa 15 queries tematicas com batch embed, RRF merge + MD5 dedup.

    Args:
        deputado_id: ID do político no cargo (deputado_id, senador_codigo,
            municipio_id p/ prefeito, sq_candidato p/ vereador, uf p/ governador).
        tipo_politico: Cargo (deputado/senador/governador/prefeito/vereador).
            Filtra o payload do Qdrant por tipo_politico + politico_id.

    Returns:
        (context_list, scored_chunks):
        - context_list: textos finais deduplicados e ranqueados por RRF
        - scored_chunks: (texto, rrf_score) para auditoria
    """
    from config.settings import RAG_MAX_CHUNKS_BY_TIPO

    max_chunks = RAG_MAX_CHUNKS_BY_TIPO.get(tipo_politico, RAG_MAX_CHUNKS)
    # Embedder (nomic) e CPU-based, nao precisa de exclusividade GPU.
    # LocalAI lazy-load na primeira chamada de embedding.

    # 1.2: reutilizar QdrantClient para todas as queries
    # trust_env=False: idem — httpx 0.28.1 quebra com no_proxy CIDR IPv6
    client = QdrantClient(url=QDRANT_URL, trust_env=False)

    # 1.3: batch embed de todas as queries em 1 request
    log.info(
        f"Batch embedding de {len(QUERIES_TEMATICAS)} queries tematicas "
        f"para {tipo_politico} {deputado_id}..."
    )
    all_vectors = embed_text_batch(QUERIES_TEMATICAS)
    if len(all_vectors) != len(QUERIES_TEMATICAS):
        log.error(
            f"Falha no batch embedding: esperado {len(QUERIES_TEMATICAS)}, "
            f"recebido {len(all_vectors)}"
        )
        client.close()
        return [], []

    # Sparse query vectors (BM25-style) — geração local rápida, sem modelo
    sparse_vectors = texts_to_sparse_vectors(QUERIES_TEMATICAS)

    # Coletar resultados de todas as queries com score e indice da query
    raw_results: list[tuple[str, float, int]] = []  # (texto, score_qdrant, query_idx)
    for qi, (query_text, vector, sparse_vec) in enumerate(
        zip(QUERIES_TEMATICAS, all_vectors, sparse_vectors)
    ):
        # Filtro por chunk type especifico de cada query
        chunk_types = QUERY_CHUNK_FILTER.get(qi)
        results = search_context_qdrant(
            deputado_id,
            query_text,
            limit=top_k_per_query,
            client=client,
            query_vector=vector,
            query_sparse_vector=sparse_vec,
            chunk_types=chunk_types,
            tipo_politico=tipo_politico,
        )
        for text, score in results:
            raw_results.append((text, score, qi))
        log.debug(f"  query '{query_text[:40]}...' -> {len(results)} chunks")

    # PITFALL 2026-08-11 (data-first): os resumos por área ("Distribuição por
    # área ... R$ total por área") são a FONTE CANÔNICA de totais literais
    # para os analistas tematicas/cruzamento/anomalias. Com 124+ chunks por
    # político, o RRF top-N frequentemente deixa o resumo de fora (as queries
    # vetoriais casam com os chunks individuais de emenda). Sem os totais
    # literais no contexto, o llama-3.2-3b inventa valores (golden 6/6 falhou
    # com 92% de R$ fabricados). Solução: buscar SEMPRE os resumos por área
    # e injetá-los no topo do contexto, independente do ranking.
    resumos_area = _buscar_resumos_por_area(deputado_id, tipo_politico, client)

    client.close()

    # 2.2: Dedup via MD5 (normalizar: lowercase + strip whitespace)
    seen_hashes: set[str] = set()
    deduped: list[tuple[str, str, float, int]] = []  # (hash, texto, score, qi)
    for text, score, qi in raw_results:
        h = hashlib.md5(text.lower().strip().encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append((h, text, score, qi))

    # 2.1: Reciprocal Rank Fusion (RRF)
    # Agrupar por query index para calcular rank per-query
    per_query_hashes: dict[int, list[str]] = {}
    for h, _text, _score, qi in deduped:
        per_query_hashes.setdefault(qi, []).append(h)

    rrf_scores: dict[str, float] = {}
    for _qi, hash_list in per_query_hashes.items():
        for rank, h in enumerate(hash_list):
            rrf_scores[h] = rrf_scores.get(h, 0.0) + 1.0 / (RRF_K + rank + 1)

    # Ordenar por RRF score desc, tomar top N
    deduped.sort(key=lambda x: rrf_scores[x[0]], reverse=True)
    final = [(text, rrf_scores[h]) for h, text, _score, _qi in deduped[:max_chunks]]

    # Injeta os resumos por área (buscados antes do client.close()) no topo.
    if resumos_area:
        log.info(
            f"Injetando {len(resumos_area)} resumo(s) por área no topo do "
            f"contexto (fonte canônica de R$)."
        )
        textos_resumo = [t for t, _s in resumos_area]
        # Dedup contra o que já veio do RRF
        hashes_existentes = {
            hashlib.md5(t.lower().strip().encode()).hexdigest() for t, _s in final
        }
        novos = [
            t for t in textos_resumo
            if hashlib.md5(t.lower().strip().encode()).hexdigest()
            not in hashes_existentes
        ]
        final = [(t, 999.0) for t in novos] + final
        final = final[: max_chunks + len(novos)]

    context_list = [text for text, _rrf in final]
    log.info(
        f"Multi-query: {len(raw_results)} brutos -> {len(deduped)} unicos "
        f"-> {len(final)} finais (RRF + resumos por área)"
    )
    return context_list, final


# ---------------------------------------------------------------------------
# Helper: detecção de modelo cloud proxy
# ---------------------------------------------------------------------------


def _is_cloud_proxy_model(model_id: str) -> bool:
    """Verifica se o modelo roda via cloud proxy (não precisa de VRAM local)."""
    return model_id in CLOUD_PROXY_MODEL_NAMES


def _effective_max_tokens(model_id: str | None = None) -> int:
    """Retorna o limite de tokens efetivo baseado no tipo de modelo."""
    model = model_id or RAG_LLM_MODEL
    if USE_MODAL_VLLM:
        return 32000
    if _is_cloud_proxy_model(model):
        return 128000  # Modelos cloud têm janela de contexto grande (128K+)
    return 7000  # Padrão local


# ---------------------------------------------------------------------------
# Validacao de tamanho do prompt (janela de contexto)
# ---------------------------------------------------------------------------


def _validate_prompt_size(
    prompt: str,
    context_list: list[str],
    nome: str,
    max_tokens: int | None = None,
) -> tuple[str, list[str]]:
    """Trunca chunks se prompt exceder janela de contexto do modelo.

    Estima tokens como len(prompt) / 4. Se exceder max_tokens,
    remove chunks ate caber (minimo RAG_MIN_CHUNKS).

    Args:
        max_tokens: Limite de tokens. Se None, usa _effective_max_tokens().

    Returns:
        (prompt_rebuild, context_list_trimmed)
    """
    if max_tokens is None:
        max_tokens = _effective_max_tokens()

    estimated_tokens = len(prompt) // RAG_TOKEN_CHARS
    if estimated_tokens <= max_tokens:
        return prompt, context_list

    log.warning(
        f"Prompt excede limite ({estimated_tokens} tokens > {max_tokens}), "
        f"reduzindo de {len(context_list)} chunks..."
    )
    trimmed = list(context_list)
    while len(trimmed) > RAG_MIN_CHUNKS:
        trimmed.pop()
        rebuilt = build_analysis_prompt(trimmed, nome)
        if len(rebuilt) // RAG_TOKEN_CHARS <= max_tokens:
            prompt = rebuilt
            break
    else:
        # Atingiu RAG_MIN_CHUNKS e ainda excede -- usar o ultimo rebuild
        prompt = build_analysis_prompt(trimmed, nome)

    final_tokens = len(prompt) // RAG_TOKEN_CHARS
    log.warning(
        f"Chunks reduzidos: {len(context_list)} -> {len(trimmed)} "
        f"({final_tokens} tokens estimados, limite: {max_tokens})"
    )
    return prompt, trimmed


# ---------------------------------------------------------------------------
# Quality check -- validacao de secoes obrigatorias
# ---------------------------------------------------------------------------


def _check_quality(analise: str) -> bool:
    """Valida se todas as secoes obrigatorias estao presentes na analise."""
    import unicodedata

    normalized = (
        unicodedata.normalize("NFKD", analise).encode("ascii", "ignore").decode("ascii").upper()
    )
    ausentes = [s for s in SECOES_OBRIGATORIAS if s not in normalized]

    if ausentes:
        log.warning(f"Secoes ausentes na analise: {', '.join(ausentes)}")

    opcional_presentes = sum(1 for s in SECOES_OPCIONAIS if s in normalized)
    log.debug(
        f"  Secoes obrigatorias: {len(SECOES_OBRIGATORIAS) - len(ausentes)}/{len(SECOES_OBRIGATORIAS)}, "
        f"opcionais: {opcional_presentes}/{len(SECOES_OPCIONAIS)}"
    )

    return len(ausentes) == 0


def score_qualidade_eval(analise: str) -> float:
    """Calcula pontuação de qualidade (0 a 100) baseada na cobertura de seções e densidade numérica."""
    import re
    import unicodedata

    normalized = (
        unicodedata.normalize("NFKD", analise).encode("ascii", "ignore").decode("ascii").upper()
    )
    encontradas = [s for s in SECOES_OBRIGATORIAS if s in normalized]
    score = (len(encontradas) / len(SECOES_OBRIGATORIAS)) * 70.0
    palavras = len(analise.split())
    densidade = min(palavras / 400.0, 1.0) * 20.0
    tem_numeros = bool(re.search(r"R\$\s*[\d.,]+|[\d.,]+%", analise))
    numeros_bonus = 10.0 if tem_numeros else 0.0
    return min(round(score + densidade + numeros_bonus, 1), 100.0)


# ---------------------------------------------------------------------------
# Prompt Adaptativo -- adapta secoes baseado nos dados disponiveis
# ---------------------------------------------------------------------------


def _count_sources(context_list: list[str]) -> dict[str, int]:
    """Conta chunks por tipo de fonte."""
    counts: dict[str, int] = {
        "perfil": 0,
        "proposicoes": 0,
        "emendas": 0,
        "votos": 0,
        "diario_oficial": 0,
        "conexao_politica": 0,
        "emendas_discricionarias": 0,
        "compras": 0,
        "indicadores_sociais": 0,
        "indicadores_municipais": 0,
        "risco_judicial": 0,
        "demografia": 0,
        "financeiro": 0,
        "resumo": 0,
        "beneficiarios": 0,
        "prefeitos": 0,
        "senadores": 0,
        "fnde": 0,
        "vereadores": 0,
        "discursos": 0,
    }
    for c in context_list:
        upper = c.upper()
        if "[VOTO]" in upper:
            counts["votos"] += 1
        elif "[EMENDA_DISCRICIONARIA]" in upper:
            counts["emendas_discricionarias"] += 1
        elif "[EMENDA]" in upper:
            counts["emendas"] += 1
        elif "[PROPOSICAO]" in upper:
            counts["proposicoes"] += 1
        elif "[DISCURSO_PLENARIO]" in upper:
            counts["discursos"] += 1
        elif "[DIARIO_OFICIAL]" in upper:
            counts["diario_oficial"] += 1
        elif "[CONEXAO_POLITICA]" in upper:
            counts["conexao_politica"] += 1
        elif "[COMPRAS_MUNICIPIO]" in upper:
            counts["compras"] += 1
        elif "[INDICADORES_SOCIAIS]" in upper:
            counts["indicadores_sociais"] += 1
        elif "[INDICADORES_MUNICIPAL]" in upper:
            counts["indicadores_municipais"] += 1
        elif "[RISCO_JUDICIAL]" in upper:
            counts["risco_judicial"] += 1
        elif "[DEMOGRAFIA_MUNICIPIO]" in upper:
            counts["demografia"] += 1
        elif "[MUNICIPIO_FINANCEIRO]" in upper:
            counts["financeiro"] += 1
        elif "[PARLAMENTAR_RESUMO]" in upper:
            counts["resumo"] += 1
        elif "[BENEFICIARIO]" in upper:
            counts["beneficiarios"] += 1
        elif "[PREFEITO]" in upper:
            counts["prefeitos"] += 1
        elif "[SENADOR]" in upper:
            counts["senadores"] += 1
        elif "[FNDE_REPASSES]" in upper:
            counts["fnde"] += 1
        elif "[VEREADORES_RESUMO]" in upper:
            counts["vereadores"] += 1
        elif "[PERFIL]" in upper:
            counts["perfil"] += 1
    return counts


def build_analysis_prompt(context_list: list[str], deputado_nome: str) -> str:
    """Monta prompt adaptativo baseado na quantidade e tipo de dados (19 chunk types)."""
    src = _count_sources(context_list)

    # Secao de votos -- so aparece se houver dados de voto
    secao_votos = ""
    if src["votos"] > 0:
        secao_votos = """
6. **PADRAO DE VOTO**: Analise o alinhamento politico. Identifique:
   - Votos com o governo vs. oposicao (sempre "Sim"/"Nao" em proposicoes)
   - Temas onde divergiu da bancada partidaria (marcar com [DISSENSO])
   - Consistencia entre discurso e voto real
   - Percentual aproximado de alinhamento com a base aliada
"""

    # Secao de emendas
    secao_emendas = ""
    if src["emendas"] > 0:
        secao_emendas = """
7. **EMENDAS PIX**: Mapeie concentracao de verbas. Identifique:
   - Municipios com maiores valores recebidos (e se sao pequenos vs. populosos)
   - Entidades recorrentes ou que aparecem em multiplas emendas
   - Possiveis anomalias: valores muito altos para municipios pequenos
   - Cruzamento com dados financeiros do municipio (se disponiveis no contexto)
"""

    # Secao de proposicoes
    secao_props = ""
    if src["proposicoes"] > 0:
        secao_props = """
8. **PROPOSICOES LEGISLATIVAS**: Identifique:
   - Areas tematicas prioritarias (saude, seguranca, educacao, etc.)
   - Volume de proposicoes como indicador de produtividade legislativa
   - Coerencia entre proposicoes e emendas (o que propoe vs. onde gasta)
"""

    # Secao de discursos
    secao_discursos = ""
    if src["discursos"] > 0:
        secao_discursos = """
9. **POSICIONAMENTO PÚBLICO E DISCURSOS**: Analise AS TAGS e KEYWORDS dos discursos do plenário:
   - TAGS/KEYWORDS mais frequentes: extraia as palavras-chave que mais aparecem (ex: "corrupção", "liberdade de expressão", "direitos humanos", "reforma tributária", "pauta de costumes")
   - Posicionamento ideológico: o deputado se posiciona como conservador, progressista, liberal, nacionalista? Cite tags que comprovem.
   - Temas polêmicos: identifique pautas quentes (armas, aborto, gênero, prisão em 2ª instância, reforma da previdência) e qual o lado do deputado
   - Tom e retórica: confrontacional, técnico/propositivo, populista, conciliador, religioso
   - Bandeiras públicas: nichos eleitorais e pautas defendidas consistentemente
   - Consistência temporal: mudou de discurso ao longo do mandato? Acompanhou a virada do partido?
   - Compare retórica com ações reais: o discurso combina com o voto em plenário e com o destino das emendas PIX?
   - Sinalize HIPOCRISIAS ou CONTRADIÇÕES: criticou o governo mas direciona emendas para base governista? Pregou austeridade e destinou verba para municípios endividados?
"""

    # Secao de conexao politica
    secao_politica = ""
    if src["conexao_politica"] > 0:
        secao_politica = """
10. **FISIOLOGISMO E ALINHAMENTO MUNICIPAL (TSE x EMENDAS)**:
   - Analise se as emendas foram concentradas em prefeituras governadas pelo MESMO PARTIDO do deputado ou da sua coligacao.
   - Identifique indicios de apadrinhamento politico ou favorecimento partidario local em repasses de emendas PIX.
"""

    # Secao de emendas discricionarias
    secao_discricionaria = ""
    if src["emendas_discricionarias"] > 0:
        secao_discricionaria = """
11. **EMENDAS DISCRICIONARIAS**: Compare com as emendas Pix:
    - Volume e valores das transferencias convencionais vs. Pix
    - Status de execucao (empenhado, liquidado, pago)
    - Se ha sobreposicao com municipios ja receptores de emendas Pix
"""

    # Secao de compras publicas
    secao_compras = ""
    if src["compras"] > 0:
        secao_compras = """
12. **COMPRAS PUBLICAS**: Analise nos municipios receptores:
    - Volume de licitacoes e contratos nos municipos que receberam emendas
    - Valor total de compras e orgaos mais ativos
    - Possiveis irregularidades ou concentracao suspeita
"""

    # Secao de indicadores sociais
    secao_indicadores = ""
    if src["indicadores_sociais"] > 0 or src["indicadores_municipais"] > 0:
        secao_indicadores = """
13. **INDICADORES SOCIAIS DOS MUNICIPIOS**: Analise:
    - Saude: quantidade de leitos, hospitais, UBS, profissionais
    - Educacao: IDEB (iniciais/finais), taxa de aprovacao, matriculas
    - Correlacao entre investimento (emendas) e melhoria dos indicadores
"""

    # Secao de risco judicial
    secao_risco = ""
    if src["risco_judicial"] > 0:
        secao_risco = """
14. **RISCO JUDICIAL**: Verifique processos judiciais nos municipios:
    - Quantidade e tipos de processos vinculados a beneficiarios
    - Se ha processos que sugerem fraude ou mau uso de recursos
    - Correlacao com emendas direcionadas
"""

    # Secao de dados demograficos e financeiros
    secao_demografia = ""
    if src["demografia"] > 0 or src["financeiro"] > 0:
        secao_demografia = """
15. **CONTEXTO DEMOGRAFICO E FINANCEIRO**: Analise:
    - Populacao, PIB per capita e IDHM dos municipios receptores
    - Receita orcamentaria, despesas e divida passiva
    - Se emendas sao proporcionais ao tamanho e necessidade do municipio
    - Fontes de receita (FPM, ICMS, ISS) e dependencia de transferencias
"""

    # Secao de rede politica local (prefeitos + vereadores + senadores)
    secao_rede = ""
    if src["prefeitos"] > 0 or src["vereadores"] > 0 or src["senadores"] > 0:
        secao_rede = """
16. **REDE POLITICA LOCAL**: Mapeie conexoes:
    - Prefeitos eleitos nos municipios receptores (partido, coligacao)
    - Vereadores eleitos do mesmo partido do deputado (base aliada local)
    - Senadores em exercicio no estado (conexoes federais)
    - Padroes de apadrinhamento ou indicacao de candidatos
"""

    # Secao de FNDE
    secao_fnde = ""
    if src["fnde"] > 0:
        secao_fnde = """
17. **REPASSES FNDE**: Cruze com emendas:
    - Programas educacionais (FUNDEB, PNAE, PNLD) nos municipios
    - Volume de repasses vs. emendas parlamentares
    - Se ha sobreposicao de investimento federal no mesmo municipio
"""

    # Secao de beneficiarios
    secao_benef = ""
    if src["beneficiarios"] > 0:
        secao_benef = """
18. **BENEFICIARIOS DIRETOS**: Analise:
    - Perfil dos beneficiarios (CNPJ, razao social, situacao cadastral)
    - Entidades que recebem múltiplas emendas
    - Possiveis conflitos de interesse ou entidades com pouco historico
"""

    contexto_str = "\n".join(f"  - {c}" for c in context_list)
    fontes_str = ", ".join(f"{k}: {v}" for k, v in src.items() if v > 0)

    return f"""Você é um Analista Investigativo Sênior especializado em Contas Públicas, Inteligência Financeira e Ciência Política.
Sua missão é realizar uma autópsia política e fiscal detalhada do mandato do deputado federal {deputado_nome}, utilizando os dados empíricos fornecidos.

Você tem acesso a dados ricos cruzados do TCU, SICONFI, TSE, Portal da Transparência, IBGE e Diário Oficial. Não faça resumos superficiais; faça uma SÍNTESE INVESTIGATIVA PROFUNDA.

=== DADOS DE CONTEXTO ({len(context_list)} fontes cruzadas: {fontes_str}) ===
{contexto_str}
=====================================================

DIRETRIZES DE RACIOCÍNIO (Chain of Thought):
1. Avalie discrepâncias: O que ele fala (votos e projetos) bate com o que ele financia (emendas)?
2. Siga o dinheiro: Há concentração anormal de repasses (emendas PIX/Discricionárias) em redutos eleitorais específicos ou municípios com prefeitos aliados?
3. Impacto vs Gasto: O município destino possui indicadores sociais (IDEB/IDHM) ou saúde condizentes com a verba, ou as compras públicas sugerem uso eleitoreiro?
4. Risco e Compliance: Existem alertas do Diário Oficial ou processos judiciais cercando os beneficiários das emendas?

=== ESTRUTURA DO DOSSIÊ (Markdown) ===

0. **CLASSIFICACAO POLITICA**: [GOVERNO | OPOSIÇÃO | INDEPENDENTE | SEM DADOS]
   - *Fundamentação:* Baseada nos votos nominais, dissenso partidário e pragmatismo no direcionamento das emendas.

1. **PERFIL BIO-POLÍTICO**: (Breve resumo do estado, partido, escolaridade, e alinhamento histórico)

2. **ÁREAS TEMÁTICAS PRIORITÁRIAS**:
   - Ordene por volume real de capital alocado (Emendas PIX + Discricionárias), não apenas por volume de projetos de lei. Compare retórica legislativa vs execução orçamentária.

3. **CRUZAMENTO DE DADOS (O Pragmatismo Político)**:
   - *Exemplo de insight desejado:* "O deputado votou sistematicamente contra pautas sociais do governo no plenário, mas destinou 60% de suas emendas PIX para prefeituras do partido do governo em seu estado." (Aplique isso aos dados reais).

4. **ALINHAMENTO POLÍTICO E DISSENSO NO PLENÁRIO**:
   - Analise os padrões de voto, destacando pautas em que ele traiu a orientação do próprio partido (dissenso).

5. **ANOMALIAS E FISIOLOGISMO (RED FLAGS)**:
   - Identifique concentração extrema de emendas em prefeituras diminutas (feudos eleitorais).
   - Aponte anomalias financeiras (ex: município com orçamento de R$ 20M recebendo R$ 15M em PIX).
   - Sinalize beneficiários (CNPJs/Prefeituras) com alto risco judicial associado.
{secao_votos}{secao_emendas}{secao_props}{secao_discursos}{secao_politica}{secao_discricionaria}{secao_compras}{secao_indicadores}{secao_risco}{secao_demografia}{secao_rede}{secao_fnde}{secao_benef}

INSTRUÇÕES FINAIS E DE TOM:
- Use um tom analítico, frio, investigativo e imparcial (padrão agência de inteligência financeira).
- SEMPRE embase suas afirmações citando os valores (R$) e os dados do contexto.
- NUNCA alucine ou invente informações fora do contexto. Se um dado ou seção inteira não tiver subsídios nos chunks, escreva "N/I (Não Identificado nos dados atuais)".
- Mantenha a saída EXCLUSIVAMENTE em Markdown limpo.
"""


# ---------------------------------------------------------------------------
# Geracao + persistencia
# ---------------------------------------------------------------------------


def _save_persona(
    deputado_id: int,
    query_text: str,
    contexto_rag: str,
    analise: str,
    fontes_usadas: list[str],
    duracao: float,
    conn=None,
    *,
    parlamentar_id: int | None = None,
    qualidade_ok: bool | None = None,
    modelo_usado: str = "llama-3.2-3b-instruct:q4_k_m",
    score_qualidade: float = 0.0,
    tipo_politico: str = "deputado",
    politico_id: int | None = None,
):
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    if qualidade_ok is not None:
        status = "APROVADO" if qualidade_ok else "REPROVADO"
        log.info(
            f"  Qualidade check: {status} | Score: {score_qualidade:.1f}/100 | Modelo: {modelo_usado}"
        )

    try:
        if politico_id is None:
            politico_id = deputado_id
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parlamentares_personas
                    (deputado_id, query_text, contexto_rag, analise_gerada,
                     fontes_usadas, versao_prompt, duracao_segundos, qualidade_ok,
                     modelo_usado, score_qualidade, parlamentar_id,
                     tipo_politico, politico_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tipo_politico, politico_id, versao_prompt) DO UPDATE SET
                    analise_gerada = EXCLUDED.analise_gerada,
                    contexto_rag = EXCLUDED.contexto_rag,
                    fontes_usadas = EXCLUDED.fontes_usadas,
                    data_analise = NOW(),
                    duracao_segundos = EXCLUDED.duracao_segundos,
                    query_text = EXCLUDED.query_text,
                    qualidade_ok = EXCLUDED.qualidade_ok,
                    modelo_usado = EXCLUDED.modelo_usado,
                    score_qualidade = EXCLUDED.score_qualidade,
                    parlamentar_id = EXCLUDED.parlamentar_id
            """,
                (
                    deputado_id if tipo_politico == "deputado" else None,
                    query_text,
                    contexto_rag,
                    analise,
                    fontes_usadas,
                    RAG_PERSONA_VERSION,
                    duracao,
                    qualidade_ok,
                    modelo_usado,
                    score_qualidade,
                    parlamentar_id,
                    tipo_politico,
                    politico_id,
                ),
            )
            conn.commit()
    except Exception as e:
        log.error(
            f"Erro ao salvar persona para {tipo_politico} {politico_id}: {e}"
        )
        conn.rollback()
    finally:
        if should_close:
            conn.close()


def _extract_fontes(context_list: list[str]) -> list[str]:
    """Extrai lista de fontes usadas a partir dos prefixes [TYPE] (todos os 19 tipos)."""
    _PREFIX_MAP: dict[str, str] = {
        "[VOTO]": "voto",
        "[EMENDA]": "emenda",
        "[PROPOSICAO]": "proposicao",
        "[DIARIO_OFICIAL]": "diario_oficial",
        "[PERFIL]": "perfil",
        "[CONEXAO_POLITICA]": "conexao_politica",
        "[EMENDA_DISCRICIONARIA]": "emenda_discricionaria",
        "[COMPRAS_MUNICIPIO]": "compras_municipio",
        "[INDICADORES_SOCIAIS]": "indicadores_sociais",
        "[INDICADORES_MUNICIPAL]": "indicadores_municipal",
        "[RISCO_JUDICIAL]": "risco_judicial",
        "[DEMOGRAFIA_MUNICIPIO]": "demografia_municipio",
        "[MUNICIPIO_FINANCEIRO]": "municipio_financeiro",
        "[PARLAMENTAR_RESUMO]": "parlamentar_resumo",
        "[BENEFICIARIO]": "beneficiario",
        "[PREFEITO]": "prefeito",
        "[SENADOR]": "senador",
        "[FNDE_REPASSES]": "fnde_repasses",
        "[VEREADORES_RESUMO]": "vereadores_resumo",
        "[DISCURSO_PLENARIO]": "discurso_plenario",
    }
    fontes: list[str] = []
    for c in context_list:
        for prefix, tag in _PREFIX_MAP.items():
            if c.startswith(prefix):
                if tag not in fontes:
                    fontes.append(tag)
                break
    return fontes


def generate_persona_analysis(
    deputado_id: int,
    nome: str,
    query: str | None = None,
    use_preparer: bool | None = None,
    tipo_politico: str = "deputado",
) -> tuple[str, float, list[str], list[str], bool | None]:
    """Gera dossier comportamental via pipeline multi-analista RAG v8.

    Cada seção do dossier é gerada por um analista especialista independente,
    com prompt focado e quality check próprio. O score global é a média
    ponderada dos scores individuais.

    Args:
        deputado_id: ID do político no cargo (politico_id no Qdrant).
        tipo_politico: Cargo (deputado/senador/governador/prefeito/vereador).

    Returns:
        (analise_text, duracao_segundos, fontes_usadas, context_list, qualidade_ok)
        context_list e retornado para reutilizacao (elimina busca duplicada).
    """
    from config.settings import RAG_MIN_CHUNKS_BY_TIPO

    min_chunks = RAG_MIN_CHUNKS_BY_TIPO.get(tipo_politico, RAG_MIN_CHUNKS)
    inicio_total = time.time()

    # 1. Recuperacao multi-query (chamada unica)
    log.info(
        f"Recuperando contexto multi-query para {nome} "
        f"({tipo_politico} ID: {deputado_id})..."
    )
    context_list, _scored = search_context_multiquery(
        deputado_id, tipo_politico=tipo_politico
    )

    if len(context_list) < min_chunks:
        msg = (
            f"Dados insuficientes para {nome}: apenas {len(context_list)} chunks "
            f"(minimo: {min_chunks}). Indexe mais dados com cron-qdrant."
        )
        log.warning(msg)
        return msg, 0.0, [], context_list, None

    # Log da distribuicao de chunks por tipo
    from src.analysts.router import count_chunks_by_type

    tipo_counts = count_chunks_by_type(context_list)
    log.info(f"Distribuicao de chunks para {nome}: {len(context_list)} total")
    for tipo, count in sorted(tipo_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            log.info(f"  [{tipo}]: {count}")

    # 2. Executar pipeline multi-analista
    # Usa RAG_LLM_MODEL (que pode ser override via CLI em main())
    results = run_analyst_pipeline(
        deputado_id=deputado_id,
        nome=nome,
        context_list=context_list,
        llm_model=RAG_LLM_MODEL,
        use_preparer=use_preparer,
        tipo_politico=tipo_politico,
    )

    if not results:
        log.error(f"Nenhum analista conseguiu gerar dados para {nome}.")
        duracao_total = time.time() - inicio_total
        return (
            "Falha na geracao: nenhum analista ativo para os dados disponiveis.",
            duracao_total,
            [],
            context_list,
            None,
        )

    # 3. Montar dossier final
    analise = assemble_dossier(results)

    # 4. Calcular score global
    score_global, qualidade_ok = calculate_global_score(results)
    # Expor para consumidores (dossier_bench) sem mudar a assinatura.
    LAST_RUN_SCORE["global"] = score_global
    LAST_RUN_SCORE["analistas"] = {
        r.analyst_id: (round(r.quality_score, 1), r.quality_ok) for r in results
    }
    duracao_total = time.time() - inicio_total

    log.info(
        f"Dossier multi-analista para {nome} gerado em {duracao_total:.1f}s "
        f"({len(results)} analistas, score: {score_global}/100, "
        f"{'APROVADO' if qualidade_ok else 'REPROVADO'})"
    )

    # Log por analista
    for r in results:
        status = "OK" if r.quality_ok else "FAIL"
        log.info(
            f"  [{r.analyst_id}] {r.section_title}: {status} "
            f"(score: {r.quality_score:.1f}, {r.duration:.1f}s, "
            f"{len(r.content)} chars)"
        )

    # 5. Extrair fontes usadas
    fontes = _extract_fontes(context_list)

    return analise, duracao_total, fontes, context_list, qualidade_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    global RAG_LLM_MODEL
    parser = argparse.ArgumentParser(
        description="Gera dossies comportamentais via RAG v8 (multi-query + RRF, multi-cargo)"
    )
    parser.add_argument("--nome", type=str, help="Nome do deputado")
    parser.add_argument(
        "--query",
        type=str,
        help="Query customizada (override das 12 tematicas)",
    )
    parser.add_argument(
        "--lote",
        type=int,
        help="Gerar para N deputados sem persona (v3)",
    )
    parser.add_argument(
        "--regerar",
        action="store_true",
        help="Regenerar mesmo se ja existir",
    )
    parser.add_argument(
        "--modelo",
        type=str,
        default="Qwen2.5-Coder-7B-Instruct-GGUF",
        help="Modelo LLM para persona (padrão: llama-3.2-3b-instruct:q4_k_m)",
    )
    parser.add_argument(
        "--tipo",
        type=str,
        default="deputado",
        choices=("deputado", "senador", "governador", "prefeito", "vereador"),
        help="Cargo do político (default: deputado)",
    )
    parser.add_argument(
        "--politico-id",
        type=int,
        default=None,
        help="ID do político no cargo (senador_codigo, municipio_id, uf-hash p/ governador, sq_candidato)",
    )
    args = parser.parse_args()

    # Override do modelo via CLI
    if args.modelo:
        import config.settings as _s

        _s.RAG_LLM_MODEL = args.modelo
        RAG_LLM_MODEL = args.modelo

    # --- Modo lote ---
    if args.lote:
        _run_lote(args.lote, args.query, args.regerar, tipo_politico=args.tipo)
        return

    # --- Modo single ---
    if not args.nome:
        parser.print_help()
        return

    # Descobrir político (multi-cargo Fase 3)
    if args.tipo == "deputado":
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT deputado_id, nome, parlamentar_id FROM parlamentares_dados WHERE nome ILIKE %s LIMIT 1",
                (f"%{args.nome}%",),
            )
            result = cur.fetchone()
        if not result:
            log.error(f"Deputado '{args.nome}' nao encontrado no banco.")
            return
        dep_id, nome_real, parl_id = result
    else:
        dep_id, nome_real, parl_id = _find_politico_por_tipo(args.tipo, args.nome, args.politico_id)
        if dep_id is None:
            log.error(f"{args.tipo} '{args.nome}' nao encontrado no banco.")
            return

    log.info(f"Gerando dossier para: {nome_real} ({args.tipo} ID: {dep_id})")

    # 1.1: chamada unica que retorna context_list junto com a analise
    analise, duracao, fontes, context_list, qualidade_ok = generate_persona_analysis(
        dep_id, nome_real or str(dep_id), args.query, tipo_politico=args.tipo
    )

    # Output
    print("\n" + "=" * 80)
    print(f" DOSSIE COMPORTAMENTAL v{RAG_PERSONA_VERSION}: {nome_real} ".center(80, "="))
    fontes_str: str = ", ".join(fontes) if fontes else "nenhuma"
    qual_str = "APROVADO" if qualidade_ok else "PENDENTE"
    print(f" Fontes: {fontes_str} | Qualidade: {qual_str} ".center(80, "-"))
    print("=" * 80 + "\n")
    print(analise)
    print("\n" + "=" * 80 + "\n")

    # 1.1: REUTILIZAR context_list (sem segunda busca no Qdrant)
    if not analise.startswith("Dados insuficientes") and not analise.startswith("Erro"):
        score = score_qualidade_eval(analise)
        modelo = args.modelo or RAG_LLM_MODEL
        _save_persona(
            dep_id,
            args.query or "Analise comportamental multi-query v3",
            "\n".join(context_list),
            analise,
            fontes,
            duracao,
            parlamentar_id=parl_id,
            qualidade_ok=qualidade_ok,
            modelo_usado=modelo,
            score_qualidade=score,
            tipo_politico=args.tipo,
        )
        log.info(f"Dossier salvo no banco (v{RAG_PERSONA_VERSION}). Score: {score:.1f}/100")
        _mark_dossie_checkpoint(args.tipo, dep_id, ok=bool(qualidade_ok))


def _generate_with_retry(
    deputado_id: int,
    nome: str,
    query: str | None = None,
    use_preparer: bool | None = None,
    tipo_politico: str = "deputado",
) -> tuple[str, float, list[str], list[str], bool | None]:
    """Gera persona com retry + fallback para uso em lote."""
    return generate_persona_analysis(
        deputado_id,
        nome,
        query,
        use_preparer=use_preparer,
        tipo_politico=tipo_politico,
    )


# ---------------------------------------------------------------------------
# Checkpoint de dossiês (dossie_checkpoint) — Fase 4
# ---------------------------------------------------------------------------


def _find_politico_por_tipo(
    tipo_politico: str, nome: str, politico_id: int | None
) -> tuple[int | None, str | None, int | None]:
    """Localiza (politico_id, nome, parlamentar_id) de um cargo não-deputado."""
    with get_connection() as conn, conn.cursor() as cur:
        if tipo_politico == "senador":
            if politico_id:
                cur.execute(
                    "SELECT senador_codigo, nome_completo FROM senadores_dados WHERE senador_codigo = %s",
                    (politico_id,),
                )
            else:
                cur.execute(
                    "SELECT senador_codigo, nome_completo FROM senadores_dados "
                    "WHERE nome_completo ILIKE %s OR nome_parlamentar ILIKE %s LIMIT 1",
                    (f"%{nome}%", f"%{nome}%"),
                )
            row = cur.fetchone()
            return (int(row[0]), row[1], None) if row else (None, None, None)
        if tipo_politico == "governador":
            cur.execute(
                "SELECT -abs(hashtext(uf)), nome_governador FROM governadores_dados "
                "WHERE nome_governador ILIKE %s OR uf ILIKE %s LIMIT 1",
                (f"%{nome}%", f"%{nome}%"),
            )
            row = cur.fetchone()
            return (int(row[0]), row[1], None) if row else (None, None, None)
        if tipo_politico == "prefeito":
            if politico_id:
                cur.execute(
                    "SELECT municipio_id, prefeito_nome FROM prefeitos_dados WHERE municipio_id = %s",
                    (politico_id,),
                )
            else:
                cur.execute(
                    "SELECT municipio_id, prefeito_nome FROM prefeitos_dados "
                    "WHERE prefeito_nome ILIKE %s LIMIT 1",
                    (f"%{nome}%",),
                )
            row = cur.fetchone()
            return (int(row[0]), row[1], None) if row else (None, None, None)
        # vereador
        if politico_id:
            cur.execute(
                "SELECT sq_candidato, nome_completo FROM vereadores_dados WHERE sq_candidato = %s",
                (politico_id,),
            )
        else:
            cur.execute(
                "SELECT sq_candidato, nome_completo FROM vereadores_dados "
                "WHERE nome_completo ILIKE %s OR nome_urna ILIKE %s LIMIT 1",
                (f"%{nome}%", f"%{nome}%"),
            )
        row = cur.fetchone()
        return (int(row[0]), row[1], None) if row else (None, None, None)


def _ensure_dossie_checkpoint_table() -> None:
    """Cria a tabela de checkpoint de dossiês (idempotente)."""
    from src.db_utils import get_connection as _gc

    conn = _gc()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS dossie_checkpoint (
                    tipo        VARCHAR(20)   NOT NULL,
                    politico_id INTEGER       NOT NULL,
                    versao      INTEGER       NOT NULL DEFAULT 8,
                    status      VARCHAR(10)   NOT NULL DEFAULT 'pendente'
                                CHECK (status IN ('ok', 'fail', 'pendente')),
                    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tipo, politico_id, versao)
                )
                """
            )
            conn.commit()
    finally:
        conn.close()


def _mark_dossie_checkpoint(tipo: str, politico_id: int, ok: bool) -> None:
    """Registra status do dossiê no checkpoint (ok/fail)."""
    from src.db_utils import get_connection as _gc

    conn = _gc()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dossie_checkpoint (tipo, politico_id, versao, status, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (tipo, politico_id, versao) DO UPDATE SET
                    status = EXCLUDED.status, updated_at = NOW()
                """,
                (tipo, politico_id, RAG_PERSONA_VERSION, "ok" if ok else "fail"),
            )
            conn.commit()
    finally:
        conn.close()


def _get_fila_por_tipo(
    tipo_politico: str, lote: int, regenerar: bool
) -> list[tuple[int, str, int | None]]:
    """Fila de políticos de um cargo (não-deputado) sem dossier v8.

    Retorna [(politico_id, nome, parlamentar_id)].
    """
    with get_connection() as conn, conn.cursor() as cur:
        if tipo_politico == "senador":
            cur.execute(
                """
                SELECT s.senador_codigo, s.nome_completo, NULL::int
                FROM senadores_dados s
                WHERE %s = TRUE
                   OR NOT EXISTS (
                       SELECT 1 FROM dossie_checkpoint dc
                       WHERE dc.tipo = 'senador' AND dc.politico_id = s.senador_codigo
                         AND dc.versao = %s AND dc.status = 'ok'
                   )
                ORDER BY s.senador_codigo
                LIMIT %s
                """,
                (regenerar, RAG_PERSONA_VERSION, lote),
            )
        elif tipo_politico == "governador":
            # governadores_dados não tem id numérico — uf é a chave.
            # politico_id = -abs(hashtext(uf)): inteiro negativo ESTÁVEL por UF
            # (consistente com o indexador e o filtro do Qdrant).
            cur.execute(
                """
                SELECT -abs(hashtext(g.uf)), g.nome_governador, NULL::int
                FROM governadores_dados g
                WHERE %s = TRUE
                   OR NOT EXISTS (
                       SELECT 1 FROM dossie_checkpoint dc
                       WHERE dc.tipo = 'governador' AND dc.politico_id = -abs(hashtext(g.uf))
                         AND dc.versao = %s AND dc.status = 'ok'
                   )
                ORDER BY g.uf
                LIMIT %s
                """,
                (regenerar, RAG_PERSONA_VERSION, lote),
            )
        elif tipo_politico == "prefeito":
            cur.execute(
                """
                SELECT p.municipio_id, p.prefeito_nome, NULL::int
                FROM prefeitos_dados p
                WHERE %s = TRUE
                   OR NOT EXISTS (
                       SELECT 1 FROM dossie_checkpoint dc
                       WHERE dc.tipo = 'prefeito' AND dc.politico_id = p.municipio_id
                         AND dc.versao = %s AND dc.status = 'ok'
                   )
                ORDER BY p.municipio_id
                LIMIT %s
                """,
                (regenerar, RAG_PERSONA_VERSION, lote),
            )
        else:  # vereador
            cur.execute(
                """
                SELECT v.sq_candidato, v.nome_completo, NULL::int
                FROM vereadores_dados v
                WHERE %s = TRUE
                   OR NOT EXISTS (
                       SELECT 1 FROM dossie_checkpoint dc
                       WHERE dc.tipo = 'vereador' AND dc.politico_id = v.sq_candidato
                         AND dc.versao = %s AND dc.status = 'ok'
                   )
                ORDER BY v.sq_candidato
                LIMIT %s
                """,
                (regenerar, RAG_PERSONA_VERSION, lote),
            )
        rows = cur.fetchall()
    return [(int(r[0]), str(r[1]), r[2]) for r in rows]


def _run_lote(
    lote: int,
    query: str | None,
    regenerar: bool,
    tipo_politico: str = "deputado",
) -> None:
    """Gera personas em lote para políticos sem persona v8 (com checkpoint)."""
    # Checkpoint de retomada (dossie_checkpoint): fila priorizada por cargo
    _ensure_dossie_checkpoint_table()

    if tipo_politico == "deputado":
        with get_connection() as conn, conn.cursor() as cur:
            if regenerar:
                cur.execute(
                    "SELECT deputado_id, nome, parlamentar_id FROM parlamentares_dados ORDER BY deputado_id LIMIT %s",
                    (lote,),
                )
            else:
                cur.execute(
                    """
                    SELECT pd.deputado_id, COALESCE(NULLIF(pd.nome, ''), pd.nome_urna) AS nome, pd.parlamentar_id
                    FROM parlamentares_dados pd
                    LEFT JOIN dossie_checkpoint dc
                        ON dc.tipo = 'deputado' AND dc.politico_id = pd.deputado_id
                        AND dc.versao = %s
                    WHERE dc.politico_id IS NULL OR dc.status = 'fail'
                    ORDER BY
                        (SELECT COUNT(*)
                         FROM parlamentar_alertas pa
                         WHERE pa.parlamentar_nome IN (pd.nome, pd.nome_urna)
                        ) DESC,
                        (SELECT COUNT(*)
                         FROM votos_camara vc
                         WHERE vc.deputado_id = pd.deputado_id
                        ) DESC,
                        (SELECT COUNT(*)
                         FROM planos_acao pa2
                         JOIN parlamentares p ON pa2.parlamentar_id = p.parlamentar_id
                         JOIN parlamentares_dados pd2 ON pd2.parlamentar_id = p.parlamentar_id
                         WHERE pd2.deputado_id = pd.deputado_id
                         ) DESC,
                        pd.deputado_id ASC
                    LIMIT %s
                """,
                    (
                        RAG_PERSONA_VERSION,
                        lote,
                    ),
                )
            politicos = cur.fetchall()
        politicos = [(r[0], r[1], r[2]) for r in politicos]
    else:
        # Cargos não-deputado: fila própria por tabela
        politicos = _get_fila_por_tipo(tipo_politico, lote, regenerar)

    if not politicos:
        log.info(f"Nenhum político do tipo '{tipo_politico}' aguardando geracao de dossier.")
        return

    log.info(f"Lote: {len(politicos)} {tipo_politico}(s) para processar.")

    # model_scope mantém o modelo carregado durante todo o lote
    # e libera automaticamente no final, com refcount tracking.
    # Como este pin impede o modelo do PREPARER (LARGE) de caber, os
    # workers passam use_preparer=False (chunks crus, sem stall de VRAM).
    model_ctx = localai_manager.model_scope(RAG_LLM_MODEL)
    model_ctx.__enter__()
    _model_ctx_active = True

    def _process_one(
        dep_id: int, nome_real: str, parl_id: int | None
    ) -> tuple[str, int, int, float, list[str]] | None:
        """Worker: gera e salva persona para um político (thread-safe)."""
        try:
            # No lote, o model_scope externo prende o modelo de análise
            # (RAG_LLM_MODEL) durante todo o batch — o modelo do PREPARER
            # (zero-gemma, LARGE) nunca cabe na GPU ao lado dele. Em vez de
            # esperar o timeout de VRAM a cada analista, pula o preparer
            # (analistas usam chunks crus diretamente, sem stall).
            analise, duracao, fontes, context_list, qualidade_ok = _generate_with_retry(
                dep_id, nome_real, query, use_preparer=False, tipo_politico=tipo_politico
            )
            if analise.startswith("Dados insuficientes") or analise.startswith("Erro"):
                log.warning(f"  -> {analise[:80]}")
                return None

            score = score_qualidade_eval(analise)
            worker_conn = get_connection()
            try:
                _save_persona(
                    dep_id,
                    query or "Analise comportamental multi-query v3",
                    "\n".join(context_list),
                    analise,
                    fontes,
                    duracao,
                    conn=worker_conn,
                    parlamentar_id=parl_id,
                    qualidade_ok=qualidade_ok,
                    modelo_usado=RAG_LLM_MODEL,
                    score_qualidade=score,
                    tipo_politico=tipo_politico,
                )
            finally:
                worker_conn.close()

            # Checkpoint de retomada (status ok/fail)
            _mark_dossie_checkpoint(
                tipo_politico,
                dep_id,
                ok=bool(qualidade_ok),
            )
            return (nome_real, dep_id, len(analise), duracao, fontes)
        except Exception as e:
            log.error(f"Erro ao processar {nome_real} (ID: {dep_id}): {e}")
            return None

    # 1.5: Paralelismo com 1 worker — dossiers EM SÉRIE.
    # Antes (max_workers=2): 2 dossiers × max_workers=3 do pipeline = até 6
    # chamadas LLM simultâneas no LocalAI (GPU 6GB, llama 3.4GB) → timeouts e
    # 500 persistentes (AIRTON/AGUINALDO/ALCEU do lote 2026-07-31 tiveram
    # analistas com "Falha na geracao: timed out" mesmo após 3 retries).
    # Serial, o pico cai para 3 (só o pipeline), que já validado no E2E single.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future_map = {
            executor.submit(_process_one, dep_id, nome_real, parl_id): (dep_id, nome_real)
            for dep_id, nome_real, parl_id in politicos
        }

        concluidos = 0
        for future in concurrent.futures.as_completed(future_map):
            dep_id, nome_real = future_map[future]
            concluidos += 1
            try:
                result = future.result()
                if result:
                    nome_r, _, n_chars, dur, fnts = result
                    log.info(
                        f"[{concluidos}/{len(politicos)}] {nome_r}: "
                        f"{n_chars} chars, {dur:.1f}s, fontes: {', '.join(fnts)}"
                    )
                else:
                    log.warning(f"[{concluidos}/{len(politicos)}] {nome_real}: skipped")
            except Exception as e:
                log.error(f"[{concluidos}/{len(politicos)}] {nome_real}: erro fatal: {e}")

    log.info(f"Lote concluido: {concluidos}/{len(politicos)} {tipo_politico}(s) processados.")

    # Liberar modelo no final do lote
    if _model_ctx_active:
        try:
            model_ctx.__exit__(None, None, None)
        except Exception:
            pass


if __name__ == "__main__":
    main()
