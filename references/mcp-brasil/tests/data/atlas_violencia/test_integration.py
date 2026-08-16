"""Integration tests for the Atlas da Violência feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.atlas_violencia.schemas import Serie, Tema, ValorSerie
from mcp_brasil.data.atlas_violencia.server import mcp

CLIENT_MODULE = "mcp_brasil.data.atlas_violencia.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_7_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "listar_temas_violencia",
                "listar_series_tema",
                "consultar_valores_violencia",
                "consultar_valores_por_regiao",
                "consultar_serie_violencia",
                "listar_fontes_violencia",
                "listar_metadados_violencia",
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
                "data://temas-atlas-violencia",
                "data://abrangencias-atlas",
            }
            assert expected.issubset(uris), f"Missing: {expected - uris}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_listar_temas_e2e(self) -> None:
        mock_data = [Tema(id=1, titulo="Homicidios")]
        with patch(
            f"{CLIENT_MODULE}.listar_temas", new_callable=AsyncMock, return_value=mock_data
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("listar_temas_violencia", {})
                assert "Homicidios" in result.data

    @pytest.mark.asyncio
    async def test_listar_series_e2e(self) -> None:
        mock_data = [Serie(id=328, titulo="Homicidios")]
        with patch(
            f"{CLIENT_MODULE}.listar_series", new_callable=AsyncMock, return_value=mock_data
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("listar_series_tema", {"tema_id": 1})
                assert "328" in result.data

    @pytest.mark.asyncio
    async def test_consultar_valores_e2e(self) -> None:
        mock_data = [ValorSerie(cod="33", sigla="RJ", valor="5000", periodo="2023-01-15")]
        with patch(
            f"{CLIENT_MODULE}.consultar_valores", new_callable=AsyncMock, return_value=mock_data
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "consultar_valores_violencia",
                    {"serie_id": 328, "abrangencia": 3},
                )
                assert "RJ" in result.data
                assert "5000" in result.data
