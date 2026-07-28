"""
Modulo RAG v3: Geracao de Personas/Dossies de Deputados.

Melhorias v3 (risp. v2):
  - Multi-query RAG (5 queries tematicas, batch embedding)
  - Reciprocal Rank Fusion (RRF) para re-ranking de chunks
  - Dedup via MD5 (nao por prefixo) para evitar falsos positivos
  - Validacao de tamanho do prompt (janela de contexto ~8K)
  - Quality check: validacao de secoes obrigatorias na analise
  - QdrantClient reutilizado por lote (nao 1 por query)
  - ensure_model_loaded() chamado 1x por lote (nao 6x por deputado)
  - ThreadPoolExecutor para processamento paralelo em lote
  - Context_list retornado por generate (elimina busca duplicada)

Fluxo:
  1. search_context_multiquery() -> batch embed + RRF -> chunks do Qdrant
  2. build_analysis_prompt() -> prompt adaptativo baseado nos tipos de dados
  3. _validate_prompt_size() -> trunca chunks se prompt exceder contexto
  4. generate_persona_analysis() -> LLM gera dossier
  5. _check_quality() -> valida secoes obrigatorias
  6. _save_persona() -> salva no DB com contexto_rag + fontes_usadas

Uso:
    ./run.sh cron-dossie --nome "Afonso Florence"
    ./run.sh cron-dossie --lote 50
    python3 -m src.enrichers.rag_persona --nome "Afonso Florence" --regerar
"""

import argparse
import concurrent.futures
import hashlib
import logging
import time

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from config.settings import (
    EMBEDDER_MODEL,
    QDRANT_COLLECTION,
    QDRANT_URL,
    RAG_LLM_MODEL,
    RAG_MAX_CHUNKS,
    RAG_MIN_CHUNKS,
    RAG_PERSONA_VERSION,
)
from src.db_utils import get_connection
from src.enrichers.rag_qdrant_indexer import embed_text_batch
from src.localai_client import LocalAIClient
from src.localai_manager import manager as localai_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes para RRF e validacao de prompt
# ---------------------------------------------------------------------------

RRF_K = 60  # Constante de suavizacao do Reciprocal Rank Fusion
RAG_TOKEN_CHARS = 4  # Estimativa: ~4 caracteres por token
RAG_MAX_TOKENS = 7000  # Limite de tokens para gemma-4-e2b-it (janela 8K - margem)
EMBEDDING_DIM = 768  # Dimensao do nomic-embed-text-v1.5

# ---------------------------------------------------------------------------
# Multi-Query RAG -- 5 queries tematicas (incluindo TSE / Conexoes Partidarias)
# ---------------------------------------------------------------------------

QUERIES_TEMATICAS = [
    "Padrao de voto e alinhamento politico do deputado em votacoes nominais no plenario",
    "Emendas parlamentares Pix, municipios beneficiarios e valores transferidos",
    "Proposicoes legislativas apresentadas e areas tematicas de foco",
    "Atos no diario oficial, fiscalizacao, decretos e movimentacoes relevantes",
    "Conexao politica local, partido dos prefeitos beneficiados e alinhamento eleitoral municipal",
]

