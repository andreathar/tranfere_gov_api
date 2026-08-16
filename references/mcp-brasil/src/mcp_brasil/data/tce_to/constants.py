"""Constants for the TCE-TO feature."""

# API base URL — e-Contas REST API behind Kong gateway
API_BASE = "https://api.tceto.tc.br/econtas/api"

# Endpoints
PESSOAS_URL = f"{API_BASE}/pessoas"
PAUTAS_URL = f"{API_BASE}/pautas"
PROCESSO_URL = f"{API_BASE}/processo"  # /{numero}/{ano}

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
