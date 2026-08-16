"""Constants for the TCE-RS feature."""

# Portal base URL
PORTAL_BASE = "https://dados.tce.rs.gov.br"

# Direct data file base URL
DATA_BASE = "https://dados.tce.rs.gov.br/dados"

# CKAN API base URL
CKAN_API_BASE = "https://dados.tce.rs.gov.br/api/3/action"

# Auxiliary reference data URLs
MUNICIPIOS_URL = f"{DATA_BASE}/auxiliar/municipios.json"

# Consolidated yearly data URL patterns (append /{year}.json)
EDUCACAO_INDICE_URL = f"{DATA_BASE}/municipal/educacao-indice"
SAUDE_INDICE_URL = f"{DATA_BASE}/municipal/saude-indice"
GESTAO_FISCAL_URL = f"{DATA_BASE}/municipal/gastos-lrf-mde-asps"

# CKAN API endpoints
PACKAGE_SEARCH_URL = f"{CKAN_API_BASE}/package_search"

# CKAN search limits
CKAN_DEFAULT_ROWS = 10
CKAN_MAX_ROWS = 50
