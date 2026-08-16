"""Client for the RENAME feature.

Data source: static list based on the official RENAME (Ministério da Saúde).
No HTTP calls — all data is embedded in constants.py.
"""

from __future__ import annotations

from .constants import GRUPOS_TERAPEUTICOS, MEDICAMENTOS_RENAME
from .schemas import MedicamentoRename


def _parse_medicamento(raw: dict[str, str | bool]) -> MedicamentoRename:
    """Parse a medication dict from constants into a MedicamentoRename model."""
    return MedicamentoRename(
        nome=str(raw["nome"]),
        principio_ativo=str(raw["principio_ativo"]),
        apresentacao=str(raw["apresentacao"]),
        grupo=str(raw["grupo"]),
        via=str(raw["via"]),
        disponivel_ubs=bool(raw.get("disponivel_ubs", True)),
    )


def buscar_medicamento(nome: str) -> list[MedicamentoRename]:
    """Search RENAME medications by name or active ingredient.

    Args:
        nome: Full or partial name to search (case-insensitive).
    """
    nome_lower = nome.lower()
    return [
        _parse_medicamento(med)
        for med in MEDICAMENTOS_RENAME
        if nome_lower in str(med["nome"]).lower()
        or nome_lower in str(med["principio_ativo"]).lower()
    ]


def listar_por_grupo(grupo: str) -> list[MedicamentoRename]:
    """List medications by therapeutic group.

    Args:
        grupo: Therapeutic group name (case-insensitive partial match).
    """
    grupo_lower = grupo.lower()
    return [
        _parse_medicamento(med)
        for med in MEDICAMENTOS_RENAME
        if grupo_lower in str(med["grupo"]).lower()
    ]


def verificar_disponibilidade_sus(nome: str) -> list[MedicamentoRename]:
    """Check if a medication is in the RENAME (available in SUS).

    Args:
        nome: Medication name or active ingredient.
    """
    return buscar_medicamento(nome)


def listar_grupos() -> list[str]:
    """Return all therapeutic groups in the RENAME."""
    return GRUPOS_TERAPEUTICOS


def listar_todos() -> list[MedicamentoRename]:
    """Return all medications in the RENAME catalog."""
    return [_parse_medicamento(med) for med in MEDICAMENTOS_RENAME]
