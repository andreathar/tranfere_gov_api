"""Pydantic schemas for IPEADATA OData API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SerieMetadado(BaseModel):
    """Metadata for an IPEADATA time series."""

    model_config = ConfigDict(extra="allow")

    SERCODIGO: str
    SERNOME: str | None = None
    SERCOMENTARIO: str | None = None
    PERNOME: str | None = None
    UNINOME: str | None = None
    BASNOME: str | None = None
    TEMCODIGO: int | None = None
    FNTNOME: str | None = None
    MULNOME: str | None = None
    SERATUALIZACAO: str | None = None
    SERSTATUS: str | None = None
    SERATUALIZACAO_ANT: str | None = None


class SerieValor(BaseModel):
    """Single data point of an IPEADATA series."""

    model_config = ConfigDict(extra="allow")

    SERCODIGO: str
    VALDATA: str | None = None
    VALVALOR: float | None = None
    NIVNOME: str | None = None
    TERCODIGO: str | None = None
