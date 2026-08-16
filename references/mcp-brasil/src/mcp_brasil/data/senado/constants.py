"""Constants for the Senado Federal feature."""

# Pagination
DEFAULT_PAGE_SIZE = 15

# API base URL
SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"

# Endpoints — Senadores
SENADORES_LISTA_URL = f"{SENADO_API_BASE}/senador/lista/atual"
SENADORES_URL = f"{SENADO_API_BASE}/senador"

# Endpoints — Matérias
MATERIAS_URL = f"{SENADO_API_BASE}/materia/pesquisa/lista"
MATERIA_URL = f"{SENADO_API_BASE}/materia"

# Endpoints — Votações (new API, replaces deprecated /plenario/lista/votacao)
VOTACOES_URL = f"{SENADO_API_BASE}/votacao"

# Endpoints — Comissões
COMISSOES_URL = f"{SENADO_API_BASE}/comissao/lista/colegiados"
COMISSAO_URL = f"{SENADO_API_BASE}/comissao"

# Endpoints — Agenda/Sessões
AGENDA_URL = f"{SENADO_API_BASE}/plenario/agenda/mes"
AGENDA_COMISSOES_URL = f"{SENADO_API_BASE}/agenda/lista/comissoes"

# Endpoints — Emendas / Relatorias
EMENDAS_URL = f"{SENADO_API_BASE}/processo/emenda"
RELATORIAS_URL = f"{SENADO_API_BASE}/processo/relatoria"

# Endpoints — Composição
BLOCOS_URL = f"{SENADO_API_BASE}/composicao/lista/blocos"
LIDERANCAS_URL = f"{SENADO_API_BASE}/composicao/lideranca"

# Endpoints — Legislatura
LEGISLATURA_URL = f"{SENADO_API_BASE}/legislatura"

# Accept header for JSON
JSON_HEADERS = {"Accept": "application/json"}

# Tipos de matéria mais comuns (referência estática)
TIPOS_MATERIA: dict[str, str] = {
    "PEC": "Proposta de Emenda à Constituição",
    "PLS": "Projeto de Lei do Senado",
    "PLC": "Projeto de Lei da Câmara",
    "PLP": "Projeto de Lei Complementar",
    "MPV": "Medida Provisória",
    "PDL": "Projeto de Decreto Legislativo",
    "PRS": "Projeto de Resolução do Senado",
    "RQS": "Requerimento do Senado",
    "REQ": "Requerimento",
    "MSF": "Mensagem do Senado Federal",
    "OFS": "Ofício do Senado",
    "AVS": "Aviso do Senado",
}
