"""Resources for the Saúde feature — static reference data for LLM context.

Resources expose read-only data that LLMs can pull for context.
These are static/low-frequency datasets useful as grounding information.
"""

from __future__ import annotations

import json

# UF codes used by CNES/DataSUS for filtering
_UFS_CNES = [
    {"codigo": "11", "sigla": "RO", "nome": "Rondônia"},
    {"codigo": "12", "sigla": "AC", "nome": "Acre"},
    {"codigo": "13", "sigla": "AM", "nome": "Amazonas"},
    {"codigo": "14", "sigla": "RR", "nome": "Roraima"},
    {"codigo": "15", "sigla": "PA", "nome": "Pará"},
    {"codigo": "16", "sigla": "AP", "nome": "Amapá"},
    {"codigo": "17", "sigla": "TO", "nome": "Tocantins"},
    {"codigo": "21", "sigla": "MA", "nome": "Maranhão"},
    {"codigo": "22", "sigla": "PI", "nome": "Piauí"},
    {"codigo": "23", "sigla": "CE", "nome": "Ceará"},
    {"codigo": "24", "sigla": "RN", "nome": "Rio Grande do Norte"},
    {"codigo": "25", "sigla": "PB", "nome": "Paraíba"},
    {"codigo": "26", "sigla": "PE", "nome": "Pernambuco"},
    {"codigo": "27", "sigla": "AL", "nome": "Alagoas"},
    {"codigo": "28", "sigla": "SE", "nome": "Sergipe"},
    {"codigo": "29", "sigla": "BA", "nome": "Bahia"},
    {"codigo": "31", "sigla": "MG", "nome": "Minas Gerais"},
    {"codigo": "32", "sigla": "ES", "nome": "Espírito Santo"},
    {"codigo": "33", "sigla": "RJ", "nome": "Rio de Janeiro"},
    {"codigo": "35", "sigla": "SP", "nome": "São Paulo"},
    {"codigo": "41", "sigla": "PR", "nome": "Paraná"},
    {"codigo": "42", "sigla": "SC", "nome": "Santa Catarina"},
    {"codigo": "43", "sigla": "RS", "nome": "Rio Grande do Sul"},
    {"codigo": "50", "sigla": "MS", "nome": "Mato Grosso do Sul"},
    {"codigo": "51", "sigla": "MT", "nome": "Mato Grosso"},
    {"codigo": "52", "sigla": "GO", "nome": "Goiás"},
    {"codigo": "53", "sigla": "DF", "nome": "Distrito Federal"},
]


def codigos_uf_cnes() -> str:
    """Códigos IBGE de UF usados para filtrar dados no CNES/DataSUS."""
    return json.dumps(_UFS_CNES, ensure_ascii=False)


def bases_datasus() -> str:
    """Catálogo das principais bases de dados do DATASUS."""
    from .constants import BASES_DATASUS

    return json.dumps(BASES_DATASUS, ensure_ascii=False)


def doencas_sinan() -> str:
    """Lista de doenças de notificação compulsória do SINAN."""
    from .constants import DOENCAS_SINAN

    return json.dumps(DOENCAS_SINAN, ensure_ascii=False)
