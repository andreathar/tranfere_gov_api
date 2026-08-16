"""Pydantic schemas for the TCE-CE feature."""

from __future__ import annotations

from pydantic import BaseModel


class Municipio(BaseModel):
    """Município cearense sob jurisdição do TCE-CE."""

    codigo_municipio: str | None = None
    nome_municipio: str | None = None


class Licitacao(BaseModel):
    """Licitação municipal no Ceará."""

    codigo_municipio: str | None = None
    numero_licitacao: str | None = None
    data_realizacao: str | None = None
    modalidade_licitacao: str | None = None
    objeto: str | None = None
    valor_orcado_estimado: float | None = None
    data_homologacao: str | None = None
    nome_responsavel_homologacao: str | None = None
    modalidade_processo_administrativo: str | None = None


class Contrato(BaseModel):
    """Contrato municipal no Ceará."""

    codigo_municipio: str | None = None
    numero_contrato: str | None = None
    data_contrato: str | None = None
    tipo_contrato: str | None = None
    modalidade_contrato: str | None = None
    objeto: str | None = None
    valor_total_contrato: float | None = None
    data_inicio_vigencia: str | None = None
    data_fim_vigencia: str | None = None


class ContratoResultado(BaseModel):
    """Resultado paginado de contratos."""

    contratos: list[Contrato] = []
    total: int = 0


class Empenho(BaseModel):
    """Nota de empenho municipal no Ceará."""

    codigo_municipio: int | None = None
    numero_empenho: str | None = None
    data_emissao: str | None = None
    valor_empenho: float | None = None
    nome_negociante: str | None = None
    numero_documento_negociante: str | None = None
    historico: str | None = None
    codigo_orgao: str | None = None
    codigo_funcao: str | None = None


class EmpenhoResultado(BaseModel):
    """Resultado paginado de empenhos."""

    empenhos: list[Empenho] = []
    total: int = 0
