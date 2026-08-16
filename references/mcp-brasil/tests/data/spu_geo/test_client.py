"""Tests for the SPU-Geo HTTP client."""

from __future__ import annotations

import re

import httpx
import pytest
import respx

from mcp_brasil.data.spu_geo import client
from mcp_brasil.data.spu_geo.constants import SPU_WMS_OWS_URL

_GEOJSON_TERRENO = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "vw_app_trecho_terreno_marinha_a.443",
            "geometry": {"type": "MultiPolygon", "coordinates": []},
            "properties": {
                "id": 443,
                "uf": "RJ",
                "area_aproximada": 13699.99,
                "etapa_demarcacao": "Aprovado",
                "situacao_trecho": "Demarcado",
                "nome_trecho": "Rua Santo Cristo",
                "fonte": "Secretaria do Patrimônio da União - SPU",
            },
        }
    ],
}

_GEOJSON_IMOVEIS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "vw_imv_localizacao_imovel_p.5569",
            "geometry": {"type": "Point", "coordinates": [-43.20122, -22.899347]},
            "properties": {
                "rip": "00005569",
                "tipo_imovel": "Gleba/Terreno/Lote sem edificação",
                "id_uf": "RJ",
                "municipio": "Rio de Janeiro",
                "bairro": "SANTO CRISTO",
                "endereco": "Praça SANTO CRISTO",
            },
        }
    ],
}

_GEOJSON_EMPTY: dict = {"type": "FeatureCollection", "features": []}


@pytest.mark.asyncio
async def test_listar_camadas_returns_catalog() -> None:
    camadas = client.listar_camadas()
    ids = {c.id for c in camadas}
    assert "terreno_marinha" in ids
    assert "imovel_localizacao" in ids
    # Every layer has a typename under spunet: or geonode:
    for c in camadas:
        assert c.typename.startswith(("spunet:", "geonode:"))
        assert c.geometry in {"Point", "MultiPolygon", "MultiLineString"}


@pytest.mark.asyncio
async def test_consultar_features_returns_parsed_geojson() -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(url__regex=re.escape(SPU_WMS_OWS_URL)).mock(
            return_value=httpx.Response(200, json=_GEOJSON_TERRENO)
        )
        feats = await client.consultar_features(
            "terreno_marinha",
            bbox="-43.2,-22.9,-43.1,-22.8",
            feature_count=1,
        )
        assert route.called
        request = route.calls.last.request
        # Essential query params
        assert request.url.params["layers"] == "spunet:vw_app_trecho_terreno_marinha_a"
        assert request.url.params["query_layers"] == "spunet:vw_app_trecho_terreno_marinha_a"
        assert request.url.params["info_format"] == "application/json"
        assert request.url.params["request"] == "GetFeatureInfo"
        assert request.url.params["feature_count"] == "1"

    assert len(feats) == 1
    f = feats[0]
    assert f.camada == "terreno_marinha"
    assert f.id == "vw_app_trecho_terreno_marinha_a.443"
    assert f.geometry_type == "MultiPolygon"
    assert f.properties["nome_trecho"] == "Rua Santo Cristo"
    assert f.properties["uf"] == "RJ"


@pytest.mark.asyncio
async def test_consultar_features_unknown_layer_raises() -> None:
    with pytest.raises(ValueError, match="Camada desconhecida"):
        await client.consultar_features("inexistente", bbox="0,0,1,1")


@pytest.mark.asyncio
async def test_verificar_ponto_aggregates_hits() -> None:
    # Mock: terreno_marinha returns a hit, other layers return empty
    def _responder(request: httpx.Request) -> httpx.Response:
        layer = request.url.params.get("layers", "")
        if "terreno_marinha_a" in layer and "acrescido" not in layer:
            return httpx.Response(200, json=_GEOJSON_TERRENO)
        return httpx.Response(200, json=_GEOJSON_EMPTY)

    with respx.mock() as mock:
        mock.get(url__regex=re.escape(SPU_WMS_OWS_URL)).mock(side_effect=_responder)
        result = await client.verificar_ponto(-22.9, -43.2)

    assert result.lat == -22.9
    assert result.lon == -43.2
    assert result.camadas_encontradas == ["terreno_marinha"]
    assert len(result.features) == 1
    assert result.features[0].camada == "terreno_marinha"


@pytest.mark.asyncio
async def test_verificar_ponto_no_hits_returns_empty() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(SPU_WMS_OWS_URL)).mock(
            return_value=httpx.Response(200, json=_GEOJSON_EMPTY)
        )
        result = await client.verificar_ponto(0.0, 0.0)

    assert result.camadas_encontradas == []
    assert result.features == []


@pytest.mark.asyncio
async def test_buscar_imoveis_bbox_returns_imoveis() -> None:
    with respx.mock() as mock:
        mock.get(url__regex=re.escape(SPU_WMS_OWS_URL)).mock(
            return_value=httpx.Response(200, json=_GEOJSON_IMOVEIS)
        )
        feats = await client.buscar_imoveis_bbox("-43.3,-23.0,-43.1,-22.8", feature_count=5)

    assert len(feats) == 1
    f = feats[0]
    assert f.camada == "imovel_localizacao"
    assert f.properties["rip"] == "00005569"
    assert f.geometry_type == "Point"


def test_bbox_around_builds_small_box() -> None:
    bbox = client._bbox_around(-22.9, -43.2, delta=0.001)
    parts = [float(x) for x in bbox.split(",")]
    # Order is minlon, minlat, maxlon, maxlat
    assert parts[0] == pytest.approx(-43.201)
    assert parts[1] == pytest.approx(-22.901)
    assert parts[2] == pytest.approx(-43.199)
    assert parts[3] == pytest.approx(-22.899)
