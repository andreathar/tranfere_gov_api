"""Integration tests for the ANA feature using fastmcp.Client.

These tests verify the full pipeline: server -> tools -> client (mocked HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.ana.schemas import DadoTelemetria, Estacao, Reservatorio
from mcp_brasil.data.ana.server import mcp

CLIENT_MODULE = "mcp_brasil.data.ana.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_3_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_estacoes",
                "consultar_telemetria",
                "monitorar_reservatorios",
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
    async def test_tipos_estacao_resource(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://tipos-estacao" in uris


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_analise_bacia_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analise_bacia" in names


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_estacoes_e2e(self) -> None:
        mock_data = [
            Estacao(
                codigo_estacao="60435000",
                nome_estacao="Itaipu",
                nome_rio="Rio Paraná",
                estado="PR",
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_estacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_estacoes", {})
                assert "Itaipu" in result.data
                assert "60435000" in result.data

    @pytest.mark.asyncio
    async def test_consultar_telemetria_e2e(self) -> None:
        mock_data = [
            DadoTelemetria(
                codigo_estacao="60435000",
                data_hora="2024-03-15 12:00:00",
                nivel=220.5,
                vazao=8500.0,
                chuva=0.0,
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.consultar_telemetria",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("consultar_telemetria", {"codigo_estacao": "60435000"})
                assert "220,50" in result.data
                assert "8.500,0" in result.data

    @pytest.mark.asyncio
    async def test_monitorar_reservatorios_e2e(self) -> None:
        mock_data = [
            Reservatorio(
                nome_reservatorio="Sobradinho",
                rio="São Francisco",
                estado="BA",
                data="2024-03-15",
                volume_util=65.3,
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.monitorar_reservatorios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("monitorar_reservatorios", {})
                assert "Sobradinho" in result.data
                assert "65,3%" in result.data

    @pytest.mark.asyncio
    async def test_buscar_estacoes_empty(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.buscar_estacoes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_estacoes", {})
                assert "Nenhuma estação" in result.data

    @pytest.mark.asyncio
    async def test_consultar_telemetria_empty(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.consultar_telemetria",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("consultar_telemetria", {"codigo_estacao": "99999"})
                assert "Nenhum dado telemétrico" in result.data
