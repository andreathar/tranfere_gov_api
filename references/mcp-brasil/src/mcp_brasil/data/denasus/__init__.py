"""Feature DENASUS — Departamento Nacional de Auditoria do SUS."""

from mcp_brasil._shared.feature import FeatureMeta

FEATURE_META = FeatureMeta(
    name="denasus",
    description=(
        "DENASUS: Departamento Nacional de Auditoria do SUS. "
        "Atividades de auditoria, relatórios anuais e planos "
        "de auditoria interna do Sistema Nacional de Auditoria."
    ),
    version="0.1.0",
    api_base="https://www.gov.br/saude/pt-br/composicao/denasus",
    requires_auth=False,
    tags=["saude", "sus", "auditoria", "denasus", "transparencia"],
)
