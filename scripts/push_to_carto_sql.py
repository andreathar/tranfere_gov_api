#!/usr/bin/env python3
"""
Push local CSVs into CARTO Data Warehouse via CARTO SQL API.

The existing API key has SQL permission (not imports), so we:
1. CREATE OR REPLACE TABLE using CTAS (SELECT ... UNION ALL ...) for small tables
2. Use batched INSERT INTO for larger tables
"""

import csv
import io
import json
import os
import sys
import time

import requests

API_KEY = os.environ.get("CARTO_API_KEY") or sys.exit(
    "CARTO_API_KEY não definida: carregue o .env (o token não fica mais no código)."
)
SQL_URL = "https://gcp-us-east1.api.carto.com/v3/sql/carto_dw/query"
PRIVATE_DS = "carto-dw-ac-xx7br32v.private_andreabenathar_a5f83fac"
EXPORTS_DIR = "data/carto_exports"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# Rows per INSERT batch (BigQuery limit is ~1MB per request)
BATCH_SIZE = 200


def sql_null(force_string: bool) -> str:
    return "CAST(NULL AS STRING)" if force_string else "NULL"


def sql_value(v: str, force_string: bool = False) -> str:
    """Escape a value for BigQuery SQL."""
    if v == "" or v is None:
        return sql_null(force_string)
    if not force_string:
        # Try int
        try:
            int(v)
            return str(int(v))
        except ValueError:
            pass
        # Try float
        try:
            float(v)
            return str(float(v))
        except ValueError:
            pass
    # String — sanitize and escape
    clean = v.replace("\x00", "").replace("\r", " ").replace("\n", " ").replace("\\", "\\\\")
    escaped = clean.replace("'", "\\'")
    return f"'{escaped}'"


def _infer_string_cols(rows: list[dict], cols: list[str]) -> set[str]:
    """Return cols that have at least one non-numeric, non-empty value across ALL rows."""
    str_cols = set()
    remaining = set(cols)
    for row in rows:
        if not remaining:
            break
        done = set()
        for c in list(remaining):
            v = row.get(c, "")
            if not v:
                continue
            try:
                int(v)
                continue
            except ValueError:
                pass
            try:
                float(v)
                continue
            except ValueError:
                pass
            str_cols.add(c)
            done.add(c)
        remaining -= done
    return str_cols


def run_sql(q: str) -> dict:
    resp = requests.post(SQL_URL, headers=HEADERS, json={"q": q}, timeout=120)
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def push_csv(csv_path: str, table_fqn: str) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        rows = list(reader)

    print(f"  {len(rows)} rows × {len(cols)} cols")

    # Detect which columns are strings (to force-quote them consistently)
    str_cols = _infer_string_cols(rows, cols)

    def row_to_select(row: dict) -> str:
        parts = []
        for c in cols:
            v = row.get(c, "")
            fs = c in str_cols
            parts.append(f"{sql_value(v, force_string=fs)} AS `{c}`")
        return "SELECT " + ", ".join(parts)

    def row_values(row: dict) -> str:
        return "(" + ", ".join(sql_value(row.get(c, ""), force_string=c in str_cols) for c in cols) + ")"

    # Step 1: CREATE table from first row (sets schema)
    create_sql = f"CREATE OR REPLACE TABLE `{table_fqn}` AS\n{row_to_select(rows[0])}"
    run_sql(create_sql)
    print(f"  Table created (string cols: {len(str_cols)}).")

    # Step 2: INSERT remaining rows in batches
    if len(rows) <= 1:
        return

    remaining = rows[1:]
    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i:i + BATCH_SIZE]
        values = ",\n".join(row_values(row) for row in batch)
        insert_sql = (
            f"INSERT INTO `{table_fqn}` "
            f"({', '.join(f'`{c}`' for c in cols)})\n"
            f"VALUES\n{values}"
        )
        run_sql(insert_sql)
        inserted = i + 1 + len(batch)
        print(f"  Inserted {inserted}/{len(rows)} rows...", end="\r")
        time.sleep(0.1)

    print(f"  ✓ All {len(rows)} rows inserted.              ")


def main():
    tables = {
        "transferegov_deputados_distritais": "transferegov_deputados_distritais",
        "transferegov_cldf_emendas": "transferegov_cldf_emendas",
        "transferegov_cldf_dodf": "transferegov_cldf_dodf",
        "transferegov_cldf_verbas": "transferegov_cldf_verbas",
    }

    # Allow filtering via CLI args
    if len(sys.argv) > 1:
        keys = sys.argv[1].split(",")
        tables = {k: v for k, v in tables.items() if k in keys}

    for csv_name, bq_table in tables.items():
        csv_path = os.path.join(EXPORTS_DIR, f"{csv_name}.csv")
        if not os.path.exists(csv_path):
            print(f"[SKIP] {csv_path} not found")
            continue

        table_fqn = f"{PRIVATE_DS}.{bq_table}"
        print(f"\n→ Pushing {csv_name} → {table_fqn}")
        try:
            push_csv(csv_path, table_fqn)
        except Exception as e:
            print(f"  ✗ Error: {e}", file=sys.stderr)

    print("\n✓ Done. Check https://app.carto.com → Data Explorer → carto_dw → private")


if __name__ == "__main__":
    main()
