"""Feature RENAME — Relação Nacional de Medicamentos Essenciais."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="rename",
    description=(
        "RENAME: Relação Nacional de Medicamentos Essenciais do SUS. "
        "Consulta de medicamentos disponíveis no SUS por nome, princípio ativo "
        "ou grupo terapêutico, com informações de apresentação e posologia."
    ),
    version="0.1.0",
    api_base="",
    requires_auth=False,
    tags=["saude", "sus", "medicamentos", "rename", "essenciais"],
)
