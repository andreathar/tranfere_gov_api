"""Static reference data for the DENASUS feature.

Resources are read-only data sources that clients can pull.
They provide context to LLMs without requiring tool calls.
"""

from __future__ import annotations

import json

from .constants import INFO_SNA, TIPOS_ATIVIDADE


def sobre_denasus() -> str:
    """Informações sobre o DENASUS e o Sistema Nacional de Auditoria do SUS."""
    return json.dumps(INFO_SNA, ensure_ascii=False, indent=2)


def tipos_atividade() -> str:
    """Tipos de atividades de auditoria realizadas pelo DENASUS."""
    return json.dumps(TIPOS_ATIVIDADE, ensure_ascii=False, indent=2)
