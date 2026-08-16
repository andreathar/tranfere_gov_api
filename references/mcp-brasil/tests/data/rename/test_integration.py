"""Integration tests for the RENAME feature using fastmcp.Client."""

import pytest
from fastmcp import Client

from mcp_brasil.data.rename.server import mcp


@pytest.fixture
def rename_client() -> Client:
    return Client(mcp)


class TestRenameIntegration:
    @pytest.mark.asyncio
    async def test_server_has_5_tools(self, rename_client: Client) -> None:
        async with rename_client:
            tools = await rename_client.list_tools()
            assert len(tools) == 5

    @pytest.mark.asyncio
    async def test_server_has_2_resources(self, rename_client: Client) -> None:
        async with rename_client:
            resources = await rename_client.list_resources()
            assert len(resources) == 2

    @pytest.mark.asyncio
    async def test_server_has_1_prompt(self, rename_client: Client) -> None:
        async with rename_client:
            prompts = await rename_client.list_prompts()
            assert len(prompts) == 1

    @pytest.mark.asyncio
    async def test_buscar_medicamento_tool(self, rename_client: Client) -> None:
        async with rename_client:
            result = await rename_client.call_tool(
                "buscar_medicamento_rename", {"nome": "paracetamol"}
            )
            assert "Paracetamol" in result.data

    @pytest.mark.asyncio
    async def test_listar_grupos_tool(self, rename_client: Client) -> None:
        async with rename_client:
            result = await rename_client.call_tool("listar_grupos_terapeuticos", {})
            assert "Antibióticos" in result.data

    @pytest.mark.asyncio
    async def test_read_catalogo_resource(self, rename_client: Client) -> None:
        async with rename_client:
            resources = await rename_client.list_resources()
            catalogo_uri = next(r for r in resources if "catalogo" in str(r.uri)).uri
            content = await rename_client.read_resource(catalogo_uri)
            text = content[0].text if hasattr(content[0], "text") else str(content[0])
            assert "Paracetamol" in text

    @pytest.mark.asyncio
    async def test_get_prompt(self, rename_client: Client) -> None:
        async with rename_client:
            result = await rename_client.get_prompt(
                "consulta_medicamento_sus", {"nome": "losartana"}
            )
            text = result.messages[0].content.text
            assert "losartana" in text
