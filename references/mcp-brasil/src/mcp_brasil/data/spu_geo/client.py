"""HTTP client for the SPU GeoPortal (GeoServer WMS).

This GeoServer publishes WFS capabilities but does NOT expose the feature
types via WFS GetFeature (401/400). The public path is:

    WMS GetFeatureInfo with info_format=application/json

which returns GeoJSON for features intersecting a bounding box.
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get
from mcp_brasil.exceptions import HttpClientError

from .constants import (
    LAYERS,
    PONTO_UNIAO_LAYERS,
    SPU_WMS_OWS_URL,
    WMS_GETFEATUREINFO_DEFAULTS,
)
from .schemas import Camada, FeatureGeo, ResultadoPonto


def _bbox_around(lat: float, lon: float, delta: float = 0.001) -> str:
    """Build a small bbox around a point (approx 110m at Brazil latitudes).

    Must be large enough that GeoServer's pixel-based intersection test has
    enough resolution — with delta < 0.0005 plus default pixel width, the
    pixel at (x,y) covers < 1m and features are missed. The `buffer=50`
    vendor param in WMS_GETFEATUREINFO_DEFAULTS compensates further.
    """
    return f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"


def listar_camadas() -> list[Camada]:
    """Return the curated catalog of layers.

    Uses the static catalog defined in constants.LAYERS rather than parsing
    WMS GetCapabilities at runtime — the catalog is stable and hand-curated
    to surface only the public-facing SPU layers (views are namespaced with
    hashes/dates that change each refresh).
    """
    return [
        Camada(
            id=short_id,
            typename=info["typename"],
            title=info["title"],
            geometry=info["geometry"],
            description=info["description"],
        )
        for short_id, info in LAYERS.items()
    ]


def _resolve_layer(camada_id: str) -> dict[str, str]:
    if camada_id not in LAYERS:
        raise ValueError(f"Camada desconhecida: '{camada_id}'. Use uma de: {list(LAYERS.keys())}")
    return LAYERS[camada_id]


async def consultar_features(
    camada_id: str,
    *,
    bbox: str,
    feature_count: int = 10,
    srs: str | None = None,
) -> list[FeatureGeo]:
    """Run WMS GetFeatureInfo on a single layer for a given bbox.

    Args:
        camada_id: Short identifier from LAYERS (ex: 'terreno_marinha').
        bbox: WMS bbox string "minx,miny,maxx,maxy" in `srs` coordinates
            (WMS 1.1.1 expects lon,lat order).
        feature_count: Max features to return.
        srs: CRS string (default: EPSG:4326).

    Returns:
        List of FeatureGeo extracted from the GeoJSON response.
    """
    layer = _resolve_layer(camada_id)
    params: dict[str, Any] = {
        **WMS_GETFEATUREINFO_DEFAULTS,
        "layers": layer["typename"],
        "query_layers": layer["typename"],
        "bbox": bbox,
        "x": "128",
        "y": "128",
        "feature_count": str(feature_count),
    }
    if srs:
        params["srs"] = srs

    try:
        data: dict[str, Any] = await http_get(SPU_WMS_OWS_URL, params=params)
    except HttpClientError:
        raise

    features_raw = data.get("features", []) if isinstance(data, dict) else []
    out: list[FeatureGeo] = []
    for feat in features_raw:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry") or {}
        out.append(
            FeatureGeo(
                id=feat.get("id"),
                camada=camada_id,
                properties=props,
                geometry_type=geom.get("type"),
            )
        )
    return out


async def verificar_ponto(
    lat: float,
    lon: float,
    camadas: tuple[str, ...] = PONTO_UNIAO_LAYERS,
) -> ResultadoPonto:
    """Check which SPU layers contain a given lat/lon point.

    Sends one GetFeatureInfo request per layer with a tiny bbox around
    the point. Returns the consolidated result.
    """
    bbox = _bbox_around(lat, lon)
    hits: list[FeatureGeo] = []
    camadas_encontradas: list[str] = []

    for camada_id in camadas:
        try:
            feats = await consultar_features(camada_id, bbox=bbox, feature_count=1)
        except (HttpClientError, ValueError):
            continue
        if feats:
            camadas_encontradas.append(camada_id)
            hits.extend(feats)

    return ResultadoPonto(
        lat=lat,
        lon=lon,
        camadas_encontradas=camadas_encontradas,
        features=hits,
    )


async def buscar_imoveis_bbox(
    bbox: str,
    *,
    feature_count: int = 20,
) -> list[FeatureGeo]:
    """List cadastered imóveis (Points) inside a bbox."""
    return await consultar_features(
        "imovel_localizacao",
        bbox=bbox,
        feature_count=feature_count,
    )
