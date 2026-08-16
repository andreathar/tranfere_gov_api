"""Resources for the ANA feature — static reference data for LLM context.

Resources expose read-only data that LLMs can pull for context.
"""

from __future__ import annotations

import json

from .constants import TIPOS_ESTACAO


def tipos_estacao() -> str:
    """Tipos de estações hidrológicas da ANA (fluviométrica e pluviométrica)."""
    data = [
        {"codigo": codigo, "descricao": descricao} for codigo, descricao in TIPOS_ESTACAO.items()
    ]
    return json.dumps(data, ensure_ascii=False)
