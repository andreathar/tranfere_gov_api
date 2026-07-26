import asyncio
import hashlib
import json
import logging
from datetime import datetime

from src.api.services.mcp_service import _mcp_client
from src.db_utils import get_connection
from src.localai_client import LocalAIClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configura o Qdrant localmente (in-memory/file storage) se necessário,
# mas por enquanto vamos manter os vetores no PostgreSQL com pgvector no futuro
# ou usar Qdrant puro. O script já deixa estruturado para injeção.
# Para manter a simplicidade e robustez sem dependência externa obrigatória,
# salvaremos no DB por agora, e o Qdrant / LLM Embeddings pode ser injetado.

# Prompt System para NER
NER_PROMPT = """Você é um especialista em análise jurídica e política.
Extraia os dados dos atos do Diário Oficial encontrados na busca.
O texto fornecido será uma lista de resultados em Markdown.
Retorne EXATAMENTE este JSON e nada mais:
{
  "itens": [
    {
      "tipo_ato": "Portaria, Licitação, Nomeação, Repasse, Lei, Convenio, etc",
      "orgao": "Quem assinou ou publicou (ex: Prefeitura de Campinas)",
      "valor_financeiro": 150000.50 (ou null se não houver),
      "entidades_citadas": ["Nome 1", "Empresa X"],
      "resumo": "Resumo do que se trata",
      "data_publicacao": "YYYY-MM-DD",
      "link": "https://..."
    }
  ]
}
"""


async def process_diario_oficial(
    query: str, escopo: str = "ambos", parlamentar_nome: str | None = None
) -> list[dict]:
    """
    Busca no Diário Oficial Unificado e usa LocalAI para classificar/extrair entidades,
    salvando no PostgreSQL.
    """
    log.info(f"Buscando Diários Oficiais: '{query}' (escopo: {escopo})")

    # 1. Chamar MCP Brasil
    res_mcp = await _mcp_client.call_tool(
        "diario_oficial_buscar_diario_unificado", {"texto": query, "escopo": escopo}
    )

    if not res_mcp:
        log.warning("Sem resultados ou erro no MCP.")
        return []

    log.info(f"Retorno MCP:\n{res_mcp[:500]}...")

    try:
        # 2. Processar a string inteira (Markdown) com LLM
        ai_client = LocalAIClient()
        resposta_llm = ai_client.chat_json(
            prompt=f"Analise o resultado de busca a seguir:\n\n{res_mcp[:8000]}", system=NER_PROMPT
        )
    except Exception as e:
        log.error(f"Erro no LLM: {e}")
        return []

    itens = resposta_llm.get("itens", [])
    if not itens:
        log.warning("LLM não extraiu nenhum item.")
        return []

    novos_atos = []

    with get_connection() as conn, conn.cursor() as cur:
        for item in itens:
            texto_ato = item.get("resumo") or "Resumo não gerado"
            data_pub = item.get("data_publicacao") or datetime.today().strftime("%Y-%m-%d")
            fonte = escopo.upper()
            link = item.get("link") or ""

            hash_conteudo = hashlib.md5(f"{texto_ato}{data_pub}".encode()).hexdigest()

            cur.execute(
                "SELECT ato_id FROM diario_oficial_atos WHERE hash_conteudo = %s", (hash_conteudo,)
            )
            if cur.fetchone():
                continue

            tipo_ato = item.get("tipo_ato", "Desconhecido")
            orgao = item.get("orgao", "Desconhecido")
            valor_fin = item.get("valor_financeiro")
            entidades = json.dumps(item.get("entidades_citadas", []))
            resumo = item.get("resumo", "")

            # Trata valor numérico
            if not isinstance(valor_fin, int | float):
                valor_fin = None

            # 3. Insere no PostgreSQL
            cur.execute(
                """
                    INSERT INTO diario_oficial_atos
                    (data_publicacao, fonte, orgao, tipo_ato, texto_bruto, resumo_ia, valor_financeiro, entidades_citadas, link_original, hash_conteudo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING ato_id
                """,
                (
                    data_pub,
                    fonte,
                    orgao,
                    tipo_ato,
                    texto_ato,
                    resumo,
                    valor_fin,
                    entidades,
                    link,
                    hash_conteudo,
                ),
            )

            ato_id = cur.fetchone()[0]
            novos_atos.append(ato_id)

            # Se há monitoramento de um parlamentar, cria um alerta
            if parlamentar_nome:
                cur.execute(
                    """
                        INSERT INTO parlamentar_alertas (parlamentar_nome, ato_id)
                        VALUES (%s, %s)
                    """,
                    (parlamentar_nome, ato_id),
                )

        conn.commit()

    log.info(f"Processamento concluído. {len(novos_atos)} novos atos inseridos no DB.")
    return novos_atos


async def main():
    await _mcp_client.connect()

    # Exemplo: Rodando rotina para um Parlamentar e uma Cidade
    await process_diario_oficial(
        query="AFONSO FLORENCE", escopo="federal", parlamentar_nome="AFONSO FLORENCE"
    )
    await process_diario_oficial(query="Convênio Educação Campinas", escopo="municipal")

    await _mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
