"""Resources for IBAMA."""

from __future__ import annotations

import json

from .constants import DATASETS_CHAVE


def catalogo_datasets_chave() -> str:
    """Datasets IBAMA mais importantes."""
    return json.dumps(DATASETS_CHAVE, ensure_ascii=False)
