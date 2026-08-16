"""Pydantic models for the Redator Oficial feature."""

from __future__ import annotations

from pydantic import BaseModel


class PronomeTratamento(BaseModel):
    """Pronome de tratamento oficial."""

    cargo: str
    tratamento: str
    vocativo: str
    abreviatura: str
    enderecamento: str


class ValidacaoDocumento(BaseModel):
    """Resultado da validação de um documento oficial."""

    valido: bool
    problemas: list[str]
    sugestoes: list[str]
