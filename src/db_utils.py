"""
db_utils — Conexão e consultas PostgreSQL centralizadas.

Substitui as 14+ cópias espalhadas de get_connection() / query_df()
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
import psycopg2
from psycopg2.extras import RealDictCursor

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


def get_real_dict_connection() -> psycopg2.extensions.connection:
    """Retorna uma conexão psycopg2 com RealDictCursor (linhas como dict)."""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        cursor_factory=RealDictCursor,
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


# ---------------------------------------------------------------------------
# Utilitários de renderização Plotly
# ---------------------------------------------------------------------------


def trace_has_data(trace: Any) -> bool:
    """Verifica se um trace Plotly contém dados válidos.

    Cobrir bar, scatter, pie, choropleth, sankey, radar, etc.
    """
    checks = [
        getattr(trace, "x", None),
        getattr(trace, "y", None),
        getattr(trace, "values", None),
        getattr(trace, "z", None),
        getattr(trace, "locations", None),
        getattr(trace, "lat", None),
        getattr(trace, "lon", None),
        getattr(trace, "r", None),
        getattr(trace, "theta", None),
    ]
    # Sankey: dados ficam em trace.link.value
    link = getattr(trace, "link", None)
    if link and hasattr(link, "value") and link.value is not None:
        checks.append(link.value)
    return any(v is not None and len(v) > 0 for v in checks)


def fig_has_data(fig: go.Figure | None) -> bool:
    """Verifica se uma figura Plotly contém ao menos um trace com dados."""
    if not fig or not hasattr(fig, "data") or len(fig.data) == 0:
        return False
    return any(trace_has_data(t) for t in fig.data)


def query_df_simple(conn, sql: str, params: Any = None) -> pd.DataFrame:
    """Executa query via conexão existente (pd.read_sql). Para uso em loops."""
    return pd.read_sql(sql, conn, params=params)
