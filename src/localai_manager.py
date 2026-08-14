"""
Gerenciamento inteligente de modelos no LocalAI — orquestração de VRAM.

RTX 3060 Laptop = 6 GB VRAM (6144 MiB).
Estratégia: carregamento aditivo sempre que possível, descarregamento
seletivo (LRU) apenas quando necessário, proteção total de modelos CPU.

Princípios:
1. Modelos de embedding (CPU) → NUNCA descarregados
2. Mesma família/arquivo GGUF → sem recarga (grupo de afinidade)
3. Se modelo cabe junto com os atuais → mantém ambos carregados
4. Se não cabe → descarrega LRU até caber (NUNCA descarrega embedding)
5. Monitoramento nvidia-smi antes de cada operação de carga
6. Context manager `model_scope()` com reference counting

Arquitetura:
    ┌─────────────────────────────────────────────┐
    │  LocalAIManager                               │
    │  ├── _loaded_models: dict[str, int]          │  # model → refcount
    │  ├── _loaded_group: str | None               │  # grupo ativo grande
    │  ├── ensure_model_loaded()                   │
    │  ├── model_scope() → context manager         │
    │  ├── unload_model/unload_all/unload_group    │
    │  └── wait_for_model_loaded/warmup_model      │
    └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Generator
from typing import Any

import httpx

from config.settings import CLOUD_PROXY_MODEL_NAMES, LOCALAI_BASE_URL, USE_MODAL_VLLM
from src.vram_tracker import (
    _OVERHEAD_ADDITIONAL_MIB,
    check_available_vram,
    get_affinity_group,
    get_vram_mib,
    is_cpu_model,
)

logger = logging.getLogger(__name__)

# Constantes
_DEFAULT_TIMEOUT = 5
_POST_TIMEOUT = 15
_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.5
# VRAM da RTX 3060 Laptop
_TOTAL_VRAM_MIB = 6144
# Margem de segurança (VRAM nunca deve chegar a 100%)
_SAFETY_MARGIN_MIB = 512
# Modelos "grandes" que exigem exclusividade (>4GB de VRAM)
_LARGE_MODEL_THRESHOLD_MIB = 4000
# Tempo máximo aguardando liberação de VRAM quando modelos em uso (refcount>0)
# bloqueiam o carregamento. Após o timeout, ensure_model_loaded levanta erro
# em vez de corromper o tracker (o antigo unload_all limpava modelos em uso).
# Configurável via LOCALAI_VRAM_WAIT_TIMEOUT (segundos).
_VRAM_WAIT_TIMEOUT = float(os.getenv("LOCALAI_VRAM_WAIT_TIMEOUT", "60.0"))


class LocalAIMonitorError(RuntimeError):
    """Falha indeterminada do /backend/monitor — modelo pode estar carregado.

    Levantada quando o monitor retorna erro de backend (gRPC morto, EOF,
    conexão recusada) e não há como afirmar que o modelo NÃO está na memória.
    """


class LocalAIManager:
    """Gerencia modelos no LocalAI com orquestração inteligente de VRAM.

    Mantém um registro dos modelos carregados, seus grupos de afinidade
    e contagem de referências. Toma decisões de descarregamento apenas
    quando a VRAM disponível é insuficiente.
    """

    def __init__(
        self,
        base_url: str = LOCALAI_BASE_URL,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.replace("/v1", "").rstrip("/")
        self.max_retries = max_retries

        # Modelos atualmente carregados no LocalAI: model_id -> refcount
        self._loaded_models: OrderedDict[str, int] = OrderedDict()
        # Grupo de afinidade do modelo "grande" atualmente carregado
        # (se houver). Apenas um grupo grande pode estar ativo.
        self._active_large_group: str | None = None
        # Flag para evitar loop de reload
        self._in_transition: bool = False
        # Guard anti-loop de docker restart: True entre um restart aplicado e
        # o próximo load bem-sucedido. Impede restart em cascata quando vários
        # analistas paralelos falham por VRAM (todos chamariam docker_restart).
        self._restart_guard: bool = False
        # Serializa TODAS as transições de load/unload entre threads.
        # O "_gpu_lock" que o pipeline multi-analista mencionava NÃO existia;
        # agora cada decisão de VRAM passa por este RLock (reentrante).
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        # Contador de falhas indeterminadas do /backend/monitor (LocalAIMonitorError)
        self._monitor_failures: int = 0

    # ------------------------------------------------------------------
    # HTTP helpers (mantidos do original)
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        **kwargs,
    ) -> httpx.Response | None:
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=timeout, trust_env=False) as client:
                    resp = client.request(method, url, **kwargs)
                    return resp
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = _RETRY_BACKOFF**attempt
                    logger.debug(
                        "LocalAI %s %s tentativa %d/%d falhou (%s), retry em %.1fs",
                        method,
                        path,
                        attempt,
                        self.max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
        logger.warning(
            "LocalAI %s %s falhou após %d tentativas: %s",
            method,
            path,
            self.max_retries,
            last_exc,
        )
        return None

    # ------------------------------------------------------------------
    # Model discovery
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

    def get_currently_loaded(self) -> list[str]:
        """Verifica quais modelos estão realmente carregados no LocalAI.

        Usa /backend/monitor para cada modelo conhecido.
        Retorna apenas os que respondem 200.
        """
        all_models = self.get_all_models()
        if not all_models:
            return []

        loaded: list[str] = []
        # Testa apenas modelos candidatos (GPU-based, não CPU)
        for model_id in all_models:
            if is_cpu_model(model_id):
                continue
            if self._is_cloud_proxy_model(model_id):
                continue
            if USE_MODAL_VLLM:
                continue
            if self.is_model_loaded(model_id):
                loaded.append(model_id)

        return loaded

    # ------------------------------------------------------------------
    # Embedding / Cloud / Modal detection (mantidos do original)
    # ------------------------------------------------------------------

    _EMBEDDING_MODELS = {"nomic-embed-text-v1.5", "nomic-embed-text", "embeddinggemma-300m"}

    def _is_embedding_model(self, model_id: str) -> bool:
        return any(model_id.lower().startswith(p) for p in self._EMBEDDING_MODELS)

    @staticmethod
    def _is_cloud_proxy_model(model_id: str) -> bool:
        return model_id in CLOUD_PROXY_MODEL_NAMES

    # ------------------------------------------------------------------
    # Model status (mantido do original com melhorias)
    # ------------------------------------------------------------------

    def is_model_loaded(self, model_id: str) -> bool:
        """Verifica se um modelo está atualmente na memória.

        Para modelos CPU → sempre True.
        Para cloud/Modal → sempre True.
        Para GPU → consulta /backend/monitor.
        """
        if is_cpu_model(model_id):
            return True
        if self._is_cloud_proxy_model(model_id):
            return True
        if USE_MODAL_VLLM and not self._is_embedding_model(model_id):
            return True

        resp = self._request(
            "GET",
            "/backend/monitor",
            params={"model": model_id},
            timeout=3,
        )
        if resp is None:
            raise LocalAIMonitorError(
                f"Falha ao consultar /backend/monitor para {model_id}: resposta vazia"
            )
        if resp.status_code == 200:
            return True
        if resp.status_code == 500:
            text = resp.text.lower()
            if "is not currently loaded" in text:
                return False
            if (
                "no grpc backend" in text
                or "connection refused" in text
                or "connection error" in text
                or "rpc error" in text
                or "unimplemented" in text
                or "eof" in text
            ):
                raise LocalAIMonitorError(
                    f"/backend/monitor para {model_id} retornou backend indisponível "
                    f"(HTTP 500): {resp.text[:300]}"
                )
            return False
        return False

    def is_model_active_internal(self, model_id: str) -> bool:
        """Verifica se nosso tracker interno considera o modelo carregado."""
        return model_id in self._loaded_models

    # ------------------------------------------------------------------
    # VRAM-aware load/unload
    # ------------------------------------------------------------------

    def _get_loaded_vram_total(self) -> int:
        """Calcula VRAM total estimada dos modelos atualmente carregados.

        Inclui overhead adicional para cada modelo extra.
        """
        if not self._loaded_models:
            return 0

        total = 0
        for i, model_id in enumerate(self._loaded_models):
            vram = get_vram_mib(model_id)
            if i > 0 and vram > 0:
                vram += _OVERHEAD_ADDITIONAL_MIB
            total += vram
        return total

    def _can_fit_additive(self, target_model: str) -> bool:
        """Verifica se target_model cabe na VRAM sem descarregar nada.

        Considera o grupo de afinidade: modelos do mesmo grupo
        compartilham o arquivo GGUF (já carregado).

        A VRAM livre real (nvidia-smi) já EXCLUI os modelos atuais,
        então só precisamos verificar se target_model cabe no espaço
        restante.
        """
        if is_cpu_model(target_model):
            return True

        target_group = get_affinity_group(target_model)
        target_vram = get_vram_mib(target_model)

        # Se o grupo de afinidade já está carregado, o arquivo GGUF já
        # está em memória — só precisa do overhead adicional.
        if target_group and target_group == self._active_large_group:
            vram_needed = _OVERHEAD_ADDITIONAL_MIB
        else:
            vram_needed = target_vram

        vram_available = self._get_free_vram()

        logger.debug(
            "VRAM additive check: %s precisa %d MiB (+%d margem), " "disponivel %d MiB",
            target_model,
            vram_needed,
            _SAFETY_MARGIN_MIB,
            vram_available,
        )

        return vram_needed + _SAFETY_MARGIN_MIB <= vram_available

    def _get_free_vram(self) -> int:
        """Obtém VRAM livre real (nvidia-smi), com fallback para estimativa."""
        vram = check_available_vram()
        if vram["free_mib"] > 0:
            return vram["free_mib"]
        # Fallback: total - estimado
        used = self._get_loaded_vram_total()
        return max(0, _TOTAL_VRAM_MIB - used - _SAFETY_MARGIN_MIB)

    def _unload_lru_until_fits(self, target_model: str) -> bool:
        """Descarrega modelos LRU até que target_model caiba na VRAM.

        NUNCA descarrega modelos de embedding (CPU).
        Preserva o grupo de afinidade se possível.
        Retorna True se conseguiu liberar espaço suficiente.
        """
        target_vram = get_vram_mib(target_model)
        target_group = get_affinity_group(target_model)

        # Se o target é do mesmo grupo do ativo, só precisa de overhead
        if target_group and target_group == self._active_large_group:
            return True  # já vai caber

        # Ordenar LRU: OrderedDict mantém ordem de inserção.
        # Só considera modelos idle (refcount=0) — em uso não podem sair.
        models_to_consider = [m for m in self._loaded_models if self._loaded_models[m] <= 0]
        models_unloaded: list[str] = []

        for model_id in models_to_consider:
            if is_cpu_model(model_id):
                continue  # NUNCA descarrega CPU
            if self._is_cloud_proxy_model(model_id):
                continue
            if model_id == target_model:
                continue  # não descarrega o target

            current_free = self._get_free_vram()
            if current_free >= target_vram + _SAFETY_MARGIN_MIB:
                break  # já tem espaço

            logger.info("LRU: descarregando %s para liberar VRAM...", model_id)
            if self.unload_model(model_id):
                models_unloaded.append(model_id)

        # Verificar se VRAM livre é suficiente
        free = self._get_free_vram()
        if free >= target_vram + _SAFETY_MARGIN_MIB:
            logger.info(
                "LRU liberou VRAM: %d MiB livres (precisa %d)",
                free,
                target_vram,
            )
            return True

        logger.warning(
            "VRAM insuficiente mesmo após descarregar %d modelos: "
            "%d MiB livres, precisa %d MiB",
            len(models_unloaded),
            free,
            target_vram,
        )
        return False

    def _wait_for_room(self, target_model: str, timeout: float = _VRAM_WAIT_TIMEOUT) -> bool:
        """Aguarda até que haja VRAM livre suficiente para carregar target_model.

        Deve ser chamado COM self._lock adquirido. Usa Condition.wait, que
        LIBERA o lock durante a espera — permitindo que outras threads
        chamem _release_model() e liberem seus modelos (sem isso haveria
        deadlock). Retorna True se conseguiu espaço dentro do timeout.
        """
        deadline = time.monotonic() + timeout

        while True:
            if self._can_fit_additive(target_model):
                return True
            if self._unload_lru_until_fits(target_model):
                return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            # Libera o lock e espera por uma notificação de _release_model
            # (ou por timeout curto, para reavaliar a VRAM).
            self._cond.wait(timeout=min(5.0, remaining))

        return self._can_fit_additive(target_model)

    def _sync_from_localai(self) -> None:
        """Sincroniza o tracker interno com o estado real do LocalAI.

        Chamado após operações de shutdown para evitar estado inconsistente.
        """
        with self._lock:
            self._sync_from_localai_locked()

    def _sync_from_localai_locked(self) -> None:
        """Corpo real de _sync_from_localai (chamar apenas com self._lock)."""
        try:
            loaded = self.get_currently_loaded()
        except LocalAIMonitorError as exc:
            # Falha indeterminada do monitor: NÃO podemos afirmar que o modelo
            # saiu da memória — preserva o tracker para não criar órfão.
            self._monitor_failures += 1
            logger.error("sync_from_localai: monitor indeterminado (%s) — tracker preservado", exc)
            try:
                from src.localai_metrics import metrics

                metrics.record(
                    model="monitor",
                    endpoint="/backend/monitor",
                    latency_ms=0,
                    tokens=0,
                    error=True,
                )
            except Exception:
                pass
            return
        try:
            self._monitor_failures = 0
            # Remove do tracker o que não está mais carregado
            for model_id in list(self._loaded_models.keys()):
                if model_id not in loaded:
                    del self._loaded_models[model_id]

            # Se não há mais modelos carregados, limpa grupo grande
            if not loaded:
                self._active_large_group = None
            else:
                # Recalcula grupo grande ativo
                for model_id in loaded:
                    group = get_affinity_group(model_id)
                    if group and group not in ("embedding-cpu", None):
                        self._active_large_group = group
                        break
        except Exception as exc:
            logger.debug("sync_from_localai ignorado: %s", exc)

    def _discover_untracked_loaded_locked(self) -> None:
        """Descobre modelos real-carregados no LocalAI não rastreados no tracker.

        Cenário: um processo anterior (teste/cron/worker encerrado de forma
        abrupta) deixou um modelo carregado na GPU, ou o Cognee / um load
        manual carregou um modelo fora deste processo. O tracker deste
        processo não o conhece, então o LRU fica "cego": a VRAM real está
        ocupada mas não há nada para descarregar -> deadlock de 60s.

        Esta função consulta o LocalAI (/backend/monitor), rastreia os
        modelos carregados como idle (refcount=0) e atualiza o grupo grande
        ativo, permitindo que o LRU os descarregue quando precisar de espaço.

        Chamar apenas com self._lock adquirido. É inofensiva se não houver
        modelos órfãos (get_currently_loaded retorna vazio).
        """
        try:
            loaded = self.get_currently_loaded()
        except Exception as exc:
            logger.debug("Descoberta de modelos carregados ignorada: %s", exc)
            return

        for model_id in loaded:
            if model_id in self._loaded_models:
                continue
            # Modelo real-carregado mas não rastreado -> marca como idle.
            # (refcount=0 = pode ser descarregado pelo LRU quando necessário)
            self._loaded_models[model_id] = 0
            logger.info(
                "Descoberto modelo carregado no LocalAI (não rastreado): %s "
                "— rastreado como idle para o LRU poder gerenciá-lo.",
                model_id,
            )
            group = get_affinity_group(model_id)
            if (
                group
                and group not in ("embedding-cpu", None)
                and get_vram_mib(model_id) >= _LARGE_MODEL_THRESHOLD_MIB
            ):
                self._active_large_group = group

    def _force_release_vram_locked(self, target_model: str) -> bool:
        """Recuperação forçada de VRAM quando o LRU está 'cego'.

        O /backend/monitor do LocalAI-orchestrator NÃO reporta modelos
        realmente carregados (retorna 500 "no grpc backend found for ...gguf")
        mesmo com o GGUF ocupando a GPU. Isso deixa o tracker vazio e o LRU
        sem nada para descarregar -> deadlock de _VRAM_WAIT_TIMEOUT.

        Esta função derruba TODOS os backends GPU configurados que NÃO estão
        em uso neste processo (refcount <= 0), independentemente do monitor
        (o POST /backend/shutdown funciona mesmo quando o monitor falha).
        Modelos em uso aqui (refcount > 0) são preservados.

        Retorna True se a VRAM ficou suficiente para o target_model.
        Chamar apenas com self._lock adquirido.
        """
        logger.warning(
            "Recuperação forçada de VRAM: monitor do LocalAI não reporta o "
            "modelo real-carregado. Derrubando backends GPU ociosos/não "
            "rastreados para liberar espaço para %s...",
            target_model,
        )
        for model_id in self.get_all_models():
            if is_cpu_model(model_id):
                continue
            if self._is_cloud_proxy_model(model_id):
                continue
            if USE_MODAL_VLLM:
                continue
            if model_id == target_model:
                continue  # não derruba o alvo
            if self._loaded_models.get(model_id, 0) > 0:
                continue  # em uso neste processo — preserva
            # Pular modelos sem processo na GPU: o unload deles retorna 500
            # "model not found" (no-op), que gerava WARNING spam e, com o
            # fallback anterior, docker restart desnecessário no meio do load.
            if self._find_orphan_pid(model_id) is None:
                continue

            if self.unload_model(model_id):
                logger.info("Recuperação forçada: backend %s descarregado.", model_id)

        self._active_large_group = None
        free = self._get_free_vram()
        target_vram = get_vram_mib(target_model)
        fits = free >= target_vram + _SAFETY_MARGIN_MIB
        logger.info(
            "Recuperação forçada: %d MiB livres (precisa %d). %s",
            free,
            target_vram,
            "Cabe!" if fits else "Ainda não cabe.",
        )
        return fits

    def ensure_model_loaded(self, target_model: str) -> None:
        """Garante que target_model está carregado com uso inteligente de VRAM.

        Thread-safe: toda a decisão de load/unload é serializada via
        self._lock (RLock), eliminando as races entre threads paralelas
        (ex: analistas do pipeline multi-analista) que podiam fazer um
        modelo "carregar" antes de outro ser descarregado, ou derrubar
        um modelo ainda em uso.

        Fluxo:
        1. Modelo CPU/cloud/Modal → no-op (não consomem VRAM local)
        2. Se já carregado e rastreado → incrementa refcount
        3. Se não rastreado mas LocalAI diz que está carregado → adiciona ao tracker
        4. Tenta carregamento aditivo (sem descarregar nada)
        5. Se não cabe → LRU unload até caber
        6. Se é modelo grande → descarrega grupo grande anterior primeiro
        """
        with self._lock:
            self._ensure_model_loaded_locked(target_model)

    def _ensure_model_loaded_locked(self, target_model: str) -> None:
        """Corpo real de ensure_model_loaded (chamar apenas com self._lock)."""
        if self._in_transition:
            logger.debug("Em transição, pulando ensure_model_loaded para %s", target_model)
            return

        # --- Modelos que não consomem VRAM local ---
        if is_cpu_model(target_model):
            logger.debug("Modelo CPU %s — sem gerenciamento VRAM.", target_model)
            return
        if self._is_cloud_proxy_model(target_model):
            logger.debug("Modelo cloud-proxy %s — sem gerenciamento VRAM.", target_model)
            return
        if USE_MODAL_VLLM:
            logger.debug("Modo Modal ativo — sem gerenciamento VRAM local.")
            return

        # --- Já carregado (fast path) ---
        if target_model in self._loaded_models:
            self._loaded_models[target_model] += 1
            self._loaded_models.move_to_end(target_model)
            logger.debug(
                "Modelo %s já carregado (refcount=%d).",
                target_model,
                self._loaded_models[target_model],
            )
            return

        # --- Verificar se o LocalAI já tem o modelo (Cognee pode ter carregado) ---
        try:
            ja_carregado = self.is_model_active_internal(
                target_model
            ) or self.is_model_loaded(target_model)
        except LocalAIMonitorError as exc:
            logger.warning(
                "ensure_model_loaded: monitor indeterminado para %s (%s) — assumindo não carregado",
                target_model,
                exc,
            )
            ja_carregado = False
        if not self.is_model_active_internal(target_model) and ja_carregado:
            logger.info(
                "Modelo %s já está carregado no LocalAI (ex: Cognee). Rastreando.", target_model
            )
            self._loaded_models[target_model] = self._loaded_models.get(target_model, 0) + 1
            group = get_affinity_group(target_model)
            if (
                group
                and group not in ("embedding-cpu", None)
                and get_vram_mib(target_model) >= _LARGE_MODEL_THRESHOLD_MIB
            ):
                self._active_large_group = group
            return

        # --- Decisão de descarregamento ---
        target_vram = get_vram_mib(target_model)
        target_group = get_affinity_group(target_model)
        is_large = target_vram >= _LARGE_MODEL_THRESHOLD_MIB

        # Se é modelo grande, verificar conflito com grupo grande atual
        if is_large and self._active_large_group and self._active_large_group != target_group:
            # Modelos grande diferentes não coexistem — descarregar grupo atual
            logger.info(
                "Modelo grande %s (%s) conflita com grupo ativo %s. "
                "Descarregando modelos do grupo %s...",
                target_model,
                target_group,
                self._active_large_group,
                self._active_large_group,
            )
            self.unload_group(self._active_large_group)

        # Tentar carregamento aditivo
        if self._can_fit_additive(target_model):
            logger.info(
                "Carregamento aditivo: %s cabe com os %d modelos atuais " "(~%d MiB livres).",
                target_model,
                len(self._loaded_models),
                self._get_free_vram(),
            )
        else:
            # Auto-cura: descobrir modelos real-carregados no LocalAI que o
            # tracker não conhece (ex: processo anterior morto, Cognee, load
            # manual) e rastreá-los como idle. Sem isso o LRU fica cego e o
            # carregamento trava por _VRAM_WAIT_TIMEOUT.
            self._discover_untracked_loaded_locked()

            # Reavaliar: a descoberta pode ter mudado o grupo grande ativo /
            # o conjunto de modelos que o LRU consegue descarregar.
            if self._can_fit_additive(target_model):
                logger.info(
                    "Após descoberta de modelos não rastreados, %s cabe "
                    "aditivamente (~%d MiB livres).",
                    target_model,
                    self._get_free_vram(),
                )
            else:
                # Precisa liberar espaço — LRU unload
                logger.info(
                    "VRAM insuficiente para %s (%d MiB). Aplicando LRU unload...",
                    target_model,
                    target_vram,
                )
                if not self._unload_lru_until_fits(target_model):
                    # LRU não achou nada: ou os modelos em uso não podem sair,
                    # ou o tracker está "cego" (monitor do LocalAI não reporta
                    # o modelo real-carregado). Tenta recuperação forçada —
                    # derruba backends GPU ociosos/não rastreados.
                    if self._force_release_vram_locked(target_model):
                        logger.info(
                            "Recuperação forçada liberou VRAM para %s.",
                            target_model,
                        )
                    else:
                        # Ainda bloqueada por modelos em uso (refcount>0): aguarda
                        # até algum modelo ser liberado (Condition.wait), com timeout.
                        # NÃO usa unload_all_models() aqui: ele limpava o tracker
                        # inclusive de modelos ainda em uso, corrompendo o estado.
                        logger.warning(
                            "VRAM bloqueada para %s (%d MiB) por modelos em uso. "
                            "Aguardando liberação...",
                            target_model,
                            target_vram,
                        )
                        if not self._wait_for_room(target_model):
                            # Último recurso: reiniciar o container LocalAI.
                            # É a única forma confiável de derrubar backends
                            # órfãos (o LocalAI perde o tracking do nome e o
                            # shutdown por nome/PID falha). Após o restart a
                            # VRAM fica 100% livre e o modelo recarrega sob
                            # demanda — por isso o RETRY, não o abort.
                            logger.warning(
                                "VRAM bloqueada para %s (%d MiB) mesmo após "
                                "%.0fs. Aplicando docker restart como último "
                                "recurso...",
                                target_model,
                                target_vram,
                                _VRAM_WAIT_TIMEOUT,
                            )
                            try:
                                if self._restart_guard:
                                    logger.error(
                                        "docker restart já aplicado para %s e "
                                        "retry falhou — abortando (estado "
                                        "preservado).",
                                        target_model,
                                    )
                                    raise RuntimeError(
                                        f"VRAM insuficiente para carregar "
                                        f"{target_model} mesmo após docker "
                                        f"restart."
                                    )
                                from src.models_config import docker_restart

                                if docker_restart():
                                    logger.info(
                                        "docker restart aplicado — tentando "
                                        "carregar %s novamente.",
                                        target_model,
                                    )
                                    self._restart_guard = True
                                    self._loaded_models.clear()
                                    self._active_large_group = None
                                    time.sleep(10)  # aguarda servidor voltar
                                    return self._ensure_model_loaded_locked(
                                        target_model
                                    )
                            except Exception as exc:
                                logger.debug("docker restart falhou: %s", exc)
                            logger.error(
                                "VRAM insuficiente para %s mesmo após %.0fs "
                                "de espera e docker restart. Abortando "
                                "carregamento (estado preservado).",
                                target_model,
                                _VRAM_WAIT_TIMEOUT,
                            )
                            raise RuntimeError(
                                f"VRAM insuficiente para carregar {target_model}: "
                                "modelos em uso não foram liberados."
                            )

        # --- Atualizar tracker ---
        self._loaded_models[target_model] = self._loaded_models.get(target_model, 0) + 1
        if target_group and target_group not in ("embedding-cpu", None) and is_large:
            self._active_large_group = target_group
        # Reset do guard de restart: o ciclo restart->load terminou com sucesso
        self._restart_guard = False

        logger.info(
            "Modelo %s assegurado. VRAM estimada: %d MiB usada de %d MiB total.",
            target_model,
            self._get_loaded_vram_total(),
            _TOTAL_VRAM_MIB,
        )

    # ------------------------------------------------------------------
    # Context manager para reference counting
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def model_scope(self, model_id: str) -> Generator[None, Any, None]:
        """Context manager que mantém o modelo carregado durante o bloco.

        Incrementa refcount no enter, decrementa no exit.
        Se refcount chega a zero, modelo pode ser descarregado por LRU.

        Uso:
            with manager.model_scope("gemma-4-e2b-it"):
                # modelo garantido na GPU
                client.chat(prompt)
        """
        self.ensure_model_loaded(model_id)
        try:
            yield
        finally:
            self._release_model(model_id)

    def _release_model(self, model_id: str) -> None:
        """Decrementa refcount de um modelo. Se zero, marca como idle.

        IMPORTANTE: o backend do LocalAI CONTINUA carregado na GPU mesmo
        com refcount=0. Por isso o modelo fica no tracker com valor 0
        (idle) — o LRU precisa saber que ele ocupa VRAM para poder
        descarregá-lo quando necessário.
        """
        with self._lock:
            self._release_model_locked(model_id)

    def _release_model_locked(self, model_id: str) -> None:
        """Corpo real de _release_model (chamar apenas com self._lock)."""
        if model_id not in self._loaded_models:
            return
        self._loaded_models[model_id] -= 1
        if self._loaded_models[model_id] <= 0:
            self._loaded_models[model_id] = 0  # idle, backend ainda na GPU
            # Atualiza grupo grande se necessário
            group = get_affinity_group(model_id)
            if group and group == self._active_large_group:
                # Verificar se ainda há algum modelo do mesmo grupo
                still_has = any(
                    get_affinity_group(m) == group and self._loaded_models[m] > 0
                    for m in self._loaded_models
                )
                if not still_has:
                    self._active_large_group = None
            logger.debug("Modelo %s liberado (refcount=0, idle).", model_id)
        # Acorda threads aguardando em _wait_for_room (VRAM pode ter mudado)
        self._cond.notify_all()

    # ------------------------------------------------------------------
    # Unload operations (com proteção de CPU models)
    # ------------------------------------------------------------------

    def unload_model(self, model_id: str) -> bool:
        """Descarrega um modelo específico.

        NUNCA descarrega modelos de embedding (CPU).
        Modelos com refcount > 0 (em uso) são preservados.
        Thread-safe: transição serializada via self._lock.
        """
        with self._lock:
            return self._unload_model_locked(model_id)

    def _unload_model_locked(self, model_id: str) -> bool:
        """Corpo real de unload_model (chamar apenas com self._lock)."""
        if is_cpu_model(model_id):
            logger.debug("Modelo CPU %s — preservado.", model_id)
            return True
        if self._is_cloud_proxy_model(model_id):
            return True
        if USE_MODAL_VLLM and not self._is_embedding_model(model_id):
            return True

        # Proteção: modelo em uso ativo não pode ser descarregado
        if self._loaded_models.get(model_id, 0) > 0:
            logger.debug("Modelo %s em uso (refcount>0) — preservado.", model_id)
            return False

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
            logger.info("Modelo %s descarregado.", model_id)
            # Atualiza tracker e grupo
            if model_id in self._loaded_models:
                del self._loaded_models[model_id]
                self._sync_from_localai()
            self._cond.notify_all()
            return True
        if resp.status_code == 500:
            text = resp.text.lower()
            # Backend já morto (processo terminou) = memória já liberada.
            # "unimplemented" ocorre quando o gRPC do backend não responde
            # porque o processo foi encerrado — o unload efetivamente ocorreu.
            #
            # PITFALL 2026-08-11: o LocalAI retorna 500 "model not found"
            # também quando o backend ESTÁ VIVO mas o tracking interno do
            # nome do modelo foi perdido (backend órfão). Nesse caso o
            # processo continua na GPU (nvidia-smi mostra a VRAM ocupada) e
            # tratar como "descarregado" é mentira — o LRU fica cego e o
            # próximo load grande aborta por VRAM insuficiente.
            if (
                "unimplemented" in text
                or "eof" in text
                or "not loaded" in text
            ):
                logger.info(
                    "Modelo %s: backend já encerrado (HTTP 500 %s). Considerando descarregado.",
                    model_id,
                    text.strip()[:80],
                )
                self._loaded_models.pop(model_id, None)
                self._sync_from_localai()
                self._cond.notify_all()
                return True

            if "not found" in text:
                # Distinguir entre "modelo não carregado" (no-op → True) e
                # "backend órfão vivo na GPU" (tem PID com VRAM compatível).
                # PITFALL 2026-08-11: o LocalAI retorna 500 "model not found"
                # também quando o backend ESTÁ VIVO mas o tracking interno do
                # nome do modelo foi perdido. Verificar a VRAM real resolve:
                # sem processo na GPU → nada a descarregar → True.
                pid = self._find_orphan_pid(model_id)
                if pid is None:
                    logger.info(
                        "Modelo %s: 500 'not found' e sem processo na GPU "
                        "— nada a descarregar. Considerando descarregado.",
                        model_id,
                    )
                    self._loaded_models.pop(model_id, None)
                    self._sync_from_localai()
                    self._cond.notify_all()
                    return True
                # Backend órfão REAL: processo na GPU mas LocalAI perdeu o
                # tracking. Tentar shutdown por PID; sem sucesso, retornar
                # False honesto (o docker restart final em ensure_model_loaded
                # resolve).
                logger.warning(
                    "Modelo %s: 500 'not found' mas PID %s segue na GPU "
                    "(%d MiB) — backend órfão. Tentando shutdown por PID...",
                    model_id, pid, self._get_gpu_vram_for_pid(pid),
                )
                resp = self._request(
                    "POST",
                    "/backend/shutdown",
                    timeout=_POST_TIMEOUT,
                    json={"model": model_id, "pid": int(pid)},
                )
                if resp is not None and resp.status_code in (200, 204):
                    logger.info(
                        "Modelo %s: backend órfão derrubado por PID.", model_id
                    )
                    self._loaded_models.pop(model_id, None)
                    self._sync_from_localai()
                    self._cond.notify_all()
                    return True
                # Último recurso: docker exec pkill dentro do container.
                # O API shutdown falhou (backend órfão resistente), mas o
                # processo está vivo na GPU e bloqueando a VRAM. Matar via
                # docker exec é mais rápido que um docker restart completo
                # (que reinicia o LocalAI inteiro e demora 15-30s).
                logger.warning(
                    "Modelo %s: backend órfão (PID %s) resistente ao "
                    "shutdown via API — tentando docker exec pkill...",
                    model_id, pid,
                )
                try:
                    import subprocess as _sp
                    # Identificar nome do container LocalAI
                    _container = os.environ.get(
                        "LOCALAI_CONTAINER_NAME", "localai-orchestrator"
                    )
                    _kill = _sp.run(
                        ["docker", "exec", _container,
                         "pkill", "-9", "-f", "llama-cpp"],
                        capture_output=True, text=True, timeout=15,
                    )
                    if _kill.returncode in (0, 1):  # 0=killed, 1=nenhum processo
                        logger.info(
                            "Modelo %s: docker exec pkill enviado (rc=%d). "
                            "Aguardando VRAM liberar...",
                            model_id, _kill.returncode,
                        )
                        # Aguardar até 10s para VRAM ser liberada
                        for _w in range(10):
                            time.sleep(1)
                            if self._get_gpu_vram_for_pid(pid) == 0:
                                logger.info(
                                    "Modelo %s: VRAM liberada após pkill (%ds).",
                                    model_id, _w + 1,
                                )
                                self._loaded_models.pop(model_id, None)
                                self._sync_from_localai()
                                self._cond.notify_all()
                                return True
                        logger.warning(
                            "Modelo %s: pkill enviado mas VRAM não liberou em 10s.",
                            model_id,
                        )
                    else:
                        logger.warning(
                            "Modelo %s: docker exec pkill falhou (rc=%d): %s",
                            model_id, _kill.returncode, _kill.stderr[:200],
                        )
                except Exception as _exc:
                    logger.warning(
                        "Modelo %s: docker exec pkill erro: %s — "
                        "docker restart será aplicado no load.",
                        model_id, _exc,
                    )
                return False
        logger.warning(
            "Falha ao descarregar %s (HTTP %d): %s",
            model_id,
            resp.status_code,
            resp.text,
        )
        return False

    def _get_gpu_vram_for_pid(self, pid: int) -> int:
        """Retorna VRAM usada (MiB) de um PID na GPU, ou 0 se ausente."""
        try:
            import subprocess

            out = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory",
                 "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode != 0:
                return 0
            for line in out.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2 or parts[0] != str(pid):
                    continue
                try:
                    return int(parts[1].replace("MiB", "").strip())
                except ValueError:
                    return 0
        except Exception:
            pass
        return 0

    def _find_orphan_pid(self, model_id: str) -> int | None:
        """Acha PID na GPU com VRAM compatível com o modelo (backend órfão).

        Retorna o PID de um processo na GPU cujo consumo está dentro de
        +/-25% (ou 512 MiB) do VRAM esperado do modelo. Usado para
        distinguir 'modelo não carregado' (sem processo) de 'backend órfão'
        (processo vivo mas com tracking perdido no LocalAI).
        """
        try:
            import subprocess

            out = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory",
                 "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode != 0:
                logger.debug("nvidia-smi falhou: %s", out.stderr.strip())
                return None

            target_vram = get_vram_mib(model_id)
            if target_vram <= 0:
                return None
            for line in out.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue
                pid, used = parts[0], parts[1]
                try:
                    used_mib = int(used.replace("MiB", "").strip())
                except ValueError:
                    continue
                if abs(used_mib - target_vram) > max(512, target_vram * 0.25):
                    continue
                logger.info(
                    "Backend órfão %s: PID %s usa %d MiB (esperado ~%d).",
                    model_id, pid, used_mib, target_vram,
                )
                return int(pid)
        except Exception as exc:
            logger.debug("find_orphan_pid falhou: %s", exc)
        return None

    def unload_group(self, group: str) -> bool:
        """Descarrega todos os modelos de um grupo de afinidade.

        Thread-safe: transição serializada via self._lock.
        """
        with self._lock:
            return self._unload_group_locked(group)

    def _unload_group_locked(self, group: str) -> bool:
        """Corpo real de unload_group (chamar apenas com self._lock)."""
        models_in_group = [
            m for m in list(self._loaded_models.keys()) if get_affinity_group(m) == group
        ]
        if not models_in_group:
            return True

        logger.info("Descarregando grupo %s (%d modelos)...", group, len(models_in_group))
        success = True
        for model_id in models_in_group:
            if not self.unload_model(model_id):
                success = False

        if self._active_large_group == group:
            self._active_large_group = None

        return success

    def unload_all_models(self) -> bool:
        """Descarrega todos os modelos GPU da VRAM.

        Modelos de embedding (CPU) são preservados.
        Modelos com refcount > 0 (em uso) NÃO são removidos do tracker —
        apenas os efetivamente descarregados saem (o antigo .clear() aqui
        corrompia o estado removendo modelos ainda em uso).
        Thread-safe: transição serializada via self._lock.
        """
        with self._lock:
            return self._unload_all_models_locked()

    def _unload_all_models_locked(self) -> bool:
        """Corpo real de unload_all_models (chamar apenas com self._lock)."""
        if USE_MODAL_VLLM:
            return True
        if CLOUD_PROXY_MODEL_NAMES:
            all_models = self.get_all_models()
            if all_models and all(self._is_cloud_proxy_model(m) for m in all_models):
                logger.debug("Apenas modelos cloud-proxy ativos — pula VRAM cleanup.")
                return True

        logger.info("Descarregando todos os modelos GPU da VRAM...")

        # Descarrega apenas modelos GPU (mantém CPU embeddings)
        gpu_models = [
            m
            for m in list(self._loaded_models.keys())
            if not is_cpu_model(m) and not self._is_cloud_proxy_model(m)
        ]

        if not gpu_models:
            # Fallback: descobrir o que o LocalAI tem carregado e descarregar
            logger.debug("Nenhum modelo GPU rastreado — descobrindo via LocalAI.")
            self._in_transition = True
            try:
                loaded_in_localai = self.get_currently_loaded()
                if not loaded_in_localai:
                    # Último recurso: shutdown all
                    resp = self._request(
                        "POST",
                        "/backend/shutdown",
                        timeout=_POST_TIMEOUT,
                        json={"model": "all"},
                    )
                    if resp is not None and resp.status_code in (200, 204):
                        self._loaded_models.clear()
                        self._active_large_group = None
                        self._cond.notify_all()
                        return True
                    return False

                success = True
                for model_id in loaded_in_localai:
                    if not self.unload_model(model_id):
                        success = False
                self._active_large_group = None
                self._cond.notify_all()
                return success
            finally:
                self._in_transition = False

        # Descarrega um por um (unload_model já remove do tracker os que
        # realmente descarregou; modelos em uso ficam preservados).
        success = True
        for model_id in gpu_models:
            if not self.unload_model(model_id):
                success = False

        # Recalcula grupo grande ativo a partir dos modelos que permanecem
        # em uso — NÃO usa clear() (evita corromper o tracker).
        self._active_large_group = None
        for model_id in self._loaded_models:
            group = get_affinity_group(model_id)
            if (
                group
                and group not in ("embedding-cpu", None)
                and self._loaded_models[model_id] > 0
            ):
                self._active_large_group = group
                break
        self._cond.notify_all()
        return success

    # ------------------------------------------------------------------
    # Warmup e wait (mantidos do original)
    # ------------------------------------------------------------------

    def wait_for_model_loaded(
        self, model_id: str, timeout: float = 60.0, interval: float = 2.0
    ) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                if self.is_model_loaded(model_id):
                    logger.info("Modelo %s carregado em %.1fs.", model_id, time.monotonic() - start)
                    return True
            except LocalAIMonitorError as exc:
                logger.warning(
                    "wait_for_model_loaded: monitor indeterminado para %s (%s) — aguardando",
                    model_id,
                    exc,
                )
            time.sleep(interval)
        logger.warning("Timeout aguardando carregamento de %s (%.1fs).", model_id, timeout)
        return False

    def warmup_model(self, model_id: str, timeout: float = 30.0) -> bool:
        """Força o pré-carregamento de um modelo com uma requisição leve."""
        logger.info("Warmup do modelo %s...", model_id)
        if is_cpu_model(model_id):
            return True
        try:
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "Ola"}],
                "max_tokens": 1,
                "temperature": 0.0,
            }
            url = f"{self.base_url}/v1/chat/completions"
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info("Warmup de %s concluido.", model_id)
                    return True
                corpo = resp.text[:300] if resp.text else ""
                logger.warning(
                    "Warmup de %s retornou HTTP %d.%s",
                    model_id,
                    resp.status_code,
                    f" Corpo: {corpo}" if corpo else "",
                )
                return False
        except Exception as exc:
            logger.warning("Warmup de %s falhou: %s", model_id, exc)
            return False

    # ------------------------------------------------------------------
    # Health check (mantido do original)
    # ------------------------------------------------------------------

    def health_check(self, model: str | None = None) -> dict:
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
                "vram": check_available_vram(),
            }

        loaded: list[str] = []
        check_models = [model] if model else models[:5]
        for m in check_models:
            try:
                if self.is_model_loaded(m):
                    loaded.append(m)
            except LocalAIMonitorError as exc:
                logger.warning(
                    "health_check: monitor indeterminado para %s (%s) — ignorando", m, exc
                )

        status = "ok" if (not model or model in loaded) else "degraded"
        if cb_status["state"] != "closed":
            status = "degraded"

        return {
            "status": status,
            "base_url": self.base_url,
            "models_available": len(models),
            "models_loaded": loaded,
            "models_tracked": list(self._loaded_models.keys()),
            "latency_ms": latency_ms,
            "circuit_breaker": cb_status,
            "metrics": metrics.summary(),
            "vram": check_available_vram(),
            "vram_estimated_used_mib": self._get_loaded_vram_total(),
        }

    # ------------------------------------------------------------------
    # Controle de backends (integração com YAMLs do LocalAI)
    # ------------------------------------------------------------------

    def get_model_config(self, model_name: str) -> dict[str, Any] | None:
        """Retorna a configuração completa de um modelo das YAMLs."""
        try:
            from src import models_config as _mc

            cfg = _mc.get_config(model_name)
            if not cfg:
                return None
            return {
                "name": cfg.name,
                "backend": cfg.backend.value,
                "gpu_layers": cfg.gpu_layers,
                "context_size": cfg.context_size,
                "gguf_mib": cfg.gguf_mib,
                "vram_estimate_mib": cfg.vram_estimate_mib,
                "no_kv_offloading": cfg.no_kv_offloading,
                "embeddings": cfg.embeddings,
                "gguf_path": str(cfg.gguf_path) if cfg.gguf_path else None,
                "affinity_group": cfg.affinity_group,
                "file_path": str(cfg.file_path),
            }
        except ImportError:
            return None

    def set_backend(
        self,
        model_name: str,
        backend: str = "cuda13-llama-cpp",
        gpu_layers: int | None = None,
        restart: bool = False,
    ) -> bool:
        """Altera o backend de um modelo nas YAMLs do LocalAI.

        Args:
            model_name: Nome do modelo (ex: 'qwen2.5-1.5b-instruct-q4-k-m')
            backend: 'cuda13-llama-cpp', 'vulkan-llama-cpp', ou 'llama-cpp'
            gpu_layers: Opcional. Se 0, remove GPU layers (CPU).
            restart: Se True, reinicia o container após alterar.

        Returns:
            True se bem-sucedido.
        """
        try:
            from src import models_config as _mc

            ok = _mc.set_model_backend(model_name, backend, gpu_layers)
            if ok and restart:
                ok = _mc.docker_restart()
            return ok
        except ImportError:
            logger.error("models_config não disponível")

            return False

    def set_gpu_layers(self, model_name: str, layers: int, restart: bool = False) -> bool:
        """Ajusta quantas camadas de um modelo rodam na GPU.

        layers=0 → CPU-only (backend vira 'llama-cpp')
        layers=1..N → N camadas GPU, resto CPU
        layers>=total → full GPU
        """
        try:
            from src import models_config as _mc

            ok = _mc.set_gpu_layers(model_name, layers)
            if ok and restart:
                ok = _mc.docker_restart()
            return ok
        except ImportError:
            logger.error("models_config não disponível")
            return False

    def set_kv_offloading(self, model_name: str, enabled: bool, restart: bool = False) -> bool:
        """Controla se o KV cache fica na GPU (mais rápido) ou RAM (menos VRAM)."""
        try:
            from src import models_config as _mc

            ok = _mc.set_kv_offloading(model_name, enabled)
            if ok and restart:
                ok = _mc.docker_restart()
            return ok
        except ImportError:
            logger.error("models_config não disponível")
            return False

    def show_model_configs(self) -> str:
        """Retorna tabela formatada de todas as configs."""
        try:
            from src import models_config as _mc

            return _mc.format_model_table()
        except ImportError:
            return "models_config não disponível"

    def show_docker_status(self) -> dict[str, Any]:
        """Retorna status dos backends no Docker."""
        try:
            from src import models_config as _mc

            return _mc.get_docker_backend_status()
        except ImportError:
            return {"error": "models_config não disponível"}


# Instância global
manager = LocalAIManager()
