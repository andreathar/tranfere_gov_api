"""Integration tests for tabua_mares via fastmcp.Client."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from mcp_brasil.data.tabua_mares.server import mcp


@pytest.fixture()
def client() -> Client:
    return Client(mcp)


@pytest.mark.asyncio
async def test_list_tools(client: Client) -> None:
    async with client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    assert "listar_estados_costeiros" in names
    assert "listar_portos" in names
    assert "buscar_portos" in names
    assert "consultar_tabua_mare" in names
    assert "porto_mais_proximo" in names
    assert "porto_mais_proximo_geral" in names
    assert "tabua_mare_por_geolocalizacao" in names


@pytest.mark.asyncio
async def test_list_resources(client: Client) -> None:
    async with client:
        resources = await client.list_resources()
    uris = {str(r.uri) for r in resources}
    assert "data://estados-costeiros" in uris


@pytest.mark.asyncio
async def test_read_resource_estados_costeiros(client: Client) -> None:
    async with client:
        content = await client.read_resource("data://estados-costeiros")
    text = content[0].text if isinstance(content, list) else str(content)
    data = json.loads(text)
    assert isinstance(data, list)
    assert len(data) == 17


@pytest.mark.asyncio
async def test_list_prompts(client: Client) -> None:
    async with client:
        prompts = await client.list_prompts()
    names = {p.name for p in prompts}
    assert "consulta_mares" in names
    assert "analise_navegacao" in names


@pytest.mark.asyncio
async def test_get_prompt_consulta_mares(client: Client) -> None:
    async with client:
        result = await client.get_prompt("consulta_mares", {"estado": "pb", "mes": "1"})
    text = result.messages[0].content.text
    assert "PB" in text
    assert "listar_portos" in text
