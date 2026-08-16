"""Feature IBAMA — dados ambientais (multas, autuações, biomas)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="ibama",
    description=(
        "IBAMA — autuações ambientais, CTF, ADA, arrecadação TCFA, biomas extra-amazônicos"
    ),
    version="0.1.0",
    api_base="https://dadosabertos.ibama.gov.br/api/3",
    requires_auth=False,
    tags=["ibama", "meio-ambiente", "multas", "fiscalizacao", "biomas", "desmatamento"],
)
