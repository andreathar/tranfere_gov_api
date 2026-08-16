"""Integration tests for IPEADATA."""

from __future__ import annotations

import pytest
from fastmcp import Client

from mcp_brasil.data.ipeadata import FEATURE_META
from mcp_brasil.data.ipeadata.server import mcp


def test_feature_meta() -> None:
    assert FEATURE_META.name == "ipeadata"
    assert FEATURE_META.requires_auth is False


@pytest.mark.asyncio
async def test_lists_tools() -> None:
    async with Client(mcp) as c:
        tools = await c.list_tools()
    names = {t.name for t in tools}
    assert "buscar_serie" in names
    assert "valores_serie" in names
    assert "metadados_serie" in names


@pytest.mark.asyncio
async def test_series_populares_offline() -> None:
    async with Client(mcp) as c:
        r = await c.call_tool("series_populares", {})
    data = getattr(r, "data", None) or str(r)
    assert "IPCA" in data
    assert "Selic" in data
