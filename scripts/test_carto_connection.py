#!/usr/bin/env python3
"""
Test Carto DB connection using CARTO_PG_* env vars or CARTO_DATABASE_URL from config.settings.

Usage:
  export CARTO_PG_HOST=... CARTO_PG_PORT=... CARTO_PG_DB=... CARTO_PG_USER=... CARTO_PG_PASS=...
  .venv/bin/python scripts/test_carto_connection.py

Or set CARTO_DATABASE_URL in the environment.
"""
from __future__ import annotations

import os
import sys

try:
    import psycopg2
except Exception:
    print("Missing dependency: install .venv/bin/pip install psycopg2-binary")
    raise

from config import settings


def get_conn_params():
    url = os.getenv("CARTO_DATABASE_URL") or getattr(settings, "CARTO_DATABASE_URL", None)
    if url and url.startswith("postgresql://"):
        return url
    host = os.getenv("CARTO_PG_HOST", settings.CARTO_PG_HOST)
    port = int(os.getenv("CARTO_PG_PORT", settings.CARTO_PG_PORT))
    db = os.getenv("CARTO_PG_DB", settings.CARTO_PG_DB)
    user = os.getenv("CARTO_PG_USER", settings.CARTO_PG_USER)
    pwd = os.getenv("CARTO_PG_PASS", settings.CARTO_PG_PASS)
    return {
        "host": host,
        "port": port,
        "dbname": db,
        "user": user,
        "password": pwd,
    }


def main():
    params = get_conn_params()
    try:
        if isinstance(params, str):
            conn = psycopg2.connect(params)
        else:
            conn = psycopg2.connect(**params)
        cur = conn.cursor()
        cur.execute("SELECT plano_acao_codigo, beneficiario_nome, beneficiario_uf, valor_total FROM v_planos_completo LIMIT 5")
        rows = cur.fetchall()
        if not rows:
            print("Connected but no rows returned from v_planos_completo.")
        else:
            print("Sample rows from v_planos_completo:")
            for r in rows:
                print(r)
        cur.close()
        conn.close()
        return 0
    except Exception as exc:
        print("Connection failed:", exc)
        print("Ensure CARTO_PG_* env vars are set and the carto_reader role exists with SELECT grants.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
