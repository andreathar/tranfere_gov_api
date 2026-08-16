"""Feature Saúde — dados de saúde pública, epidemiologia e infraestrutura via CNES/DataSUS."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="saude",
    description=(
        "CNES/DataSUS: estabelecimentos de saúde, profissionais, leitos, urgências, "
        "resumo de rede municipal e comparação. "
        "Epidemiologia: alertas InfoDengue (dengue/chikungunya/zika), "
        "InfoGripe (SRAG), catálogo DATASUS, doenças SINAN e geocódigos de municípios."
    ),
    version="0.2.0",
    api_base="https://apidadosabertos.saude.gov.br/cnes",
    requires_auth=False,
    tags=[
        "saude",
        "sus",
        "cnes",
        "hospitais",
        "leitos",
        "epidemiologia",
        "dengue",
        "arbovirose",
        "gripe",
        "sinan",
        "datasus",
    ],
)
