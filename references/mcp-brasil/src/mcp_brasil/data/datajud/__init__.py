"""Feature DataJud — API Pública do Conselho Nacional de Justiça (CNJ)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="datajud",
    description="DataJud (CNJ): processos judiciais, movimentações e assuntos de tribunais",
    version="0.1.0",
    api_base="https://api-publica.datajud.cnj.jus.br",
    requires_auth=True,
    auth_env_var="DATAJUD_API_KEY",
    tags=["judiciario", "processos", "cnj", "tribunais", "datajud"],
)
