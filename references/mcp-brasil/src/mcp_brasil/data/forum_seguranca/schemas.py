"""Pydantic schemas for the Fórum Brasileiro de Segurança Pública feature."""

from __future__ import annotations

from pydantic import BaseModel


class Publicacao(BaseModel):
    """Uma publicação do repositório DSpace."""

    uuid: str | None = None
    titulo: str | None = None
    autores: list[str] = []
    resumo: str | None = None
    data_publicacao: str | None = None
    editora: str | None = None
    assuntos: list[str] = []
    uri: str | None = None
    handle: str | None = None
    issn: str | None = None


class Comunidade(BaseModel):
    """Uma comunidade temática do repositório."""

    uuid: str | None = None
    nome: str | None = None
    descricao: str | None = None
    quantidade_itens: int = 0
    handle: str | None = None


class ResultadoBusca(BaseModel):
    """Resultado paginado de uma busca no repositório."""

    total: int = 0
    pagina: int = 0
    total_paginas: int = 0
    publicacoes: list[Publicacao] = []
