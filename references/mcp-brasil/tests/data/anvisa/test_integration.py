"""Integration tests for the ANVISA feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.anvisa.schemas import BulaMedicamento, MedicamentoBulario
from mcp_brasil.data.anvisa.server import mcp

CLIENT_MODULE = "mcp_brasil.data.anvisa.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_10_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_medicamento",
                "buscar_por_principio_ativo",
                "consultar_bula",
                "listar_categorias",
                "informacoes_bula",
                "buscar_por_categoria",
                "buscar_genericos",
                "verificar_registro",
                "buscar_por_empresa",
                "resumo_regulatorio",
            }
            assert expected.issubset(names), f"Missing: {expected - names}"
            assert len(tool_list) == 10

    @pytest.mark.asyncio
    async def test_tools_have_docstrings(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            for tool in tool_list:
                assert tool.description, f"Tool {tool.name} has no description"


class TestResourcesRegistered:
    @pytest.mark.asyncio
    async def test_resources_registered(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://categorias-regulatorias" in uris
            assert "data://tipos-bula" in uris
            assert "data://secoes-bula" in uris


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_prompt_registered(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "pesquisa_medicamento" in names


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_medicamento_e2e(self) -> None:
        mock_data = [
            MedicamentoBulario(
                nome_produto="Dipirona Sódica",
                principio_ativo="DIPIRONA SÓDICA",
                categoria_regulatoria="Genérico",
                numero_processo="25351.123/2020-00",
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_medicamento",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_medicamento", {"nome": "dipirona"})
                assert "Dipirona Sódica" in result.data

    @pytest.mark.asyncio
    async def test_consultar_bula_e2e(self) -> None:
        mock_data = [
            BulaMedicamento(
                id_bula="999",
                nome_produto="Dipirona",
                tipo_bula="PACIENTE",
                url_bula="https://example.com/bula",
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.consultar_bula",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "consultar_bula", {"numero_processo": "25351.123/2020-00"}
                )
                assert "Dipirona" in result.data
                assert "PACIENTE" in result.data

    @pytest.mark.asyncio
    async def test_informacoes_bula_e2e(self) -> None:
        async with Client(mcp) as c:
            result = await c.call_tool("informacoes_bula", {})
            assert "Indicações" in result.data
            assert "Contraindicações" in result.data
