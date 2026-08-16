"""Resources for the INPE feature — static reference data for LLM context.

Resources expose read-only data that LLMs can pull for context.
These are static datasets useful as grounding information.
"""

from __future__ import annotations

import json

from .constants import BIOMAS, ESTADOS_AMAZONIA_LEGAL


def biomas_brasileiros() -> str:
    """Lista dos 6 biomas brasileiros monitorados pelo INPE."""
    data = [{"codigo": k, "nome": v} for k, v in BIOMAS.items()]
    return json.dumps(data, ensure_ascii=False)


def estados_amazonia_legal() -> str:
    """Lista dos 9 estados da Amazônia Legal."""
    data = [{"sigla": uf} for uf in ESTADOS_AMAZONIA_LEGAL]
    return json.dumps(data, ensure_ascii=False)
