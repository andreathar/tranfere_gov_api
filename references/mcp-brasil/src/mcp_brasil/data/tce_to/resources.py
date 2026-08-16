"""Static reference data for the TCE-TO feature."""

from __future__ import annotations

import json


def endpoints_tce_to() -> str:
    """Catálogo de endpoints disponíveis no TCE-TO."""
    endpoints = [
        {
            "endpoint": "/pessoas",
            "params": "nome, codigo, pagina, tamanho",
            "descricao": "Busca pessoas com processos (requer ao menos um filtro)",
        },
        {
            "endpoint": "/processo/{numero}/{ano}",
            "descricao": "Detalhes de um processo específico",
        },
        {
            "endpoint": "/pautas",
            "params": "ordem, tamanho",
            "descricao": "Pautas de sessões das câmaras e plenário",
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
