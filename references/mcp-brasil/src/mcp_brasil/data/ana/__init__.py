"""Feature ANA — dados hidrológicos da Agência Nacional de Águas."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="ana",
    description=(
        "ANA — Agência Nacional de Águas: estações hidrológicas, "
        "telemetria fluviométrica e monitoramento de reservatórios."
    ),
    version="0.1.0",
    api_base="https://www.snirh.gov.br/hidroweb/rest/api",
    requires_auth=False,
    tags=["agua", "hidrologia", "reservatorios", "rios", "chuva"],
)