# Secoes obrigatorias que a analise gerada deve conter
SECOES_OBRIGATORIAS = [
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
) -> list[tuple[str, float]]:
    """Busca chunks relevantes no Qdrant para um deputado e query especifica.

    Args:
        client: QdrantClient reutilizado (None = criar novo).
        query_vector: Vector ja embbedido (None = embbed agora).

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

    # 1.2: Reutilizar client quando fornecido
    should_close = False
    if client is None:
        client = QdrantClient(url=QDRANT_URL)
        should_close = True

    filtro = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="deputado_id",
                match=qdrant_models.MatchValue(value=deputado_id),
            )
        ]
    )

    try:
        hits = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vector,
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


def search_context_multiquery(
    deputado_id: int, top_k_per_query: int = 8
) -> tuple[list[str], list[tuple[str, float]]]:
    """Executa 5 queries tematicas com batch embed, RRF merge + MD5 dedup.

    Returns:
        (context_list, scored_chunks):
        - context_list: textos finais deduplicados e ranqueados por RRF
        - scored_chunks: (texto, rrf_score) para auditoria
    """
    # Embedder (nomic) e CPU-based, nao precisa de exclusividade GPU.
    # LocalAI lazy-load na primeira chamada de embedding.

    # 1.2: reutilizar QdrantClient para todas as 5 queries
    client = QdrantClient(url=QDRANT_URL)

    # 1.3: batch embed das 5 queries em 1 request (nao 5 sequenciais)
    log.info(f"Batch embedding de {len(QUERIES_TEMATICAS)} queries para deputado {deputado_id}...")
    all_vectors = embed_text_batch(QUERIES_TEMATICAS)
    if len(all_vectors) != len(QUERIES_TEMATICAS):
        log.error(
            f"Falha no batch embedding: esperado {len(QUERIES_TEMATICAS)}, "
            f"recebido {len(all_vectors)}"
        )
        client.close()
        return [], []

    # Coletar resultados de todas as queries com score e indice da query
    raw_results: list[tuple[str, float, int]] = []  # (texto, score_qdrant, query_idx)
    for qi, (query_text, vector) in enumerate(zip(QUERIES_TEMATICAS, all_vectors)):
        results = search_context_qdrant(
            deputado_id,
            query_text,
            limit=top_k_per_query,
            client=client,
            query_vector=vector,
        )
        for text, score in results:
            raw_results.append((text, score, qi))
        log.debug(f"  query '{query_text[:40]}...' -> {len(results)} chunks")

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
    for qi, hash_list in per_query_hashes.items():
        for rank, h in enumerate(hash_list):
            rrf_scores[h] = rrf_scores.get(h, 0.0) + 1.0 / (RRF_K + rank + 1)

    # Ordenar por RRF score desc, tomar top N
    deduped.sort(key=lambda x: rrf_scores[x[0]], reverse=True)
    final = [(text, rrf_scores[h]) for h, text, _score, _qi in deduped[:RAG_MAX_CHUNKS]]

    context_list = [text for text, _rrf in final]
    log.info(
        f"Multi-query: {len(raw_results)} brutos -> {len(deduped)} unicos "
        f"-> {len(final)} finais (RRF)"
    )
    return context_list, final


# ---------------------------------------------------------------------------
# Validacao de tamanho do prompt (janela de contexto)
# ---------------------------------------------------------------------------


def _validate_prompt_size(
    prompt: str, context_list: list[str], nome: str
) -> tuple[str, list[str]]:
    """Trunca chunks se prompt exceder janela de contexto do modelo (~8K).

    Estima tokens como len(prompt) / 4. Se exceder RAG_MAX_TOKENS,
    remove chunks ate caber (minimo RAG_MIN_CHUNKS).

    Returns:
        (prompt_rebuild, context_list_trimmed)
    """
    estimated_tokens = len(prompt) // RAG_TOKEN_CHARS
    if estimated_tokens <= RAG_MAX_TOKENS:
        return prompt, context_list

    log.warning(
        f"Prompt excede limite ({estimated_tokens} tokens > {RAG_MAX_TOKENS}), "
        f"reduzindo de {len(context_list)} chunks..."
    )
    trimmed = list(context_list)
    while len(trimmed) > RAG_MIN_CHUNKS:
        trimmed.pop()
        rebuilt = build_analysis_prompt(trimmed, nome)
        if len(rebuilt) // RAG_TOKEN_CHARS <= RAG_MAX_TOKENS:
            prompt = rebuilt
            break
    else:
        # Atingiu RAG_MIN_CHUNKS e ainda excede -- usar o ultimo rebuild
        prompt = build_analysis_prompt(trimmed, nome)

    final_tokens = len(prompt) // RAG_TOKEN_CHARS
    log.warning(
        f"Chunks reduzidos: {len(context_list)} -> {len(trimmed)} "
        f"({final_tokens} tokens estimados)"
    )
    return prompt, trimmed


# ---------------------------------------------------------------------------
# Quality check -- validacao de secoes obrigatorias
# ---------------------------------------------------------------------------


def _check_quality(analise: str) -> bool:
    """Valida se todas as secoes obrigatorias estao presentes na analise.

    Secoes obrigatorias: PERFIL, AREAS TEMATICAS, CRUZAMENTO DE DADOS,
    ALINHAMENTO POLITICO, ANOMALIAS E FISIOLOGISMO.

    Normaliza acentos (unicodedata NFKD) antes de comparar para evitar
    falsos negativos quando o LLM gera headers com acentos (ex: "AREAS TEMATICAS").

    Returns:
        True se todas as obrigatorias estiverem presentes.
    """
    import unicodedata

    # Normalizar: lowercase + remover acentos (NFKD decompose, strip combining)
    normalized = (
        unicodedata.normalize("NFKD", analise)
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
    )
    ausentes = [s for s in SECOES_OBRIGATORIAS if s not in normalized]

    if ausentes:
        log.warning(f"Secoes ausentes na analise: {', '.join(ausentes)}")

    # Contar opcionais presentes (para logging)
    opcional_presentes = sum(1 for s in SECOES_OPCIONAIS if s in normalized)
    log.debug(
        f"  Secoes obrigatorias: {len(SECOES_OBRIGATORIAS) - len(ausentes)}/{len(SECOES_OBRIGATORIAS)}, "
        f"opcionais: {opcional_presentes}/{len(SECOES_OPCIONAIS)}"
    )

    return len(ausentes) == 0


# ---------------------------------------------------------------------------
# Prompt Adaptativo -- adapta secoes baseado nos dados disponiveis
# ---------------------------------------------------------------------------


def _count_sources(context_list: list[str]) -> dict[str, int]:
    """Conta chunks por tipo de fonte."""
    counts = {
        "votos": 0,
        "emendas": 0,
        "proposicoes": 0,
        "diario_oficial": 0,
        "perfil": 0,
        "conexao_politica": 0,
    }
    for c in context_list:
        upper = c.upper()
        if "[VOTO]" in upper:
            counts["votos"] += 1
        elif "[EMENDA]" in upper:
            counts["emendas"] += 1
        elif "[PROPOSICAO]" in upper:
            counts["proposicoes"] += 1
        elif "[DIARIO_OFICIAL]" in upper:
            counts["diario_oficial"] += 1
        elif "[PERFIL]" in upper:
            counts["perfil"] += 1
        elif "[CONEXAO_POLITICA]" in upper:
            counts["conexao_politica"] += 1
    return counts


def build_analysis_prompt(context_list: list[str], deputado_nome: str) -> str:
    """Monta prompt adaptativo baseado na quantidade e tipo de dados."""
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

    # Secao de conexao politica
    secao_politica = ""
    if src["conexao_politica"] > 0:
        secao_politica = """
