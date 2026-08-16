"""Pydantic schemas for the TCE-SC feature."""

from __future__ import annotations

from pydantic import BaseModel


class Municipio(BaseModel):
    """Município de Santa Catarina."""

    codigo_municipio: int | None = None
    nome_municipio: str | None = None


class UnidadeGestora(BaseModel):
    """Unidade gestora jurisdicionada pelo TCE-SC."""

    codigo_unidade: int | None = None
    nome_unidade: str | None = None
    sigla_unidade: str | None = None
    nome_municipio: str | None = None
