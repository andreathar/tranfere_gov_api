#!/usr/bin/env python3
"""localai-health: Painel de saúde do LocalAI (API, modelos, VRAM, circuit breaker).

Uso:
    python3 src/localai_health.py
    python3 src/localai_health.py --json
    python3 src/localai_health.py --db
    python3 src/localai_health.py --model llama-3.2-3b-instruct:q4_k_m
    ./run.sh localai-health

Exit code: 0 = ok | 1 = degradado | 2 = erro (API indisponível).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from src.localai_manager import LocalAIMonitorError, manager
from src.localai_metrics import metrics

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("localai_health")


def _exit_code(status: str) -> int:
    return {"ok": 0, "degraded": 1}.get(status, 2)


def _format_vram(vram: dict[str, int]) -> str:
    total = vram.get("total_mib", 0)
    free = vram.get("free_mib", 0)
    used = vram.get("used_mib", 0)
    if total <= 0:
        return "VRAM indisponível (nvidia-smi ausente?)"
    pct = (used / total) * 100 if total else 0
    return f"{used}/{total} MiB usados ({pct:.0f}%) · {free} MiB livres"


def _check_model_state(model: str) -> str:
    try:
        if manager.is_model_loaded(model):
            return "carregado"
        return "não carregado"
    except LocalAIMonitorError as exc:
        return f"indeterminado (monitor: {exc})"


def _render_panel(health: dict[str, Any], check_model: str | None) -> str:
    vram = health.get("vram", {})
    cb = health.get("circuit_breaker", {})
    lines = [
        "=== LocalAI Health ===",
        f"Status: {health.get('status', 'unknown')}",
        f"Base URL: {health.get('base_url', '-')}",
        f"Modelos disponíveis: {health.get('models_available', 0)}",
        f"Modelos carregados: {', '.join(health.get('models_loaded', [])) or '-'}",
        f"Modelos rastreados: {', '.join(health.get('models_tracked', [])) or '-'}",
        f"Latência (listagem): {health.get('latency_ms', 0):.1f} ms",
        f"VRAM: {_format_vram(vram)}",
        f"VRAM estimada (tracker): {health.get('vram_estimated_used_mib', 0)} MiB",
        f"Circuit breaker: {cb.get('state', '-')} "
        f"(falhas: {cb.get('failure_count', 0)})",
        f"Falhas de monitor indeterminadas: {manager._monitor_failures}",
    ]
    if check_model:
        lines.append(f"Modelo {check_model}: {_check_model_state(check_model)}")
    return "\n".join(lines)


def _persist(health: dict[str, Any]) -> None:
    from src.db_utils import get_connection

    vram = health.get("vram", {})
    cb = health.get("circuit_breaker", {})
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO localai_health_log
                    (status, base_url, models_available, models_loaded,
                     models_tracked, latency_ms, circuit_state, circuit_failures,
                     vram_total_mib, vram_free_mib, vram_used_mib,
                     vram_estimated_used_mib, monitor_failures, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    health.get("status"),
                    health.get("base_url"),
                    health.get("models_available"),
                    health.get("models_loaded"),
                    health.get("models_tracked"),
                    health.get("latency_ms"),
                    cb.get("state"),
                    cb.get("failure_count"),
                    vram.get("total_mib"),
                    vram.get("free_mib"),
                    vram.get("used_mib"),
                    health.get("vram_estimated_used_mib"),
                    manager._monitor_failures,
                    json.dumps(health.get("metrics", {})),
                ),
            )
        conn.commit()
    log.info("Snapshot persistido em localai_health_log.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Painel de saúde do LocalAI")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    parser.add_argument("--db", action="store_true", help="Persiste em localai_health_log")
    parser.add_argument("--model", help="Verifica estado de um modelo específico")
    args = parser.parse_args()

    try:
        health = manager.health_check(args.model)
    except Exception as exc:
        log.error("health_check falhou: %s", exc)
        health = {
            "status": "error",
            "base_url": manager.base_url,
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(health, ensure_ascii=False, indent=2))
        else:
            print(_render_panel(health, args.model))
        return _exit_code("error")

    if args.db:
        _persist(health)

    if args.json:
        print(json.dumps(health, ensure_ascii=False, indent=2))
    else:
        print(_render_panel(health, args.model))
        metrics.summary_log()
    return _exit_code(health.get("status", "error"))


if __name__ == "__main__":
    sys.exit(main())
