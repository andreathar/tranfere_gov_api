"""Integration tests for the Fórum Segurança feature via fastmcp.Client."""

import pytest
from fastmcp import Client

from mcp_brasil.data.forum_seguranca.server import mcp


@pytest.mark.asyncio
async def test_server_lists_tools() -> None:
    """All Fórum Segurança tools should be registered."""
    async with Client(mcp) as c:
        tools = await c.list_tools()
    names = {t.name for t in tools}
    expected = {
        "buscar_publicacoes_seguranca",
        "listar_temas_seguranca",
        "detalhar_publicacao_seguranca",
        "buscar_por_tema_seguranca",
    }
    assert expected.issubset(names), f"Missing tools: {expected - names}"


@pytest.mark.asyncio
async def test_server_lists_resources() -> None:
    """The community catalog resource should be registered."""
    async with Client(mcp) as c:
        resources = await c.list_resources()
    uris = {str(r.uri) for r in resources}
    assert "data://catalogo-comunidades" in uris
