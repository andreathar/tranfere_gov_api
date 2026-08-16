"""Feature SPU-Geo — GeoPortal SPUnet (terrenos de marinha e imóveis da União)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="spu_geo",
    description=(
        "SPU GeoPortal: terrenos de marinha, acrescidos, marginais, ilhas federais, "
        "praias, manguezais e localização de imóveis da União. Consulta geoespacial "
        "via GeoServer WMS (GetFeatureInfo) da Secretaria do Patrimônio da União."
    ),
    version="0.1.0",
    api_base="https://geoportal-spunet.gestao.gov.br/geoserver",
    requires_auth=False,
    tags=["spu", "geo", "terreno-marinha", "imoveis-uniao", "geoservidor", "ogc", "wms"],
)
