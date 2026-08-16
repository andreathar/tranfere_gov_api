"""Feature ANEEL — dados do setor elétrico brasileiro."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="aneel",
    description=(
        "ANEEL — setor elétrico: geração (SIGA), mini/micro geração distribuída, "
        "tarifas, bandeiras, autos de infração"
    ),
    version="0.1.0",
    api_base="https://dadosabertos.aneel.gov.br/api/3",
    requires_auth=False,
    tags=["aneel", "energia", "eletricidade", "solar", "eolica", "tarifas", "geracao"],
)
