"""Integration tests for the TCE-PE feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.tce_pe.schemas import UnidadeJurisdicionada
from mcp_brasil.data.tce_pe.server import mcp

CLIENT_MODULE = "mcp_brasil.data.tce_pe.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_5_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_unidades_pe",
                "buscar_licitacoes_pe",
                "buscar_contratos_pe",
                "buscar_despesas_pe",
                "buscar_fornecedores_pe",
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

    @pytest.mark.asyncio
    async def test_endpoints_content(self) -> None:
        async with Client(mcp) as c:
            content = await c.read_resource("data://endpoints")
            text = content[0].text if isinstance(content, list) else str(content)
            assert "UnidadesJurisdicionadas" in text
            assert "LicitacaoUG" in text
            assert "Contratos" in text
            assert "DespesasMunicipais" in text
            assert "Fornecedores" in text


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_analisar_municipio_prompt(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analisar_municipio_pe" in names, f"Prompts: {names}"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_unidades_e2e(self) -> None:
        mock_data = [
            UnidadeJurisdicionada(codigo="123", nome="PREFEITURA DO RECIFE", municipio="Recife"),
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_unidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_unidades_pe", {})
                assert "PREFEITURA DO RECIFE" in result.data

    @pytest.mark.asyncio
    async def test_buscar_fornecedores_empty_e2e(self) -> None:
        with patch(
            f"{CLIENT_MODULE}.buscar_fornecedores",
            new_callable=AsyncMock,
            return_value=[],
        ):
            async with Client(mcp) as c:
                result = await c.call_tool(
                    "buscar_fornecedores_pe",
                    {"nome": "INEXISTENTE"},
                )
                assert "Nenhum fornecedor" in result.data
