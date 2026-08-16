"""Pydantic models for IBGE API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Regiao(BaseModel):
    """Macro-região brasileira."""

    id: int
    sigla: str
    nome: str


class Estado(BaseModel):
    """Estado brasileiro."""

    id: int
    sigla: str
    nome: str
    regiao: Regiao


class Municipio(BaseModel):
    """Município brasileiro (formato simplificado)."""

    id: int = Field(description="Código IBGE de 7 dígitos")
    nome: str


class NomeFrequencia(BaseModel):
    """Frequência de um nome em um período (endpoint /nomes/{nome})."""

    periodo: str
    frequencia: int


class NomeConsulta(BaseModel):
    """Resultado de consulta de frequência de um nome por década."""

    nome: str
    sexo: str | None = None
    localidade: str
    res: list[NomeFrequencia]


class RankingEntry(BaseModel):
    """Uma entrada no ranking de nomes (endpoint /nomes/ranking)."""

    nome: str
    frequencia: int
    ranking: int


class RankingResult(BaseModel):
    """Resultado do ranking de nomes."""

    localidade: str
    sexo: str | None = None
    res: list[RankingEntry]


class AgregadoValor(BaseModel):
    """Valor de uma variável de agregado IBGE."""

    localidade_id: str
    localidade_nome: str
    valor: str | None = None


class MalhaMetadados(BaseModel):
    """Metadados geográficos de uma malha IBGE."""

    id: str
    nivel_geografico: str
    centroide_lat: float
    centroide_lon: float
    area_km2: float | None = None
    bbox_min_lon: float | None = None
    bbox_min_lat: float | None = None
    bbox_max_lon: float | None = None
    bbox_max_lat: float | None = None


class CnaeSubclasse(BaseModel):
    """Subclasse CNAE com hierarquia completa."""

    id: str
    descricao: str
    classe_id: str = ""
    classe_descricao: str = ""
    grupo_id: str = ""
    grupo_descricao: str = ""
    divisao_id: str = ""
    divisao_descricao: str = ""
    secao_id: str = ""
    secao_descricao: str = ""
    atividades: list[str] = Field(default_factory=list)


class CnaeSecao(BaseModel):
    """Seção da CNAE (nível mais alto da hierarquia)."""

    id: str
    descricao: str
