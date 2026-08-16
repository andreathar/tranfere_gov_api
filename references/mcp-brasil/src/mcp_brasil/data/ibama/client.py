"""HTTP client for IBAMA (CKAN v3)."""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.ckan import package_list, package_search, package_show

from .constants import IBAMA_CKAN_BASE


async def listar_datasets() -> list[str]:
    return await package_list(IBAMA_CKAN_BASE)


async def buscar_datasets(query: str, rows: int = 20) -> dict[str, Any]:
    return await package_search(IBAMA_CKAN_BASE, query, rows)


async def detalhe_dataset(package_id: str) -> dict[str, Any]:
    return await package_show(IBAMA_CKAN_BASE, package_id)
