"""Integration tests for the Jurisprudência feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.jurisprudencia.schemas import Jurisprudencia
from mcp_brasil.data.jurisprudencia.server import mcp

CLIENT_MODULE = "mcp_brasil.data.jurisprudencia.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_6_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_jurisprudencia_stf",
                "buscar_jurisprudencia_stj",
                "buscar_jurisprudencia_tst",
                "buscar_sumulas",
                "buscar_repercussao_geral",
                "buscar_informativos",
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
    async def test_all_3_resources_registered(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            expected = {
                "data://tribunais-superiores",
                "data://operadores-busca",
                "data://info-api",
            }
            assert expected.issubset(uris), f"Missing: {expected - uris}"


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_all_2_prompts_registered(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            expected = {"pesquisa_jurisprudencial", "analise_tema"}
            assert expected.issubset(names), f"Missing: {expected - names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_stf_e2e(self) -> None:
        mock_data = [
            Jurisprudencia(
                tribunal="STF",
                ementa="Teste E2E STF",
                relator="Min. E2E",
                numero_processo="RE 999",
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_stf",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "buscar_jurisprudencia_stf",
                    {"query": "teste"},
                )
                assert "Teste E2E STF" in result.data
