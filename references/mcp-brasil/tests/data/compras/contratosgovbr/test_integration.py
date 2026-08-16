"""Integration tests for the Contratos.gov.br feature via fastmcp.Client."""

import pytest
from fastmcp import Client

from mcp_brasil.data.compras.contratosgovbr.server import mcp


@pytest.mark.asyncio
async def test_server_lists_tools() -> None:
    """All contratosgovbr tools should be registered."""
    async with Client(mcp) as c:
        tools = await c.list_tools()
    names = {t.name for t in tools}
    expected = {
        "listar_contratos_unidade",
        "consultar_contrato_id",
        "consultar_empenhos_contrato",
        "consultar_faturas_contrato",
        "consultar_historico_contrato",
        "consultar_itens_contrato",
        "consultar_terceirizados_contrato",
    }
    assert expected.issubset(names), f"Missing tools: {expected - names}"
