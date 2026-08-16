"""Integration tests for the TCE-RN feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tce_rn.schemas import Jurisdicionado
from mcp_brasil.data.tce_rn.server import mcp

CLIENT_MODULE = "mcp_brasil.data.tce_rn.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_5_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "listar_jurisdicionados_rn",
                "buscar_despesas_rn",
                "buscar_receitas_rn",
                "buscar_licitacoes_rn",
                "buscar_contratos_rn",
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
    async def test_analisar_unidade_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analisar_unidade_rn" in names, f"Prompts: {names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_listar_jurisdicionados_e2e(self) -> None:
        mock_data = [
            Jurisdicionado(identificador_unidade=1, nome_orgao="PREFEITURA DE NATAL"),
        ]
        with patch(
            f"{CLIENT_MODULE}.listar_jurisdicionados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("listar_jurisdicionados_rn", {})
                assert "PREFEITURA DE NATAL" in result.data
