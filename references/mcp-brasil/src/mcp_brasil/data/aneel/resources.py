"""Resources for ANEEL."""

from __future__ import annotations

import json

from .constants import DATASETS_CHAVE


def catalogo_datasets_chave() -> str:
    """Datasets ANEEL mais importantes (curadoria)."""
    return json.dumps(DATASETS_CHAVE, ensure_ascii=False)
