"""Static reference data for the Tabua Mares feature.

Resources are read-only data sources that clients can pull.
They provide context to LLMs without requiring tool calls.

Resources are registered with data:// URIs (without the feature namespace —
mount() adds the namespace prefix automatically).
"""

from __future__ import annotations

import json

from .constants import ESTADOS_COSTEIROS


def estados_costeiros() -> str:
    """Lista dos 17 estados costeiros do Brasil com dados de marés disponíveis."""
    estados = [
        {"sigla": sigla.upper(), "nome": nome} for sigla, nome in sorted(ESTADOS_COSTEIROS.items())
    ]
    return json.dumps(estados, ensure_ascii=False, indent=2)
