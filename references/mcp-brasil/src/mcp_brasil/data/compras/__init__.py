"""Feature Compras — contratações públicas federais, estaduais e municipais.

Sub-packages:
    - pncp: Portal Nacional de Contratações Públicas (Lei 14.133/2021)
    - dadosabertos: Dados Abertos Compras.gov.br (SIASG/ComprasNet legado + nova API)
    - contratosgovbr: Contratos.gov.br (contratos federais pós-2021)
"""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="compras",
    description=(
        "Compras públicas: PNCP, Dados Abertos Compras.gov.br, Contratos.gov.br "
        "(licitações, contratos, fornecedores, CATMAT, CATSER, pregões, empenhos)."
    ),
    version="0.3.0",
    api_base="https://pncp.gov.br/api/consulta",
    requires_auth=False,
    tags=[
        "licitacoes",
        "contratos",
        "compras",
        "pncp",
        "fornecedores",
        "catmat",
        "catser",
        "empenhos",
    ],
)
