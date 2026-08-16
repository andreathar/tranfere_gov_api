"""Shared CKAN v3 API helpers.

Used by features that expose data via CKAN (ANEEL, IBAMA, ANTT, etc.).
CKAN uses a uniform JSON envelope: ``{success: bool, result: ...}``.

Docs: https://docs.ckan.org/en/2.9/api/
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get
from mcp_brasil.exceptions import HttpClientError


async def ckan_action(
    base_url: str,
    action: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call a CKAN action endpoint and return the ``result`` payload.

    Args:
        base_url: CKAN API base, e.g. "https://dadosabertos.aneel.gov.br/api/3/action".
        action: Action name (e.g. "package_show", "package_search").
        params: Query string parameters.

    Raises:
        HttpClientError: When the CKAN envelope reports ``success=false``.
    """
    url = f"{base_url}/{action}"
    data = await http_get(url, params=params or {})
    if isinstance(data, dict):
        if data.get("success") is False:
            err = data.get("error", {})
            raise HttpClientError(f"CKAN {action} failed: {err}")
        return data.get("result")
    return data


async def package_list(base_url: str) -> list[str]:
    """Return the list of dataset (package) names on a CKAN portal."""
    result = await ckan_action(base_url, "package_list")
    return [str(x) for x in result] if isinstance(result, list) else []


async def package_show(base_url: str, package_id: str) -> dict[str, Any]:
    """Return full metadata + resources for one package."""
    result = await ckan_action(base_url, "package_show", {"id": package_id})
    return result if isinstance(result, dict) else {}


async def package_search(
    base_url: str,
    query: str = "",
    rows: int = 20,
) -> dict[str, Any]:
    """Search packages by keyword."""
    params: dict[str, Any] = {"rows": rows}
    if query:
        params["q"] = query
    result = await ckan_action(base_url, "package_search", params)
    return result if isinstance(result, dict) else {}
