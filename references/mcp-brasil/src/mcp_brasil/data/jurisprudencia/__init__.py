"""Feature Jurisprudência — Busca em tribunais superiores (STF, STJ, TST)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="jurisprudencia",
    description="Jurisprudência: busca de acórdãos, súmulas e decisões no STF, STJ e TST",
    version="0.1.0",
    api_base="https://jurisprudencia.stf.jus.br",
    requires_auth=False,
    tags=["judiciario", "jurisprudencia", "stf", "stj", "tst", "sumulas"],
)
