"""Integration tests for ANEEL."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import Client

from mcp_brasil.data.aneel import FEATURE_META
from mcp_brasil.data.aneel.constants import ANEEL_CKAN_BASE
from mcp_brasil.data.aneel.server import mcp


def test_feature_meta() -> None:
    assert FEATURE_META.name == "aneel"
    assert FEATURE_META.requires_auth is False


@pytest.mark.asyncio
async def test_lists_tools() -> None:
    async with Client(mcp) as c:
        tools = await c.list_tools()
    names = {t.name for t in tools}
    assert "listar_datasets_aneel" in names
    assert "buscar_datasets_aneel" in names


@pytest.mark.asyncio
@respx.mock
async def test_listar_datasets() -> None:
    respx.get(f"{ANEEL_CKAN_BASE}/package_list").mock(
        return_value=httpx.Response(
            200, json={"success": True, "result": ["dataset-1", "dataset-2"]}
        )
    )
    async with Client(mcp) as c:
        r = await c.call_tool("listar_datasets_aneel", {})
    data = getattr(r, "data", None) or str(r)
    assert "dataset-1" in data


@pytest.mark.asyncio
@respx.mock
async def test_buscar_datasets() -> None:
    respx.get(f"{ANEEL_CKAN_BASE}/package_search").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "count": 1,
                    "results": [
                        {
                            "name": "siga",
                            "title": "SIGA — Sistema de Informações de Geração",
                            "resources": [{"name": "siga.csv"}],
                        }
                    ],
                },
            },
        )
    )
    async with Client(mcp) as c:
        r = await c.call_tool("buscar_datasets_aneel", {"termo": "siga"})
    data = getattr(r, "data", None) or str(r)
    assert "SIGA" in data


@pytest.mark.asyncio
async def test_datasets_chave_offline() -> None:
    async with Client(mcp) as c:
        r = await c.call_tool("datasets_chave_aneel", {})
    data = getattr(r, "data", None) or str(r)
    assert "SIGA" in data
