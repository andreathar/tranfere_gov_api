"""Feature inep_enem — Microdados do ENEM (INEP).

Microdados completos do Exame Nacional do Ensino Médio — inscrições,
perfil socioeconômico (Q001-Q025), notas por área e redação.

Atenção: dataset muito grande (~520 MB ZIP / ~2.5 GB CSV). Só ative
se tiver espaço em disco e memória suficientes.

Ativação: ``MCP_BRASIL_DATASETS=inep_enem`` no ``.env``.
"""

from mcp_brasil import settings
from mcp_brasil._shared.datasets import DatasetSpec
from mcp_brasil._shared.feature import FeatureMeta

from .constants import ANO_COBERTURA, ZIP_MEMBER, ZIP_URL

DATASET_ID = "inep_enem"
DATASET_TABLE = "enem"

DATASET_SPEC = DatasetSpec(
    id=DATASET_ID,
    url=ZIP_URL,
    zip_member=ZIP_MEMBER,
    table=DATASET_TABLE,
    ttl_days=365,
    approx_size_mb=2500,  # CSV descomprimido
    source=f"Inep — Microdados ENEM {ANO_COBERTURA}",
    description=(
        f"Microdados ENEM {ANO_COBERTURA}: ~3,9M inscritos com perfil "
        "socioeconômico, notas (CN/CH/LC/MT/Redação) e situação da prova."
    ),
    source_encoding="cp1252",
    csv_options={
        "delim": ";",
        "header": True,
        "decimal_separator": ",",
        "ignore_errors": True,
        "sample_size": -1,
        "nullstr": ["", " "],
        "dtypes": {
            "NU_NOTA_CN": "DOUBLE",
            "NU_NOTA_CH": "DOUBLE",
            "NU_NOTA_LC": "DOUBLE",
            "NU_NOTA_MT": "DOUBLE",
            "NU_NOTA_REDACAO": "DOUBLE",
        },
    },
    # NU_INSCRICAO é identificador único do inscrito — sensível.
    pii_columns=frozenset({"NU_INSCRICAO"}),
)

FEATURE_META = FeatureMeta(
    name=DATASET_ID,
    description=(
        f"ENEM {ANO_COBERTURA} (Inep): microdados de ~3,9M inscritos com "
        "notas e perfil socioeconômico. Consulta SQL via DuckDB. "
        "Dataset pesado — ~2,5 GB descomprimido. "
        "Opt-in: MCP_BRASIL_DATASETS=inep_enem."
    ),
    version="0.1.0",
    api_base="https://download.inep.gov.br",
    requires_auth=False,
    enabled=DATASET_ID in settings.DATASETS_ENABLED,
    tags=[
        "inep",
        "educacao",
        "enem",
        "notas",
        "socioeconomico",
        "dataset",
        "duckdb",
    ],
)
