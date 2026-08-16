"""Constants for the IBGE feature."""

# API base URLs
IBGE_API_BASE = "https://servicodados.ibge.gov.br/api"
LOCALIDADES_URL = f"{IBGE_API_BASE}/v1/localidades"
NOMES_URL = f"{IBGE_API_BASE}/v2/censos/nomes"
AGREGADOS_URL = f"{IBGE_API_BASE}/v3/agregados"
CNAE_URL = f"{IBGE_API_BASE}/v2/cnae"
MALHAS_URL = f"{IBGE_API_BASE}/v3/malhas"

# Níveis territoriais para a API de agregados
# Formato: N{nivel}[{localidade}] ou N{nivel}[all]
NIVEIS_TERRITORIAIS = {
    "pais": "N1",
    "regiao": "N2",
    "estado": "N3",
    "mesorregiao": "N7",
    "microrregiao": "N9",
    "municipio": "N6",
}

# Agregados populares para consultas diretas
AGREGADOS_POPULARES: dict[str, dict[str, int | str]] = {
    "populacao": {
        "id": 6579,
        "variavel": 9324,
        "descricao": "População residente estimada",
    },
    "pib": {
        "id": 5938,
        "variavel": 37,
        "descricao": "Produto Interno Bruto a preços correntes",
    },
    "pib_per_capita": {
        "id": 6784,
        "variavel": 9812,
        "descricao": "PIB per capita — valores correntes (apenas nível país)",
    },
    "area_territorial": {
        "id": 1301,
        "variavel": 615,
        "descricao": "Área territorial (km²)",
    },
}
