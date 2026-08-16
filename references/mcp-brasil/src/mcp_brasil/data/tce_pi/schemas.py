"""Pydantic models for TCE-PI data."""

from pydantic import BaseModel


class Prefeitura(BaseModel):
    """Municipality registered at TCE-PI."""

    id: int
    nome: str
    codIBGE: str | None = None
    urlPrefeitura: str | None = None
    urlCamara: str | None = None


class Gestor(BaseModel):
    """Current mayor of a municipality."""

    nome: str
    inicio_gestao: str | None = None


class DespesaAnual(BaseModel):
    """Annual expense totals for a municipality or state."""

    exercicio: int
    empenhada: float = 0
    liquidada: float = 0
    paga: float = 0


class DespesaFuncao(BaseModel):
    """Expense breakdown by government function."""

    funcao: str
    paga: float = 0


class ReceitaAnual(BaseModel):
    """Annual revenue totals for a municipality or state."""

    exercicio: int | None = None
    prevista: float = 0
    arrecadada: float = 0


class ReceitaDetalhe(BaseModel):
    """Revenue detail for a specific year."""

    categoria: str | None = None
    origem: str | None = None
    receita: str | None = None
    detalhamento: str | None = None
    prevista: float = 0
    arrecadada: float = 0


class Orgao(BaseModel):
    """State organ/entity registered at TCE-PI."""

    id: str
    nome: str
    sigla: str | None = None


class Credor(BaseModel):
    """Top creditor for a municipality."""

    nome: str
    pago: float = 0
