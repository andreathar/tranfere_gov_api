"""
Configuração centralizada para extração Transferegov.

Todas as constantes que os scripts precisam ficam aqui.
Import via: from config.settings import API_URL, SITUACOES_NEGADAS, etc.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

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
# CARTO — connection helpers for Carto agents (read-only)
# ---------------------------------------------------------------------------
# Carto agents require a read-only Postgres connection. Set these in the
# Carto/agent environment or secrets store. Defaults reuse the main PG host/db.
CARTO_PG_HOST = os.getenv("CARTO_PG_HOST", PG_HOST)
CARTO_PG_PORT = int(os.getenv("CARTO_PG_PORT", str(PG_PORT)))
CARTO_PG_DB = os.getenv("CARTO_PG_DB", PG_DB)
CARTO_PG_USER = os.getenv("CARTO_PG_USER", "carto_reader")
CARTO_PG_PASS = os.getenv("CARTO_PG_PASS", "")
# Example connection string for Carto agents (set CARTO_PG_USER/CARTO_PG_PASS securely):
CARTO_DATABASE_URL = f"postgresql://{CARTO_PG_USER}:{CARTO_PG_PASS}@{CARTO_PG_HOST}:{CARTO_PG_PORT}/{CARTO_PG_DB}"

# --- CARTO platform API (register this DB as a Connection in CARTO Workspace) ---
# https://docs.carto.com/carto-user-manual/developers/managing-credentials/api-base-url
# Region/deployment-specific, e.g. https://gcp-us-east1.api.carto.com (Cloud US)
# or https://your-carto-tenant-domain.com/api (Self-Hosted).
CARTO_API_BASE_URL = os.getenv("CARTO_API_BASE_URL", "")
# M2M OAuth client (Workspace > Developers > Credentials > OAuth Clients).
# Used to obtain a Bearer token via the client_credentials grant against
# https://auth.carto.com/oauth/token — required by the Connections API,
# which does NOT accept plain API Access Tokens.
CARTO_OAUTH_CLIENT_ID = os.getenv("CARTO_OAUTH_CLIENT_ID", "")
CARTO_OAUTH_CLIENT_SECRET = os.getenv("CARTO_OAUTH_CLIENT_SECRET", "")
CARTO_OAUTH_TOKEN_URL = os.getenv("CARTO_OAUTH_TOKEN_URL", "https://auth.carto.com/oauth/token")
CARTO_OAUTH_AUDIENCE = os.getenv("CARTO_OAUTH_AUDIENCE", "carto-cloud-native-api")
# Name the connection will be registered under in CARTO Workspace.
CARTO_CONNECTION_NAME = os.getenv("CARTO_CONNECTION_NAME", "transferegov_db")


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
REASONING_SERVICES_URL = os.getenv("REASONING_SERVICES_URL", "https://reasoning.services/mcp")
REASONING_SERVICES_API_KEY = os.getenv(
    "RS_API_KEY",
    os.getenv("RSVC_API_KEY", os.getenv("REASONING_SERVICES_API_KEY", "")),
)

# ---------------------------------------------------------------------------
# LocalAI — Modelos locais via API compatível OpenAI
# ---------------------------------------------------------------------------
LOCALAI_BASE_URL = os.getenv("LOCALAI_BASE_URL", "http://localhost:8080")
LOCALAI_TIMEOUT = int(os.getenv("LOCALAI_TIMEOUT", "300"))  # segundos
LOCALAI_MAX_RETRIES = int(os.getenv("LOCALAI_MAX_RETRIES", "3"))

# Modal vLLM (Cloud GPU)
MODAL_VLLM_URL = os.getenv("MODAL_VLLM_URL", None)
MODAL_VLLM_TOKEN = os.getenv("MODAL_VLLM_TOKEN", None)
USE_MODAL_VLLM = os.getenv("USE_MODAL_VLLM", "false").lower() == "true"

# Modelos categorizados por tarefa (validados via benchmark de qualidade/desempenho)
# Atualizado 2026-08-15: removidos modelos sem YAML/GGUF (agente-dossie-*, zero-gemma4, gemma-4-e2b).
# Todos os jobs agora usam Qwen2.5-Coder-7B (modelo único residente na GPU).
#
# Corrigido 2026-08-15: "analysis" e "fast" ainda apontavam para llama-3.1-8b e
# qwen2.5-1.5b, contradizendo o comentário acima. Testado com GET /system
# loaded_models: qualquer segundo modelo de chat na GPU (mesmo o pequeno de 1.1GB)
# expulsa o Qwen2.5-Coder-7B da VRAM (6GB no total, sem espaço pra dois residentes).
# Ver /mnt/data/Projects_SSD/docs/localai-models.json para os testes.
LOCALAI_MODELS = {
    # Dossiê comportamental RAG (padrão; registry LocalAI local)
    "dossie": "Qwen2.5-Coder-7B-Instruct-GGUF",
    # Análise profunda / auditoria pesada
    "analysis": "Qwen2.5-Coder-7B-Instruct-GGUF",
    # Tarefas ultra-rápidas / Triagem
    "fast": "Qwen2.5-Coder-7B-Instruct-GGUF",
    # Código
    "code": "Qwen2.5-Coder-7B-Instruct-GGUF",
    # Uso geral
    "general": "Qwen2.5-Coder-7B-Instruct-GGUF",
    # Embeddings
    "embedding": "embeddinggemma-300m",
}

# Modelo padrão para jobs de pipeline
LOCALAI_DEFAULT_MODEL = LOCALAI_MODELS["dossie"]

# Telemetria QC dos analistas RAG (persistir resultados em dossie_analyst_qc)
RAG_PERSIST_QC = os.getenv("RAG_PERSIST_QC", "false").lower() == "true"

# ---------------------------------------------------------------------------
# vLLM Local — Engine de inferência local alternativa (GGUF models)
# ---------------------------------------------------------------------------
# Permite usar o vLLM (fork local em /mnt/data/Projects_SSD/vllm) no lugar do
# LocalAI para servir modelos GGUF, aproveitando PagedAttention, continuous
# batching, prefix caching, etc.
# Ativar: USE_LOCAL_VLLM=true LOCAL_VLLM_BASE_URL=http://localhost:8001
USE_LOCAL_VLLM = os.getenv("USE_LOCAL_VLLM", "false").lower() == "true"
LOCAL_VLLM_FORK_DIR = os.getenv("LOCAL_VLLM_FORK_DIR", str(PROJECT_ROOT.parent / "vllm"))
LOCAL_VLLM_BASE_URL = os.getenv("LOCAL_VLLM_BASE_URL", "http://localhost:8001")
LOCAL_VLLM_MODELS_DIR = os.getenv("LOCAL_VLLM_MODELS_DIR", "/mnt/data/models")
LOCAL_VLLM_TIMEOUT = int(os.getenv("LOCAL_VLLM_TIMEOUT", "300"))
LOCAL_VLLM_GPU_MEM_UTIL = float(os.getenv("LOCAL_VLLM_GPU_MEM_UTIL", "0.88"))
LOCAL_VLLM_MAX_MODEL_LEN = int(os.getenv("LOCAL_VLLM_MAX_MODEL_LEN", "8192"))
LOCAL_VLLM_PORT = int(os.getenv("LOCAL_VLLM_PORT", "8001"))

# Mapeamento modelos → vLLM. Cada entry pode ter:
#   hf_model_id:  HF model ID (prioritário, usa cache HuggingFace)
#   gguf_path:    path .gguf (fallback) + tokenizer_id
#   quantization: "bitsandbytes" para BNB 4bit
LOCAL_VLLM_MODEL_MAP: dict[str, dict[str, str]] = {
    "llama-3.2-3b": {
        "hf_model_id": "unsloth/llama-3.2-3b-unsloth-bnb-4bit",
        "quantization": "bitsandbytes",
        "gguf_path": f"{LOCAL_VLLM_MODELS_DIR}/localai/llm/llama-3.2-3b/llama-3.2-3b-instruct-q4_k_m.gguf",
        "tokenizer_id": "hugging-quants/Llama-3.2-3B-Instruct-GGUF",
    },
    "llama-3.2-3b-instruct:q4_k_m": {
        "gguf_path": f"{LOCAL_VLLM_MODELS_DIR}/localai/llm/llama-3.2-3b/llama-3.2-3b-instruct-q4_k_m.gguf",
        "tokenizer_id": "hugging-quants/Llama-3.2-3B-Instruct-GGUF",
    },
    "qwen2.5-1.5b-instruct-q4-k-m": {
        "gguf_path": f"{LOCAL_VLLM_MODELS_DIR}/localai/llm/qwen2.5-1.5b/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "tokenizer_id": "Qwen/Qwen2.5-1.5B-Instruct",
    },
    "Qwen2.5-Coder-7B-Instruct-GGUF": {
        "gguf_path": f"{LOCAL_VLLM_MODELS_DIR}/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf",
        "tokenizer_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
    },
}

# Timeouts por modelo (em segundos) — sobrescrevem LOCALAI_TIMEOUT geral
# Atualizado 2026-08-15: removidos modelos inexistentes (agente-dossie-*, gemma-4, zero-gemma4).
LOCALAI_MODEL_TIMEOUTS: dict[str, int] = {
    "llama-3.2-3b-instruct:q4_k_m": 120,  # 3B, rápido e estável
    "qwen2.5-1.5b-instruct-q4-k-m": 120,  # 1.5B, rápido
    "llama-3.1-8b-q4-k-m": 300,  # 8B, denso
    "Qwen2.5-Coder-7B-Instruct-GGUF": 300,  # 7B, código/RAG
    "nomic-embed-text-v1.5": 30,  # emb., rápido
    "embeddinggemma-300m": 30,  # 300M, rápido
}

# ---------------------------------------------------------------------------
# Cloud Proxy LocalAI — Roteia requests para LLMs cloud via backend cloud-proxy
# ---------------------------------------------------------------------------
# O cloud proxy é um backend nativo do LocalAI que recebe requests
# OpenAI-compatíveis e as encaminha para provedores cloud (OpenAI, Anthropic).
#
# Cada chave é o nome do modelo configurado no LocalAI com backend: cloud-proxy.
# O cliente Python usa LOCALAI_BASE_URL + model name (auth é server-side).
#
# Configuração de exemplo no LocalAI (model.yaml):
#   backend: cloud-proxy
#   upstream_url: https://api.openai.com/v1
#   upstream_model: gpt-4o-mini
#   api_key_env: OPENAI_API_KEY
#   mode: translate
#   provider: openai
CLOUD_PROXY_MODELS: dict[str, dict[str, str | int]] = {
    # Exemplo (descomentar para usar):
    # "gpt-4o-mini": {
    #     "upstream_url": "https://api.openai.com/v1",
    #     "upstream_model": "gpt-4o-mini",
    #     "api_key_env": "OPENAI_API_KEY",
    #     "provider": "openai",
    #     "mode": "translate",
    #     "timeout": 300,
    # },
}

# Nomes dos modelos que rodam via cloud proxy (para detecção rápida)
CLOUD_PROXY_MODEL_NAMES: set[str] = set(CLOUD_PROXY_MODELS.keys())

# ---------------------------------------------------------------------------
# RAG — Qdrant + Embeddings + Persona
# ---------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "deputados_perfis"
EMBEDDER_MODEL = "embeddinggemma-300m"
EMBEDDING_DIM = 768
RAG_LLM_MODEL = os.getenv("RAG_LLM_MODEL", "Qwen2.5-Coder-7B-Instruct-GGUF")
PREPARER_MODEL = os.getenv("PREPARER_MODEL", "Qwen2.5-Coder-7B-Instruct-GGUF")
# Fallback: se o modelo principal falhar ou quality check reprovar, tenta este
RAG_FALLBACK_MODEL = os.getenv("RAG_FALLBACK_MODEL", "Qwen2.5-Coder-7B-Instruct-GGUF")
RAG_PERSONA_VERSION = (
    8  # v8: 6 analistas (votacao fundido, rede_politica novo) + briefing único + QC estruturado
)
RAG_MIN_CHUNKS = 3  # Mínimo de chunks para gerar persona (evitar análises vazias)
RAG_MAX_CHUNKS = 30  # Máximo de chunks por deputado no contexto final

# --- RAG v8 (Fase 3): dossiês multi-cargo ---
TIPOS_POLITICOS = ("deputado", "senador", "governador", "prefeito", "vereador")
# Limites por cargo (cargos novos têm menos fontes disponíveis no Qdrant).
# min=1 para cargos não-deputado: o piloto valida o pipeline E2E com o
# chunk de perfil; a riqueza de chunks virá de novos extratores (votos de
# senador, proposições, etc.) em iteração futura do indexador.
RAG_MIN_CHUNKS_BY_TIPO: dict[str, int] = {
    "deputado": RAG_MIN_CHUNKS,
    "senador": 1,
    "governador": 1,
    "prefeito": 1,
    "vereador": 1,
}
RAG_MAX_CHUNKS_BY_TIPO: dict[str, int] = {
    "deputado": RAG_MAX_CHUNKS,
    "senador": 25,
    "governador": 20,
    "prefeito": 20,
    "vereador": 15,
}
RAG_BATCH_SIZE = 50  # Tamanho do batch para embedding em lote
RAG_MAX_RETRIES = 2  # Tentativas com fallback se quality check reprovar

# --- RAG v3: Parâmetros de Qualidade ---
RAG_RRF_K: int = 60  # Constante para Reciprocal Rank Fusion
RAG_PROMPT_TOKEN_LIMIT: int = 7000  # Limite de tokens antes de truncar
RAG_CHARS_PER_TOKEN: int = 4  # Estimativa de caracteres por token
RAG_DEDUP_ALGO: str = "md5"  # Algoritmo de deduplicação ("prefix" ou "md5")

# --- RAG v5: Tipos de Chunk (18 tipos — sync com rag_qdrant_indexer.py) ---
RAG_CHUNK_TYPES: dict[str, str] = {
    "perfil": "Perfil enriquecido (escolaridade, naturalidade, situacao)",
    "proposicao": "Proposições legislativas com resumo_ia (LIMIT 30)",
    "emenda": "Emendas PIX com contexto demografico inline",
    "emenda_discricionaria": "Emendas discricionarias com CNPJ beneficiario",
    "voto": "Padrão de votação nominal",
    "diario_oficial": "Atos DOU com nivel_relevancia (LIMIT 20)",
    "conexao_politica": "Conexões Deputado→Prefeito→Vereador",
    "compras_municipio": "Compras públicas do município",
    "indicadores_sociais": "Saude + educacao + IDHM + populacao (fundido)",
    "risco_judicial": "Processos judiciais vinculados",
    "demografia_municipio": "Dados demográficos IBGE",
    "municipio_financeiro": "Dados financeiros SICONFI (UF corrigida)",
    "parlamentar_resumo": "Resumo consolidado do deputado",
    "beneficiario": "Perfil de beneficiários diretos",
    "prefeito": "Perfil do prefeito municipal",
    "senador": "Senadores em exercício no estado",
    "fnde_repasses": "Repasses educacionais FNDE",
    "vereadores_resumo": "Rede política local (vereadores)",
}
