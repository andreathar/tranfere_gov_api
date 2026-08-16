"""Integration tests for the DENASUS feature using fastmcp.Client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_brasil.data.denasus.schemas import AtividadeAuditoria
from mcp_brasil.data.denasus.server import mcp

CLIENT_MODULE = "mcp_brasil.data.denasus.client"


@pytest.fixture
def denasus_client() -> Client:
    return Client(mcp)


MOCK_ATIVIDADES = [
    AtividadeAuditoria(
        titulo="Auditoria Hospital - SP",
        uf="SP",
        tipo="Auditoria",
        situacao="Concluída",
    ),
]


class TestDenasusIntegration:
    @pytest.mark.asyncio
    async def test_server_has_5_tools(self, denasus_client: Client) -> None:
        async with denasus_client:
            tools = await denasus_client.list_tools()
            assert len(tools) == 5

    @pytest.mark.asyncio
    async def test_server_has_2_resources(self, denasus_client: Client) -> None:
        async with denasus_client:
            resources = await denasus_client.list_resources()
            assert len(resources) == 2

    @pytest.mark.asyncio
    async def test_server_has_1_prompt(self, denasus_client: Client) -> None:
        async with denasus_client:
            prompts = await denasus_client.list_prompts()
            assert len(prompts) == 1

    @pytest.mark.asyncio
    async def test_buscar_auditorias_tool(self, denasus_client: Client) -> None:
        with patch(
            f"{CLIENT_MODULE}.listar_atividades_auditoria",
            new_callable=AsyncMock,
            return_value=MOCK_ATIVIDADES,
        ):
            async with denasus_client:
                result = await denasus_client.call_tool("buscar_auditorias", {})
                assert "Auditoria" in result.data

    @pytest.mark.asyncio
    async def test_informacoes_sna_tool(self, denasus_client: Client) -> None:
        async with denasus_client:
            result = await denasus_client.call_tool("informacoes_sna", {})
            assert "DENASUS" in result.data

    @pytest.mark.asyncio
    async def test_read_sobre_resource(self, denasus_client: Client) -> None:
        async with denasus_client:
            resources = await denasus_client.list_resources()
            sobre_uri = next(r for r in resources if "sobre" in str(r.uri)).uri
            content = await denasus_client.read_resource(sobre_uri)
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            assert "DENASUS" in text

    @pytest.mark.asyncio
    async def test_get_prompt(self, denasus_client: Client) -> None:
        async with denasus_client:
            result = await denasus_client.get_prompt(
                "analise_auditoria_municipal",
                {"municipio": "Teresina", "uf": "PI"},
            )
            text = result.messages[0].content.text
            assert "Teresina" in text
