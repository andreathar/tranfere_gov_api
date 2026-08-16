"""Feature FNDE — Fundo Nacional de Desenvolvimento da Educação."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="fnde",
    description=(
        "Dados do FNDE: matrículas FUNDEB, alimentação escolar (PNAE), "
        "livro didático (PNLD) e transporte escolar (PNATE)"
    ),
    version="0.1.0",
    api_base="https://www.fnde.gov.br/olinda-ide/servico",
    requires_auth=False,
    tags=["educação", "fundeb", "pnae", "pnld", "pnate", "escola"],
)
