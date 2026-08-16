"""Feature TCE-TO — Dados Abertos do Tribunal de Contas do Tocantins."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_to",
    description=(
        "TCE-TO: processos, pautas de sessões e busca de pessoas "
        "do Tribunal de Contas do Tocantins via API e-Contas."
    ),
    version="0.1.0",
    api_base="https://api.tceto.tc.br/econtas/api",
    requires_auth=False,
    tags=["tce", "to", "processos", "pautas"],
)
