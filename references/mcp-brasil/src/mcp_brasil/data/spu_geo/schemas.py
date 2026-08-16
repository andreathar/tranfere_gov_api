"""Pydantic schemas for the SPU-Geo feature."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Camada(BaseModel):
    """Camada geoespacial do GeoPortal SPU."""

    id: str = Field(description="Identificador curto usado nas tools (ex: 'terreno_marinha')")
    typename: str = Field(description="Nome completo no GeoServer (ex: 'spunet:vw_app_...')")
    title: str
    geometry: str = Field(description="Tipo da geometria (Point, MultiPolygon, ...)")
    description: str


class FeatureGeo(BaseModel):
    """Feature retornada pelo WMS GetFeatureInfo (GeoJSON)."""

    id: str | None = None
    camada: str = Field(description="ID curto da camada (ex: 'terreno_marinha')")
    properties: dict[str, Any] = Field(default_factory=dict)
    geometry_type: str | None = None


class ImovelUniaoPonto(BaseModel):
    """Subconjunto das propriedades relevantes da camada vw_imv_localizacao_imovel_p."""

    rip: str | None = None
    rip_primitivo: str | None = None
    tipo_imovel: str | None = None
    uf: str | None = None
    municipio: str | None = None
    bairro: str | None = None
    endereco: str | None = None
    cep: str | None = None
    sistema_fonte: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class TerrenoUniao(BaseModel):
    """Subconjunto relevante das camadas de terrenos da União."""

    nome_trecho: str | None = None
    uf: str | None = None
    area_aproximada: float | None = Field(default=None, description="Área em m²")
    area_oficial: float | None = None
    etapa_demarcacao: str | None = None
    situacao_trecho: str | None = None
    data_determinacao: str | None = None
    data_aprovacao: str | None = None
    fonte: str | None = None


class ResultadoPonto(BaseModel):
    """Resultado consolidado da verificação de um ponto em múltiplas camadas."""

    lat: float
    lon: float
    camadas_encontradas: list[str] = Field(default_factory=list)
    features: list[FeatureGeo] = Field(default_factory=list)
