"""Pydantic schemas for the Atlas da Violência (IPEA) feature."""

from __future__ import annotations

from pydantic import BaseModel


class Tema(BaseModel):
    """Tema (grupo temático) do Atlas da Violência."""

    id: int
    titulo: str
    tema_id: int = 0
    tipo: int = 0


class Serie(BaseModel):
    """Série de dados dentro de um tema."""

    id: int
    titulo: str


class ValorSerie(BaseModel):
    """Ponto de dados de uma série temporal."""

    cod: str
    sigla: str
    valor: str | None = None
    periodo: str | None = None


class Fonte(BaseModel):
    """Fonte de dados do Atlas."""

    id: int
    titulo: str


class Unidade(BaseModel):
    """Unidade de medida."""

    id: int
    titulo: str


class Periodicidade(BaseModel):
    """Periodicidade dos dados."""

    id: int
    titulo: str
