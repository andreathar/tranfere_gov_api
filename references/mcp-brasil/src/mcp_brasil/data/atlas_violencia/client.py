"""HTTP client for the Atlas da Violência (IPEA) API.

Base URL: https://www.ipea.gov.br/atlasviolencia/api/v1
Auth: None required
Response format: JSON (arrays or objects)
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    FONTES_URL,
    PERIODICIDADES_URL,
    SERIE_URL,
    SERIES_URL,
    TEMA_URL,
    TEMAS_URL,
    UNIDADES_URL,
    VALORES_REGIOES_URL,
    VALORES_URL,
)
from .schemas import Fonte, Periodicidade, Serie, Tema, Unidade, ValorSerie


async def listar_temas() -> list[Tema]:
    """List all themes from the Atlas da Violência.

    Returns:
        List of themes.
    """
    data: list[dict[str, Any]] = await http_get(TEMAS_URL)
    return [Tema(**item) for item in data]


async def consultar_tema(tema_id: int) -> Tema | None:
    """Get details of a specific theme.

    Args:
        tema_id: Theme ID.

    Returns:
        Theme details or None.
    """
    url = f"{TEMA_URL}/{tema_id}"
    data: dict[str, Any] = await http_get(url)
    if not data or "id" not in data:
        return None
    return Tema(**data)


async def listar_series(tema_id: int) -> list[Serie]:
    """List all data series for a given theme.

    Args:
        tema_id: Theme ID.

    Returns:
        List of series.
    """
    url = f"{SERIES_URL}/{tema_id}"
    data: list[dict[str, Any]] = await http_get(url)
    return [Serie(**item) for item in data]


async def consultar_serie(serie_id: int) -> Serie | None:
    """Get metadata for a specific series.

    Args:
        serie_id: Series ID.

    Returns:
        Series details or None.
    """
    url = f"{SERIE_URL}/{serie_id}"
    data: dict[str, Any] = await http_get(url)
    if not data or "id" not in data:
        return None
    return Serie(**data)


async def consultar_valores(
    serie_id: int,
    abrangencia: int,
) -> list[ValorSerie]:
    """Get time-series data values for a series.

    Args:
        serie_id: Series ID.
        abrangencia: Geographic scope (1=País, 2=Região, 3=UF, 4=Município).

    Returns:
        List of data points.
    """
    url = f"{VALORES_URL}/{serie_id}/{abrangencia}"
    data: list[dict[str, Any]] = await http_get(url)
    return [ValorSerie(**item) for item in data]


async def consultar_valores_por_regioes(
    serie_id: int,
    abrangencia: int,
    regioes: str,
) -> list[ValorSerie]:
    """Get time-series data filtered by specific regions.

    Args:
        serie_id: Series ID.
        abrangencia: Geographic scope (1=País, 2=Região, 3=UF, 4=Município).
        regioes: Comma-separated region codes (e.g. "33,35" for RJ+SP).

    Returns:
        List of filtered data points.
    """
    url = f"{VALORES_REGIOES_URL}/{serie_id}/{abrangencia}/{regioes}"
    data: list[dict[str, Any]] = await http_get(url)
    return [ValorSerie(**item) for item in data]


async def listar_fontes() -> list[Fonte]:
    """List all data sources.

    Returns:
        List of sources.
    """
    data: list[dict[str, Any]] = await http_get(FONTES_URL)
    return [Fonte(**item) for item in data]


async def listar_unidades() -> list[Unidade]:
    """List all measurement units.

    Returns:
        List of units.
    """
    data: list[dict[str, Any]] = await http_get(UNIDADES_URL)
    return [Unidade(**item) for item in data]


async def listar_periodicidades() -> list[Periodicidade]:
    """List all data periodicities.

    Returns:
        List of periodicities.
    """
    data: list[dict[str, Any]] = await http_get(PERIODICIDADES_URL)
    return [Periodicidade(**item) for item in data]
