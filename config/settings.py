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

# ---------------------------------------------------------------------------
# Parâmetros de request
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT = 60       # segundos
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0        # base do backoff exponencial
SLEEP_BETWEEN_PAGES = 1.0  # segundos — cortesia ao servidor gov

# ---------------------------------------------------------------------------
# Situações dos Planos de Ação
# ---------------------------------------------------------------------------
SITUACOES_NEGADAS = {"REPROVADO", "IMPEDIDO", "CANCELADO", "NAO_CUMPROU"}

SITUACOES_CONHECIDAS = {
    "CIENTE",
    "APROVADO",
    "REPROVADO",
    "IMPEDIDO",
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
