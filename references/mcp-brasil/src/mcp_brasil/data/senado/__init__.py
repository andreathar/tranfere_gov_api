"""Feature Senado — Senado Federal (Dados Abertos)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="senado",
    description="Senado Federal: senadores, matérias, votações, comissões, agenda plenária",
    version="0.1.0",
    api_base="https://legis.senado.leg.br/dadosabertos",
    requires_auth=False,
    tags=["legislativo", "senadores", "matérias", "votações", "comissões", "agenda"],
)
