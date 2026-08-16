"""Integration tests for the INPE feature using fastmcp.Client.

These tests verify the full pipeline: server -> tools -> client (mocked HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.inpe.schemas import FocoQueimada, Satelite
from mcp_brasil.data.inpe.server import mcp

CLIENT_MODULE = "mcp_brasil.data.inpe.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_4_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_focos_queimadas",
                "consultar_desmatamento",
                "alertas_deter",
                "dados_satelite",
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
    async def test_all_2_resources_registered(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            expected = {
                "data://biomas",
                "data://amazonia-legal",
            }
            assert expected.issubset(uris), f"Missing: {expected - uris}"


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_prompt_registered(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "monitoramento_ambiental" in names


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_focos_queimadas_e2e(self) -> None:
        mock_data = [
            FocoQueimada(
                id="1",
                latitude=-10.5,
                longitude=-50.3,
                data_hora="2024-03-15T14:30:00",
                satelite="AQUA_M-T",
                municipio="São Félix do Xingu",
                estado="PA",
                bioma="Amazônia",
                risco_fogo=0.85,
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_focos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_focos_queimadas", {"estado": "PA"})
                assert "São Félix do Xingu" in result.data

    @pytest.mark.asyncio
    async def test_dados_satelite_e2e(self) -> None:
        mock_data = [
            Satelite(nome="AQUA_M-T", descricao="EOS/NASA"),
        ]
        with patch(
            f"{CLIENT_MODULE}.listar_satelites",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("dados_satelite", {})
                assert "AQUA_M-T" in result.data

    @pytest.mark.asyncio
    async def test_buscar_focos_empty_e2e(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.buscar_focos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_focos_queimadas", {})
                assert "Nenhum foco" in result.data

    @pytest.mark.asyncio
    async def test_consultar_desmatamento_empty_e2e(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.buscar_dados_prodes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("consultar_desmatamento", {})
                assert "Nenhum dado" in result.data
