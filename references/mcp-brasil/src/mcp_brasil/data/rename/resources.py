"""Static reference data for the RENAME feature.

Resources are read-only data sources that clients can pull.
They provide context to LLMs without requiring tool calls.

Resources are registered with data:// URIs (without the feature namespace —
mount() adds the namespace prefix automatically).
"""

from __future__ import annotations

import json

from .constants import GRUPOS_TERAPEUTICOS, MEDICAMENTOS_RENAME


def catalogo_rename() -> str:
    """Catálogo completo da RENAME com todos os medicamentos essenciais."""
    return json.dumps(MEDICAMENTOS_RENAME, ensure_ascii=False, indent=2)


def grupos_terapeuticos() -> str:
    """Lista de grupos terapêuticos da RENAME."""
    return json.dumps(GRUPOS_TERAPEUTICOS, ensure_ascii=False, indent=2)
