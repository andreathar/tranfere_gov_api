"""Integration tests for the TCE-RJ feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tce_rj.schemas import (
    LicitacaoResultado,
    ObraParalisada,
)
from mcp_brasil.data.tce_rj.server import mcp

CLIENT_MODULE = "mcp_brasil.data.tce_rj.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_7_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_licitacoes",
                "buscar_contratos_municipio",
                "buscar_compras_diretas",
                "buscar_obras_paralisadas",
                "buscar_penalidades",
                "buscar_prestacao_contas",
                "buscar_concessoes",
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
    async def test_endpoints_disponiveis_resource(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://endpoints-disponiveis" in uris, f"URIs: {uris}"

    @pytest.mark.asyncio
    async def test_endpoints_disponiveis_content(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("data://endpoints-disponiveis")
            text = content[0].text if isinstance(content, list) else str(content)
            assert "Licitações" in text
            assert "Contratos Municipais" in text
            assert "Obras Paralisadas" in text


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_analisar_municipio_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analisar_municipio_rj" in names, f"Prompts: {names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_licitacoes_e2e(self) -> None:
        mock_data = LicitacaoResultado(total=0, licitacoes=[])
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_licitacoes", {})
                assert "Nenhuma licitação" in result.data

    @pytest.mark.asyncio
    async def test_buscar_obras_paralisadas_e2e(self) -> None:
        mock_data = [
            ObraParalisada(
                nome="Construção de escola",
                ente="NITEROI",
                valor_total_contrato=2000000.0,
            ),
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_obras_paralisadas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_obras_paralisadas", {})
                assert "Construção de escola" in result.data
