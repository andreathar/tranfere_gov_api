"""Resource functions for the Atlas da Violência feature."""

from __future__ import annotations

import json

from .constants import ABRANGENCIAS, TEMAS_CONHECIDOS


def temas_atlas() -> str:
    """Catálogo de temas disponíveis no Atlas da Violência."""
    return json.dumps(TEMAS_CONHECIDOS, ensure_ascii=False, indent=2)


def abrangencias_atlas() -> str:
    """Níveis de abrangência geográfica para consultas."""
    return json.dumps(ABRANGENCIAS, ensure_ascii=False, indent=2)
