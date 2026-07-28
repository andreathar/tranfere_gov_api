"""
Circuit Breaker para LocalAI — evita spam de requests a servidor morto.

Padrão: CLOSED (normal) → OPEN (bloqueia após N falhas) → HALF_OPEN (testa) → CLOSED.

Uso:
    from src.localai_circuit import circuit_breaker

    if not circuit_breaker.allow_request():
        raise RuntimeError("LocalAI indisponível (circuit OPEN)")

    try:
        result = make_request()
        circuit_breaker.record_success()
    except Exception:
        circuit_breaker.record_failure()
        raise
"""

from __future__ import annotations

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class State(Enum):
    CLOSED = "closed"        # Normal — requests passam
    OPEN = "open"            # Bloqueado — requests são recusados
    HALF_OPEN = "half_open"  # Teste — 1 request permitido


class CircuitBreaker:
    """Circuit breaker thread-safe para proteger chamadas ao LocalAI.

    Args:
        failure_threshold: N falhas consecutivas para abrir o circuito
        recovery_timeout: segundos para transição OPEN → HALF_OPEN
        half_open_max_calls: quantos requests testar em HALF_OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> State:
        """Retorna o estado atual, verificando transição automática OPEN→HALF_OPEN."""
        if self._state == State.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                logger.info(
                    "Circuit breaker: OPEN→HALF_OPEN (cooldown %.0fs expirou)",
                    elapsed,
                )
                self._state = State.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def allow_request(self) -> bool:
        """Retorna True se o request deve ser permitido."""
        current = self.state  # aciona transição automática
        if current == State.CLOSED:
            return True
        if current == State.HALF_OPEN:
            if self._half_open_calls < self._half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        # OPEN
        return False

    def record_success(self) -> None:
        """Registra uma chamada bem-sucedida."""
        if self._state == State.HALF_OPEN:
            self._success_count += 1
            logger.info(
                "Circuit breaker: HALF_OPEN→CLOSED (sucesso #%d)",
                self._success_count,
            )
            self._state = State.CLOSED
            self._failure_count = 0
            self._success_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Registra uma falha. Abre o circuito após threshold."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == State.HALF_OPEN:
            logger.warning("Circuit breaker: HALF_OPEN→OPEN (falha no teste)")
            self._state = State.OPEN
        elif self._failure_count >= self._failure_threshold:
            logger.warning(
                "Circuit breaker: CLOSED→OPEN (%d falhas consecutivas)",
                self._failure_count,
            )
            self._state = State.OPEN

    def reset(self) -> None:
        """Força reset para CLOSED (para testes ou recovery manual)."""
        self._state = State.CLOSED
        self._failure_count = 0
        self._success_count = 0

    def status(self) -> dict:
        """Retorna status do circuit breaker para logging/monitoramento."""
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_age_s": (
                round(time.monotonic() - self._last_failure_time, 1)
                if self._last_failure_time
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Instância global
# ---------------------------------------------------------------------------
circuit_breaker = CircuitBreaker()
