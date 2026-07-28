"""
Categorias de ferramentas MCP para filtragem por domínio.
"""

TOOL_CATEGORIES: dict[str, list[str]] = {
    "transferegov": ["transferegov"],
    "camara": ["camara"],
    "senado": ["senado"],
    "tse": ["tse"],
    "ibge": ["ibge"],
    "siconfi": ["siconfi"],
    "compras": ["compras", "pncp", "contratosgovbr", "dadosabertos"],
    "saude": [
        "saude", "farmacia_popular", "rename",
        "denasus", "imunizacao", "opendatasus",
    ],
    "educacao": ["inep", "fnde"],
    "seguranca": ["atlas_violencia", "forum_seguranca", "mj", "sinesp"],
    "ambiental": ["ibama", "inpe"],
    "financeiro": ["bacen", "bcb_olinda", "b3", "bndes", "bps"],
    "judicial": ["datajud", "jurisprudencia", "tcu"],
    "diario_oficial": ["diario_oficial"],
    "dashboard": [
        "list_registered_charts", "inspect_chart_health",
        "get_chart_data_summary",
    ],
    "meta": [
        "listar_features", "recomendar_tools", "planejar_consulta",
        "executar_lote", "listar_datasets_disponiveis",
    ],
}
