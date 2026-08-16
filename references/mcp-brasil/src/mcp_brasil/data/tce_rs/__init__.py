"""Feature TCE-RS — Dados Abertos do Tribunal de Contas do Rio Grande do Sul."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_rs",
    description=(
        "TCE-RS: índices de educação e saúde, gestão fiscal (LRF) "
        "e catálogo de datasets dos municípios do Rio Grande do Sul "
        "via portal CKAN do TCE-RS."
    ),
    version="0.1.0",
    api_base="https://dados.tce.rs.gov.br",
    requires_auth=False,
    tags=["tce", "rs", "educacao", "saude", "gestao-fiscal", "ckan"],
)
