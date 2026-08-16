"""Feature INEP — Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="inep",
    description=(
        "Dados do INEP: IDEB por estado/região, catálogo de microdados "
        "(Censo Escolar, ENEM, SAEB, ENADE), indicadores educacionais"
    ),
    version="0.1.0",
    api_base="https://download.inep.gov.br",
    requires_auth=False,
    tags=["educação", "ideb", "censo escolar", "enem", "saeb", "escola"],
)
