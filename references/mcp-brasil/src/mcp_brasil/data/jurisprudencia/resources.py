"""Resources for the Jurisprudência feature — static reference data for LLM context."""

from __future__ import annotations

import json

from .constants import OPERADORES_BUSCA, TRIBUNAIS_SUPERIORES


def tribunais_superiores() -> str:
    """Informações sobre os tribunais superiores (STF, STJ, TST)."""
    return json.dumps(TRIBUNAIS_SUPERIORES, ensure_ascii=False)


def operadores_busca() -> str:
    """Operadores de busca disponíveis por tribunal para pesquisa jurisprudencial."""
    return json.dumps(OPERADORES_BUSCA, ensure_ascii=False)


def info_api() -> str:
    """Informações gerais sobre as APIs de jurisprudência."""
    data = {
        "nome": "APIs de Jurisprudência — STF, STJ e TST",
        "tribunais": ["STF", "STJ", "TST"],
        "autenticacao": "Não requer autenticação",
        "formato": "REST (JSON) — APIs não oficiais (reverse-engineered)",
        "tipos_busca": [
            "Acórdãos (decisões colegiadas)",
            "Súmulas (enunciados vinculantes e não vinculantes)",
            "Repercussão Geral (temas de alcance geral — STF)",
            "Informativos (resumos periódicos de decisões)",
        ],
        "observacao": (
            "As APIs são baseadas nos sistemas de pesquisa dos tribunais. "
            "Resultados podem variar conforme disponibilidade dos serviços."
        ),
    }
    return json.dumps(data, ensure_ascii=False)
