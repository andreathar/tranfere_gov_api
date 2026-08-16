"""Feature TCE-PE — Dados Abertos do Tribunal de Contas de Pernambuco."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="tce_pe",
    description=(
        "TCE-PE: licitações, contratos, despesas e fornecedores "
        "dos municípios e órgãos estaduais de Pernambuco via API SAGRES/LICON."
    ),
    version="0.1.0",
    api_base="https://sistemas.tce.pe.gov.br/DadosAbertos",
    requires_auth=False,
    tags=["tce", "pe", "licitacoes", "contratos", "despesas", "fornecedores"],
)
