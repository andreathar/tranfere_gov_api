"""Feature TSE — Tribunal Superior Eleitoral (DivulgaCandContas)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tse",
    description="TSE: eleições, candidatos, prestação de contas, cargos eleitorais",
    version="0.1.0",
    api_base="https://divulgacandcontas.tse.jus.br/divulga/rest/v1",
    requires_auth=False,
    tags=["eleitoral", "candidatos", "eleicoes", "tse", "prestacao-contas"],
)
