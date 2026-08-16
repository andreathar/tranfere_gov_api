"""Dataset specification model (ADR-004)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SourceFormat = Literal["csv", "parquet", "xlsx"]


@dataclass(frozen=True)
class DatasetSpec:
    """Declarative specification of a cached local dataset.

    Each ``datasets/{id}/__init__.py`` must export a ``DATASET_SPEC`` of this
    type alongside the standard ``FEATURE_META`` from ADR-002.

    Attributes:
        id: Stable identifier used in env vars and tool names (snake_case).
        url: Public URL of the source CSV/Parquet/ZIP.
        table: Name of the table created in the DuckDB file.
        ttl_days: Days between automatic refreshes.
        csv_options: ``duckdb.read_csv_auto`` options (delim, header,
            encoding, sample_size, names, dtypes, etc). See
            https://duckdb.org/docs/data/csv/overview.html
        pii_columns: Columns treated as PII — masked unless dataset is in
            ``MCP_BRASIL_LGPD_ALLOW_PII``.
        approx_size_mb: Documented size; used by ``listar_datasets``.
        source: Human-readable source attribution.
        description: One-line description shown in listings.
    """

    id: str
    url: str
    table: str
    ttl_days: int = 30
    csv_options: dict[str, Any] = field(default_factory=dict)
    pii_columns: frozenset[str] = frozenset()
    approx_size_mb: int = 0
    source: str = ""
    description: str = ""
    # Encoding of the source file at the URL. When set to anything other than
    # "utf-8"/"latin-1"/"utf-16" (the DuckDB-supported set), the loader
    # transcodes the stream to UTF-8 on disk before handing it to DuckDB.
    # Common case: "cp1252" (Windows-1252 — smart quotes, en-dashes, etc.).
    source_encoding: str = "utf-8"
    # When the source is a ZIP archive, name (or glob) of the CSV member to
    # extract. The loader downloads the ZIP, extracts this member, transcodes
    # if needed, and feeds it to DuckDB. Example: "consulta_cand_2024_BRASIL.csv".
    zip_member: str | None = None
    # Multi-source support — tuples of (url, zip_member_or_None, suffix).
    # When non-empty, the loader:
    #   1. Loads each source into a per-year table named f"{table}_{suffix}"
    #   2. Creates a view named `table` doing UNION ALL BY NAME across all
    # The "main" url/zip_member fields above are ignored when sources is set.
    sources: tuple[tuple[str, str | None, str], ...] = ()
    # Source file format. CSV (default) is read via read_csv_auto with
    # csv_options. Parquet is read via read_parquet (csv_options ignored,
    # source_encoding ignored — binary format). XLSX is pre-converted to CSV
    # via openpyxl before ingestion, then read as CSV (csv_options apply to
    # the converted file, though defaults usually work).
    source_format: SourceFormat = "csv"
    # XLSX only: sheet name (str) or 0-based index (int) to extract. Ignored
    # for csv/parquet.
    xlsx_sheet: str | int = 0

    def __post_init__(self) -> None:
        if not self.id or not self.id.replace("_", "").isalnum():
            raise ValueError(f"Invalid dataset id: {self.id!r}")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"Dataset URL must be http(s): {self.url!r}")
        if self.source_format not in ("csv", "parquet", "xlsx"):
            raise ValueError(f"Invalid source_format: {self.source_format!r}")
        if self.source_format == "parquet" and self.zip_member:
            raise ValueError("zip_member is not supported for parquet sources")
