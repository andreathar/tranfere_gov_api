"""
Observability helpers for the TransfereGov pipeline.

Provides simple counters, timers, and summary logging without external dependencies.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Observability:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._timers: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "count": 0,
                "total_ms": 0.0,
                "min_ms": float("inf"),
                "max_ms": 0.0,
            }
        )

    def inc(self, key: str, amount: int = 1) -> None:
        """Incrementa um contador simples."""
        if amount == 0:
            return
        with self._lock:
            self._counters[key] += amount

    def gauge(self, key: str, value: int | float) -> None:
        """Registra um valor atual (gauge)."""
        with self._lock:
            self._counters[key] = int(value)

    def observe(self, key: str, duration_ms: float) -> None:
        """Registra um tempo de execução em milissegundos."""
        with self._lock:
            timer = self._timers[key]
            timer["count"] += 1
            timer["total_ms"] += duration_ms
            timer["min_ms"] = min(timer["min_ms"], duration_ms)
            timer["max_ms"] = max(timer["max_ms"], duration_ms)

    @contextmanager
    def timed(self, key: str):
        """Context manager para medir a duração de um bloco."""
        start = time.perf_counter()
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.observe(key, elapsed_ms)

    def summary(self) -> dict[str, dict[str, float] | int]:
        """Retorna o resumo atual das métricas."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "timers": {
                    key: {
                        "count": values["count"],
                        "total_ms": round(values["total_ms"], 1),
                        "avg_ms": round(
                            values["total_ms"] / values["count"], 1
                        )
                        if values["count"]
                        else 0.0,
                        "min_ms": 0.0
                        if values["min_ms"] == float("inf")
                        else round(values["min_ms"], 1),
                        "max_ms": round(values["max_ms"], 1),
                    }
                    for key, values in self._timers.items()
                },
            }

    def log_summary(self, prefix: str = "Observability") -> None:
        """Loga um resumo das métricas no logger."""
        data = self.summary()
        logger.info("%s summary:", prefix)
        for key, count in sorted(data["counters"].items()):
            logger.info("  counter %-40s %s", key, count)
        for key, values in sorted(data["timers"].items()):
            logger.info(
                "  timer   %-40s count=%s avg_ms=%s min_ms=%s max_ms=%s",
                key,
                values["count"],
                values["avg_ms"],
                values["min_ms"],
                values["max_ms"],
            )


observability = Observability()
