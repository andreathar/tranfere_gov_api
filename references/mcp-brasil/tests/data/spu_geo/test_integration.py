"""End-to-end integration tests via fastmcp.Client (mocked HTTP)."""

from __future__ import annotations

import re

import httpx
import pytest
import respx
from fastmcp import Client

from mcp_brasil.data.spu_geo.constants import SPU_WMS_OWS_URL
from mcp_brasil.data.spu_geo.server import mcp


def _text(result: object) -> str:
    data = getattr(result, "data", None)
    if isinstance(data, str):
        return data
    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            return text
    return str(result)


@pytest.mark.asyncio
async def test_listar_camadas_end_to_end() -> None:
    async with Client(mcp) as c:
        r = await c.call_tool("listar_camadas_spu", {})
        assert "GeoPortal SPU" in _text(r)


@pytest.mark.asyncio
async def test_consultar_ponto_end_to_end() -> None:
    hit_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "vw_app_trecho_terreno_marinha_a.1",
                "geometry": {"type": "MultiPolygon", "coordinates": []},
                "properties": {
                    "nome_trecho": "Praia de Copacabana",
                    "uf": "RJ",
                    "area_aproximada": 25000.0,
                    "etapa_demarcacao": "Aprovado",
                },
            }
        ],
    }
    empty = {"type": "FeatureCollection", "features": []}

    def responder(request: httpx.Request) -> httpx.Response:
        layer = request.url.params.get("layers", "")
        if "terreno_marinha_a" in layer and "acrescido" not in layer:
            return httpx.Response(200, json=hit_payload)
        return httpx.Response(200, json=empty)

    with respx.mock() as mock:
        mock.get(url__regex=re.escape(SPU_WMS_OWS_URL)).mock(side_effect=responder)
        async with Client(mcp) as c:
            r = await c.call_tool("consultar_ponto_spu", {"lat": -22.97, "lon": -43.18})

    text = _text(r)
    assert "terras da União" in text
    assert "terreno_marinha" in text
    assert "Praia de Copacabana" in text


@pytest.mark.asyncio
async def test_buscar_imoveis_area_end_to_end() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "vw_imv_localizacao_imovel_p.1",
                "geometry": {"type": "Point", "coordinates": [-43.2, -22.9]},
                "properties": {
                    "rip": "00005569",
                    "tipo_imovel": "Terreno",
                    "id_uf": "RJ",
                    "municipio": "Rio de Janeiro",
                    "endereco": "Praça Santo Cristo",
                },
            }
        ],
    }
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(SPU_WMS_OWS_URL)).mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with Client(mcp) as c:
            r = await c.call_tool(
                "buscar_imoveis_area_spu",
                {"bbox": "-43.3,-23.0,-43.1,-22.8", "limite": 5},
            )
    text = _text(r)
    assert "00005569" in text
    assert "Rio de Janeiro" in text


@pytest.mark.asyncio
async def test_resource_catalogo_returns_json() -> None:
    async with Client(mcp) as c:
        data = await c.read_resource("data://catalogo")
        text = data[0].text  # type: ignore[union-attr]
        assert "terreno_marinha" in text
        assert "camadas" in text
