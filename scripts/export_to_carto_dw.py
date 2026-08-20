#!/usr/bin/env python3
"""
Export key TransfereGov tables to CARTO Data Warehouse (BigQuery).

CARTO's cloud cannot reach our local PostgreSQL (127.0.0.1), so we export
data via CARTO's Import API into the project carto-dw-ac-xx7br32v.

Usage:
    python scripts/export_to_carto_dw.py [--tables all|deputados|emendas|dodf|verbas]

Requires:
    CARTO_API_KEY env var (already in .env)
"""

import argparse
import csv
import io
import json
import os
import sys

import psycopg2
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CARTO_API_KEY = os.environ.get("CARTO_API_KEY") or sys.exit(
    "CARTO_API_KEY não definida: carregue o .env (o token não fica mais no código)."
)
CARTO_BASE = "https://gcp-us-east1.api.carto.com/v3"
CARTO_CONN_ID = "e6722957-f80e-452f-bc62-9494a810d527"  # carto_dw BigQuery connection

PG_DSN = "postgresql://cognee:cognee@127.0.0.1:5432/transferegov_db"

HEADERS = {
    "Authorization": f"Bearer {CARTO_API_KEY}",
    "Content-Type": "application/json",
}

# Tables to export: {local_query: carto_table_name}
EXPORTS = {
    "deputados": {
        "query": """
            SELECT
                id, nome_candidato, nr_candidato, sigla_partido,
                situacao, legislatura, ocupacao, sexo, grau_instrucao,
                estado_civil, idade, uf_nascimento,
                votos_total, pct_votos, total_bens, gasto_campanha_r1
            FROM df_deputados_distritais_cldf
            LIMIT 100
        """,
        "table": "transferegov_deputados_distritais",
    },
    "emendas": {
        "query": """
            SELECT
                id, nr_emenda, ano_emenda, nome_uo, cod_uo,
                status_emenda, pt,
                vl_emenda, vl_empenhado, vl_liquidado,
                vl_disponivel, vl_bloqueado_siggo
            FROM cldf_emendas
            LIMIT 5000
        """,
        "table": "transferegov_cldf_emendas",
    },
    "dodf": {
        "query": """
            SELECT
                id, deputado_nome, date_pub::text AS date_pub,
                gazette_url, txt_url, edition,
                SUBSTRING(excerpt, 1, 500) AS excerpt,
                query_term, sq_candidato
            FROM cldf_dodf_mentions
            ORDER BY date_pub DESC
            LIMIT 5000
        """,
        "table": "transferegov_cldf_dodf",
    },
    "verbas": {
        "query": """
            SELECT
                id, nome_parlamentar, cpf_parlamentar,
                nome_prestador, cnpj_prestador,
                data_comprovante::text AS data_comprovante,
                valor_despesa, classificacao, observacoes
            FROM cldf_verbas_indenizatorias
            LIMIT 10000
        """,
        "table": "transferegov_cldf_verbas",
    },
}


def pg_to_csv(query: str) -> bytes:
    """Run query against local PostgreSQL and return UTF-8 CSV bytes."""
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()
    cur.execute(query)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for row in rows:
        writer.writerow([str(v) if v is not None else "" for v in row])
    return buf.getvalue().encode("utf-8")


def import_via_url(ndjson_url: str, table_name: str) -> str:
    """Trigger CARTO Import API using a public URL (ngrok etc.)."""
    resp = requests.post(
        f"{CARTO_BASE}/imports",
        headers=HEADERS,
        json={
            "url": ndjson_url,
            "connection_id": CARTO_CONN_ID,
            "table_name": table_name,
            "if_exists": "replace",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("job_id") or data.get("id") or str(data)


def save_csv(data: bytes, table_name: str, out_dir: str = "data/carto_exports") -> str:
    """Save CSV to disk. Returns the file path."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{table_name}.csv")
    with open(path, "wb") as f:
        f.write(data)
    return path


def export_table(key: str, spec: dict, public_base_url: str | None = None) -> None:
    print(f"\n→ Exporting '{key}' → '{spec['table']}'...")
    data = pg_to_csv(spec["query"])
    row_count = data.count(b"\n") - 1  # subtract header
    print(f"  Fetched {row_count} rows ({len(data):,} bytes)")

    path = save_csv(data, spec["table"])
    print(f"  Saved → {path}")

    if public_base_url:
        url = f"{public_base_url.rstrip('/')}/{spec['table']}.csv"
        try:
            job_id = import_via_url(url, spec["table"])
            print(f"  CARTO import job: {job_id}")
            print(f"  ✓ Triggered. Check https://app.carto.com → Data Explorer → {spec['table']}")
        except Exception as e:
            print(f"  ✗ CARTO import error: {e}", file=sys.stderr)
            print(f"  → Upload manually: https://app.carto.com (drag & drop {path})")
    else:
        print(f"  ✓ Ready. Upload manually:")
        print(f"    1. Go to https://app.carto.com → Data Explorer")
        print(f"    2. Click 'Import data' → drag & drop  {path}")
        print(f"    OR re-run with --public-url https://<ngrok-id>.ngrok.io/data/carto_exports")


def main():
    parser = argparse.ArgumentParser(description="Export TransfereGov data to CARTO DW")
    parser.add_argument(
        "--tables",
        default="all",
        help="Comma-separated list of tables to export: all | deputados,emendas,dodf,verbas",
    )
    parser.add_argument(
        "--public-url",
        default=None,
        help="Public base URL serving data/carto_exports/ (e.g. https://abc123.ngrok.io). "
             "If omitted, files are saved locally for manual CARTO web upload.",
    )
    args = parser.parse_args()

    keys = list(EXPORTS.keys()) if args.tables == "all" else [t.strip() for t in args.tables.split(",")]
    unknown = [k for k in keys if k not in EXPORTS]
    if unknown:
        print(f"Unknown tables: {unknown}. Valid: {list(EXPORTS.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"CARTO Export — {len(keys)} table(s): {keys}")
    print(f"Target connection: carto_dw (BigQuery project carto-dw-ac-xx7br32v)")

    for key in keys:
        try:
            export_table(key, EXPORTS[key], args.public_url)
        except Exception as e:
            print(f"  ✗ Failed '{key}': {e}", file=sys.stderr)

    print("\n✓ Export complete. NDJSON files in data/carto_exports/")


if __name__ == "__main__":
    main()