9. **FISIOLOGISMO E ALINHAMENTO MUNICIPAL (TSE x EMENDAS)**:
   - Analise se as emendas foram concentradas em prefeituras governadas pelo MESMO PARTIDO do deputado ou da sua coligacao.
   - Identifique indicios de apadrinhamento politico ou favorecimento partidario local em repasses de emendas PIX.
"""

    contexto_str = "\n".join(f"  - {c}" for c in context_list)
    fontes_str = ", ".join(f"{k}: {v}" for k, v in src.items() if v > 0)

    return f"""Voce e um Analista Investigativo especializado em Contas Publicas e Ciencia Politica.
Analise o perfil do deputado federal {deputado_nome} com base nos dados reais abaixo.

CONTEXTO ({len(context_list)} fontes: {fontes_str}):
{contexto_str}

INSTRUCOES DE ANALISE (Markdown):

1. **PERFIL**: Nome, partido, UF. Contexto politico (situacao/oposicao).

2. **AREAS TEMATICAS**: Identifique as principais areas de atuacao priorizando
   volume de emendas e proposicoes. Ordene por concentracao de verbas.

3. **CRUZAMENTO DE DADOS**: Conecte votos com emendas e proposicoes.
   Exemplo: "Votou contra PEC da saude mas destinou R$ 2M para hospitais."
   Busque contradicoes e coerencias entre o que o deputado vota, propoe e financia.

