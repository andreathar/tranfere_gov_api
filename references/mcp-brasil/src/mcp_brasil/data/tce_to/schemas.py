"""Pydantic schemas for the TCE-TO feature."""

from __future__ import annotations

from pydantic import BaseModel


class Pessoa(BaseModel):
    """Pessoa com processos no TCE-TO."""

    id: int | None = None
    nome: str | None = None
    codigo: str | None = None
    processos: list[ProcessoResumo] | None = None


class ProcessoResumo(BaseModel):
    """Resumo de processo vinculado a uma pessoa."""

    numero_ano: str | None = None
    assunto: str | None = None
    classe_assunto: str | None = None
    entidade_origem: str | None = None
    entidade_origem_municipio: str | None = None
    data_entrada: str | None = None
    departamento_atual: str | None = None


class Processo(BaseModel):
    """Processo detalhado do TCE-TO."""

    numero_ano: str | None = None
    assunto: str | None = None
    classe_assunto: str | None = None
    entidade_origem: str | None = None
    entidade_origem_municipio: str | None = None
    entidade_origem_cnpj: str | None = None
    data_entrada: str | None = None
    departamento_atual: str | None = None
    complemento: str | None = None
    distribuicao: str | None = None
    eletronico: str | None = None
    sigiloso: bool | None = None


class Pauta(BaseModel):
    """Pauta de sessão do TCE-TO."""

    data: str | None = None
    hora: str | None = None
    tipo: str | None = None
    origem: str | None = None
    url: str | None = None


# Resolve forward reference
Pessoa.model_rebuild()
