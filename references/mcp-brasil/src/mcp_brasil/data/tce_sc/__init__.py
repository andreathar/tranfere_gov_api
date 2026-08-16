"""Feature TCE-SC — Dados Abertos do Tribunal de Contas de Santa Catarina."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_sc",
    description=(
        "TCE-SC: municípios e unidades gestoras de Santa Catarina "
        "via Portal da Transparência do TCE-SC."
    ),
    version="0.1.0",
    api_base="https://servicos.tcesc.tc.br/endpoints-portal-transparencia",
    requires_auth=False,
    tags=["tce", "sc", "municipios", "unidades-gestoras"],
)
