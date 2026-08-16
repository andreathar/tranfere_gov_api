"""Constants for the Contratos.gov.br API."""

# API base URL
API_BASE = "https://contratos.comprasnet.gov.br"

# Public endpoints (no auth required)
CONTRATO_POR_ID_URL = f"{API_BASE}/api/contrato/id"
CONTRATO_POR_UG_URL = f"{API_BASE}/api/contrato/ug"
CONTRATO_INATIVO_POR_UG_URL = f"{API_BASE}/api/contrato/inativo/ug"
CONTRATO_POR_UASG_NUMERO_URL = f"{API_BASE}/api/contrato/ugorigem"
ORGAOS_URL = f"{API_BASE}/api/contrato/orgaos"
UNIDADES_URL = f"{API_BASE}/api/contrato/unidades"

# Sub-resource URL template (appended to API_BASE/api/contrato/{id}/{recurso})
CONTRATO_SUBRESOURCE_URL = f"{API_BASE}/api/contrato"
