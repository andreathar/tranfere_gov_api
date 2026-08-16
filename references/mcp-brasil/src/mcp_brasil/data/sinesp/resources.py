"""Resource functions for the SINESP/MJSP CKAN feature."""

from __future__ import annotations

import json

from .constants import GRUPOS, ORGS_SEGURANCA


def organizacoes_seguranca() -> str:
    """Organizações de segurança pública no portal MJSP."""
    return json.dumps(ORGS_SEGURANCA, ensure_ascii=False, indent=2)


def grupos_tematicos() -> str:
    """Grupos temáticos do portal MJSP."""
    return json.dumps(GRUPOS, ensure_ascii=False, indent=2)
