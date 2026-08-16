"""Static reference data for the TCE-SC feature."""

from __future__ import annotations

import json


def endpoints_tce_sc() -> str:
    """Catálogo de endpoints disponíveis no TCE-SC."""
    endpoints = [
        {
            "endpoint": "municipios.php",
            "descricao": "Lista de municípios de SC com código IBGE (295 municípios)",
        },
        {
            "endpoint": "unidades-gestoras.php",
            "descricao": "Unidades gestoras com código, nome, sigla e município (~2768 unidades)",
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
