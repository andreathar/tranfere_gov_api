"""Integration tests for the TCE-PI feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tce_pi.schemas import Prefeitura
from mcp_brasil.data.tce_pi.server import mcp

CLIENT_MODULE = "mcp_brasil.data.tce_pi.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_5_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "listar_prefeituras_pi",
                "buscar_prefeitura_pi",
                "consultar_despesas_pi",
                "consultar_receitas_pi",
                "listar_orgaos_pi",
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
    async def test_analisar_municipio_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analisar_municipio_pi" in names, f"Prompts: {names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_listar_prefeituras_e2e(self) -> None:
        mock_data = [
            Prefeitura(id=133, nome="Teresina", codIBGE="2211001"),
        ]
        with patch(
            f"{CLIENT_MODULE}.listar_prefeituras",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("listar_prefeituras_pi", {})
                assert "Teresina" in result.data
