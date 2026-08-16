#!/usr/bin/env python3
"""localai-observability: Cadeia de eventos do LocalAI para follow-up de falhas.

Uso:
    python3 src/localai_observability.py
    python3 src/localai_observability.py --model Qwen2.5-Coder-7B-Instruct-GGUF
    python3 src/localai_observability.py --since 5m
    python3 src/localai_observability.py --db
    python3 src/localai_observability.py --json
    ./run.sh localai-observability

Saída: cadeia cronológica de traces + backend-traces + logs + flags de anomalia.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from config.settings import LOCALAI_BASE_URL

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("localai_observability")

_TIMEOUT = 15.0
_ANOMALY_PATTERNS = [
    (re.compile(r"connection refused", re.I), "connection_refused"),
    (re.compile(r"OOM|out of memory|CUDA out of memory", re.I), "oom"),
    (re.compile(r"RPC.*EOF|rpc error", re.I), "rpc_error"),
    (re.compile(r"backend.*unavailable|backend.*crashed", re.I), "backend_crash"),
    (re.compile(r"no grpc backend found", re.I), "backend_missing"),
]


def _parse_since(since: str) -> datetime:
    m = re.match(r"^(\d+)([smhd])$", since.strip().lower())
    if not m:
        raise ValueError(f"--since inválido: {since!r} (use 5m, 1h, 2d)")
    n, unit = int(m.group(1)), m.group(2)
    delta = {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
             "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
    return datetime.now(UTC) - delta


def _get(path: str, params: dict | None = None) -> Any:
    url = f"{LOCALAI_BASE_URL}{path}"
    try:
        with httpx.Client(timeout=_TIMEOUT, trust_env=False) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as exc:
        return {"_error": f"HTTP {exc.response.status_code}", "path": path}
    except Exception as exc:
        return {"_error": str(exc), "path": path}


def fetch_traces() -> list[dict]:
    data = _get("/api/traces")
    return data if isinstance(data, list) else []


def fetch_backend_traces() -> list[dict]:
    data = _get("/api/backend-traces")
    return data if isinstance(data, list) else []


def fetch_backend_logs(model: str) -> list[dict]:
    data = _get(f"/api/backend-logs/{model}")
    return data if isinstance(data, list) else []


def fetch_system() -> dict:
    return _get("/system")


def fetch_metrics_text() -> str:
    url = f"{LOCALAI_BASE_URL}/metrics"
    try:
        with httpx.Client(timeout=_TIMEOUT, trust_env=False) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.text
    except Exception as exc:
        return f"# erro ao buscar /metrics: {exc}"


def _parse_timestamp(ts: str) -> datetime:
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(UTC)


def _ns_to_ms(ns: int) -> float:
    return ns / 1_000_000.0


def build_chain(model: str | None = None, since: datetime | None = None) -> list[dict]:
    events: list[dict] = []

    for t in fetch_traces():
        ts = _parse_timestamp(t.get("timestamp", ""))
        if since and ts < since:
            continue
        req = t.get("request", {}) or {}
        resp = t.get("response", {}) or {}
        body = t.get("data", {}) or {}
        status_code = resp.get("status_code")
        events.append({
            "event_at": ts.isoformat(),
            "event_type": "request",
            "level": "error" if status_code and status_code >= 500 else "info",
            "model": body.get("model") or _extract_model_from_body(req.get("body", "")),
            "method": req.get("method"),
            "path": req.get("path"),
            "status_code": status_code,
            "duration_ms": _ns_to_ms(t.get("duration", 0)),
            "summary": f"{req.get('method', '?')} {req.get('path', '?')} → {status_code or '?'}",
        })

    for bt in fetch_backend_traces():
        ts = _parse_timestamp(bt.get("timestamp", ""))
        if since and ts < since:
            continue
        if model and bt.get("model_name") != model:
            continue
        events.append({
            "event_at": ts.isoformat(),
            "event_type": "backend",
            "level": "info",
            "model": bt.get("model_name"),
            "backend": bt.get("backend"),
            "duration_ms": _ns_to_ms(bt.get("duration", 0)),
            "summary": (bt.get("summary") or "")[:200],
        })

    if model:
        for entry in fetch_backend_logs(model):
            ts = _parse_timestamp(entry.get("timestamp", ""))
            if since and ts < since:
                continue
            events.append({
                "event_at": ts.isoformat(),
                "event_type": "log",
                "level": entry.get("level", "info").lower(),
                "model": model,
                "summary": (entry.get("message") or "")[:300],
            })

    events.sort(key=lambda e: e["event_at"])
    return events


def _extract_model_from_body(body: str) -> str | None:
    if not body:
        return None
    try:
        import base64
        decoded = base64.b64decode(body).decode("utf-8", errors="replace")
        data = json.loads(decoded)
        return data.get("model")
    except Exception:
        return None


def flag_anomalies(chain: list[dict]) -> list[dict]:
    anomalies: list[dict] = []
    for ev in chain:
        code = ev.get("status_code")
        if code and code >= 500:
            anomalies.append({
                "type": "http_5xx",
                "event_at": ev["event_at"],
                "model": ev.get("model"),
                "detail": f"HTTP {code} em {ev.get('method')} {ev.get('path')}",
            })
        text = json.dumps(ev, ensure_ascii=False, default=str)
        for pattern, label in _ANOMALY_PATTERNS:
            if pattern.search(text):
                anomalies.append({
                    "type": label,
                    "event_at": ev["event_at"],
                    "model": ev.get("model"),
                    "detail": pattern.pattern,
                })
    seen: set[str] = set()
    unique: list[dict] = []
    for a in anomalies:
        key = f"{a['type']}|{a['event_at']}|{a.get('model')}"
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def persist_snapshot(chain: list[dict], anomalies: list[dict], model: str | None) -> int:
    from src.db_utils import get_connection

    status = "ok" if not anomalies else ("error" if any(a["type"] in ("http_5xx", "connection_refused", "oom") for a in anomalies) else "degraded")
    duration_hint = max((ev.get("duration_ms") or 0) for ev in chain) if chain else 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO localai_chain_snapshot
                    (model, status, duration_hint, events_count, anomalies, chain)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (model, status, duration_hint, len(chain),
                 json.dumps(anomalies, ensure_ascii=False, default=str),
                 json.dumps(chain, ensure_ascii=False, default=str)),
            )
            snap_id = cur.fetchone()[0]
            for ev in chain:
                cur.execute(
                    """
                    INSERT INTO localai_event_log
                        (event_at, event_type, level, model, backend, method, path,
                         status_code, duration_ms, summary, payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ev.get("event_at"),
                        ev.get("event_type"),
                        ev.get("level", "info"),
                        ev.get("model"),
                        ev.get("backend"),
                        ev.get("method"),
                        ev.get("path"),
                        ev.get("status_code"),
                        ev.get("duration_ms"),
                        ev.get("summary"),
                        json.dumps({k: v for k, v in ev.items() if k not in (
                            "event_at", "event_type", "level", "model", "backend",
                            "method", "path", "status_code", "duration_ms", "summary",
                        )}, ensure_ascii=False, default=str) if ev else None,
                    ),
                )
        conn.commit()
    return snap_id


