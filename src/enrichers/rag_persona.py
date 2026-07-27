"""
Módulo RAG v2: Geração de Personas/Dossiês de Deputados.

Melhorias v2:
  - Multi-query RAG (4 queries temáticas em vez de 1 genérica)
  - Prompt adaptativo por volume de dados disponíveis
  - Contexto rastreável salvo no DB (auditoria)
  - Batch otimizado: modelo carregado 1x por lote
  - Versionamento de personas (versao_prompt)

Fluxo:
  1. search_context_multiquery() → chunks do Qdrant (4 queries × top-k)
  2. build_analysis_prompt() → prompt adaptativo baseado nos tipos de dados
  3. generate_persona_analysis() → LLM gera dossiê
  4. _save_persona() → salva no DB com contexto_rag + fontes_usadas

Uso:
    ./run.sh cron-dossie --nome "Afonso Florence"
    ./run.sh cron-dossie --lote 50
    python3 -m src.enrichers.rag_persona --nome "Afonso Florence" --regerar
"""

import argparse
import logging
import time
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from config.settings import (
    QDRANT_URL,
    QDRANT_COLLECTION,
    EMBEDDER_MODEL,
    EMBEDDING_DIM,
    RAG_LLM_MODEL,
    RAG_PERSONA_VERSION,
    RAG_MIN_CHUNKS,
    RAG_MAX_CHUNKS,
)
from src.db_utils import get_connection
from src.localai_manager import manager as localai_manager
from src.localai_client import LocalAIClient
from src.enrichers.rag_qdrant_indexer import embed_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Multi-Query RAG — 4 queries temáticas
# ---------------------------------------------------------------------------

QUERIES_TEMATICAS = [
    "Padrão de voto e alinhamento político do deputado em votações nominais no plenário",
    "Emendas parlamentares Pix, municípios beneficiários e valores transferidos",
    "Proposições legislativas apresentadas e áreas temáticas de foco",
    "Atos no diário oficial, fiscalização, decretos e movimentações relevantes",
]


def search_context_qdrant(
    deputado_id: int, query_text: str, limit: int = 10
) -> List[str]:
    """Busca chunks relevantes no Qdrant para um deputado e query específica."""
    localai_manager.ensure_model_loaded(EMBEDDER_MODEL)
    query_vector = embed_text(query_text)
    if not query_vector:
        log.error(f"Falha ao embeddar query: '{query_text[:60]}...'")
        return []

    client = QdrantClient(url=QDRANT_URL)
    filtro = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="deputado_id",
                match=qdrant_models.MatchValue(value=deputado_id),
            )
        ]
    )

    hits = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=filtro,
        limit=limit,
    )

    contextos = []
    for hit in hits.points:
        if hit.payload and "text" in hit.payload:
            tipo = hit.payload.get("type", "info").upper()
            contextos.append(f"[{tipo}] {hit.payload['text']}")
    return contextos


def search_context_multiquery(
    deputado_id: int, top_k_per_query: int = 8
) -> List[str]:
    """Executa 4 queries temáticas, merge + dedup, retorna top chunks únicos."""
    all_chunks: List[str] = []
    for q in QUERIES_TEMATICAS:
        chunks = search_context_qdrant(deputado_id, q, limit=top_k_per_query)
        all_chunks.extend(chunks)
        log.debug(f"  query '{q[:40]}...' -> {len(chunks)} chunks")

    # Dedup por prefixo do texto (primeiros 100 chars)
    seen: set[str] = set()
    unique: List[str] = []
    for c in all_chunks:
        key = c[:100]
        if key not in seen:
            seen.add(key)
            unique.append(c)

    result = unique[:RAG_MAX_CHUNKS]
    log.info(
        f"Multi-query: {len(all_chunks)} brutos -> "
        f"{len(unique)} unicos -> {len(result)} finais"
    )
    return result


# ---------------------------------------------------------------------------
# Prompt Adaptativo — adapta seções baseado nos dados disponíveis
# ---------------------------------------------------------------------------

