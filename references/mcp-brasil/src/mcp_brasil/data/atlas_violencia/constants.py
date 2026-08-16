"""Constants for the Atlas da Violência (IPEA) feature."""

API_BASE = "https://www.ipea.gov.br/atlasviolencia/api/v1"

# Endpoints
TEMAS_URL = f"{API_BASE}/temas"
TEMA_URL = f"{API_BASE}/tema"  # + /{id}
SERIES_URL = f"{API_BASE}/series"  # + /{tema_id}
SERIE_URL = f"{API_BASE}/serie"  # + /{id}
VALORES_URL = f"{API_BASE}/valores-series"  # + /{serie_id}/{abrangencia}
VALORES_REGIOES_URL = f"{API_BASE}/valores-series-por-regioes"  # + /{serie_id}/{abr}/{regs}
FONTES_URL = f"{API_BASE}/fontes"
FONTE_URL = f"{API_BASE}/fonte"  # + /{id}
UNIDADES_URL = f"{API_BASE}/unidades"
PERIODICIDADES_URL = f"{API_BASE}/periodicidades"

# Abrangências (geographic scope)
ABRANGENCIAS: dict[int, str] = {
    1: "País",
    2: "Região",
    3: "UF (Estado)",
    4: "Município",
}

# Temas conhecidos (cache estático para resource)
TEMAS_CONHECIDOS: dict[int, str] = {
    1: "Homicídios",
    2: "Juventude Perdida",
    3: "Violência por Raça",
    4: "Mortes Violentas por Causa Indeterminada",
    5: "Óbitos por Armas de Fogo",
    12: "Violência no Trânsito",
    15: "Óbitos por Causas Externas",
    16: "Suicídio",
    58: "Violência Física",
    59: "Violência Sexual",
    60: "Violência Psicológica",
    61: "Violência por Gênero",
}
