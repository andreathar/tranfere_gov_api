"""
Gerenciamento de modelos no LocalAI — exclusividade VRAM, health check, retry.

Migrou de `requests` para `httpx` (consistente com LocalAIClient).
Adicionou retry com backoff exponencial e health check por modelo.
"""

from __future__ import annotations

import logging
import time

import httpx

from config.settings import LOCALAI_BASE_URL

logger = logging.getLogger(__name__)

# Retry config (consistente com LOCALAI_MAX_RETRIES do settings)
_DEFAULT_TIMEOUT = 5      # GET rápido
_POST_TIMEOUT = 15        # POST (unload é mais pesado)
_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.5      # base do backoff


class LocalAIManager:
    """Gerencia exclusividade de VRAM no LocalAI + health check."""

    def __init__(
        self,
        base_url: str = LOCALAI_BASE_URL,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.replace("/v1", "").rstrip("/")
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        **kwargs,
    ) -> httpx.Response | None:
        """HTTP request com retry + backoff. Retorna None se todas as tentativas falharem."""
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.request(method, url, **kwargs)
                    return resp
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = _RETRY_BACKOFF ** attempt
                    logger.debug(
                        "LocalAI %s %s tentativa %d/%d falhou (%s), retry em %.1fs",
                        method, path, attempt, self.max_retries, exc, wait,
                    )
                    time.sleep(wait)

        logger.warning(
            "LocalAI %s %s falhou após %d tentativas: %s",
            method, path, self.max_retries, last_exc,
        )
        return None

    # ------------------------------------------------------------------
    # Modelos
    # ------------------------------------------------------------------

    def get_all_models(self) -> list[str]:
        """Retorna todos os modelos configurados no LocalAI."""
        resp = self._request("GET", "/v1/models", timeout=_DEFAULT_TIMEOUT)
        if resp is None or resp.status_code != 200:
            return []
        try:
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except (KeyError, ValueError) as exc:
            logger.warning("Resposta inesperada ao listar modelos: %s", exc)
            return []

    def is_model_loaded(self, model_id: str) -> bool:
        """Verifica se um modelo está atualmente na memória.

        Retorna False em caso de timeout ou erro (antes retornava True em timeout,
        o que causava falsa presunção de que o modelo estava carregado quando na
        verdade a GPU estava sobrecarregada).
        """
        resp = self._request(
            "GET",
            "/backend/monitor",
            params={"model": model_id},
            timeout=3,
        )
        if resp is None:
            # Falha de conexão total — servidor provavelmente indisponível
            return False
        if resp.status_code == 200:
            return True
        if resp.status_code == 500:
            text = resp.text.lower()
            if "is not currently loaded" in text or "no grpc backend" in text:
                return False
        return False

    def unload_model(self, model_id: str) -> bool:
        """Força o descarregamento (shutdown) do backend de um modelo."""
        logger.info("Descarregando modelo da memória: %s ...", model_id)
        resp = self._request(
            "POST",
            "/backend/shutdown",
            timeout=_POST_TIMEOUT,
            json={"model": model_id},
        )
        if resp is None:
            return False
        if resp.status_code in (200, 204) or resp.text.strip() == "":
            logger.info("Modelo %s descarregado com sucesso.", model_id)
            return True
        logger.warning("Falha ao descarregar %s (HTTP %d): %s", model_id, resp.status_code, resp.text)
        return False

    # ------------------------------------------------------------------
    # Exclusividade VRAM
    # ------------------------------------------------------------------

    def ensure_model_loaded(self, target_model: str) -> None:
        """Garante que apenas o target_model esteja na memória (exclusividade).

        LocalAI carrega modelos sob demanda (lazy-load). Esta função descarrega
        outros modelos ativos para liberar VRAM/GPU.
        """
        all_models = self.get_all_models()
        if not all_models:
            logger.warning("Não foi possível listar modelos do LocalAI (servidor indisponível?)")
            return

        for m in all_models:
            if m == target_model:
                continue
            if self.is_model_loaded(m):
                self.unload_model(m)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self, model: str | None = None) -> dict:
        """Verifica status do LocalAI: conectividade, modelos, circuit breaker, métricas.

        Returns:
            {
                "status": "ok" | "degraded" | "error",
                "base_url": str,
                "models_available": int,
                "models_loaded": list[str],
                "latency_ms": float,
                "circuit_breaker": {"state": str, "failure_count": int},
                "metrics": {...},
            }
        """
        from src.localai_circuit import circuit_breaker
        from src.localai_metrics import metrics

        start = time.monotonic()
        models = self.get_all_models()
        latency_ms = (time.monotonic() - start) * 1000

        cb_status = circuit_breaker.status()

        if not models:
            return {
                "status": "error",
                "base_url": self.base_url,
                "models_available": 0,
                "models_loaded": [],
                "latency_ms": latency_ms,
                "circuit_breaker": cb_status,
                "metrics": metrics.summary(),
            }

        # Descobrir quais estão carregados
        loaded: list[str] = []
        check_models = [model] if model else models[:5]
        for m in check_models:
            if self.is_model_loaded(m):
                loaded.append(m)

        status = "ok" if (not model or model in loaded) else "degraded"
        if cb_status["state"] != "closed":
            status = "degraded"

        return {
            "status": status,
            "base_url": self.base_url,
            "models_available": len(models),
            "models_loaded": loaded,
            "latency_ms": latency_ms,
            "circuit_breaker": cb_status,
            "metrics": metrics.summary(),
        }


# ------------------------------------------------------------------
# Instância global (compatível com imports existentes)
# ------------------------------------------------------------------
manager = LocalAIManager()
