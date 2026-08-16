"""Pydantic schemas for the SPU-Imoveis feature."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Imovel(BaseModel):
    """Imóvel da União (linha do patrimonio-uniao.csv)."""

    orgao_superior_sigla: str | None = None
    orgao_superior_nome: str | None = None
    orgao_sigla: str | None = None
    orgao_nome: str | None = None
    ano_mes_referencia: str | None = None
    regime_utilizacao: str | None = None
    tipo_destinacao: str | None = None
    tipo_imovel: str | None = None
    endereco: str | None = None
    municipio_nome: str | None = None
    municipio_cod_ibge: str | None = None
    uf: str | None = None
    area_terreno_m2: float | None = Field(default=None, description="Área do terreno em m²")
    area_construida_m2: float | None = None
    valor_imovel: float | None = Field(default=None, description="Valor em BRL")
    valor_aluguel: float | None = None


class ResumoOrgao(BaseModel):
    """Agregado de imóveis por órgão."""

    orgao_superior_sigla: str
    orgao_superior_nome: str
    total_imoveis: int
    area_total_m2: float = 0.0
    area_construida_total_m2: float = 0.0
    valor_total: float = 0.0


class ResumoUF(BaseModel):
    """Agregado de imóveis por UF."""

    uf: str
    total_imoveis: int
    area_total_m2: float = 0.0
    area_construida_total_m2: float = 0.0
    valor_total: float = 0.0
    valor_aluguel_total: float = 0.0


class DatasetInfo(BaseModel):
    """Metadados do dataset Raio-X patrimônio da União."""

    nome: str
    url_csv: str
    url_datapackage: str
    total_linhas: int
    meses_referencia: list[str] = Field(default_factory=list)
    ultima_atualizacao_cache: str | None = None
