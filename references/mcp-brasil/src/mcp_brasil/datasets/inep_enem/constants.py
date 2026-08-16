"""Constants for the inep_enem dataset feature."""

from __future__ import annotations

ANO_COBERTURA = 2023
ZIP_URL = f"https://download.inep.gov.br/microdados/microdados_enem_{ANO_COBERTURA}.zip"
ZIP_MEMBER = f"DADOS/MICRODADOS_ENEM_{ANO_COBERTURA}.csv"

# TP_SEXO
SEXOS = {"M": "Masculino", "F": "Feminino"}

# TP_COR_RACA
COR_RACA = {
    0: "Não declarado",
    1: "Branca",
    2: "Preta",
    3: "Parda",
    4: "Amarela",
    5: "Indígena",
    6: "Não dispõe da informação",
}

# TP_ESCOLA
ESCOLA = {1: "Não respondeu", 2: "Pública", 3: "Privada"}

# TP_PRESENCA_* (CN/CH/LC/MT)
PRESENCA = {0: "Faltou", 1: "Presente", 2: "Eliminado"}

# TP_LINGUA
LINGUA = {0: "Inglês", 1: "Espanhol"}

# TP_STATUS_REDACAO
STATUS_REDACAO = {
    1: "Sem problemas",
    2: "Anulada",
    3: "Cópia Texto Motivador",
    4: "Em Branco",
    6: "Fuga ao tema",
    7: "Não atendimento tipo textual",
    8: "Texto insuficiente",
    9: "Parte desconectada",
}

COLUNAS_DISTINCT_PERMITIDAS: frozenset[str] = frozenset(
    {
        "SG_UF_PROVA",
        "SG_UF_ESC",
        "TP_SEXO",
        "TP_COR_RACA",
        "TP_ESCOLA",
        "TP_LINGUA",
        "TP_FAIXA_ETARIA",
        "TP_ST_CONCLUSAO",
    }
)
