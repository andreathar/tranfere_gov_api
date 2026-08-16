"""Pydantic schemas for the TCE-RS feature."""

from __future__ import annotations

from pydantic import BaseModel


class Municipio(BaseModel):
    """Município do Rio Grande do Sul."""

    codigo: int | None = None
    nome: str | None = None
    uf: str | None = None
    codigo_ibge: int | None = None


class IndiceEducacao(BaseModel):
    """Índice de aplicação em educação de um município do RS."""

    ano: int | None = None
    codigo_orgao: int | None = None
    nome_orgao: str | None = None
    valor_despesa: float | None = None
    valor_receita: float | None = None
    indice: float | None = None


class IndiceSaude(BaseModel):
    """Índice de aplicação em saúde de um município do RS."""

    ano: int | None = None
    codigo_orgao: int | None = None
    nome_orgao: str | None = None
    valor_despesa: float | None = None
    valor_receita: float | None = None
    indice: float | None = None


class GestaoFiscal(BaseModel):
    """Dados de gestão fiscal (LRF) do poder executivo municipal do RS."""

    ano: int | None = None
    codigo_orgao: int | None = None
    nome_orgao: str | None = None
    receita_corrente_liquida: float | None = None
    despesa_pessoal: float | None = None
    divida_consolidada: float | None = None
    operacoes_credito: float | None = None
    receita_mde: float | None = None
    despesa_mde: float | None = None
    receita_asps: float | None = None
    despesa_asps: float | None = None


class Dataset(BaseModel):
    """Dataset do portal CKAN do TCE-RS."""

    nome: str | None = None
    titulo: str | None = None
    grupo: str | None = None
    notas: str | None = None
    url: str | None = None
    num_recursos: int | None = None
