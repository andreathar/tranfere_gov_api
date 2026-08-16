"""Feature Redator Oficial — Geração de documentos oficiais."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="redator",
    description="Redação oficial: ofício, despacho, portaria, parecer, nota técnica",
    version="0.1.0",
    requires_auth=False,
    tags=["documentos", "redacao-oficial", "govtech"],
)
