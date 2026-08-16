"""Tests for the SPU-Imoveis prompts."""

from __future__ import annotations

import pytest
from fastmcp import Client

from mcp_brasil.data.spu_imoveis.prompts import patrimonio_municipio, patrimonio_orgao
from mcp_brasil.data.spu_imoveis.server import mcp


def test_patrimonio_orgao_references_tool() -> None:
    out = patrimonio_orgao("MEC")
    assert "buscar_imoveis_spu" in out
    assert "MEC" in out


def test_patrimonio_municipio_includes_params() -> None:
    out = patrimonio_municipio("RJ", "Rio de Janeiro")
    assert "Rio de Janeiro" in out
    assert "RJ" in out
    assert "buscar_imoveis_spu" in out


@pytest.mark.asyncio
async def test_prompts_registered() -> None:
    async with Client(mcp) as c:
        prompts = await c.list_prompts()
        names = {p.name for p in prompts}
        assert "patrimonio_orgao" in names
        assert "patrimonio_municipio" in names
