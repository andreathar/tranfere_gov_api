"""Constants for the SINESP/MJSP CKAN feature."""

CKAN_BASE = "https://dados.mj.gov.br/api/3/action"

# CKAN API endpoints
PACKAGE_LIST_URL = f"{CKAN_BASE}/package_list"
PACKAGE_SHOW_URL = f"{CKAN_BASE}/package_show"
PACKAGE_SEARCH_URL = f"{CKAN_BASE}/package_search"
ORGANIZATION_LIST_URL = f"{CKAN_BASE}/organization_list"
ORGANIZATION_SHOW_URL = f"{CKAN_BASE}/organization_show"
GROUP_LIST_URL = f"{CKAN_BASE}/group_list"
GROUP_SHOW_URL = f"{CKAN_BASE}/group_show"

# Well-known datasets
DATASET_SINESP = "sistema-nacional-de-estatisticas-de-seguranca-publica"
DATASET_INFOPEN = "infopen-levantamento-nacional-de-informacoes-penitenciarias"

# Organizações relevantes para segurança pública
ORGS_SEGURANCA: dict[str, str] = {
    "senasp": "Secretaria Nacional de Segurança Pública",
    "depen": "Departamento Penitenciário Nacional",
    "dpf": "Departamento de Polícia Federal",
    "dprf": "Departamento de Polícia Rodoviária Federal",
}

# Grupos temáticos
GRUPOS: dict[str, str] = {
    "seguranca-publica": "Segurança Pública",
    "consumidor": "Consumidor",
    "justica-e-legislacao": "Justiça e Legislação",
    "combate-as-drogas": "Combate às Drogas",
    "estrangeiros": "Estrangeiros",
    "dados-em-destaque": "Dados em Destaque",
    "arquivos-e-memoria": "Arquivos e Memória",
}
