"""Constants for the TCE-RN feature."""

# API base URL
API_BASE = "https://apidadosabertos.tce.rn.gov.br/api"

# Endpoints — all use path parameters, format is Json or Csv
# /InformacoesBasicasApi/JurisdicionadosTCE/{formato}
JURISDICIONADOS_PATH = f"{API_BASE}/InformacoesBasicasApi/JurisdicionadosTCE/Json"

# /BalancoOrcamentarioApi/Despesa/{fmt}/{ano}/{bimestre}/{idUnidade}
DESPESA_PATH = f"{API_BASE}/BalancoOrcamentarioApi/Despesa/Json"

# /BalancoOrcamentarioApi/Receita/{fmt}/{ano}/{bimestre}/{idUnidade}
RECEITA_PATH = f"{API_BASE}/BalancoOrcamentarioApi/Receita/Json"

# /ProcedimentosLicitatoriosApi/LicitacaoPublica/{fmt}/{idUnidade}/{dataInicio}/{dataFim}
LICITACOES_PATH = f"{API_BASE}/ProcedimentosLicitatoriosApi/LicitacaoPublica/Json"

# /ContratosApi/Contratos/{fmt}/{idUnidade}/{considerarHierarquia}
CONTRATOS_PATH = f"{API_BASE}/ContratosApi/Contratos/Json"
