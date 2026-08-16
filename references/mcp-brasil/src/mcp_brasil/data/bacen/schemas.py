"""Pydantic schemas for the Bacen feature.

Ported from bcb-br-mcp/src/tools.ts interfaces SerieValor, SerieMetadados.
"""

from __future__ import annotations

from pydantic import BaseModel


class SerieValor(BaseModel):
    """A single data point from a BCB time series."""

    data: str
    valor: float


class SerieMetadados(BaseModel):
    """Metadata for a BCB time series."""

    codigo: int
    nome: str
    unidade: str = "Não informada"
    periodicidade: str = "Não informada"
    fonte: str = "Banco Central do Brasil"
    especial: bool = False


class ExpectativaFocus(BaseModel):
    """Expectativa do mercado do Boletim Focus."""

    indicador: str
    data: str
    data_referencia: str
    media: float | None = None
    mediana: float | None = None
    desvio_padrao: float | None = None
    minimo: float | None = None
    maximo: float | None = None
    base_calculo: int | None = None
