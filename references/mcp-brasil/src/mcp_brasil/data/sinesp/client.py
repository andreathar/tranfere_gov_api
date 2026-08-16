"""HTTP client for the SINESP/MJSP CKAN API.

Base URL: https://dados.mj.gov.br/api/3/action
Auth: None required
Response format: JSON (CKAN standard: {success: bool, result: ...})
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    GROUP_SHOW_URL,
    ORGANIZATION_LIST_URL,
    ORGANIZATION_SHOW_URL,
    PACKAGE_LIST_URL,
    PACKAGE_SEARCH_URL,
    PACKAGE_SHOW_URL,
)
from .schemas import DatasetCKAN, OrganizacaoCKAN, RecursoCKAN


def _parse_resource(raw: dict[str, Any]) -> RecursoCKAN:
    """Parse a CKAN resource dict into RecursoCKAN."""
    return RecursoCKAN(
        id=raw.get("id", ""),
        nome=raw.get("name") or raw.get("description"),
        formato=raw.get("format"),
        url=raw.get("url"),
        descricao=raw.get("description"),
        tamanho=raw.get("size"),
    )


def _parse_dataset(raw: dict[str, Any]) -> DatasetCKAN:
    """Parse a CKAN package dict into DatasetCKAN."""
    org = raw.get("organization") or {}
    recursos_raw = raw.get("resources", [])
    tags_raw = raw.get("tags", [])

    return DatasetCKAN(
        id=raw.get("id", ""),
        nome=raw.get("name", ""),
        titulo=raw.get("title"),
        descricao=raw.get("notes"),
        organizacao=org.get("title") or org.get("name"),
        licenca=raw.get("license_title"),
        tags=[t.get("display_name", t.get("name", "")) for t in tags_raw],
        num_recursos=len(recursos_raw),
        recursos=[_parse_resource(r) for r in recursos_raw],
    )


async def listar_datasets() -> list[str]:
    """List all dataset names on the MJSP CKAN portal.

    Returns:
        List of dataset slugs.
    """
    data: dict[str, Any] = await http_get(PACKAGE_LIST_URL)
    result = data.get("result", [])
    return list(result) if isinstance(result, list) else []


async def buscar_datasets(
    query: str,
    limite: int = 10,
) -> tuple[int, list[DatasetCKAN]]:
    """Search datasets by keyword.

    Args:
        query: Search terms.
        limite: Max results (default 10).

    Returns:
        Tuple of (total count, list of datasets).
    """
    params: dict[str, str] = {"q": query, "rows": str(limite)}
    data: dict[str, Any] = await http_get(PACKAGE_SEARCH_URL, params=params)
    result = data.get("result", {})
    total: int = result.get("count", 0)
    datasets = [_parse_dataset(d) for d in result.get("results", [])]
    return total, datasets


async def detalhar_dataset(dataset_id: str) -> DatasetCKAN | None:
    """Get full details of a dataset including resources.

    Args:
        dataset_id: Dataset slug or UUID.

    Returns:
        Dataset details or None.
    """
    params: dict[str, str] = {"id": dataset_id}
    data: dict[str, Any] = await http_get(PACKAGE_SHOW_URL, params=params)
    if not data.get("success"):
        return None
    return _parse_dataset(data.get("result", {}))


async def listar_organizacoes() -> list[OrganizacaoCKAN]:
    """List all organizations on the portal.

    Returns:
        List of organizations.
    """
    params: dict[str, str] = {"all_fields": "true"}
    data: dict[str, Any] = await http_get(ORGANIZATION_LIST_URL, params=params)
    result = data.get("result", [])
    return [
        OrganizacaoCKAN(
            id=o.get("id", ""),
            nome=o.get("name", ""),
            titulo=o.get("title"),
            descricao=o.get("description"),
            num_datasets=o.get("package_count", 0),
        )
        for o in result
        if isinstance(o, dict)
    ]


async def detalhar_organizacao(org_id: str) -> tuple[OrganizacaoCKAN | None, list[DatasetCKAN]]:
    """Get organization details and its datasets.

    Args:
        org_id: Organization slug.

    Returns:
        Tuple of (organization, datasets).
    """
    params: dict[str, str] = {"id": org_id, "include_datasets": "true"}
    data: dict[str, Any] = await http_get(ORGANIZATION_SHOW_URL, params=params)
    if not data.get("success"):
        return None, []
    result = data.get("result", {})
    org = OrganizacaoCKAN(
        id=result.get("id", ""),
        nome=result.get("name", ""),
        titulo=result.get("title"),
        descricao=result.get("description"),
        num_datasets=result.get("package_count", 0),
    )
    datasets = [_parse_dataset(d) for d in result.get("packages", [])]
    return org, datasets


async def listar_datasets_grupo(grupo_id: str) -> tuple[str | None, list[DatasetCKAN]]:
    """List datasets in a CKAN group.

    Args:
        grupo_id: Group slug (e.g. "seguranca-publica").

    Returns:
        Tuple of (group title, datasets).
    """
    params: dict[str, str] = {"id": grupo_id, "include_datasets": "true"}
    data: dict[str, Any] = await http_get(GROUP_SHOW_URL, params=params)
    if not data.get("success"):
        return None, []
    result = data.get("result", {})
    titulo: str | None = result.get("title")
    datasets = [_parse_dataset(d) for d in result.get("packages", [])]
    return titulo, datasets
