"""
db_utils — Conexão e consultas PostgreSQL centralizadas.

Substitui as 14+ cópias espalhadas de get_connection() / query_df()
"""
from __future__ import annotations

import atexit
import threading
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER

# ---------------------------------------------------------------------------
# Connection Pool (thread-safe, lazy init)
# ---------------------------------------------------------------------------
_POOL_MIN = 2
_POOL_MAX = 10
_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ThreadedConnectionPool:
    """Retorna (ou cria) o pool de conexões thread-safe."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(
                    _POOL_MIN, _POOL_MAX,
                    host=PG_HOST, port=PG_PORT,
                    dbname=PG_DB, user=PG_USER, password=PG_PASS,
                )
                atexit.register(_pool.closeall)
    return _pool


class _PooledConnection:
    """Wrapper that returns a psycopg2 connection to the pool on close/exit.

    Delegates all attribute access to the real connection so it behaves
    identically in every context (cursor(), execute(), etc.) without
    mutating the C-extension object.
    """

    __slots__ = ("_conn", "_pool", "_released")

    def __init__(self, conn: psycopg2.extensions.connection, pool: ThreadedConnectionPool) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_released", [False])

    def _release(self) -> None:
        if self._released[0]:
            return
        self._released[0] = True
        try:
            self._conn.close()
        except Exception:
            pass
        self._pool.putconn(self._conn)

    def close(self) -> None:
        self._release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        result = self._conn.__exit__(exc_type, exc_val, exc_tb)
        self._release()
        return result

    def __getattr__(self, name: str):
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value):
        setattr(self._conn, name, value)

    def __repr__(self):
        return f"<PooledConnection released={self._released[0]} conn={self._conn!r}>"


def get_connection() -> _PooledConnection:
    """Retorna uma conexão do pool. Usar com context manager:

    with get_connection() as conn:
        ...
    """
    pool = _get_pool()
    conn = pool.getconn()
    return _PooledConnection(conn, pool)


def get_real_dict_connection() -> _PooledConnection:
    """Retorna uma conexão do pool com RealDictCursor (linhas como dict)."""
    pool = _get_pool()
    conn = pool.getconn()
    conn.cursor_factory = RealDictCursor
    return _PooledConnection(conn, pool)


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