4. **ALINHAMENTO POLITICO**: Com base nos votos nominais, estime o grau de
   alinhamento com a base do governo. Identifique momentos de dissenso.

5. **ANOMALIAS E FISIOLOGISMO**: Valores atipicos em emendas, apadrinhamento de prefeitos do mesmo partido,
   entidades pouco transparentes, padroes que merecem investigacao mais profunda.
{secao_votos}{secao_emendas}{secao_props}{secao_politica}

FORMATO: Markdown com titulos, bullet points e dados numericos.
TOM: Firme, critico, fundamentado em dados reais.
NAO invente informacoes ausentes do contexto. Se um dado nao esta disponivel, diga.
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
    qualidade_ok: bool | None = None,
):
    """Salva persona no DB com contexto rastreavel e versionamento.

    Args:
        qualidade_ok: Resultado do quality check (True/False). Logado mas
            nao salvo em coluna propria (requer migration separada).
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    # Log do quality check (coluna nao existe ainda no schema)
    if qualidade_ok is not None:
        status = "APROVADO" if qualidade_ok else "REPROVADO"
        log.info(f"  Qualidade check: {status}")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parlamentares_personas
                    (deputado_id, query_text, contexto_rag, analise_gerada,
                     fontes_usadas, versao_prompt, duracao_segundos)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (deputado_id, versao_prompt) DO UPDATE SET
                    analise_gerada = EXCLUDED.analise_gerada,
                    contexto_rag = EXCLUDED.contexto_rag,
                    fontes_usadas = EXCLUDED.fontes_usadas,
                    data_analise = NOW(),
                    duracao_segundos = EXCLUDED.duracao_segundos,
                    query_text = EXCLUDED.query_text
            """,
                (
                    deputado_id,
                    query_text,
                    contexto_rag,
                    analise,
                    fontes_usadas,
                    RAG_PERSONA_VERSION,
                    duracao,
                ),
            )
            conn.commit()
    except Exception as e:
        log.error(f"Erro ao salvar persona para deputado {deputado_id}: {e}")
        conn.rollback()
    finally:
        if should_close:
            conn.close()


def _extract_fontes(context_list: list[str]) -> list[str]:
    """Extrai lista de fontes usadas a partir dos prefixes [TYPE]."""
    fontes: list[str] = []
    for c in context_list:
        for prefix in ("[VOTO]", "[EMENDA]", "[PROPOSICAO]", "[DIARIO_OFICIAL]", "[PERFIL]"):
            if c.startswith(prefix):
                tag = prefix.strip("[]").lower()
                if tag not in fontes:
                    fontes.append(tag)
    return fontes


