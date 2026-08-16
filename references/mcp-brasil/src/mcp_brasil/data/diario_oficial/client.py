"""HTTP client for the Querido Diário API.

Endpoints:
    - /gazettes?querystring=...          → buscar_diarios (multi-território)
    - /gazettes/{territory_id}?...       → buscar_diarios (município único)
    - /cities?city_name=...              → buscar_cidades
    - /cities                            → listar_cidades
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_brasil._shared.http_client import http_get
from mcp_brasil.exceptions import HttpClientError

from .constants import CITIES_URL, DEFAULT_PAGE_SIZE, GAZETTES_URL
from .schemas import (
    CidadeQueridoDiario,
    DiarioOficial,
    DiarioResultado,
)

logger = logging.getLogger(__name__)


async def buscar_diarios(
    querystring: str,
    territory_ids: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    offset: int = 0,
    size: int = DEFAULT_PAGE_SIZE,
    excerpt_size: int = 500,
    number_of_excerpts: int = 3,
    is_exact_search: bool = True,
    sort_by: str = "relevance",
) -> DiarioResultado:
    """Search gazettes by keyword with advanced filtering.

    Supports multi-territory search via territory_ids list,
    configurable excerpt size, exact/fuzzy search, and sorting.
    """
    params: dict[str, str] = {
        "querystring": querystring,
        "offset": str(offset),
        "size": str(size),
        "excerpt_size": str(excerpt_size),
        "number_of_excerpts": str(number_of_excerpts),
    }

    if not is_exact_search:
        params["pre_tags"] = ""
        params["post_tags"] = ""

    if territory_ids:
        params["territory_ids"] = ",".join(territory_ids)

    if since:
        params["since"] = since
    if until:
        params["until"] = until

    if sort_by != "relevance":
        params["sort_by"] = sort_by

    try:
        data: dict[str, Any] = await http_get(GAZETTES_URL, params=params)
    except HttpClientError as exc:
        logger.warning("Querido Diário API error for '%s': %s", querystring, exc)
        return DiarioResultado(total_gazettes=0, gazettes=[])

    if not data or not isinstance(data, dict):
        return DiarioResultado(total_gazettes=0, gazettes=[])

    gazettes = [DiarioOficial(**g) for g in data.get("gazettes", [])]
    return DiarioResultado(
        total_gazettes=data.get("total_gazettes", len(gazettes)),
        gazettes=gazettes,
    )


def _extract_cities(data: Any) -> list[dict[str, Any]]:
    """Extract city list from API response (handles both dict and list formats)."""
    if isinstance(data, dict):
        cities = data.get("cities", [])
        return cities if isinstance(cities, list) else []
    if isinstance(data, list):
        return data
    return []


async def buscar_cidades(nome_cidade: str) -> list[CidadeQueridoDiario]:
    """Search cities available in Querido Diário by name."""
    try:
        data = await http_get(CITIES_URL, params={"city_name": nome_cidade})
    except (HttpClientError, Exception) as exc:
        logger.warning("Querido Diário API error searching cities '%s': %s", nome_cidade, exc)
        return []

    items = _extract_cities(data)
    return [CidadeQueridoDiario(**c) for c in items]


async def listar_cidades() -> list[CidadeQueridoDiario]:
    """List all cities available in Querido Diário."""
    try:
        data = await http_get(CITIES_URL)
    except (HttpClientError, Exception) as exc:
        logger.warning("Querido Diário API error listing cities: %s", exc)
        return []

    items = _extract_cities(data)
    return [CidadeQueridoDiario(**c) for c in items]