def _count_sources(context_list: List[str]) -> dict:
    """Conta chunks por tipo de fonte."""
    counts = {
        "votos": 0, "emendas": 0, "proposicoes": 0,
        "diario_oficial": 0, "perfil": 0,
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
    return counts


def build_analysis_prompt(context_list: List[str], deputado_nome: str) -> str:
    """Monta prompt adaptativo baseado na quantidade e tipo de dados."""
    src = _count_sources(context_list)

    # Seção de votos — só aparece se houver dados de voto
    secao_votos = ""
    if src["votos"] > 0:
        secao_votos = """
6. **PADRAO DE VOTO**: Analise o alinhamento politico. Identifique:
   - Votos com o governo vs. oposicao (sempre "Sim"/"Nao" em proposicoes)
   - Temas onde divergiu da bancada partidaria (marcar com [DISSENSO])
   - Consistencia entre discurso e voto real
   - Percentual aproximado de alinhamento com a base aliada
"""

    # Seção de emendas
    secao_emendas = ""
    if src["emendas"] > 0:
        secao_emendas = """
7. **EMENDAS PIX**: Mapeie concentracao de verbas. Identifique:
   - Municipios com maiores valores recebidos (e se sao pequenos vs. populosos)
   - Entidades recorrentes ou que aparecem em multiplas emendas
   - Possiveis anomalias: valores muito altos para municipios pequenos
   - Cruzamento com dados financeiros do municipio (se disponiveis no contexto)
"""

    # Seção de proposições
    secao_props = ""
    if src["proposicoes"] > 0:
        secao_props = """
8. **PROPOSICOES LEGISLATIVAS**: Identifique:
   - Areas tematicas prioritarias (saude, seguranca, educacao, etc.)
   - Volume de proposicoes como indicador de produtividade legislativa
   - Coerencia entre proposicoes e emendas (o que propoe vs. onde gasta)
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
   Busque contradies e coerencias entre o que o deputado vota, propoe e financia.

4. **ALINHAMENTO POLITICO**: Com base nos votos nominais, estime o grau de
   alinhamento com a base do governo. Identifique momentos de dissesso.

5. **ANOMALIAS**: Valores atipicos em emendas, entidades pouco transparentes,
   padroes que merecem investigacao mais profunda.
{secao_votos}{secao_emendas}{secao_props}

FORMATO: Markdown com titulos, bullet points e dados numericos.
TOM: Firme, critico, fundamentado em dados reais.
NAO invente informacoes ausentes do contexto. Se um dado nao esta disponivel, diga.
"""


# ---------------------------------------------------------------------------
# Geração + persistência
# ---------------------------------------------------------------------------

def _save_persona(
    deputado_id: int,
    query_text: str,
    contexto_rag: str,
    analise: str,
    fontes_usadas: List[str],
    duracao: float,
    conn=None,
):
    """Salva persona no DB com contexto rastreável e versionamento."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        with conn.cursor() as cur:
            cur.execute("""
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
            """, (
                deputado_id,
                query_text,
                contexto_rag,
                analise,
                fontes_usadas,
                RAG_PERSONA_VERSION,
                duracao,
            ))
            conn.commit()
    except Exception as e:
        log.error(f"Erro ao salvar persona para deputado {deputado_id}: {e}")
        conn.rollback()
    finally:
        if should_close:
            conn.close()


def _extract_fontes(context_list: List[str]) -> List[str]:
    """Extrai lista de fontes usadas a partir dos prefixes [TYPE]."""
    fontes: List[str] = []
    for c in context_list:
        for prefix in ("[VOTO]", "[EMENDA]", "[PROPOSICAO]",
                        "[DIARIO_OFICIAL]", "[PERFIL]"):
            if c.startswith(prefix):
                tag = prefix.strip("[]").lower()
                if tag not in fontes:
                    fontes.append(tag)
    return fontes


def generate_persona_analysis(
    deputado_id: int,
    nome: str,
    query: str | None = None,
) -> Tuple[str, float, List[str]]:
    """Gera dossiê comportamental via RAG multi-query + LLM.

    Returns:
        (analise_text, duracao_segundos, fontes_usadas)
    """
    # 1. Multi-query retrieval
    log.info(f"Recuperando contexto multi-query para {nome} (ID: {deputado_id})...")
    context_list = search_context_multiquery(deputado_id)

    if len(context_list) < RAG_MIN_CHUNKS:
        msg = (
            f"Dados insuficientes para {nome}: apenas {len(context_list)} chunks "
            f"(minimo: {RAG_MIN_CHUNKS}). Indexe mais dados com cron-qdrant."
        )
        log.warning(msg)
        return msg, 0.0, []

    # 2. Montar prompt adaptativo
    prompt = build_analysis_prompt(context_list, nome)
    query_text = query or "Analise comportamental multi-query v2"

    # 3. Gerar com LLM
    llm_model = RAG_LLM_MODEL
    log.info(f"Carregando modelo LLM ({llm_model})...")
    localai_manager.ensure_model_loaded(llm_model)

    ai_client = LocalAIClient(model=llm_model)

    log.info(
        f"Gerando dossier para {nome} ({len(context_list)} chunks no contexto)..."
    )
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
        return f"Erro na geracao: {e}", duracao, []

    # 4. Extrair fontes usadas
    fontes = _extract_fontes(context_list)

    return resposta, duracao, fontes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Gera dossies comportamentais via RAG v2 (multi-query)"
    )
    parser.add_argument("--nome", type=str, help="Nome do deputado")
    parser.add_argument(
        "--query", type=str,
        help="Query customizada (override das 4 tematicas)",
    )
    parser.add_argument(
        "--lote", type=int,
        help="Gerar para N deputados sem persona (v2)",
    )
    parser.add_argument(
        "--regerar", action="store_true",
        help="Regenerar mesmo se ja existir",
    )
    args = parser.parse_args()

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
            "SELECT deputado_id, nome FROM parlamentares_dados "
            "WHERE nome ILIKE %s LIMIT 1",
            (f"%{args.nome}%",),
        )
        result = cur.fetchone()

    if not result:
        log.error(f"Deputado '{args.nome}' nao encontrado no banco.")
        return

    dep_id, nome_real = result
    log.info(f"Gerando dossier para: {nome_real} (ID: {dep_id})")

    analise, duracao, fontes = generate_persona_analysis(
        dep_id, nome_real, args.query
    )

    # Output
    print("\n" + "=" * 80)
    print(f" DOSSIE COMPORTAMENTAL v2: {nome_real} ".center(80, "="))
    fontes_str = ", ".join(fontes) if fontes else "nenhuma"
    print(f" Fontes: {fontes_str} ".center(80, "-"))
    print("=" * 80 + "\n")
    print(analise)
    print("\n" + "=" * 80 + "\n")

    # Salvar
    context_list = search_context_multiquery(dep_id)
    _save_persona(
        dep_id,
        args.query or "Analise comportamental multi-query v2",
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
) -> Tuple[str, float, List[str]]:
    """Gera persona usando um client ja existente (sem reload de modelo)."""
    # Multi-query
    context_list = search_context_multiquery(deputado_id)
    if len(context_list) < RAG_MIN_CHUNKS:
        return (
            f"Dados insuficientes: {len(context_list)} chunks "
            f"(minimo {RAG_MIN_CHUNKS})",
            0.0,
            [],
        )

    prompt = build_analysis_prompt(context_list, nome)

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
        return f"Erro LLM: {e}", duracao, []

    fontes = _extract_fontes(context_list)
    return resposta, duracao, fontes


def _run_lote(lote: int, query: str | None, regenerar: bool):
    """Gera personas em lote para deputados sem persona v2."""
    with get_connection() as conn, conn.cursor() as cur:
        if regenerar:
            cur.execute(
                "SELECT deputado_id, nome FROM parlamentares_dados "
                "ORDER BY deputado_id LIMIT %s",
                (lote,),
            )
        else:
            cur.execute("""
                SELECT pd.deputado_id, pd.nome
                FROM parlamentares_dados pd
                LEFT JOIN parlamentares_personas pp
                    ON pd.deputado_id = pp.deputado_id
                    AND pp.versao_prompt = %s
                WHERE pp.deputado_id IS NULL
                ORDER BY pd.deputado_id
                LIMIT %s
            """, (RAG_PERSONA_VERSION, lote,))
        deputados = cur.fetchall()

    if not deputados:
        log.info("Nenhum deputado aguardando geracao de dossier.")
        return

    log.info(f"Lote: {len(deputados)} deputados para processar.")

    # Carregar LLM uma vez so
    llm_model = RAG_LLM_MODEL
    localai_manager.ensure_model_loaded(llm_model)
    ai_client = LocalAIClient(model=llm_model)

    conn = get_connection()
    try:
        for idx, (dep_id, nome_real) in enumerate(deputados, 1):
            log.info(f"[{idx}/{len(deputados)}] {nome_real} (ID: {dep_id})...")

            analise, duracao, fontes = _generate_with_client(
                ai_client, dep_id, nome_real, query
            )

            if analise.startswith("Dados insuficientes") or analise.startswith("Erro"):
                log.warning(f"  -> {analise[:80]}")
                continue

            # Salvar
            context_list = search_context_multiquery(dep_id)
            _save_persona(
                dep_id,
                query or "Analise comportamental multi-query v2",
                "\n".join(context_list),
                analise,
                fontes,
                duracao,
                conn=conn,
            )
            log.info(
                f"  -> Dossier salvo ({len(analise)} chars, {duracao:.1f}s, "
                f"fontes: {', '.join(fontes)})"
            )
    finally:
        conn.close()

    log.info(f"Lote concluido: {len(deputados)} deputados processados.")


if __name__ == "__main__":
    main()
