"""Resources for the IBGE feature — static reference data for LLM context.

Resources expose read-only data that LLMs can pull for context.
These are static/low-frequency datasets useful as grounding information.
"""

from __future__ import annotations

import json

from .constants import NIVEIS_TERRITORIAIS

# Pre-computed static data (avoids HTTP calls for reference data)
_ESTADOS = [
    {"sigla": "AC", "nome": "Acre", "regiao": "Norte"},
    {"sigla": "AL", "nome": "Alagoas", "regiao": "Nordeste"},
    {"sigla": "AM", "nome": "Amazonas", "regiao": "Norte"},
    {"sigla": "AP", "nome": "Amapá", "regiao": "Norte"},
    {"sigla": "BA", "nome": "Bahia", "regiao": "Nordeste"},
    {"sigla": "CE", "nome": "Ceará", "regiao": "Nordeste"},
    {"sigla": "DF", "nome": "Distrito Federal", "regiao": "Centro-Oeste"},
    {"sigla": "ES", "nome": "Espírito Santo", "regiao": "Sudeste"},
    {"sigla": "GO", "nome": "Goiás", "regiao": "Centro-Oeste"},
    {"sigla": "MA", "nome": "Maranhão", "regiao": "Nordeste"},
    {"sigla": "MG", "nome": "Minas Gerais", "regiao": "Sudeste"},
    {"sigla": "MS", "nome": "Mato Grosso do Sul", "regiao": "Centro-Oeste"},
    {"sigla": "MT", "nome": "Mato Grosso", "regiao": "Centro-Oeste"},
    {"sigla": "PA", "nome": "Pará", "regiao": "Norte"},
    {"sigla": "PB", "nome": "Paraíba", "regiao": "Nordeste"},
    {"sigla": "PE", "nome": "Pernambuco", "regiao": "Nordeste"},
    {"sigla": "PI", "nome": "Piauí", "regiao": "Nordeste"},
    {"sigla": "PR", "nome": "Paraná", "regiao": "Sul"},
    {"sigla": "RJ", "nome": "Rio de Janeiro", "regiao": "Sudeste"},
    {"sigla": "RN", "nome": "Rio Grande do Norte", "regiao": "Nordeste"},
    {"sigla": "RO", "nome": "Rondônia", "regiao": "Norte"},
    {"sigla": "RR", "nome": "Roraima", "regiao": "Norte"},
    {"sigla": "RS", "nome": "Rio Grande do Sul", "regiao": "Sul"},
    {"sigla": "SC", "nome": "Santa Catarina", "regiao": "Sul"},
    {"sigla": "SE", "nome": "Sergipe", "regiao": "Nordeste"},
    {"sigla": "SP", "nome": "São Paulo", "regiao": "Sudeste"},
    {"sigla": "TO", "nome": "Tocantins", "regiao": "Norte"},
]

_REGIOES = [
    {"id": 1, "sigla": "N", "nome": "Norte", "estados": 7},
    {"id": 2, "sigla": "NE", "nome": "Nordeste", "estados": 9},
    {"id": 3, "sigla": "SE", "nome": "Sudeste", "estados": 4},
    {"id": 4, "sigla": "S", "nome": "Sul", "estados": 3},
    {"id": 5, "sigla": "CO", "nome": "Centro-Oeste", "estados": 4},
]


def estados_brasileiros() -> str:
    """Lista dos 27 estados brasileiros com sigla, nome e região."""
    return json.dumps(_ESTADOS, ensure_ascii=False)


def regioes_brasileiras() -> str:
    """As 5 macro-regiões do Brasil com quantidade de estados."""
    return json.dumps(_REGIOES, ensure_ascii=False)


def niveis_territoriais() -> str:
    """Referência dos níveis territoriais do IBGE e seus códigos de API."""
    data = [
        {"nivel": k, "codigo": v, "descricao": f"Nível {k} (código {v})"}
        for k, v in NIVEIS_TERRITORIAIS.items()
    ]
    return json.dumps(data, ensure_ascii=False)
