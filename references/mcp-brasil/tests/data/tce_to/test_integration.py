"""Integration tests for the TCE-TO feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tce_to.schemas import Pessoa, ProcessoResumo
from mcp_brasil.data.tce_to.server import mcp

CLIENT_MODULE = "mcp_brasil.data.tce_to.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_3_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_pessoas_to",
                "consultar_processo_to",
                "listar_pautas_to",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"

    @pytest.mark.asyncio
    async def test_tools_have_docstrings(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            for tool in tool_list:
                assert tool.description, f"Tool {tool.name} has no description"


class TestResourcesRegistered:
    @pytest.mark.asyncio
    async def test_endpoints_resource(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://endpoints" in uris, f"URIs: {uris}"


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_analisar_pessoa_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analisar_pessoa_to" in names, f"Prompts: {names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_pessoas_e2e(self) -> None:
        mock_data = [
            Pessoa(
                nome="JOAO DA SILVA",
                processos=[ProcessoResumo(numero_ano="1/2024")],
            ),
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_pessoas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_pessoas_to", {"nome": "JOAO"})
                assert "JOAO DA SILVA" in result.data
