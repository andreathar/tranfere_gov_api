"""Feature INPE — dados de queimadas e desmatamento."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="inpe",
    description=(
        "INPE — Instituto Nacional de Pesquisas Espaciais: focos de queimadas, "
        "alertas de desmatamento DETER, dados históricos PRODES e satélites."
    ),
    version="0.1.0",
    api_base="https://terrabrasilis.dpi.inpe.br",
    requires_auth=False,
    tags=["queimadas", "desmatamento", "amazonia", "meio-ambiente", "inpe"],
)