def record_event(
    event_type: str,
    level: str = "info",
    model: str | None = None,
    backend: str | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    duration_ms: float | None = None,
    summary: str | None = None,
    payload: dict | None = None,
) -> None:
    try:
        from src.db_utils import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO localai_event_log
                        (event_type, level, model, backend, method, path,
                         status_code, duration_ms, summary, payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (event_type, level, model, backend, method, path,
                     status_code, duration_ms, summary,
                     json.dumps(payload, ensure_ascii=False, default=str) if payload else None),
                )
            conn.commit()
    except Exception as exc:
        log.warning("record_event falhou: %s", exc)


def render(chain: list[dict], anomalies: list[dict], model: str | None) -> str:
    lines = [
        "=== LocalAI Observability Chain ===",
        f"Modelo: {model or '(todos)'}",
        f"Eventos: {len(chain)}",
        f"Anomalias: {len(anomalies)}",
        "",
    ]
    if anomalies:
        lines.append("--- ANOMALIAS ---")
        for a in anomalies:
            lines.append(f"  [{a['type']}] {a['event_at']} | {a.get('model','-')} | {a['detail']}")
        lines.append("")
    lines.append("--- CADEIA DE EVENTOS ---")
    for ev in chain[-30:]:
        flag = "⚠" if ev.get("level") == "error" else " "
        lines.append(
            f"  {flag} {ev['event_at'][11:19]} {ev['event_type']:8s} "
            f"{ev.get('model','')[:30]:30s} "
            f"{ev.get('duration_ms',0):8.0f}ms "
            f"{ev.get('summary','')[:80]}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cadeia de eventos do LocalAI")
    parser.add_argument("--model", help="Filtrar por modelo")
    parser.add_argument("--since", help="Janela temporal (ex: 5m, 1h, 2d)")
    parser.add_argument("--db", action="store_true", help="Persiste snapshot no banco")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    args = parser.parse_args()

    since = _parse_since(args.since) if args.since else None
    chain = build_chain(model=args.model, since=since)
    anomalies = flag_anomalies(chain)

    if args.db:
        snap_id = persist_snapshot(chain, anomalies, args.model)
        log.info("Snapshot persistido: id=%d", snap_id)

    if args.json:
        print(json.dumps({"chain": chain, "anomalies": anomalies}, ensure_ascii=False, indent=2, default=str))
    else:
        print(render(chain, anomalies, args.model))

    if any(a["type"] in ("http_5xx", "connection_refused", "oom") for a in anomalies):
        return 2
    return 0 if not anomalies else 1


if __name__ == "__main__":
    sys.exit(main())
