"""Tests for the SPU-Geo prompts."""

from __future__ import annotations

import pytest
from fastmcp import Client

from mcp_brasil.data.spu_geo.prompts import analise_terreno_uniao, imoveis_em_area
from mcp_brasil.data.spu_geo.server import mcp


def test_analise_terreno_uniao_references_tool() -> None:
    out = analise_terreno_uniao(-22.9, -43.2)
    assert "consultar_ponto_spu" in out
    assert "-22.9" in out
    assert "-43.2" in out


def test_imoveis_em_area_includes_objetivo() -> None:
    out = imoveis_em_area("-43.3,-23.0,-43.1,-22.8", objetivo="auditoria")
    assert "buscar_imoveis_area_spu" in out
    assert "auditoria" in out


@pytest.mark.asyncio
async def test_prompts_registered_on_server() -> None:
    async with Client(mcp) as c:
        prompts = await c.list_prompts()
        names = {p.name for p in prompts}
        assert "analise_terreno_uniao" in names
        assert "imoveis_em_area" in names
