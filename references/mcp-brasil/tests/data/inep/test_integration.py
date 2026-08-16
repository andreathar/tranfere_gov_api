"""Integration tests for the INEP feature using fastmcp.Client.

These tests verify the full pipeline: server → tools → client.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.inep.schemas import IdebUrl
from mcp_brasil.data.inep.server import mcp

CLIENT_MODULE = "mcp_brasil.data.inep.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_4_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "consultar_ideb",
                "listar_microdados_inep",
                "gerar_url_download_inep",
                "listar_indicadores_educacionais",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"

    @pytest.mark.asyncio
    async def test_tools_have_docstrings(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            for tool in tool_list:
                assert tool.description, f"Tool {tool.name} has no description"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_consultar_ideb_e2e(self) -> None:
        mock_data = [
            IdebUrl(
                nivel="regioes_ufs",
                etapa=None,
                ano=2023,
                url="https://download.inep.gov.br/ideb/resultados/divulgacao_regioes_ufs_ideb_2023.xlsx",
                tamanho_estimado="~200 KB",
            ),
        ]
        with patch(
            f"{CLIENT_MODULE}.gerar_urls_ideb",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("consultar_ideb", {"ano": 2023})
                assert "2023" in result.data
                assert "download.inep.gov.br" in result.data

    @pytest.mark.asyncio
    async def test_listar_microdados_e2e(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool("listar_microdados_inep", {})
            assert "Censo Escolar" in result.data
            assert "ENEM" in result.data or "enem" in result.data
