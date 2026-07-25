"""
db_utils — Conexão e consultas PostgreSQL centralizadas.

Substitui as 14+ cópias espalhadas de get_connection() / query_df()
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import psycopg2

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER


def get_connection() -> psycopg2.extensions.connection:
    """Retorna uma conexão psycopg2 com o banco transferegov_db."""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
    )


def query_df(sql: str, params: Any = None) -> pd.DataFrame:
    """Executa query SQL e retorna DataFrame com tipos numéricos convertidos.

    Comportamento: abre conexão, executa, fecha. Seguro para uso isolado.
    Para queries em loop, usar get_connection() diretamente.
    """
    with get_connection() as conn, conn.cursor() as cur:
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        if cur.description:
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=cols)
            for col in df.columns:
                if df[col].dtype == "object":
                    converted = pd.to_numeric(df[col], errors="coerce")
                    if not converted.isna().all():
                        df[col] = converted
            return df
    return pd.DataFrame()


def query_df_simple(conn, sql: str) -> pd.DataFrame:
    """Executa query via conexão existente (pd.read_sql). Para uso em loops."""
    return pd.read_sql(sql, conn)
