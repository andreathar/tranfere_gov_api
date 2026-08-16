"""Feature Bacen — Banco Central do Brasil."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="bacen",
    description=(
        "Séries temporais do BCB: juros, inflação, câmbio, PIB, emprego e +190 indicadores"
    ),
    version="0.1.0",
    api_base="https://api.bcb.gov.br/dados/serie/bcdata.sgs",
    requires_auth=False,
    tags=["economia", "juros", "inflacao", "cambio", "pib", "selic"],
)
