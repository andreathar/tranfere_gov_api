"""Pydantic schemas for the TCE-PE feature."""

from __future__ import annotations

from pydantic import BaseModel


class UnidadeJurisdicionada(BaseModel):
    """Unidade jurisdicionada (prefeitura, câmara, etc.)."""

    codigo: str | None = None
    nome: str | None = None
    natureza: str | None = None
    municipio: str | None = None
    codigo_municipio: str | None = None


class Licitacao(BaseModel):
    """Licitação registrada no TCE-PE (SAGRES/LICON)."""

    numero_licitacao: str | None = None
    ano_licitacao: int | None = None
    modalidade: str | None = None
    objeto: str | None = None
    valor_estimado: float | None = None
    situacao: str | None = None
    municipio: str | None = None
    unidade_gestora: str | None = None
    id_unidade_gestora: int | None = None


class Contrato(BaseModel):
    """Contrato registrado no TCE-PE."""

    numero_contrato: str | None = None
    ano_referencia: int | None = None
    objeto: str | None = None
    valor_contrato: float | None = None
    fornecedor: str | None = None
    cpf_cnpj: str | None = None
    municipio: str | None = None
    unidade_gestora: str | None = None
    id_unidade_gestora: int | None = None


class Despesa(BaseModel):
    """Despesa municipal registrada no TCE-PE."""

    numero_empenho: str | None = None
    ano_referencia: int | None = None
    mes_referencia: int | None = None
    fornecedor: str | None = None
    cpf_cnpj: str | None = None
    historico: str | None = None
    valor_empenhado: float | None = None
    valor_liquidado: float | None = None
    valor_pago: float | None = None
    funcao: str | None = None
    elemento_despesa: str | None = None
    unidade_gestora: str | None = None
    codigo_municipio: str | None = None


class Fornecedor(BaseModel):
    """Fornecedor registrado no TCE-PE."""

    cpf_cnpj: str | None = None
    nome: str | None = None
    tipo_credor: int | None = None
