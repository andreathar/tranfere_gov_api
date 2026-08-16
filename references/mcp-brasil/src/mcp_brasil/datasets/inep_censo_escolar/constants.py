"""Constants for the inep_censo_escolar dataset feature."""

from __future__ import annotations

ANO_COBERTURA = 2023
ZIP_URL = (
    f"https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ANO_COBERTURA}.zip"
)
# Member inside the ZIP that holds the schools master file.
ZIP_MEMBER = f"microdados_ed_basica_{ANO_COBERTURA}.csv"

# TP_DEPENDENCIA
DEPENDENCIAS = {1: "Federal", 2: "Estadual", 3: "Municipal", 4: "Privada"}

# TP_LOCALIZACAO
LOCALIZACOES = {1: "Urbana", 2: "Rural"}

# TP_SITUACAO_FUNCIONAMENTO
SITUACOES = {1: "Em atividade", 2: "Paralisada", 3: "Extinta (no ano)", 4: "Nova"}

# Colunas permitidas em valores_distintos
COLUNAS_DISTINCT_PERMITIDAS: frozenset[str] = frozenset(
    {
        "SG_UF",
        "NO_UF",
        "NO_REGIAO",
        "TP_DEPENDENCIA",
        "TP_LOCALIZACAO",
        "TP_SITUACAO_FUNCIONAMENTO",
        "NO_MUNICIPIO",
    }
)
