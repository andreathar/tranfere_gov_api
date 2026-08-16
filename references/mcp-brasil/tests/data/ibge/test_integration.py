"""Integration tests for the IBGE feature using fastmcp.Client.

These tests verify the full pipeline: server → tools → client (mocked HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.ibge.schemas import Estado, Municipio, Regiao
from mcp_brasil.data.ibge.server import mcp

CLIENT_MODULE = "mcp_brasil.data.ibge.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_9_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "listar_estados",
                "buscar_municipios",
                "listar_regioes",
                "consultar_nome",
                "ranking_nomes",
                "consultar_agregado",
                "listar_pesquisas",
                "obter_malha",
                "buscar_cnae",
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
                "data://estados",
                "data://regioes",
                "data://niveis-territoriais",
            }
            assert expected.issubset(uris), f"Missing: {expected - uris}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_listar_estados_e2e(self) -> None:
        mock_data = [
            Estado(
                id=35,
                sigla="SP",
                nome="São Paulo",
                regiao=Regiao(id=3, sigla="SE", nome="Sudeste"),
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.listar_estados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("listar_estados", {})
                assert "SP" in result.data
                assert "São Paulo" in result.data

    @pytest.mark.asyncio
    async def test_buscar_municipios_e2e(self) -> None:
        mock_data = [Municipio(id=2211001, nome="Teresina")]
        with patch(
            f"{CLIENT_MODULE}.listar_municipios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_municipios", {"uf": "PI"})
                assert "Teresina" in result.data

    @pytest.mark.asyncio
    async def test_consultar_agregado_no_params(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool("consultar_agregado", {})
            assert "Informe" in result.data

    @pytest.mark.asyncio
    async def test_buscar_cnae_sections(self) -> None:
        from mcp_brasil.data.ibge.schemas import CnaeSecao

        mock_data = [CnaeSecao(id="A", descricao="AGRICULTURA")]
        with patch(
            f"{CLIENT_MODULE}.listar_cnae_secoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_cnae", {})
                assert "Agricultura" in result.data