def generate_persona_analysis(
    deputado_id: int,
    nome: str,
    query: str | None = None,
) -> tuple[str, float, list[str], list[str]]:
    """Gera dossier comportamental via RAG multi-query + LLM.

    Returns:
        (analise_text, duracao_segundos, fontes_usadas, context_list)
        context_list e retornado para reutilizacao (elimina busca duplicada).
    """
    # 1. Recuperacao multi-query (chamada unica)
    log.info(f"Recuperando contexto multi-query para {nome} (ID: {deputado_id})...")
    context_list, _scored = search_context_multiquery(deputado_id)

    if len(context_list) < RAG_MIN_CHUNKS:
        msg = (
            f"Dados insuficientes para {nome}: apenas {len(context_list)} chunks "
            f"(minimo: {RAG_MIN_CHUNKS}). Indexe mais dados com cron-qdrant."
        )
        log.warning(msg)
        return msg, 0.0, [], context_list

    # 2. Montar prompt adaptativo
    prompt = build_analysis_prompt(context_list, nome)

    # 2.3 Validar tamanho do prompt (janela de contexto)
    prompt, context_list = _validate_prompt_size(prompt, context_list, nome)

    # 3. Gerar com LLM
    llm_model = RAG_LLM_MODEL
    log.info(f"Carregando modelo LLM ({llm_model})...")
    localai_manager.ensure_model_loaded(llm_model)

    ai_client = LocalAIClient(model=llm_model)

    log.info(f"Gerando dossier para {nome} ({len(context_list)} chunks no contexto)...")
    inicio = time.time()
    try:
        resposta = ai_client.chat(
            prompt=prompt,
            system=(
                "Voce e um assistente analitico focado em ciencia politica "
                "e dados empiricos. Analise friamente os dados, sem viés ideologico."
            ),
        )
        duracao = time.time() - inicio
        log.info(f"Geracao concluida em {duracao:.1f}s ({len(resposta)} chars).")
    except Exception as e:
        duracao = time.time() - inicio
        log.error(f"Erro LLM apos {duracao:.1f}s: {e}")
        return f"Erro na geracao: {e}", duracao, [], context_list

    # 2.4 Quality check
    qualidade_ok = _check_quality(resposta)

    # 4. Extrair fontes usadas
    fontes = _extract_fontes(context_list)

    return resposta, duracao, fontes, context_list


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera dossies comportamentais via RAG v3 (multi-query + RRF)"
    )
    parser.add_argument("--nome", type=str, help="Nome do deputado")
    parser.add_argument(
        "--query",
        type=str,
        help="Query customizada (override das 5 tematicas)",
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
        default=None,
        help="Modelo LLM para persona (padrão: llama-3.2-3b-instruct:q4_k_m)",
    )
    args = parser.parse_args()

    # Override do modelo via CLI
    if args.modelo:
        import config.settings as _s
        _s.RAG_LLM_MODEL = args.modelo

    # --- Modo lote ---
    if args.lote:
        _run_lote(args.lote, args.query, args.regerar)
        return

    # --- Modo single ---
    if not args.nome:
        parser.print_help()
        return

    # Descobrir deputado
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT deputado_id, nome FROM parlamentares_dados WHERE nome ILIKE %s LIMIT 1",
            (f"%{args.nome}%",),
        )
        result = cur.fetchone()

    if not result:
        log.error(f"Deputado '{args.nome}' nao encontrado no banco.")
        return

    dep_id, nome_real = result
    log.info(f"Gerando dossier para: {nome_real} (ID: {dep_id})")

    # 1.1: chamada unica que retorna context_list junto com a analise
    analise, duracao, fontes, context_list = generate_persona_analysis(
        dep_id, nome_real, args.query
    )

    # Output
    print("\n" + "=" * 80)
    print(f" DOSSIE COMPORTAMENTAL v3: {nome_real} ".center(80, "="))
    fontes_str: str = ", ".join(fontes) if fontes else "nenhuma"
    print(f" Fontes: {fontes_str} ".center(80, "-"))
    print("=" * 80 + "\n")
    print(analise)
    print("\n" + "=" * 80 + "\n")

    # 1.1: REUTILIZAR context_list (sem segunda busca no Qdrant)
    if not analise.startswith("Dados insuficientes") and not analise.startswith("Erro"):
        _save_persona(
            dep_id,
            args.query or "Analise comportamental multi-query v3",
            "\n".join(context_list),
            analise,
            fontes,
            duracao,
        )
        log.info(f"Dossier salvo no banco (v{RAG_PERSONA_VERSION}).")


def _generate_with_client(
    ai_client: LocalAIClient,
    deputado_id: int,
    nome: str,
    query: str | None = None,
) -> tuple[str, float, list[str], list[str]]:
    """Gera persona usando um client ja existente (sem reload de modelo).

    Returns:
        (analise, duracao, fontes, context_list)
    """
    # Multi-query (1.1: retorna context_list)
    context_list, _scored = search_context_multiquery(deputado_id)
    if len(context_list) < RAG_MIN_CHUNKS:
        return (
            f"Dados insuficientes: {len(context_list)} chunks (minimo {RAG_MIN_CHUNKS})",
            0.0,
            [],
            context_list,
        )

    prompt = build_analysis_prompt(context_list, nome)
    prompt, context_list = _validate_prompt_size(prompt, context_list, nome)

    inicio = time.time()
    try:
        resposta = ai_client.chat(
            prompt=prompt,
            system=(
                "Voce e um assistente analitico focado em ciencia politica "
                "e dados empiricos. Analise friamente os dados, sem viés ideologico."
            ),
        )
        duracao = time.time() - inicio
    except Exception as e:
        duracao = time.time() - inicio
        return f"Erro LLM: {e}", duracao, [], context_list

    qualidade_ok = _check_quality(resposta)

    fontes = _extract_fontes(context_list)
    return resposta, duracao, fontes, context_list


