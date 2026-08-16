"""Pydantic models for INPE API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FocoQueimada(BaseModel):
    """Foco de queimada detectado por satélite."""

    id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    data_hora: str = ""
    satelite: str = ""
    municipio: str = ""
    estado: str = ""
    bioma: str = ""
    dias_sem_chuva: int | None = None
    risco_fogo: float | None = None
    frp: float | None = Field(default=None, description="Fire Radiative Power (MW)")


class AlertaDeter(BaseModel):
    """Alerta de desmatamento DETER."""

    id: str = ""
    data: str = ""
    area_km2: float = 0.0
    municipio: str = ""
    estado: str = ""
    bioma: str = ""
    classe: str = ""
    satelite: str = ""


class DadosProdes(BaseModel):
    """Dados históricos de desmatamento PRODES."""

    ano: int = 0
    bioma: str = ""
    area_km2: float = 0.0
    estado: str = ""
    municipio: str = ""


class Satelite(BaseModel):
    """Satélite de monitoramento disponível."""

    nome: str
    descricao: str = ""
