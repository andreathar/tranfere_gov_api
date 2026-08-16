"""Resources for the Bacen feature — catalog and reference data for LLM context.

Resources expose read-only data that LLMs can pull for context.
These give LLMs knowledge of available series without calling tools.
"""

from __future__ import annotations

import json

from .catalog import SERIES_POPULARES
from .constants import CATEGORIAS, INDICADORES_CHAVE


def catalogo_series() -> str:
    """Catálogo completo das 193 séries temporais do BCB disponíveis."""
    data = [
        {
            "codigo": s.codigo,
            "nome": s.nome,
            "categoria": s.categoria,
            "periodicidade": s.periodicidade,
        }
        for s in SERIES_POPULARES
    ]
    return json.dumps(data, ensure_ascii=False)


def categorias_series() -> str:
    """As 12 categorias de séries temporais do BCB com contagem de séries."""
    contagem: dict[str, int] = {}
    for s in SERIES_POPULARES:
        contagem[s.categoria] = contagem.get(s.categoria, 0) + 1

    data = [
        {"categoria": cat, "quantidade": contagem.get(cat, 0)}
        for cat in CATEGORIAS
        if cat in contagem
    ]
    return json.dumps(data, ensure_ascii=False)


def indicadores_chave() -> str:
    """Os 5 indicadores econômicos principais: Selic, IPCA, IPCA 12m, Dólar PTAX, IBC-Br."""
    return json.dumps(INDICADORES_CHAVE, ensure_ascii=False)
