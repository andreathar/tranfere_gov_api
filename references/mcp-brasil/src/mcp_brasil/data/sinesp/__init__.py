"""Feature SINESP — dados de segurança pública via portal CKAN do MJSP."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="sinesp",
    description=(
        "SINESP/MJSP: datasets de segurança pública (homicídios, estupros, "
        "roubos, furtos, tráfico, sistema penitenciário) via API CKAN do "
        "Ministério da Justiça e Segurança Pública."
    ),
    version="0.1.0",
    api_base="https://dados.mj.gov.br/api/3/action",
    requires_auth=False,
    tags=[
        "seguranca-publica",
        "sinesp",
        "mjsp",
        "ckan",
        "crimes",
        "penitenciario",
    ],
)