def _run_lote(lote: int, query: str | None, regenerar: bool) -> None:
    """Gera personas em lote para deputados sem persona v3.

    1.5: Processamento paralelo com ThreadPoolExecutor(max_workers=2).
    Cada worker tem propria conexao DB e QdrantClient.
    """
    with get_connection() as conn, conn.cursor() as cur:
        if regenerar:
            cur.execute(
                "SELECT deputado_id, nome FROM parlamentares_dados ORDER BY deputado_id LIMIT %s",
                (lote,),
            )
        else:
            cur.execute(
                """
                SELECT pd.deputado_id, pd.nome
                FROM parlamentares_dados pd
                LEFT JOIN parlamentares_personas pp
                    ON pd.deputado_id = pp.deputado_id
                    AND pp.versao_prompt = %s
                WHERE pp.deputado_id IS NULL
                ORDER BY
                    (SELECT COUNT(*)
                     FROM parlamentar_alertas pa
                     WHERE pa.parlamentar_nome IN (pd.nome, pd.nome_urna)
                    ) DESC,
                    (SELECT COUNT(*)
                     FROM votos_camara vc
                     WHERE vc.deputado_id = pd.deputado_id
                    ) DESC,
                    pd.deputado_id ASC
                LIMIT %s
            """,
                (
                    RAG_PERSONA_VERSION,
                    lote,
                ),
            )
        deputados = cur.fetchall()

    if not deputados:
        log.info("Nenhum deputado aguardando geracao de dossier.")
        return

    log.info(f"Lote: {len(deputados)} deputados para processar.")

    # Garantir exclusividade GPU para o LLM antes do paralelismo.
    # Embedder (nomic) e CPU-based, nao precisa de ensure_model_loaded.
    llm_model = RAG_LLM_MODEL
    localai_manager.ensure_model_loaded(llm_model)

    def _process_one(
        dep_id: int, nome_real: str
    ) -> tuple[str, int, int, float, list[str]] | None:
        """Worker: gera e salva persona para um deputado (thread-safe)."""
        ai_client = LocalAIClient(model=llm_model)
        try:
            analise, duracao, fontes, context_list = _generate_with_client(
                ai_client, dep_id, nome_real, query
            )
            if analise.startswith("Dados insuficientes") or analise.startswith("Erro"):
                log.warning(f"  -> {analise[:80]}")
                return None

            # 1.1: REUTILIZAR context_list (sem segunda busca)
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
                )
            finally:
                worker_conn.close()

            return (nome_real, dep_id, len(analise), duracao, fontes)
        except Exception as e:
            log.error(f"Erro ao processar {nome_real} (ID: {dep_id}): {e}")
            return None

    # 1.5: Paralelismo com 2 workers (evitar VRAM exhaustion)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_map = {
            executor.submit(_process_one, dep_id, nome_real): (dep_id, nome_real)
            for dep_id, nome_real in deputados
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
                        f"[{concluidos}/{len(deputados)}] {nome_r}: "
                        f"{n_chars} chars, {dur:.1f}s, fontes: {', '.join(fnts)}"
                    )
                else:
                    log.warning(
                        f"[{concluidos}/{len(deputados)}] {nome_real}: skipped"
                    )
            except Exception as e:
                log.error(
                    f"[{concluidos}/{len(deputados)}] {nome_real}: erro fatal: {e}"
                )

    log.info(
        f"Lote concluido: {concluidos}/{len(deputados)} deputados processados."
    )


if __name__ == "__main__":
    main()
