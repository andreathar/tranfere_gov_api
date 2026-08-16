"""Pydantic schemas for the Diário Oficial feature."""

from __future__ import annotations

from pydantic import BaseModel

# =============================================================================
# Querido Diário (municipal)
# =============================================================================


class DiarioOficial(BaseModel):
    """Edição de diário oficial retornada pela API."""

    territory_id: str | None = None
    territory_name: str | None = None
    state_code: str | None = None
    date: str | None = None
    edition_number: str | None = None
    is_extra_edition: bool | None = None
    url: str | None = None
    txt_url: str | None = None
    excerpts: list[str] | None = None
    highlight_texts: list[str] | None = None
    scraped_at: str | None = None
    source_text: str | None = None
    themes: list[str] | None = None
    subthemes: list[str] | None = None


class DiarioResultado(BaseModel):
    """Resultado paginado da busca de diários."""

    total_gazettes: int = 0
    gazettes: list[DiarioOficial] = []


class CidadeQueridoDiario(BaseModel):
    """Cidade disponível na base do Querido Diário."""

    territory_id: str
    territory_name: str
    state_code: str
    publication_urls: list[str] | None = None
    level: str | None = None


# =============================================================================
# DOU — Diário Oficial da União (federal)
# =============================================================================


class PublicacaoDOU(BaseModel):
    """Publicação individual no Diário Oficial da União."""

    titulo: str | None = None
    resumo: str | None = None
    url_titulo: str | None = None
    orgao: str | None = None
    tipo_publicacao: str | None = None
    secao: str | None = None
    data_publicacao: str | None = None
    edicao: str | None = None
    pagina: str | None = None
    conteudo: str | None = None
    assinante: str | None = None
    cargo_assinante: str | None = None


class ResultadoDOU(BaseModel):
    """Resultado paginado de busca no DOU."""

    total: int = 0
    publicacoes: list[PublicacaoDOU] = []
