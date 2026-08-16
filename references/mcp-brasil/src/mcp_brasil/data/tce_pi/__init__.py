"""Feature TCE-PI — Portal da Cidadania do Tribunal de Contas do Piauí."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_pi",
    description=(
        "TCE-PI: prefeituras, despesas, receitas e órgãos do Piauí "
        "via API do Portal da Cidadania do TCE-PI."
    ),
    version="0.1.0",
    api_base="https://sistemas.tce.pi.gov.br/api/portaldacidadania",
    requires_auth=False,
    tags=["tce", "pi", "prefeituras", "despesas", "receitas", "orgaos"],
)
