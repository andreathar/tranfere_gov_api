"""HTTP client for the Fórum Brasileiro de Segurança Pública DSpace API.

Base URL: https://publicacoes.forumseguranca.org.br/server/api
Auth: None required
Response format: HAL+JSON (DSpace 7+)
Pagination: page/size (0-indexed pages)
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import COMMUNITIES_URL, DEFAULT_PAGE_SIZE, ITEM_URL, MAX_PAGE_SIZE, SEARCH_URL
from .schemas import Comunidade, Publicacao, ResultadoBusca


def _get_metadata_value(metadata: dict[str, Any], key: str) -> str | None:
    """Extract first value from DSpace Dublin Core metadata field."""
    values = metadata.get(key, [])
    if isinstance(values, list) and values:
        val: str | None = values[0].get("value")
        return val
    return None


def _get_metadata_values(metadata: dict[str, Any], key: str) -> list[str]:
    """Extract all values from a multi-valued DSpace metadata field."""
    values = metadata.get(key, [])
    if isinstance(values, list):
        return [v.get("value", "") for v in values if isinstance(v, dict) and v.get("value")]
    return []


def _parse_item(item: dict[str, Any]) -> Publicacao:
    """Parse a DSpace item into a Publicacao."""
    metadata = item.get("metadata", {})

    # Authors: try dc.contributor.author1 first, then dc.contributor.author
    autores = _get_metadata_values(metadata, "dc.contributor.author1")
    if not autores:
        autores = _get_metadata_values(metadata, "dc.contributor.author")

    return Publicacao(
        uuid=item.get("uuid"),
        titulo=item.get("name") or _get_metadata_value(metadata, "dc.title"),
        autores=autores,
        resumo=_get_metadata_value(metadata, "dc.description.resumo")
        or _get_metadata_value(metadata, "dc.description.abstract")
        or _get_metadata_value(metadata, "dc.description"),
        data_publicacao=_get_metadata_value(metadata, "dc.date.issued"),
        editora=_get_metadata_value(metadata, "dc.publisher"),
        assuntos=_get_metadata_values(metadata, "dc.subject"),
        uri=_get_metadata_value(metadata, "dc.identifier.uri"),
        handle=item.get("handle"),
        issn=_get_metadata_value(metadata, "dc.identifier.issn"),
    )


def _parse_search_response(data: dict[str, Any]) -> ResultadoBusca:
    """Parse a DSpace discover search HAL+JSON response."""
    embedded = data.get("_embedded", {})
    search_result = embedded.get("searchResult", {})
    page_info = search_result.get("page", {})

    objects = search_result.get("_embedded", {}).get("objects", [])
    publicacoes: list[Publicacao] = []
    for obj in objects:
        indexable = obj.get("_embedded", {}).get("indexableObject", {})
        if indexable.get("type") == "item":
            publicacoes.append(_parse_item(indexable))

    return ResultadoBusca(
        total=page_info.get("totalElements", 0),
        pagina=page_info.get("number", 0),
        total_paginas=page_info.get("totalPages", 0),
        publicacoes=publicacoes,
    )


async def buscar_publicacoes(
    query: str,
    limite: int = DEFAULT_PAGE_SIZE,
    pagina: int = 0,
) -> ResultadoBusca:
    """Search publications by keyword.

    Args:
        query: Search terms (e.g. 'feminicídio', 'violência policial').
        limite: Results per page (max 50).
        pagina: Page number (0-indexed).

    Returns:
        Paginated search results.
    """
    size = min(limite, MAX_PAGE_SIZE)
    params: dict[str, str] = {
        "query": query,
        "size": str(size),
        "page": str(pagina),
    }
    data: dict[str, Any] = await http_get(SEARCH_URL, params=params)
    return _parse_search_response(data)


async def listar_comunidades() -> list[Comunidade]:
    """List all thematic communities in the repository.

    Returns:
        List of communities with item counts.
    """
    params: dict[str, str] = {"size": "20"}
    data: dict[str, Any] = await http_get(COMMUNITIES_URL, params=params)

    embedded = data.get("_embedded", {})
    communities_raw = embedded.get("communities", [])

    comunidades: list[Comunidade] = []
    for c in communities_raw:
        nome = c.get("name", "")
        if not nome:
            continue
        metadata = c.get("metadata", {})
        descricao = _get_metadata_value(metadata, "dc.description")
        comunidades.append(
            Comunidade(
                uuid=c.get("uuid"),
                nome=nome,
                descricao=descricao,
                quantidade_itens=c.get("archivedItemsCount", 0),
                handle=c.get("handle"),
            )
        )
    return comunidades


async def detalhar_publicacao(uuid: str) -> Publicacao | None:
    """Get full details of a publication by UUID.

    Args:
        uuid: DSpace item UUID.

    Returns:
        Publication details or None if not found.
    """
    url = f"{ITEM_URL}/{uuid}"
    data: dict[str, Any] = await http_get(url)
    if not data or not data.get("uuid"):
        return None
    return _parse_item(data)


async def buscar_por_tema(
    comunidade_uuid: str,
    query: str = "",
    limite: int = DEFAULT_PAGE_SIZE,
    pagina: int = 0,
) -> ResultadoBusca:
    """Search publications within a specific thematic community.

    Args:
        comunidade_uuid: UUID of the community to search in.
        query: Search terms (optional, empty returns all items).
        limite: Results per page (max 50).
        pagina: Page number (0-indexed).

    Returns:
        Paginated search results scoped to the community.
    """
    size = min(limite, MAX_PAGE_SIZE)
    params: dict[str, str] = {
        "scope": comunidade_uuid,
        "query": query or "*",
        "size": str(size),
        "page": str(pagina),
    }
    data: dict[str, Any] = await http_get(SEARCH_URL, params=params)
    return _parse_search_response(data)
