"""HTTP client for ANEEL (CKAN v3)."""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.ckan import package_list, package_search, package_show

from .constants import ANEEL_CKAN_BASE


async def listar_datasets() -> list[str]:
    """Lista todos os packages (datasets) do portal ANEEL."""
    return await package_list(ANEEL_CKAN_BASE)


async def buscar_datasets(query: str, rows: int = 20) -> dict[str, Any]:
    """Busca datasets por palavra-chave."""
    return await package_search(ANEEL_CKAN_BASE, query, rows)


async def detalhe_dataset(package_id: str) -> dict[str, Any]:
    """Detalhe completo de um package + recursos para download."""
    return await package_show(ANEEL_CKAN_BASE, package_id)
