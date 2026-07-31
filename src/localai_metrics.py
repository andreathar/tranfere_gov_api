"""
Métricas de uso de modelos LocalAI — latência, erros, contagem.

Coleta dados in-memory para logging e monitoramento.
Não requer dependências externas (sem Prometheus/StatsD).

Uso:
    from src.localai_metrics import metrics

    metrics.record(model="gemma-4-e2b-it", latency_ms=1500, tokens=256, error=False)
    print(metrics.summary())
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class _ModelStats:
    """Estatísticas acumuladas para um modelo."""

    __slots__ = (
        "total_calls",
        "error_calls",
        "total_latency_ms",
        "total_tokens",
        "min_latency_ms",
        "max_latency_ms",
    )

    def __init__(self) -> None:
        self.total_calls: int = 0
        self.error_calls: int = 0
        self.total_latency_ms: float = 0.0
        self.total_tokens: int = 0
        self.min_latency_ms: float = float("inf")
        self.max_latency_ms: float = 0.0

    def record(self, latency_ms: float, tokens: int, error: bool) -> None:
        self.total_calls += 1
        if error:
            self.error_calls += 1
        self.total_latency_ms += latency_ms
        self.total_tokens += tokens
        if latency_ms < self.min_latency_ms:
            self.min_latency_ms = latency_ms
        if latency_ms > self.max_latency_ms:
            self.max_latency_ms = latency_ms

    def to_dict(self) -> dict:
        avg = self.total_latency_ms / self.total_calls if self.total_calls else 0
        error_rate = self.error_calls / self.total_calls * 100 if self.total_calls else 0
        return {
            "calls": self.total_calls,
            "errors": self.error_calls,
            "error_rate_pct": round(error_rate, 1),
            "avg_latency_ms": round(avg, 1),
            "min_latency_ms": (
                round(self.min_latency_ms, 1) if self.min_latency_ms != float("inf") else 0
            ),
            "max_latency_ms": round(self.max_latency_ms, 1),
            "total_tokens": self.total_tokens,
        }


class LocalAIMetrics:
    """Métricas thread-safe de chamadas a modelos LocalAI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_model: dict[str, _ModelStats] = defaultdict(_ModelStats)
        self._by_endpoint: dict[str, _ModelStats] = defaultdict(_ModelStats)
        self._start_time = time.monotonic()

    def record(
        self,
        model: str = "unknown",
        endpoint: str = "unknown",
        latency_ms: float = 0,
        tokens: int = 0,
        error: bool = False,
    ) -> None:
        """Registra uma chamada."""
        with self._lock:
            self._by_model[model].record(latency_ms, tokens, error)
            self._by_endpoint[endpoint].record(latency_ms, tokens, error)

    def summary(self) -> dict:
        """Resumo consolidado por modelo e endpoint."""
        with self._lock:
            uptime_s = time.monotonic() - self._start_time
            return {
                "uptime_s": round(uptime_s, 1),
                "by_model": {k: v.to_dict() for k, v in sorted(self._by_model.items())},
                "by_endpoint": {k: v.to_dict() for k, v in sorted(self._by_endpoint.items())},
            }

    def summary_log(self) -> str:
        """Resumo formatado para logging."""
        data = self.summary()
        lines = [f"LocalAI Metrics (uptime: {data['uptime_s']:.0f}s):"]
        for model, stats in data["by_model"].items():
            lines.append(
                f"  {model}: {stats['calls']} calls, "
                f"avg {stats['avg_latency_ms']:.0f}ms, "
                f"errors {stats['error_rate_pct']:.0f}%"
            )
        return "\n".join(lines)

    def reset(self) -> None:
        """Limpa todas as métricas."""
        with self._lock:
            self._by_model.clear()
            self._by_endpoint.clear()
            self._start_time = time.monotonic()


# ---------------------------------------------------------------------------
# Instância global
# ---------------------------------------------------------------------------
metrics = LocalAIMetrics()
