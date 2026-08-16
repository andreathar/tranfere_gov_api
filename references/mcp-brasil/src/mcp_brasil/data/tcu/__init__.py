"""Feature TCU — Tribunal de Contas da União."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tcu",
    description="Dados do TCU: acórdãos, inabilitados, inidôneos, certidões, débitos e contratos",
    version="0.1.0",
    api_base="https://dados-abertos.apps.tcu.gov.br/api",
    requires_auth=False,
    tags=["controle", "contas", "acordaos", "licitacoes", "certidoes"],
)
