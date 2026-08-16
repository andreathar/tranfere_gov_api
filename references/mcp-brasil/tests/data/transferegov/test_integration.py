"""Integration tests for the transferegov feature using fastmcp.Client.

These tests verify the full pipeline: server → tools → client (mocked HTTP).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.transferegov.schemas import TransferenciaEspecial
from mcp_brasil.data.transferegov.server import mcp

CLIENT_MODULE = "mcp_brasil.data.transferegov.client"


class TestToolsRegistered:
    @pytest.mark.asyncio
    async def test_all_5_tools_registered(self) -> None:
        async with Client(mcp) as c:
            tool_list = await c.list_tools()
            names = {t.name for t in tool_list}
            expected = {
                "buscar_emendas_pix",
                "buscar_emenda_por_autor",
                "detalhe_emenda",
                "emendas_por_municipio",
                "resumo_emendas_ano",
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
    async def test_info_api_resource(self) -> None:
        async with Client(mcp) as c:
            resources = await c.list_resources()
            uris = {str(r.uri) for r in resources}
            assert "data://info-api" in uris


class TestPromptsRegistered:
    @pytest.mark.asyncio
    async def test_prompt_registered(self) -> None:
        async with Client(mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "analise_emendas_pix" in names


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_buscar_emendas_pix_e2e(self) -> None:
        mock_data = [
            TransferenciaEspecial(
                numero_emenda="EMD-E2E",
                nome_parlamentar="Dep. Teste",
                valor_custeio=50000.0,
                valor_investimento=50000.0,
                nome_beneficiario="MUNICIPIO TESTE",
                uf_beneficiario="PI",
            )
        ]
        with patch(
            f"{CLIENT_MODULE}.buscar_emendas_pix",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("buscar_emendas_pix", {"ano": 2024})
                assert "EMD-E2E" in result.data

    @pytest.mark.asyncio
    async def test_detalhe_emenda_e2e(self) -> None:
        mock_data = TransferenciaEspecial(
            id_plano_acao=42,
            numero_emenda="EMD-DET",
            nome_parlamentar="Dep. Detalhe",
            valor_custeio=50000.0,
        )
        with patch(
            f"{CLIENT_MODULE}.detalhe_emenda",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            async with Client(mcp) as c:
                result = await c.call_tool("detalhe_emenda", {"id_plano_acao": 42})
                assert "EMD-DET" in result.data
