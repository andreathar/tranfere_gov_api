"""Feature Fórum Brasileiro de Segurança Pública — repositório de publicações."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="forum_seguranca",
    description=(
        "Fórum Brasileiro de Segurança Pública: publicações sobre segurança pública, "
        "violência, sistema prisional, Atlas da Violência e Anuário via DSpace API."
    ),
    version="0.1.0",
    api_base="https://publicacoes.forumseguranca.org.br/server/api",
    requires_auth=False,
    tags=["seguranca-publica", "violencia", "dspace", "publicacoes", "forum-seguranca"],
)
