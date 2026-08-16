"""Constants for the TCE-RJ feature."""

API_BASE = "https://dados.tcerj.tc.br/api/v1"

# Municipal endpoints
LICITACOES_URL = f"{API_BASE}/licitacoes"
CONTRATOS_MUNICIPIO_URL = f"{API_BASE}/contratos_municipio"
COMPRAS_DIRETAS_MUNICIPIO_URL = f"{API_BASE}/compras_diretas_municipio"
OBRAS_PARALISADAS_URL = f"{API_BASE}/obras_paralisadas"
CONCESSOES_PUBLICAS_URL = f"{API_BASE}/concessoes_publicas"
PRESTACAO_CONTAS_MUNICIPIO_URL = f"{API_BASE}/prestacao_contas_municipio"
PENALIDADES_MUNICIPIO_URL = f"{API_BASE}/penalidades_ressarcimento_municipio"

# State endpoints
COMPRAS_DIRETAS_ESTADO_URL = f"{API_BASE}/compras_diretas_estado"
CONTRATOS_ESTADO_URL = f"{API_BASE}/contratos_estado"
PENALIDADES_ESTADO_URL = f"{API_BASE}/penalidades_ressarcimento_estado"

# Defaults
DEFAULT_LIMITE = 100
