"""Pydantic schemas for the Contratos.gov.br API."""

from __future__ import annotations

from pydantic import BaseModel


class ContratoResumo(BaseModel):
    """Contrato resumido retornado em listagens."""

    id: int | None = None
    receita_despesa: str | None = None
    numero: str | None = None
    orgao_codigo: str | None = None
    orgao_nome: str | None = None
    unidade_codigo: str | None = None
    unidade_nome: str | None = None
    fornecedor_tipo: str | None = None
    fornecedor_cnpj_cpf: str | None = None
    fornecedor_nome: str | None = None
    tipo: str | None = None
    categoria: str | None = None
    processo: str | None = None
    objeto: str | None = None
    fundamento_legal: str | None = None
    modalidade: str | None = None
    data_assinatura: str | None = None
    data_publicacao: str | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    valor_inicial: str | None = None
    valor_global: str | None = None
    valor_parcela: str | None = None
    valor_acumulado: str | None = None
    situacao: str | None = None


class Empenho(BaseModel):
    """Empenho vinculado a um contrato."""

    id: int | None = None
    numero: str | None = None
    credor: str | None = None
    fonte_recurso: str | None = None
    programa_trabalho: str | None = None
    naturezadespesa: str | None = None
    empenhado: str | None = None
    liquidado: str | None = None
    pago: str | None = None


class Fatura(BaseModel):
    """Fatura vinculada a um contrato."""

    id: int | None = None
    numero: str | None = None
    emissao: str | None = None
    vencimento: str | None = None
    valor: str | None = None
    juros: str | None = None
    multa: str | None = None
    glosa: str | None = None
    valorliquido: str | None = None
    situacao: str | None = None


class HistoricoContrato(BaseModel):
    """Termo aditivo ou apostilamento de contrato."""

    id: int | None = None
    tipo: str | None = None
    numero: str | None = None
    fornecedor: str | None = None
    data_assinatura: str | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    valor_global: str | None = None
    situacao_contrato: str | None = None


class ItemContrato(BaseModel):
    """Item de um contrato."""

    tipo_item: str | None = None
    codigo_item: str | None = None
    descricao_item: str | None = None
    unidade: str | None = None
    quantidade: str | None = None
    valor_unitario: str | None = None
    valor_total: str | None = None


class Terceirizado(BaseModel):
    """Trabalhador terceirizado vinculado a um contrato."""

    id: int | None = None
    funcao: str | None = None
    jornada: str | None = None
    salario: str | None = None
    custo: str | None = None
    escolaridade: str | None = None
    situacao: str | None = None
