"""Feature anp_precos — série histórica de preços de combustíveis (ANP).

CSV mensal por tipo de combustível (gasolina/etanol, diesel/GNV, GLP).
Cobertura inicial: ano ${ANO_COBERTURA} integral (36 arquivos). ~25 MB agregado.

Fonte: Agência Nacional do Petróleo, Gás Natural e Biocombustíveis.
Pesquisa semanal de preços em postos revendedores (art. 8º Lei nº 9.478/1997).

Ativação: ``MCP_BRASIL_DATASETS=anp_precos`` no ``.env``.
"""

from mcp_brasil import settings
from mcp_brasil._shared.datasets import DatasetSpec
from mcp_brasil._shared.feature import FeatureMeta

from .constants import ANO_COBERTURA, COLUMN_NAMES, SOURCES

DATASET_ID = "anp_precos"
DATASET_TABLE = "precos_combustiveis"

DATASET_SPEC = DatasetSpec(
    id=DATASET_ID,
    url=SOURCES[0][0],  # placeholder — sources tuple is authoritative
    sources=SOURCES,
    table=DATASET_TABLE,
    ttl_days=30,
    approx_size_mb=25,
    source="ANP — Pesquisa semanal de preços de combustíveis",
    description=(
        f"Preços semanais de combustíveis em postos revendedores (ANP), "
        f"cobertura {ANO_COBERTURA} integral por gasolina/etanol, diesel/GNV e GLP."
    ),
    # Arquivos ANP vêm com BOM UTF-8 — DuckDB lida nativamente.
    source_encoding="utf-8",
    csv_options={
        "delim": ";",
        "header": True,
        "decimal_separator": ",",
        "ignore_errors": True,
        "sample_size": -1,
        "names": COLUMN_NAMES,
        "skip": 1,  # pula o header original (diferente dos nomes renomeados)
        "dtypes": {
            "valor_venda": "DOUBLE",
            "valor_compra": "DOUBLE",
        },
    },
    # CNPJ da revenda é PII (pessoa jurídica — não tão sensível, mas LGPD aplica)
    pii_columns=frozenset({"cnpj_revenda"}),
)

FEATURE_META = FeatureMeta(
    name=DATASET_ID,
    description=(
        "ANP — preços semanais de combustíveis por posto/município/bandeira "
        f"(cobertura {ANO_COBERTURA}). Consulta SQL via DuckDB local. "
        "Opt-in: MCP_BRASIL_DATASETS=anp_precos."
    ),
    version="0.1.0",
    api_base="https://www.gov.br/anp",
    requires_auth=False,
    enabled=DATASET_ID in settings.DATASETS_ENABLED,
    tags=[
        "anp",
        "combustiveis",
        "precos",
        "gasolina",
        "etanol",
        "diesel",
        "glp",
        "dataset",
        "duckdb",
    ],
)
