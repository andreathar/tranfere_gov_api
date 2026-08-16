"""Feature IBGE — Instituto Brasileiro de Geografia e Estatística."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="ibge",
    description="Dados do IBGE: estados, municípios, regiões, nomes e agregados estatísticos",
    version="0.1.0",
    api_base="https://servicodados.ibge.gov.br/api",
    requires_auth=False,
    tags=["geodados", "censo", "indicadores", "localidades"],
)
