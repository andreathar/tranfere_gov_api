"""LocalAI Observabilidade - Endpoints para visualizar cadeia de eventos."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.db_utils import query_df

router = APIRouter(prefix="/localai", tags=["localai"])


class Event(BaseModel):
    id: int
    event_at: str
    event_type: str
    level: str
    model: Optional[str]
    backend: Optional[str]
    method: Optional[str]
    path: Optional[str]
    status_code: Optional[int]
    duration_ms: Optional[float]
    summary: Optional[str]


class ChainSnapshot(BaseModel):
    id: int
    taken_at: str
    model: Optional[str]
    status: str
    duration_hint: Optional[float]
    events_count: int
    anomalies_count: int


@router.get("/events", response_model=list[Event])
def list_events(
    limit: int = 100,
    level: Optional[str] = None,
    model: Optional[str] = None,
    since: Optional[str] = None,
):
    """Listar eventos do LocalAI (cadeia de traces)."""
    sql = """
        SELECT id, event_at, event_type, level, model, backend, method, path,
               status_code, duration_ms, summary
        FROM localai_event_log
        WHERE 1=1
    """
    params: list = []

    if level:
        sql += " AND level = %s"
        params.append(level)
    if model:
        sql += " AND model = %s"
        params.append(model)
    if since:
        sql += " AND event_at > now() - interval %s"
        params.append(since)

    sql += f" ORDER BY event_at DESC LIMIT {min(limit, 500)}"

    df = query_df(sql, params)
    return df.to_dict("records")


@router.get("/snapshots", response_model=list[ChainSnapshot])
def list_snapshots(limit: int = 20):
    """Listar snapshots da cadeia de eventos."""
    sql = """
        SELECT id, taken_at, model, status, duration_hint, events_count,
               jsonb_array_length(anomalies) as anomalies_count
        FROM localai_chain_snapshot
        ORDER BY taken_at DESC
        LIMIT %s
    """
    df = query_df(sql, [limit])
    return df.to_dict("records")


@router.get("/snapshot/{snapshot_id}")
def get_snapshot(snapshot_id: int):
    """Obter snapshot completo com cadeia de eventos."""
    sql = """
        SELECT * FROM localai_chain_snapshot WHERE id = %s
    """
    df = query_df(sql, [snapshot_id])
    if df.empty:
        raise HTTPException(status_code=404, detail="Snapshot não encontrado")

    row = df.iloc[0]
    return {
        "id": row["id"],
        "taken_at": row["taken_at"],
        "model": row["model"],
        "status": row["status"],
        "duration_hint": row["duration_hint"],
        "events_count": row["events_count"],
        "anomalies": row["anomalies"],
        "chain": row["chain"],
    }


@router.get("/stats")
def get_stats():
    """Estatísticas resumidas dos eventos."""
    sql = """
        SELECT
            COUNT(*) as total_events,
            COUNT(CASE WHEN level = 'error' THEN 1 END) as error_count,
            COUNT(DISTINCT model) as models_count,
            MAX(event_at) as last_event_at,
            AVG(duration_ms) as avg_duration_ms
        FROM localai_event_log
    """
    df = query_df(sql)
    return df.iloc[0].to_dict()
