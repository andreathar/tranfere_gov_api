"""Static reference data for the ANVISA feature.

Resources are read-only data sources that clients can pull.
They provide context to LLMs without requiring tool calls.
"""

from __future__ import annotations

import json

from .constants import CATEGORIAS_MEDICAMENTO, SECOES_BULA, TIPOS_BULA


def categorias_regulatorias() -> str:
    """Categorias regulatórias de medicamentos definidas pela ANVISA."""
    data = [{"codigo": k, "descricao": v} for k, v in CATEGORIAS_MEDICAMENTO.items()]
    return json.dumps(data, ensure_ascii=False, indent=2)


def tipos_bula() -> str:
    """Tipos de bula de medicamento (paciente e profissional)."""
    data = [{"tipo": k, "descricao": v} for k, v in TIPOS_BULA.items()]
    return json.dumps(data, ensure_ascii=False, indent=2)


def secoes_bula() -> str:
    """Seções padrão de uma bula de medicamento no Brasil."""
    return json.dumps(SECOES_BULA, ensure_ascii=False, indent=2)
