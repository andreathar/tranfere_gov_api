"""Feature inep_censo_escolar — Censo Escolar da Educação Básica (INEP).

Microdados anuais de todas as escolas de educação básica do Brasil —
nome, localização, dependência administrativa, matrículas por etapa,
infraestrutura (água, energia, internet, biblioteca, quadra, etc.).

Fonte: Inep — `download.inep.gov.br/dados_abertos/`.
Cobertura inicial: ano 2023 (~210 MB descomprimido, ~32 MB zipped).

Ativação: ``MCP_BRASIL_DATASETS=inep_censo_escolar`` no ``.env``.
"""

from mcp_brasil import settings
from mcp_brasil._shared.datasets import DatasetSpec
from mcp_brasil._shared.feature import FeatureMeta

from .constants import ANO_COBERTURA, ZIP_MEMBER, ZIP_URL

DATASET_ID = "inep_censo_escolar"
DATASET_TABLE = "escolas"

DATASET_SPEC = DatasetSpec(
    id=DATASET_ID,
    url=ZIP_URL,
    zip_member=ZIP_MEMBER,
    table=DATASET_TABLE,
    ttl_days=365,  # atualizado 1x/ano
    approx_size_mb=220,
    source=f"Inep — Censo Escolar da Educação Básica {ANO_COBERTURA}",
    description=(
        f"Microdados Censo Escolar {ANO_COBERTURA}: todas as escolas de "
        "educação básica do Brasil com atributos de infraestrutura, "
        "dependência administrativa e matrículas por etapa."
    ),
    source_encoding="cp1252",
    csv_options={
        "delim": ";",
        "header": True,
        "ignore_errors": True,
        "sample_size": -1,
        "nullstr": ["", " "],
    },
    # Dados Inep são de escolas (institucional) — sem PII de alunos/profissionais.
    pii_columns=frozenset(),
)

FEATURE_META = FeatureMeta(
    name=DATASET_ID,
    description=(
        f"Censo Escolar {ANO_COBERTURA} (Inep): ~180k escolas com infraestrutura "
        "e matrículas. Consulta SQL via DuckDB local. "
        "Opt-in: MCP_BRASIL_DATASETS=inep_censo_escolar."
    ),
    version="0.1.0",
    api_base="https://download.inep.gov.br",
    requires_auth=False,
    enabled=DATASET_ID in settings.DATASETS_ENABLED,
    tags=[
        "inep",
        "educacao",
        "censo-escolar",
        "escolas",
        "matriculas",
        "infraestrutura",
        "dataset",
        "duckdb",
    ],
)
