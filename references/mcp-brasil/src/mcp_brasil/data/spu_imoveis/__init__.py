"""Feature SPU-Imoveis — Patrimônio da União (Raio-X APF / Gov360)."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="spu_imoveis",
    description=(
        "Imóveis da União (Raio-X APF / Gov360): consulta de imóveis federais "
        "por órgão, UF, município, regime de utilização (aforamento, ocupação, "
        "imóvel funcional, etc.) e tipo de destinação. Dados consolidados do "
        "SPUnet/SIAPA republicados mensalmente pelo MGI em repositorio.dados.gov.br."
    ),
    version="0.1.0",
    api_base="https://repositorio.dados.gov.br/seges/raio-x",
    requires_auth=False,
    tags=[
        "spu",
        "imoveis-uniao",
        "patrimonio",
        "raio-x",
        "gov360",
        "mgi",
        "administracao-publica-federal",
    ],
)
