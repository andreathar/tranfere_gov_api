"""Feature TCE-RN — Dados Abertos do Tribunal de Contas do Rio Grande do Norte."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_rn",
    description=(
        "TCE-RN: jurisdicionados, licitações, contratos, despesas e receitas "
        "do Rio Grande do Norte via API SIAI do TCE-RN."
    ),
    version="0.1.0",
    api_base="https://apidadosabertos.tce.rn.gov.br",
    requires_auth=False,
    tags=["tce", "rn", "licitacoes", "contratos", "despesas", "receitas"],
)
