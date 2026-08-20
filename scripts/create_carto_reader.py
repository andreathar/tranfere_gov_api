#!/usr/bin/env python3
"""
Create or update the carto_reader role and grant SELECT privileges for Carto integration.

Run as a DB superuser or a role with CREATEROLE. Will print a generated password and
an example connection string for Carto. If the current DB user lacks permission the
script will fail with a helpful message (and suggested psql commands for a DBA).

Usage:
  .venv/bin/python scripts/create_carto_reader.py

DO NOT COMMIT GENERATED PASSWORDS. Copy the printed connection string into Carto
secrets and rotate the password after onboarding.
"""

from __future__ import annotations

import secrets
import sys
from typing import List

try:
    import psycopg2
    from psycopg2 import sql
except Exception as exc:
    print("Missing dependency: psycopg2. Install with: .venv/bin/pip install psycopg2-binary")
    raise

from config import settings

PW = secrets.token_urlsafe(24)
ROLE = "carto_reader"
DB = settings.PG_DB

GRANTS: List[sql.SQL] = [
    sql.SQL("GRANT CONNECT ON DATABASE {} TO {role}").format(sql.Identifier(DB), role=sql.Identifier(ROLE)),
    sql.SQL("GRANT USAGE ON SCHEMA public TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_planos_completo TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_planos_enriquecidos TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_resumo_por_estado TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_resumo_por_objeto TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_resumo_por_parlamentar TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_resumo_por_politica_estado TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_resumo_por_objeto_parlamentar TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_ranking_parlamentares_enriquecido TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_parlamentar_municipio TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON v_negados TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON beneficiarios TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON municipios_ibge TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON planos_acao TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("GRANT SELECT ON parlamentares TO {role}").format(role=sql.Identifier(ROLE)),
    sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {role}").format(role=sql.Identifier(ROLE)),
]

CREATE_SQL = sql.SQL("CREATE ROLE {role} WITH LOGIN PASSWORD %s").format(role=sql.Identifier(ROLE))
ALTER_SQL = sql.SQL("ALTER ROLE {role} WITH PASSWORD %s").format(role=sql.Identifier(ROLE))


def main() -> int:
    try:
        conn = psycopg2.connect(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            dbname=settings.PG_DB,
            user=settings.PG_USER,
            password=settings.PG_PASS,
        )
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,))
        exists = cur.fetchone() is not None
        if not exists:
            print(f"Creating role '{ROLE}'...")
            try:
                cur.execute(CREATE_SQL, (PW,))
            except Exception as exc:
                print("Failed to create role:", exc)
                return 2
        else:
            print(f"Role '{ROLE}' exists — updating password...")
            try:
                cur.execute(ALTER_SQL, (PW,))
            except Exception as exc:
                print("Failed to alter role password:", exc)
                return 3

        print("Applying grants...")
        for g in GRANTS:
            try:
                cur.execute(g)
            except Exception as exc:
                print("Grant failed (continuing):", exc)

        cur.close()
        conn.close()

        conn_string = f"postgresql://{ROLE}:{PW}@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
        print("\nSUCCESS — carto_reader created/updated.")
        print("Store the following connection string securely in Carto or your agent runtime (do NOT commit it):\n")
        print(conn_string)
        print("\nSuggested environment variables to set in Carto:\n  CARTO_PG_HOST CARTO_PG_PORT CARTO_PG_DB CARTO_PG_USER CARTO_PG_PASS")
        print("Rotate the password after onboarding and restrict DB network access to Carto IPs.")
        return 0

    except Exception as exc:
        print("ERROR: could not perform DB changes.")
        print("Reason:", exc)
        print("\nIf you lack CREATEROLE privileges, ask a DBA to run the migration file: data/migration_048_carto_integration.sql")
        print("Or the DBA can run the following psql commands (replace STRONG_PASSWORD):\n\n  CREATE ROLE carto_reader WITH LOGIN PASSWORD 'STRONG_PASSWORD';\n  GRANT CONNECT ON DATABASE ", DB, " TO carto_reader;\n  GRANT USAGE ON SCHEMA public TO carto_reader;\n  GRANT SELECT ON v_planos_completo, v_planos_enriquecidos, v_resumo_por_estado, v_resumo_por_objeto, v_resumo_por_parlamentar, v_resumo_por_politica_estado, v_resumo_por_objeto_parlamentar, v_ranking_parlamentares_enriquecido, v_parlamentar_municipio, v_negados, beneficiarios, municipios_ibge, planos_acao, parlamentares TO carto_reader;\n  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO carto_reader;\n")
        return 4


if __name__ == "__main__":
    sys.exit(main())
