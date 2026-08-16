"""Feature Atlas da Violência — séries históricas de violência no Brasil (IPEA)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="atlas_violencia",
    description=(
        "Atlas da Violência (IPEA/FBSP): séries históricas de homicídios, "
        "violência por gênero/raça, suicídios, armas de fogo, mortes no trânsito "
        "e intervenção policial por município, UF e região."
    ),
    version="0.1.0",
    api_base="https://www.ipea.gov.br/atlasviolencia/api/v1",
    requires_auth=False,
    tags=[
        "violencia",
        "homicidios",
        "seguranca-publica",
        "ipea",
        "atlas-violencia",
        "series-historicas",
    ],
)
