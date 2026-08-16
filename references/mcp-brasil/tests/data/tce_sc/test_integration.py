"""Integration tests for the TCE-SC feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tce_sc.schemas import Municipio
from mcp_brasil.data.tce_sc.server import mcp

CLIENT_MODULE = "mcp_brasil.data.tce_sc.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_2_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {"listar_municipios_sc", "listar_unidades_gestoras_sc"}
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

    @pytest.mark.asyncio
    async def test_endpoints_content(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("data://endpoints")
            text = content[0].text if isinstance(content, list) else str(content)
            assert "municipios" in text
            assert "unidades-gestoras" in text


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_consultar_unidades_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "consultar_unidades_sc" in names, f"Prompts: {names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_listar_municipios_e2e(self) -> None:
        mock_data = [Municipio(codigo_municipio=420540, nome_municipio="Florianópolis")]
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("listar_municipios_sc", {})
                assert "Florianópolis" in result.data
