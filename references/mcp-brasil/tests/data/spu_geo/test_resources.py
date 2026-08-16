"""Tests for the SPU-Geo resources."""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from mcp_brasil.data.spu_geo.resources import (
    catalogo_camadas,
    glossario_patrimonial,
    info_api,
)
from mcp_brasil.data.spu_geo.server import mcp


def test_catalogo_camadas_is_valid_json() -> None:
    data = json.loads(catalogo_camadas())
    assert "camadas" in data
    ids = {c["id"] for c in data["camadas"]}
    assert "terreno_marinha" in ids
    assert "imovel_localizacao" in ids
    assert "ponto_uniao_default" in data
    assert "terreno_marinha" in data["ponto_uniao_default"]


def test_glossario_patrimonial_has_key_terms() -> None:
    data = json.loads(glossario_patrimonial())
    termos = {t["termo"] for t in data["termos"]}
    assert "RIP" in termos
    assert "Terreno de Marinha" in termos
    assert "Laudêmio" in termos


def test_info_api_has_endpoint() -> None:
    data = json.loads(info_api())
    assert "endpoint_ows" in data
    assert data["endpoint_ows"].startswith("https://")
    assert "GetFeatureInfo" in data["protocolo_disponivel"]


@pytest.mark.asyncio
async def test_resources_registered_on_server() -> None:
    async with Client(mcp) as c:
        resources = await c.list_resources()
        uris = {str(r.uri) for r in resources}
        assert "data://catalogo" in uris
        assert "data://glossario" in uris
        assert "data://info" in uris
