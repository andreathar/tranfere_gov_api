"""Constants for the SPU-Geo feature."""

SPU_GEO_API_BASE = "https://geoportal-spunet.gestao.gov.br/geoserver"
SPU_WMS_OWS_URL = f"{SPU_GEO_API_BASE}/ows"

# WMS GetFeatureInfo accepts this CRS; internal data uses SIRGAS 2000 (EPSG:4674)
# but EPSG:4326 is compatible for the lat/lon range of Brazil within ~1m error.
DEFAULT_SRS = "EPSG:4326"

# Curated layer catalog — the WMS workspace exposes many internal views;
# these are the ones with public-facing value.
# Key: short_id (used in tools); Value: (typename, title, geometry_type, description)
LAYERS: dict[str, dict[str, str]] = {
    "terreno_marinha": {
        "typename": "spunet:vw_app_trecho_terreno_marinha_a",
        "title": "Trechos de Terreno de Marinha",
        "geometry": "MultiPolygon",
        "description": (
            "Faixa de 33m a partir da linha preamar média de 1831 (DL 9.760/1946, art. 2º)."
        ),
    },
    "acrescido_marinha": {
        "typename": "spunet:vw_app_trecho_terreno_acrescido_marinha_a",
        "title": "Terrenos Acrescidos de Marinha",
        "geometry": "MultiPolygon",
        "description": (
            "Terrenos formados natural ou artificialmente além dos terrenos de marinha."
        ),
    },
    "terreno_marginal": {
        "typename": "spunet:vw_app_trecho_terreno_marginal_a",
        "title": "Trechos de Terreno Marginal",
        "geometry": "MultiPolygon",
        "description": "Terrenos marginais de rios federais (faixa de 15m).",
    },
    "acrescido_marginal": {
        "typename": "spunet:vw_app_trecho_terreno_acrescido_marginal_a",
        "title": "Terrenos Acrescidos Marginais",
        "geometry": "MultiPolygon",
        "description": "Acrescidos em terrenos marginais.",
    },
    "ilha_federal": {
        "typename": "spunet:vw_app_ilha_federal_a",
        "title": "Ilhas Federais",
        "geometry": "MultiPolygon",
        "description": "Ilhas de propriedade da União.",
    },
    "praia_federal": {
        "typename": "spunet:vw_app_praia_federal_a",
        "title": "Praias Federais",
        "geometry": "MultiPolygon",
        "description": "Praias (bem de uso comum do povo sob administração da União).",
    },
    "manguezal_federal": {
        "typename": "spunet:vw_app_manguezal_federal_a",
        "title": "Manguezais Federais",
        "geometry": "MultiPolygon",
        "description": "Áreas de manguezal em terras da União.",
    },
    "espelho_dagua_federal": {
        "typename": "spunet:vw_app_espelho_dagua_federal_a",
        "title": "Espelhos d'Água Federais",
        "geometry": "MultiPolygon",
        "description": "Corpos d'água federais (rios, lagos, reservatórios).",
    },
    "imovel_localizacao": {
        "typename": "spunet:vw_imv_localizacao_imovel_p",
        "title": "Localização de Imóveis da União",
        "geometry": "Point",
        "description": (
            "Pontos geocodificados de imóveis cadastrados no SPUnet, "
            "com RIP, tipo, endereço e utilização."
        ),
    },
    "linha_preamar_media": {
        "typename": "spunet:vw_lpp_trecho_lpm_l",
        "title": "Linha de Preamar Média (LPM)",
        "geometry": "MultiLineString",
        "description": "Linha de Preamar Média de 1831 (referência para terrenos de marinha).",
    },
    "linha_terreno_marinha": {
        "typename": "spunet:vw_lpp_trecho_ltm_l",
        "title": "Linha do Terreno de Marinha (LTM)",
        "geometry": "MultiLineString",
        "description": "Limite dos 33m da faixa de terreno de marinha.",
    },
    "limite_lltm": {
        "typename": "spunet:vw_lpp_trecho_lltm_l",
        "title": "Limite da Linha do Terreno de Marinha (LLTM)",
        "geometry": "MultiLineString",
        "description": "Limite superior da demarcação de terrenos de marinha.",
    },
    "lmeo": {
        "typename": "spunet:vw_lpp_trecho_lmeo_l",
        "title": "Linha Média das Enchentes Ordinárias (LMEO)",
        "geometry": "MultiLineString",
        "description": "Referência para terrenos marginais em rios federais.",
    },
}

# Layers checked by default when testing whether a point is on União property
PONTO_UNIAO_LAYERS: tuple[str, ...] = (
    "terreno_marinha",
    "acrescido_marinha",
    "terreno_marginal",
    "acrescido_marginal",
    "ilha_federal",
    "praia_federal",
    "manguezal_federal",
)

WMS_GETFEATUREINFO_DEFAULTS: dict[str, str] = {
    "service": "WMS",
    "version": "1.1.1",
    "request": "GetFeatureInfo",
    "info_format": "application/json",
    "width": "256",
    "height": "256",
    "srs": DEFAULT_SRS,
    # GeoServer vendor param: expands the pixel tolerance for intersection tests.
    # Without this, tiny bboxes (< ~500m) can miss features due to sub-pixel
    # tolerance.
    "buffer": "50",
}
