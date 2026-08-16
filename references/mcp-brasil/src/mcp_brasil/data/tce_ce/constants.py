"""Constants for the TCE-CE feature."""

API_BASE = "https://api-dados-abertos.tce.ce.gov.br"

# Endpoints
MUNICIPIOS_URL = f"{API_BASE}/municipios"
LICITACOES_URL = f"{API_BASE}/licitacoes"
CONTRATOS_URL = f"{API_BASE}/contrato"
EMPENHOS_URL = f"{API_BASE}/notas_empenhos"

# Pagination
DEFAULT_QUANTIDADE = 50
MAX_QUANTIDADE = 100
