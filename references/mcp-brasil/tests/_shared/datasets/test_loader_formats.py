"""Tests for Parquet and XLSX source formats in the dataset loader.

These exercise the Fase 0 extension that added ``source_format`` and
``xlsx_sheet`` to DatasetSpec. Fixtures are generated in-process (DuckDB
for Parquet, openpyxl for XLSX) so no network is required.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest
from openpyxl import Workbook

from mcp_brasil import settings
from mcp_brasil._shared.datasets import DatasetSpec, ensure_loaded, executar_query


@pytest.fixture
def tmp_cache(monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tempfile.mkdtemp(prefix="mcp-brasil-test-fmt-")
    monkeypatch.setattr(settings, "DATASET_CACHE_DIR", d)
    return Path(d)


@pytest.fixture
def parquet_bytes(tmp_path: Path) -> bytes:
    """Generate a small Parquet file and return its bytes."""
    pq = tmp_path / "fixture.parquet"
    con = duckdb.connect()
    try:
        con.execute(
            "COPY (SELECT * FROM (VALUES "
            "('MEC','SP',1000.5),"
            "('MD','DF',200.0),"
            "('MGI','RJ',50.25)"
            ") t(orgao, uf, valor)) "
            f"TO '{pq}' (FORMAT PARQUET)"
        )
    finally:
        con.close()
    return pq.read_bytes()


@pytest.fixture
def xlsx_bytes(tmp_path: Path) -> bytes:
    """Generate a small single-sheet XLSX file and return its bytes."""
    xlsx = tmp_path / "fixture.xlsx"
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "dados"
    ws.append(["orgao", "uf", "valor"])
    ws.append(["MEC", "SP", 1000.5])
    ws.append(["MD", "DF", 200.0])
    ws.append(["MGI", "RJ", 50.25])
    # Second sheet to exercise xlsx_sheet selection
    ws2 = wb.create_sheet("outra")
    ws2.append(["x"])
    ws2.append([1])
    wb.save(xlsx)
    return xlsx.read_bytes()


# ---------------------------------------------------------------------------
# Spec validation
# ---------------------------------------------------------------------------


def test_spec_rejects_invalid_source_format() -> None:
    with pytest.raises(ValueError, match="source_format"):
        DatasetSpec(
            id="x",
            url="https://e.test/y",
            table="t",
            source_format="avro",  # type: ignore[arg-type]
        )


def test_spec_rejects_parquet_with_zip_member() -> None:
    with pytest.raises(ValueError, match="zip_member"):
        DatasetSpec(
            id="x",
            url="https://e.test/y.zip",
            table="t",
            source_format="parquet",
            zip_member="x.parquet",
        )


# ---------------------------------------------------------------------------
# Parquet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parquet_loads_and_queries(tmp_cache: Path, parquet_bytes: bytes) -> None:
    spec = DatasetSpec(
        id="test_parquet",
        url="https://example.invalid/x.parquet",
        table="amostra",
        source_format="parquet",
        source="unit test",
    )

    def _fake_binary(url: str, dest: Path, timeout: float) -> int:
        dest.write_bytes(parquet_bytes)
        return len(parquet_bytes)

    with patch(
        "mcp_brasil._shared.datasets.loader._download_binary",
        side_effect=_fake_binary,
    ):
        m = await ensure_loaded(spec)
        rows = await executar_query(
            spec,
            "SELECT orgao, valor FROM amostra WHERE uf = ? ORDER BY orgao",
            ["SP"],
        )

    assert m.row_count == 3
    assert rows == [{"orgao": "MEC", "valor": 1000.5}]


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xlsx_loads_default_sheet(tmp_cache: Path, xlsx_bytes: bytes) -> None:
    spec = DatasetSpec(
        id="test_xlsx",
        url="https://example.invalid/x.xlsx",
        table="dados",
        source_format="xlsx",
        source="unit test",
    )

    def _fake_binary(url: str, dest: Path, timeout: float) -> int:
        dest.write_bytes(xlsx_bytes)
        return len(xlsx_bytes)

    with patch(
        "mcp_brasil._shared.datasets.loader._download_binary",
        side_effect=_fake_binary,
    ):
        m = await ensure_loaded(spec)
        rows = await executar_query(spec, "SELECT orgao FROM dados WHERE uf = 'DF'")

    assert m.row_count == 3
    assert rows == [{"orgao": "MD"}]


@pytest.mark.asyncio
async def test_xlsx_sheet_by_name(tmp_cache: Path, xlsx_bytes: bytes) -> None:
    spec = DatasetSpec(
        id="test_xlsx_named",
        url="https://example.invalid/x.xlsx",
        table="outro",
        source_format="xlsx",
        xlsx_sheet="outra",
        source="unit test",
    )

    def _fake_binary(url: str, dest: Path, timeout: float) -> int:
        dest.write_bytes(xlsx_bytes)
        return len(xlsx_bytes)

    with patch(
        "mcp_brasil._shared.datasets.loader._download_binary",
        side_effect=_fake_binary,
    ):
        m = await ensure_loaded(spec)

    assert m.row_count == 1


def test_xlsx_to_csv_rejects_bad_sheet(xlsx_bytes: bytes, tmp_path: Path) -> None:
    from mcp_brasil._shared.datasets.loader import _xlsx_to_csv

    xlsx = tmp_path / "f.xlsx"
    xlsx.write_bytes(xlsx_bytes)
    csv = tmp_path / "f.csv"
    with pytest.raises(RuntimeError, match="sheet"):
        _xlsx_to_csv(xlsx, csv, sheet="nao_existe")


# ---------------------------------------------------------------------------
# Render dispatch
# ---------------------------------------------------------------------------


def test_render_read_call_parquet() -> None:
    from mcp_brasil._shared.datasets.loader import _render_read_call

    spec = DatasetSpec(
        id="x",
        url="https://e.test/y.parquet",
        table="t",
        source_format="parquet",
    )
    out = _render_read_call(Path("/tmp/a.parquet"), spec)
    assert out.startswith("read_parquet('")
    assert "/tmp/a.parquet" in out


def test_render_read_call_csv_keeps_options() -> None:
    from mcp_brasil._shared.datasets.loader import _render_read_call

    spec = DatasetSpec(
        id="x",
        url="https://e.test/y.csv",
        table="t",
        csv_options={"delim": ";"},
    )
    out = _render_read_call(Path("/tmp/a.csv"), spec)
    assert out.startswith("read_csv_auto('")
    assert "delim=';'" in out
