"""Pydantic schemas for the RENAME feature."""

from __future__ import annotations

from pydantic import BaseModel


class MedicamentoRename(BaseModel):
    """Medicamento da RENAME (Relação Nacional de Medicamentos Essenciais)."""

    nome: str
    principio_ativo: str
    apresentacao: str
    grupo: str
    via: str
    disponivel_ubs: bool = True
