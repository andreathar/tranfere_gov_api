"""Pydantic schemas for the SINESP/MJSP CKAN feature."""

from __future__ import annotations

from pydantic import BaseModel


class RecursoCKAN(BaseModel):
    """Recurso (arquivo) dentro de um dataset CKAN."""

    id: str
    nome: str | None = None
    formato: str | None = None
    url: str | None = None
    descricao: str | None = None
    tamanho: int | None = None


class DatasetCKAN(BaseModel):
    """Dataset do portal CKAN do MJSP."""

    id: str
    nome: str
    titulo: str | None = None
    descricao: str | None = None
    organizacao: str | None = None
    licenca: str | None = None
    tags: list[str] = []
    num_recursos: int = 0
    recursos: list[RecursoCKAN] = []


class OrganizacaoCKAN(BaseModel):
    """Organização no portal CKAN."""

    id: str
    nome: str
    titulo: str | None = None
    descricao: str | None = None
    num_datasets: int = 0
