"""
Módulo de RAG para extração de Perfis e Personas dos Deputados.
Ele busca o contexto no Qdrant e usa o LLM (Llama) para gerar análises políticas e comportamentais.
"""

import argparse
import logging
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.http import models

from config.settings import LOCALAI_MODELS
from src.db_utils import get_connection
from src.localai_manager import manager as localai_manager
from src.localai_client import LocalAIClient
from src.enrichers.rag_qdrant_indexer import QDRANT_URL, COLLECTION_NAME, EMBEDDER_MODEL, embed_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def search_context_qdrant(deputado_id: int, query_text: str, limit: int = 15) -> List[str]:
    """Busca o contexto mais relevante no Qdrant para um dado deputado."""
    log.info(f"Gerando embedding para a query: '{query_text}'")
    
    # Garante que o embedder está rodando
    localai_manager.ensure_model_loaded(EMBEDDER_MODEL)
    query_vector = embed_text(query_text)
    
    if not query_vector:
        log.error("Falha ao gerar vetor para a query.")
        return []

    client = QdrantClient(url=QDRANT_URL)
    
    # Filtro obrigatório: só buscar dados Deste deputado
    filtro = models.Filter(
        must=[
            models.FieldCondition(
                key="deputado_id", 
                match=models.MatchValue(value=deputado_id)
            )
        ]
    )

    log.info(f"Buscando os {limit} trechos mais relevantes no Qdrant...")
    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=filtro,
        limit=limit
    )

    contextos = []
    for hit in hits.points:
        # hit.payload tem {"text": "...", "type": "..."}
        if hit.payload and "text" in hit.payload:
            contextos.append(f"[{hit.payload.get('type', 'info').upper()}] {hit.payload['text']}")

    return contextos


def generate_persona_analysis(deputado_id: int, nome: str, query: str = None) -> str:
    """Gera uma análise via LLM usando o contexto resgatado do Qdrant."""
    if not query:
        query = "Faça uma análise profunda do perfil comportamental, áreas prioritárias de atuação, alinhamento político e foco de gastos orçamentários deste deputado."

    context_list = search_context_qdrant(deputado_id, query)
    
    if not context_list:
        return "Não há contexto suficiente indexado no Qdrant para este deputado."

    contexto_str = "\n".join(f"- {c}" for c in context_list)
    
    prompt = f"""Você é um Cientista Político Sênior especialista no Legislativo Brasileiro.
Sua missão é responder à seguinte pergunta ou solicitação sobre o Deputado(a) {nome}:
"{query}"

Você deve basear sua análise RIGOROSAMENTE no seguinte contexto extraído (Emendas Pix, Proposições e Diário Oficial):
{contexto_str}

Instruções:
1. Sintetize as áreas temáticas mais presentes (ex: saúde, infraestrutura, segurança).
2. Tente identificar um "padrão comportamental" ou prioridade eleitoral com base nos municípios e leis propostas.
3. Não invente informações que não estejam no contexto.
4. Escreva em formato Markdown, usando títulos e bullet points estruturados.
"""

    log.info("Descarregando embedder e preparando modelo de Texto LLaMA...")
    # O Llama 8b pode precisar de muita memória, garantimos exclusividade:
    llm_model = LOCALAI_MODELS["general"]
    localai_manager.ensure_model_loaded(llm_model)

    ai_client = LocalAIClient(model=llm_model)
    
    log.info("Gerando análise comportamental...")
    try:
        resposta = ai_client.chat(
            prompt=prompt, 
            system="Você é um assistente analítico focado em ciência política e dados empíricos."
        )
        return resposta
    except Exception as e:
        log.error(f"Erro ao gerar LLM Persona: {e}")
        return f"Erro na geração da persona: {e}"


def main():
    parser = argparse.ArgumentParser(description="Consulta o RAG para criar Análises de Deputados")
    parser.add_argument("--nome", type=str, required=True, help="Nome do Deputado (ex: 'Danilo Forte')")
    parser.add_argument("--query", type=str, default=None, help="Pergunta específica sobre o deputado")
    args = parser.parse_args()

    # Descobrir o ID do deputado
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT deputado_id, nome FROM parlamentares_dados WHERE nome ILIKE %s LIMIT 1", (f"%{args.nome}%",))
        result = cur.fetchone()
        
    if not result:
        log.error(f"Deputado '{args.nome}' não encontrado no banco de dados local.")
        return

    dep_id, nome_real = result
    
    log.info(f"Iniciando Dossiê/Persona RAG para: {nome_real} (ID: {dep_id})")
    
    analise = generate_persona_analysis(dep_id, nome_real, args.query)
    
    print("\n" + "="*80)
    print(f" DOSSIÊ COMPORTAMENTAL: {nome_real} ".center(80, "="))
    print("="*80 + "\n")
    print(analise)
    print("\n" + "="*80 + "\n")

    # Salva na tabela parlamentares_personas, caso ela já exista (ou cria)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parlamentares_personas (
                id SERIAL PRIMARY KEY,
                deputado_id INTEGER REFERENCES parlamentares_dados(deputado_id),
                query_text TEXT,
                analise_gerada TEXT,
                data_analise TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            INSERT INTO parlamentares_personas (deputado_id, query_text, analise_gerada)
            VALUES (%s, %s, %s)
        """, (dep_id, args.query or "Analise Comportamental Geral", analise))
        conn.commit()
    log.info("Dossiê armazenado no banco com sucesso (tabela parlamentares_personas).")


if __name__ == "__main__":
    main()
