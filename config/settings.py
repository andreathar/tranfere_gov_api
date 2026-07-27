"""
Configuração centralizada para extração Transferegov.

Todas as constantes que os scripts precisam ficam aqui.
Import via: from config.settings import API_URL, SITUACOES_NEGADAS, etc.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths do projeto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_XLSX = OUTPUT_DIR / "xlsx"
OUTPUT_CSV = OUTPUT_DIR / "csv"
OUTPUT_JSON = OUTPUT_DIR / "json"
OUTPUT_LOGS = OUTPUT_DIR / "logs"

# Garantir que pastas existem
for d in (OUTPUT_DIR, OUTPUT_XLSX, OUTPUT_CSV, OUTPUT_JSON, OUTPUT_LOGS):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# API — Transferências Especiais (endpoint público)
# ---------------------------------------------------------------------------
API_URL_LISTAGEM = (
    "https://especiais.transferegov.sistema.gov.br"
    "/maisbrasil-transferencia-especial-backend"
    "/api/public/plano-acao/listagem"
)

# Headers padrão
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; TransfereGov-Extractor/1.0)",
}

# Parâmetros de query disponíveis na API (descobertos via URL real)
# Todos são opcionais. Combinar para filtrar.
# Exemplo completo:
#   uf=AL&beneficiario=9858&parlamentar=4291&emenda=11228
#   &programaId=25&planoAcaoSituacao=IMPEDIDO_RESTRICAO_TECNICA
#   &planoTrabalhoSituacao=ENVIADO_PARA_ANALISE&politicasPublicas=4
#   &objetoExecucao=1&objetoExecucaoAno=2026&pageSize=100&pageNumber=1
API_PARAMS_KNOWN = [
    "uf",  # UF do beneficiário (ex: AL, SP, PI)
    "beneficiario",  # ID do beneficiário
    "parlamentar",  # ID do parlamentar autor
    "emenda",  # ID da emenda
    "programaId",  # ID do programa (25 = Transferências Especiais)
    "planoAcaoSituacao",  # Situação do plano (underscores, sem acento)
    "planoTrabalhoSituacao",  # Situação do plano de trabalho
    "politicasPublicas",  # Código da política pública
    "objetoExecucao",  # Código do objeto de execução
    "objetoExecucaoAno",  # Ano exercício
    "pageSize",  # Itens por página (máx: 100)
    "pageNumber",  # Página atual (1-indexed)
]

# Situações de plano de ação (valores reais da API, com underscores)
# Mapeamento display site → valor API:
#   "Impedido por Restrição Técnica"          → IMPEDIDO
#   "Impedido por Rejeição do Plano de Trabalho" → IMPEDIDO_REJEICAO_PLANO_TRABALHO
SITUACOES_TRANSFEREGOV = {
    "AGUARDANDO_CIENCIA",
    "PLANO_TRABALHO_EM_ELABORACAO",
    "CIENTE",
    "IMPEDIDO",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO",
    "CANCELADO",
    "EM_EXECUCAO",
    "CONCLUIDO",
    "NAO_CUMPROU",
}

# Situações que indicam plano negado/perdido
SITUACOES_NEGADAS = {
    "REPROVADO",
    "IMPEDIDO",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO",
    "CANCELADO",
    "NAO_CUMPROU",
}

# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 60  # segundos
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # base do backoff exponencial
SLEEP_BETWEEN_PAGES = 1.0  # segundos — cortesia ao servidor gov

SITUACOES_CONHECIDAS = {
    "CIENTE",
    "APROVADO",
    "REPROVADO",
    "IMPEDIDO",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO",
    "CANCELADO",
    "EM_EXECUCAO",
    "CONCLUIDO",
    "NAO_CUMPROU",
}

# ---------------------------------------------------------------------------
# API antiga (legado — não usar para novos scripts)
# ---------------------------------------------------------------------------
API_URL_LEGADO = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
ENDPOINT_LEGADO = "/plano_acao_especial"

# ---------------------------------------------------------------------------
# PostgreSQL — Banco transferegov_db
# ---------------------------------------------------------------------------
PG_HOST = os.environ.get("PGHOST", "127.0.0.1")
PG_PORT = int(os.environ.get("PGPORT", "5432"))
PG_DB = os.environ.get("PGDATABASE", "transferegov_db")
PG_USER = os.environ.get("PGUSER", "cognee")
PG_PASS = os.environ.get("PGPASSWORD", "cognee")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# ---------------------------------------------------------------------------
# Enriquecimento (mcp-brasil como biblioteca Python)
# ---------------------------------------------------------------------------
ENRICH_ENABLED = os.getenv("ENRICH_ENABLED", "true").lower() == "true"
ENRICH_CACHE_TTL = int(os.getenv("ENRICH_CACHE_TTL", "3600"))  # 1 hora
ENRICH_RATE_LIMIT = float(os.getenv("ENRICH_RATE_LIMIT", "0.2"))  # 5s entre reqs
ENRICH_BATCH_SIZE = int(os.getenv("ENRICH_BATCH_SIZE", "50"))

# APIs externas
BRASILAPI_BASE = "https://brasilapi.com.br/api"
IBGE_API_BASE = "https://servicodados.ibge.gov.br/api/v1"
CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"

# ---------------------------------------------------------------------------
# LocalAI — Modelos locais via API compatível OpenAI
# ---------------------------------------------------------------------------
LOCALAI_BASE_URL = os.getenv("LOCALAI_BASE_URL", "http://localhost:8080/v1")
LOCALAI_TIMEOUT = int(os.getenv("LOCALAI_TIMEOUT", "300"))  # segundos
LOCALAI_MAX_RETRIES = int(os.getenv("LOCALAI_MAX_RETRIES", "3"))

# Modelos categorizados por tarefa (validados via benchmark)
LOCALAI_MODELS = {
    # Análise de dossiês (qualidade e redação em PT-BR ideal — 36.8 tok/s)
    "gemma": "gemma-4-e2b-it",
    # Análise profunda / auditoria pesada (7.7 tok/s)
    "analysis": "llama-3.1-8b-q4-k-m",
    # Código
    "code": "Qwen2.5-Coder-7B-Instruct-GGUF",
    # Tarefas ultra-rápidas / NER (88.9 tok/s - resposta em 11s)
    "fast": "qwen2.5-1.5b-instruct-q4-k-m",
    # Uso geral
    "general": "gemma-4-e2b-it",
    # Embeddings
    "embedding": "nomic-embed-text-v1.5",
    # Roteamento inteligente
    "router": "intelligent-router",
}

# Modelo padrão para jobs de pipeline
LOCALAI_DEFAULT_MODEL = LOCALAI_MODELS["gemma"]

# ---------------------------------------------------------------------------
# RAG — Qdrant + Embeddings + Persona
# ---------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "deputados_perfis"
EMBEDDER_MODEL = "nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
RAG_LLM_MODEL = os.getenv(
    "RAG_LLM_MODEL", "gemma-4-e2b-it"
)  # gemma-4-e2b-it (qualidade/velocidade ideal)
RAG_PERSONA_VERSION = 3  # Incrementar para a nova versão enriquecida
RAG_MIN_CHUNKS = 3  # Mínimo de chunks para gerar persona (evitar análises vazias)
RAG_MAX_CHUNKS = 30  # Máximo de chunks por deputado no contexto final
RAG_BATCH_SIZE = 50  # Tamanho do batch para embedding em lote
