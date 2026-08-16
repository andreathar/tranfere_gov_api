"""Feature Diário Oficial — busca em diários oficiais municipais e federais."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="diario_oficial",
    description=(
        "Diários oficiais: busca em diários municipais (Querido Diário, 5.000+ cidades) "
        "e no Diário Oficial da União (DOU federal). Contratos, nomeações, licitações, "
        "decretos, portarias e atos administrativos."
    ),
    version="0.2.0",
    api_base="https://api.queridodiario.ok.org.br",
    requires_auth=False,
    tags=[
        "diario-oficial",
        "transparencia",
        "municipios",
        "federal",
        "dou",
        "licitacoes",
        "contratos",
    ],
)
