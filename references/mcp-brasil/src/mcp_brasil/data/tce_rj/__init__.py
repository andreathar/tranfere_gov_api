"""Feature TCE-RJ — Tribunal de Contas do Estado do Rio de Janeiro."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_rj",
    description=(
        "TCE-RJ: licitações, contratos, compras diretas, obras paralisadas, "
        "penalidades, prestação de contas e concessões públicas do Estado "
        "e municípios do Rio de Janeiro."
    ),
    version="0.1.0",
    api_base="https://dados.tcerj.tc.br/api/v1",
    requires_auth=False,
    tags=["tce", "rj", "licitacoes", "contratos", "obras", "penalidades"],
)
