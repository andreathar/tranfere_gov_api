"""Resources for the TSE feature — static reference data for LLM context."""

from __future__ import annotations

import json

from .constants import CARGOS_ELEITORAIS, TSE_API_BASE


def cargos_eleitorais() -> str:
    """Códigos de cargos eleitorais do TSE."""
    return json.dumps(CARGOS_ELEITORAIS, ensure_ascii=False)


def info_api() -> str:
    """Informações gerais sobre a API do TSE (DivulgaCandContas)."""
    data = {
        "nome": "API DivulgaCandContas — Tribunal Superior Eleitoral",
        "url_base": TSE_API_BASE,
        "autenticacao": "Não requer autenticação",
        "formato": "REST (JSON)",
        "documentacao": "https://divulgacandcontas.tse.jus.br (não oficial)",
        "cobertura": "Eleições, candidatos, prestação de contas desde 2002",
        "observacao": "API não oficial (reverse-engineered). Sem CORS. Rate limit recomendado.",
    }
    return json.dumps(data, ensure_ascii=False)
