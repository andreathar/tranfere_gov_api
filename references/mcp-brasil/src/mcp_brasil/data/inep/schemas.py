"""Pydantic models for INEP data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IdebUrl(BaseModel):
    """URL gerada para download de dados IDEB."""

    nivel: str = Field(description="Nível: brasil, regioes_ufs, municipios, escolas")
    etapa: str | None = Field(
        default=None, description="Etapa: anos_iniciais, anos_finais, ensino_medio"
    )
    ano: int = Field(description="Ano IDEB (bienal)")
    url: str = Field(description="URL para download do arquivo XLSX")
    tamanho_estimado: str = Field(description="Tamanho estimado do arquivo")


class MicrodadosDataset(BaseModel):
    """Informações de um dataset de microdados INEP."""

    codigo: str = Field(description="Código interno do dataset")
    nome: str = Field(description="Nome completo do dataset")
    descricao: str = Field(description="Descrição do conteúdo")
    frequencia: str = Field(description="Frequência de publicação")
    anos_disponiveis: list[int] = Field(description="Anos com dados publicados")
    url_template: str = Field(description="Template da URL (substituir {ano})")


class IndicadorEducacional(BaseModel):
    """Informações de um indicador educacional do INEP."""

    codigo: str = Field(description="Código interno do indicador")
    nome: str = Field(description="Nome do indicador")
    descricao: str = Field(description="Descrição do que mede")
