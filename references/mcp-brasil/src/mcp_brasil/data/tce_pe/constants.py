"""Constants for the TCE-PE feature."""

# API base URL — append {Entity}!json?{params}
API_BASE = "https://sistemas.tce.pe.gov.br/DadosAbertos"

# Endpoint entities (appended to API_BASE with !json suffix)
UNIDADES_ENTITY = "UnidadesJurisdicionadas"
LICITACOES_ENTITY = "LicitacaoUG"
CONTRATOS_ENTITY = "Contratos"
DESPESAS_ENTITY = "DespesasMunicipais"
FORNECEDORES_ENTITY = "Fornecedores"

# Response encoding — TCE-PE uses ISO-8859-1
RESPONSE_ENCODING = "iso-8859-1"

# Result limit (server-side, cannot be changed via params)
RESULT_LIMIT = 100_000
