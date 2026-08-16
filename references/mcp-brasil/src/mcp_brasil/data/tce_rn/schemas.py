"""Pydantic schemas for the TCE-RN feature."""

from __future__ import annotations

from pydantic import BaseModel


class Jurisdicionado(BaseModel):
    """Entidade jurisdicionada pelo TCE-RN."""

    identificador_unidade: int | None = None
    codigo_orgao: str | None = None
    nome_orgao: str | None = None
    cnpj: str | None = None


class Despesa(BaseModel):
    """Despesa orçamentária (balanço orçamentário)."""

    descricao_categoria_economica: str | None = None
    descricao_grupo_despesa: str | None = None
    descricao_elemento_despesa: str | None = None
    valor_dotacao_inicial: float | None = None
    valor_dotacao_atualizada: float | None = None
    valor_empenho_ate_periodo: float | None = None
    valor_liquidacao_ate_periodo: float | None = None
    valor_pago_ate_periodo: float | None = None


class Receita(BaseModel):
    """Receita orçamentária (balanço orçamentário)."""

    descricao_receita: str | None = None
    cod_natureza_receita: str | None = None
    valor_previsto_inicial: float | None = None
    valor_previsto_atualizado: float | None = None
    valor_realizado_no_exercicio: float | None = None


class Licitacao(BaseModel):
    """Licitação pública registrada no TCE-RN."""

    numero_licitacao: str | None = None
    ano_licitacao: str | None = None
    modalidade: str | None = None
    tipo_objeto: str | None = None
    descricao_objeto: str | None = None
    valor_total_orcado: float | None = None
    situacao: str | None = None
    nome_jurisdicionado: str | None = None


class Contrato(BaseModel):
    """Contrato registrado no TCE-RN."""

    numero_contrato: str | None = None
    ano_contrato: int | None = None
    objeto_contrato: str | None = None
    valor_contrato: float | None = None
    nome_contratado: str | None = None
    cpf_cnpj_contratado: str | None = None
    data_inicio_vigencia: str | None = None
    data_termino_vigencia: str | None = None
