"""Feature ANVISA — Agência Nacional de Vigilância Sanitária."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="anvisa",
    description=(
        "ANVISA: busca de medicamentos no Bulário Eletrônico, consulta de bulas, "
        "categorias (genérico, similar, referência), princípios ativos, "
        "preços CMED e registros de medicamentos."
    ),
    version="0.1.0",
    api_base="https://consultas.anvisa.gov.br/api/consulta",
    requires_auth=False,
    tags=["saude", "anvisa", "medicamentos", "bulas", "bulario"],
)
