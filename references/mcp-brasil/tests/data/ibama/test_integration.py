"""Integration tests for IBAMA."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import Client

from mcp_brasil.data.ibama import FEATURE_META
from mcp_brasil.data.ibama.constants import IBAMA_CKAN_BASE
from mcp_brasil.data.ibama.server import mcp


def test_feature_meta() -> None:
    assert FEATURE_META.name == "ibama"


@pytest.mark.asyncio
async def test_lists_tools() -> None:
    async with Client(mcp) as c:
        tools = await c.list_tools()
    assert {t.name for t in tools} >= {"listar_datasets_ibama", "buscar_datasets_ibama"}


@pytest.mark.asyncio
@respx.mock
async def test_detalhe_dataset_with_resources() -> None:
    respx.get(f"{IBAMA_CKAN_BASE}/package_show").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "title": "Fiscalização - auto de infração",
                    "notes": "Autos de infração lavrados pelo IBAMA.",
                    "resources": [
                        {
                            "name": "arquivo_autos_infracao_2024.csv",
                            "format": "CSV",
                            "url": "https://example.invalid/auto.csv",
                        }
                    ],
                },
            },
        )
    )
    async with Client(mcp) as c:
        r = await c.call_tool(
            "detalhe_dataset_ibama",
            {"package_id": "fiscalizacao-auto-de-infracao"},
        )
    data = getattr(r, "data", None) or str(r)
    assert "Fiscalização" in data
    assert "auto.csv" in data
