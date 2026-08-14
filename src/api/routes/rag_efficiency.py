from datetime import datetime
from typing import Protocol, TypeAlias, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db_utils import get_connection

router = APIRouter()


class _Cursor(Protocol):
    def execute(self, query: str, params: object = ...) -> object: ...

    def fetchone(self) -> object: ...

    def fetchall(self) -> list[object]: ...

    def close(self) -> object: ...


RAGRunRow: TypeAlias = (
    tuple[int, datetime, str, int, float | None, float | None, float | None]
)
RAGMetricRow: TypeAlias = (
    tuple[
        int,
        str,
        str,
        str,
        str,
        float | None,
        float | None,
        int | None,
        int | None,
        float | None,
        float | None,
        int | None,
        float | None,
    ]
)
LatestRunRow: TypeAlias = (
    tuple[int, datetime, str, str, int, float | None, float | None, float | None, float | None]
)
LatestCountsRow: TypeAlias = tuple[int, int, float | None, float | None]
LatestTipoRow: TypeAlias = tuple[str, int, float | None, float | None]

class RAGRunResponse(BaseModel):
    id: int
    run_date: datetime
    model_name: str
    total_questions: int
    global_efficiency_score: float | None
    avg_retrieval_hit_rate: float | None
    avg_generation_faithfulness: float | None

@router.get("/runs", response_model=list[RAGRunResponse])
def get_runs():
    """Retorna o histórico de runs do RAG Efficiency."""
    conn = get_connection()
    cur = cast(_Cursor, conn.cursor())
    results = []
    try:
        cur.execute("""
            SELECT id, run_date, model_name, total_questions,
                   global_efficiency_score, avg_retrieval_hit_rate, avg_generation_faithfulness
            FROM rag_efficiency_runs
            ORDER BY run_date DESC
            LIMIT 50
        """)
        rows = cast(list[RAGRunRow], cur.fetchall())

        for r in rows:
            results.append({
                "id": r[0],
                "run_date": r[1],
                "model_name": r[2],
                "total_questions": r[3],
                "global_efficiency_score": float(r[4]) if r[4] is not None else None,
                "avg_retrieval_hit_rate": float(r[5]) if r[5] is not None else None,
                "avg_generation_faithfulness": float(r[6]) if r[6] is not None else None,
            })
    finally:
        cur.close()
        conn.close()

    return results


@router.get("/runs/latest")
def get_latest_run():
    conn = get_connection()
    cur = cast(_Cursor, conn.cursor())
    try:
        cur.execute("""
            SELECT id, run_date, model_name, golden_set_version, total_questions,
                   global_efficiency_score, avg_retrieval_hit_rate,
                   avg_generation_faithfulness, avg_emergence_layer
            FROM rag_efficiency_runs
            WHERE id = (SELECT MAX(id) FROM rag_efficiency_runs)
        """)
        run = cast(LatestRunRow | None, cur.fetchone())

        if run is None:
            raise HTTPException(
                status_code=404,
                detail="Nenhum run de eficiência RAG encontrado. Rode ./run.sh rag-efficiency.",
            )

        cur.execute("""
            SELECT COUNT(*), COUNT(emergence_layer), AVG(mrr_at_k), AVG(context_utilization_score)
            FROM rag_efficiency_metrics
            WHERE run_id = %s
        """, (run[0],))
        counts_row = cast(LatestCountsRow, cur.fetchone())

        cur.execute("""
            SELECT tipo_politico, COUNT(*), AVG(hit_rate_at_k), AVG(faithfulness_score)
            FROM rag_efficiency_metrics
            WHERE run_id = %s
            GROUP BY tipo_politico
            ORDER BY tipo_politico
        """, (run[0],))
        tipo_rows = cast(list[LatestTipoRow], cur.fetchall())

        by_tipo = {}
        for tipo_politico, n, avg_hit_rate, avg_faithfulness in tipo_rows:
            by_tipo[tipo_politico] = {
                "n": n,
                "avg_hit_rate": float(avg_hit_rate) if avg_hit_rate is not None else None,
                "avg_faithfulness": float(avg_faithfulness) if avg_faithfulness is not None else None,
            }

        return {
            "id": run[0],
            "run_date": run[1],
            "model_name": run[2],
            "golden_set_version": run[3],
            "total_questions": run[4],
            "global_efficiency_score": float(run[5]) if run[5] is not None else None,
            "avg_retrieval_hit_rate": float(run[6]) if run[6] is not None else None,
            "avg_generation_faithfulness": float(run[7]) if run[7] is not None else None,
            "avg_emergence_layer": float(run[8]) if run[8] is not None else None,
            "counts": {
                "total_questions": counts_row[0],
                "questions_with_emergence_layer": counts_row[1],
            },
            "averages": {
                "mrr_at_k": float(counts_row[2]) if counts_row[2] is not None else None,
                "context_utilization_score": (
                    float(counts_row[3]) if counts_row[3] is not None else None
                ),
            },
            "by_tipo": by_tipo,
        }
    finally:
        cur.close()
        conn.close()

@router.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: int):
    """Retorna as métricas detalhadas (pergunta a pergunta) de um run."""
    conn = get_connection()
    cur = cast(_Cursor, conn.cursor())
    try:
        cur.execute("""
            SELECT politico_id, tipo_politico, question, expected_answer, actual_answer,
                   hit_rate_at_k, faithfulness_score, emergence_layer,
                   retrieved_chunks_count, mrr_at_k, context_utilization_score,
                   total_layers, target_token_prob
            FROM rag_efficiency_metrics
            WHERE run_id = %s
            ORDER BY id ASC
        """, (run_id,))
        rows = cast(list[RAGMetricRow], cur.fetchall())

        if not rows:
            raise HTTPException(status_code=404, detail="Run not found")

        results = []
        for r in rows:
            results.append({
                "politico_id": r[0],
                "tipo_politico": r[1],
                "question": r[2],
                "expected_answer": r[3],
                "actual_answer": r[4],
                "hit_rate": float(r[5]) if r[5] is not None else None,
                "faithfulness": float(r[6]) if r[6] is not None else None,
                "emergence_layer": r[7],
                "retrieved_chunks_count": r[8],
                "mrr_at_k": float(r[9]) if r[9] is not None else None,
                "context_utilization_score": float(r[10]) if r[10] is not None else None,
                "total_layers": r[11],
                "target_token_prob": float(r[12]) if r[12] is not None else None,
            })
        return results
    finally:
        cur.close()
        conn.close()
