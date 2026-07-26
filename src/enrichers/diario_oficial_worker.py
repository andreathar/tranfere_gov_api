import asyncio
import hashlib
import json
import logging
from datetime import datetime

import requests

from config.settings import CAMARA_API_BASE, LOCALAI_MODELS
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
    query: str,
    escopo: str = "ambos",
    parlamentar_nome: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> list[dict]:
    """
    Busca no Diário Oficial Unificado e usa LocalAI para classificar/extrair entidades,
    salvando no PostgreSQL.
    """
    log.info(f"Buscando Diários Oficiais: '{query}' (escopo: {escopo})")

    # 1. Chamar MCP Brasil
    res_mcp = await _mcp_client.call_tool(
        "diario_oficial_buscar_diario_unificado",
        {"texto": query, "escopo": escopo, "data_inicio": data_inicio, "data_fim": data_fim},
    )

    if not res_mcp:
        log.warning("Sem resultados ou erro no MCP.")
        return []

    log.info(f"Retorno MCP:\n{res_mcp[:500]}...")

    try:
        # 2. Processar a string inteira (Markdown) com LLM
        ai_client = LocalAIClient(model=LOCALAI_MODELS["fast"])
        resposta_llm = ai_client.chat_json(
            prompt=f"Analise o resultado de busca a seguir:\n\n{str(res_mcp)[:4000]}", system=NER_PROMPT
        )
    except Exception as e:
        log.error(f"Erro no LLM: {e}")
        return []

    if isinstance(resposta_llm, list):
        itens = resposta_llm
    else:
        itens = resposta_llm.get("itens", [])
    if not itens:
        log.warning("LLM não extraiu nenhum item.")
        return []

    novos_atos = []

    with get_connection() as conn, conn.cursor() as cur:
        for item in itens:
            texto_ato = item.get("resumo") or "Resumo não gerado"
            import pandas as pd
            raw_date = item.get("data_publicacao") or datetime.today().strftime("%Y-%m-%d")
            if isinstance(raw_date, list):
                raw_date = str(raw_date[0]) if raw_date else datetime.today().strftime("%Y-%m-%d")
            raw_date = str(raw_date)
            try:
                data_pub = pd.to_datetime(raw_date, dayfirst=True).strftime("%Y-%m-%d")
            except Exception:
                data_pub = datetime.today().strftime("%Y-%m-%d")
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


async def process_proposicoes(deputado_id: int, nome: str) -> None:
    """Busca proposições recentes do deputado via API da Câmara e salva no banco de dados."""
    log.info(f"Buscando proposições para: {nome} (ID: {deputado_id})")

    url = f"{CAMARA_API_BASE}/proposicoes"
    params = {"idDeputadoAutor": deputado_id, "itens": 10, "ordem": "DESC", "ordenarPor": "ano"}

    try:
        resp = requests.get(url, params=params, timeout=15)  # type: ignore[arg-type]
        if resp.status_code != 200:
            log.warning(f"Erro na API da Câmara para {nome}: {resp.status_code}")
            return

        dados = resp.json().get("dados", [])
        if not dados:
            return
    except Exception as e:
        log.error(f"Erro ao buscar proposições nativas: {e}")
        return

    # Usamos o LLM para classificar e gerar um resumo curto
    NER_PROPOSICAO = """Extraia as proposições do texto JSON/Markdown fornecido e retorne NESTE formato JSON:
    { "itens": [ { "id": 123, "sigla_tipo": "PL", "numero": 100, "ano": 2024, "ementa": "...", "data": "2024-01-01" } ] }"""

    try:
        ai_client = LocalAIClient(model=LOCALAI_MODELS["fast"])
        resposta_llm = ai_client.chat_json(
            prompt=f"Proposições (JSON bruto):\n\n{json.dumps(dados, ensure_ascii=False)[:4000]}",
            system=NER_PROPOSICAO,
        )
    except Exception as e:
        log.error(f"Erro no LLM (Proposições): {e}")
        return

    itens = resposta_llm.get("itens", [])
    if not isinstance(itens, list):
        log.warning(f"LLM não retornou uma lista válida para proposições de {nome}.")
        return

    with get_connection() as conn, conn.cursor() as cur:
        for item in itens:
            cur.execute(
                "SELECT proposicao_id FROM parlamentar_proposicoes WHERE proposicao_id = %s",
                (item.get("id"),),
            )
            if cur.fetchone():
                continue


            # Safe date extraction for data_apresentacao
            raw_date_prop = item.get("data") or datetime.today().strftime("%Y-%m-%d")
            if isinstance(raw_date_prop, list):
                raw_date_prop = str(raw_date_prop[0]) if raw_date_prop else datetime.today().strftime("%Y-%m-%d")
            raw_date_prop = str(raw_date_prop)
            try:
                import pandas as pd
                data_prop = pd.to_datetime(raw_date_prop, dayfirst=True).strftime("%Y-%m-%d")
            except Exception:
                data_prop = datetime.today().strftime("%Y-%m-%d")

            cur.execute(
                """
                INSERT INTO parlamentar_proposicoes
                (proposicao_id, deputado_id, parlamentar_nome, sigla_tipo, numero, ano, ementa, data_apresentacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    item.get("id"),
                    deputado_id,
                    nome,
                    item.get("sigla_tipo"),
                    item.get("numero"),
                    item.get("ano"),
                    item.get("ementa"),
                    data_prop,
                ),
            )
        conn.commit()
    log.info(f"{len(itens)} proposições salvas para {nome}.")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Worker do Diário Oficial")
    parser.add_argument("--limit", type=int, default=10, help="Quantidade de deputados a processar no lote")
    args = parser.parse_args()

    # Garantir que o modelo de LLM (fast) esteja carregado e limpe a memória
    from src.localai_manager import manager as localai_manager
    localai_manager.ensure_model_loaded(LOCALAI_MODELS["fast"])

    await _mcp_client.connect()

    from datetime import datetime, timedelta

    trinta_dias_atras = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    hoje = datetime.today().strftime("%Y-%m-%d")

    with get_connection() as conn, conn.cursor() as cur:
        # Adiciona coluna de controle se não existir
        cur.execute("ALTER TABLE parlamentares_dados ADD COLUMN IF NOT EXISTS ultimo_check_diario TIMESTAMP DEFAULT '1970-01-01'")
        conn.commit()

        # Puxa N deputados priorizando os que não são checados há mais tempo
        cur.execute(
            "SELECT deputado_id, nome FROM parlamentares_dados ORDER BY ultimo_check_diario ASC NULLS FIRST LIMIT %s",
            (args.limit,)
        )
        deputados = cur.fetchall()

    for dep_id, nome in deputados:
        log.info(f"=== Processando {nome} ===")
        try:
            # 1. Busca Diários Oficiais (restrito aos últimos 30 dias)
            await process_diario_oficial(
                query=nome,
                escopo="ambos",
                parlamentar_nome=nome,
                data_inicio=trinta_dias_atras,
                data_fim=hoje,
            )

            # 2. Busca Proposições da Câmara
            await process_proposicoes(dep_id, nome)

            # Atualiza a data de checagem com sucesso
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("UPDATE parlamentares_dados SET ultimo_check_diario = NOW() WHERE deputado_id = %s", (dep_id,))
                conn.commit()
                
        except Exception as e:
            log.error(f"Falha não tratada ao processar {nome}: {e}")

        # Timeout leve para não engasgar o MCP local
        await asyncio.sleep(2)

    await _mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
