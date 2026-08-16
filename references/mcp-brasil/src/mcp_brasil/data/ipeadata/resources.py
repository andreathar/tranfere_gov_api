"""Resources for IPEADATA."""

from __future__ import annotations

import json

from .constants import SERIES_POPULARES, TEMAS


def catalogo_populares() -> str:
    """Catálogo curado de séries IPEADATA mais usadas."""
    return json.dumps(SERIES_POPULARES, ensure_ascii=False)


def catalogo_temas() -> str:
    """Temas disponíveis no IPEADATA."""
    return json.dumps(TEMAS, ensure_ascii=False)
