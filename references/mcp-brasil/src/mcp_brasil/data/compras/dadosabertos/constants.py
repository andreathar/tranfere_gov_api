"""Constants for the Dados Abertos Compras.gov.br API."""

# API base URL
API_BASE = "https://dadosabertos.compras.gov.br"

# Module endpoints
LICITACOES_URL = f"{API_BASE}/modulo-legado/1_consultarLicitacao"
ITENS_LICITACAO_URL = f"{API_BASE}/modulo-legado/2_consultarItemLicitacao"
PREGOES_URL = f"{API_BASE}/modulo-legado/3_consultarPregoes"
COMPRAS_SEM_LICITACAO_URL = f"{API_BASE}/modulo-legado/5_consultarComprasSemLicitacao"
CONTRATOS_URL = f"{API_BASE}/modulo-contratos/1_consultarContratos"
FORNECEDOR_URL = f"{API_BASE}/modulo-fornecedor/1_consultarFornecedor"
GRUPO_MATERIAL_URL = f"{API_BASE}/modulo-material/1_consultarGrupoMaterial"
ITEM_MATERIAL_URL = f"{API_BASE}/modulo-material/4_consultarItemMaterial"
ITEM_SERVICO_URL = f"{API_BASE}/modulo-servico/6_consultarItemServico"
UASG_URL = f"{API_BASE}/modulo-uasg/1_consultarUasg"
PESQUISA_PRECO_MATERIAL_URL = f"{API_BASE}/modulo-pesquisa-preco/1_consultarMaterial"
PESQUISA_PRECO_SERVICO_URL = f"{API_BASE}/modulo-pesquisa-preco/3_consultarServico"

# Pagination
DEFAULT_PAGE_SIZE = 10
MIN_PAGE_SIZE = 10
MAX_PAGE_SIZE = 500
