"""Feature IPEADATA — séries históricas do Ipea."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="ipeadata",
    description=(
        "IPEADATA — base macro, regional e social do Ipea com milhares de séries históricas"
    ),
    version="0.1.0",
    api_base="http://ipeadata.gov.br/api/odata4",
    requires_auth=False,
    tags=["economia", "macro", "series", "historicas", "ipea", "regional", "social"],
)
