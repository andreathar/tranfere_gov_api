"""HTTP client for the Meta Ad Library API (Biblioteca de Anúncios).

Endpoints:
    - GET /ads_archive — busca anúncios na biblioteca (único endpoint)

Nota: A Graph API espera arrays como strings no formato "['valor']"
(aspas simples, não JSON). delivery_by_region é apenas campo de resposta,
não filtro de busca — a filtragem regional é feita pós-busca.
"""

from __future__ import annotations

import os
from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    ADS_ARCHIVE_URL,
    BUSCA_PALAVRAS,
    CAMPOS_ANUNCIO_POLITICO,
    LIMITE_PADRAO,
    TIPO_POLITICO,
)
from .schemas import RespostaAnuncios


def _get_access_token() -> str:
    """Retrieve Meta access token from environment.

    Supports both user tokens and app tokens (APP_ID|APP_SECRET).
    Checks META_AD_LIBRARY_TOKEN first, then META_ACCESS_TOKEN.
    """
    token = os.environ.get("META_AD_LIBRARY_TOKEN") or os.environ.get("META_ACCESS_TOKEN") or ""
    if not token:
        msg = (
            "Token da Meta não configurado. "
            "Defina META_ACCESS_TOKEN ou META_AD_LIBRARY_TOKEN no ambiente."
        )
        raise RuntimeError(msg)
    return token


def _format_list_param(values: list[str]) -> str:
    """Format a list as Graph API array parameter.

    The Graph API expects arrays as "['value1','value2']" (single quotes),
    NOT JSON format with double quotes.

    Args:
        values: List of string values.

    Returns:
        String in format "['val1','val2']".
    """
    items = ",".join(f"'{v}'" for v in values)
    return f"[{items}]"


async def buscar_anuncios(
    *,
    search_terms: str = "",
    search_page_ids: list[str] | None = None,
    ad_type: str = TIPO_POLITICO,
    ad_reached_countries: list[str] | None = None,
    ad_active_status: str | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    bylines: list[str] | None = None,
    estimated_audience_size_min: int | None = None,
    estimated_audience_size_max: int | None = None,
    languages: list[str] | None = None,
    media_type: str | None = None,
    publisher_platforms: list[str] | None = None,
    search_type: str = BUSCA_PALAVRAS,
    unmask_removed_content: bool = False,
    fields: str = CAMPOS_ANUNCIO_POLITICO,
    limit: int = LIMITE_PADRAO,
) -> RespostaAnuncios:
    """Search ads in the Meta Ad Library.

    Args:
        search_terms: Termos de busca (max 100 chars). Espaço = AND.
        search_page_ids: IDs de páginas do Facebook (até 10).
        ad_type: Tipo de anúncio (POLITICAL_AND_ISSUE_ADS, ALL, etc.).
        ad_reached_countries: Países ISO (padrão: ['BR']).
        ad_active_status: Status (ACTIVE, INACTIVE, ALL).
        ad_delivery_date_min: Data mínima de veiculação (YYYY-mm-dd).
        ad_delivery_date_max: Data máxima de veiculação (YYYY-mm-dd).
        bylines: Financiadores (quem pagou pelo anúncio).
        estimated_audience_size_min: Tamanho mínimo da audiência estimada.
        estimated_audience_size_max: Tamanho máximo da audiência estimada.
        languages: Idiomas (ISO 639-1).
        media_type: Tipo de mídia (ALL, IMAGE, MEME, VIDEO, NONE).
        publisher_platforms: Plataformas (FACEBOOK, INSTAGRAM, etc.).
        search_type: Tipo de busca (KEYWORD_UNORDERED, KEYWORD_EXACT_PHRASE).
        unmask_removed_content: Revelar conteúdo removido por violação.
        fields: Campos a retornar na resposta.
        limit: Número máximo de resultados por página.

    Returns:
        Resposta paginada com anúncios.
    """
    countries = ad_reached_countries or ["BR"]

    params: dict[str, Any] = {
        "access_token": _get_access_token(),
        "ad_type": ad_type,
        "ad_reached_countries": _format_list_param(countries),
        "search_type": search_type,
        "fields": fields,
        "limit": min(limit, 500),
    }

    if search_terms:
        params["search_terms"] = search_terms
    if search_page_ids:
        params["search_page_ids"] = _format_list_param(search_page_ids)
    if ad_active_status:
        params["ad_active_status"] = ad_active_status
    if ad_delivery_date_min:
        params["ad_delivery_date_min"] = ad_delivery_date_min
    if ad_delivery_date_max:
        params["ad_delivery_date_max"] = ad_delivery_date_max
    if bylines:
        params["bylines"] = _format_list_param(bylines)
    if estimated_audience_size_min is not None:
        params["estimated_audience_size_min"] = estimated_audience_size_min
    if estimated_audience_size_max is not None:
        params["estimated_audience_size_max"] = estimated_audience_size_max
    if languages:
        params["languages"] = _format_list_param(languages)
    if media_type:
        params["media_type"] = media_type
    if publisher_platforms:
        params["publisher_platforms"] = _format_list_param(publisher_platforms)
    if unmask_removed_content:
        params["unmask_removed_content"] = "true"

    data: dict[str, Any] = await http_get(ADS_ARCHIVE_URL, params=params)
    return RespostaAnuncios(**data)


async def buscar_proxima_pagina(next_url: str) -> RespostaAnuncios:
    """Follow a pagination cursor URL.

    Args:
        next_url: URL completa da próxima página (campo paging.next).

    Returns:
        Resposta paginada com anúncios.
    """
    data: dict[str, Any] = await http_get(next_url)
    return RespostaAnuncios(**data)
