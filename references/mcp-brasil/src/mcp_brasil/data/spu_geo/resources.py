"""Static reference data for the spu_geo feature."""

from __future__ import annotations

import json

from .constants import LAYERS, PONTO_UNIAO_LAYERS


def catalogo_camadas() -> str:
    """Catálogo completo das camadas geoespaciais da SPU."""
    data = {
        "camadas": [
            {
                "id": cid,
                "typename": info["typename"],
                "title": info["title"],
                "geometry": info["geometry"],
                "description": info["description"],
            }
            for cid, info in LAYERS.items()
        ],
        "ponto_uniao_default": list(PONTO_UNIAO_LAYERS),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def glossario_patrimonial() -> str:
    """Glossário de termos patrimoniais federais usados nas camadas SPU."""
    termos = [
        {
            "termo": "RIP",
            "definicao": (
                "Registro Imobiliário Patrimonial. Identificador único do imóvel da "
                "União no SPUnet/SIAPA/SPIUNET. Pode ter até 13 dígitos."
            ),
        },
        {
            "termo": "Terreno de Marinha",
            "definicao": (
                "Faixa de 33m medida a partir da Linha Preamar Média de 1831 "
                "(DL 9.760/1946, art. 2º)."
            ),
        },
        {
            "termo": "Terreno Acrescido",
            "definicao": (
                "Terreno formado natural ou artificialmente para o lado do mar ou "
                "dos rios federais, além dos terrenos de marinha ou marginais."
            ),
        },
        {
            "termo": "Terreno Marginal",
            "definicao": (
                "Faixa de 15m medida horizontalmente para a parte da terra das "
                "margens de rios federais, a partir da Linha Média das Enchentes "
                "Ordinárias (LMEO)."
            ),
        },
        {
            "termo": "LPM",
            "definicao": "Linha de Preamar Média de 1831 — referência para terrenos de marinha.",
        },
        {
            "termo": "LTM",
            "definicao": ("Linha do Terreno de Marinha — limite dos 33m a partir da LPM."),
        },
        {
            "termo": "LLTM",
            "definicao": "Limite da Linha do Terreno de Marinha (limite superior da demarcação).",
        },
        {
            "termo": "LMEO",
            "definicao": (
                "Linha Média das Enchentes Ordinárias — referência para terrenos "
                "marginais de rios federais."
            ),
        },
        {
            "termo": "Aforamento/Enfiteuse",
            "definicao": (
                "Regime sobre terreno de marinha em que o foreiro paga foro anual "
                "(0,6% do valor de domínio pleno)."
            ),
        },
        {
            "termo": "Ocupação",
            "definicao": (
                "Regime precário em que o ocupante paga taxa anual (2% ou 5% conforme o caso)."
            ),
        },
        {
            "termo": "Laudêmio",
            "definicao": (
                "5% do valor atualizado, devido à União na transferência onerosa "
                "de imóvel foreiro."
            ),
        },
    ]
    return json.dumps({"termos": termos}, ensure_ascii=False, indent=2)


def info_api() -> str:
    """Metadados da API do GeoPortal SPU (endpoint, padrões OGC, CRS)."""
    info = {
        "fonte": "GeoPortal SPUnet — Secretaria do Patrimônio da União (MGI)",
        "url": "https://geoportal-spunet.gestao.gov.br",
        "endpoint_ows": "https://geoportal-spunet.gestao.gov.br/geoserver/ows",
        "protocolo_disponivel": (
            "WMS 1.1.1 / 1.3.0 (GetFeatureInfo com info_format=application/json)"
        ),
        "wfs_get_feature": (
            "Indisponível publicamente — WFS GetCapabilities retorna vazio, e "
            "GetFeature retorna InvalidParameterValue para typenames conhecidos."
        ),
        "crs_oficial_spu": "SIRGAS 2000 (EPSG:4674)",
        "crs_usado_consulta": "EPSG:4326 (compatível dentro da margem de ~1m no Brasil)",
        "auth": "Sem autenticação",
        "licenca": "Dados abertos (Lei 12.527/2011 + Decreto 8.777/2016)",
    }
    return json.dumps(info, ensure_ascii=False, indent=2)
