"""
Rastreador de VRAM — orçamento e monitoramento de memória GPU.

Fontes da verdade:
  1. YAMLs em /mnt/data/Projects_SSD/LocalAI/models/ (via models_config)
  2. nvidia-smi (VRAM real)
  3. MODEL_VRAM dict (fallback hardcoded)

RTX 3060 Laptop = 6 GB VRAM (6144 MiB).
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VRAM Budget — hardcoded para modelos conhecidos (fallback)
# Usado quando models_config.scan_all_model_configs() não está disponível
# ---------------------------------------------------------------------------


@dataclass
class ModelVRAM:
    """Orçamento VRAM de um modelo específico."""

    gguf_bytes: int
    overhead_mib: int
    group: str = ""


# Tamanho real dos GGUFs (bytes) + overhead estimado (MiB)
# Overhead inclui: KV cache parcial + backend buffers + CUDA context
# Atualizado 2026-08-15: removidos modelos sem YAML/GGUF (gemma-4-e2b-it,
# zero-gemma4, agente-dossie-*, minicpm5, qwen3.5-9b, llama-3.1-8b-vulkan).
MODEL_VRAM: dict[str, ModelVRAM] = {
    # --- LLMs (GPU via cuda13-llama-cpp) ---
    "qwen2.5-1.5b-instruct-q4-k-m": ModelVRAM(1_100_000_000, 400, "qwen2.5-family"),
    "llama-3.2-3b-instruct:q4_k_m": ModelVRAM(1_900_000_000, 500, "llama3.2-family"),
    "llama-3.1-8b-q4-k-m": ModelVRAM(
        4_600_000_000, 400, "llama3.1-family"
    ),  # no_kv_offloading=false, KV offload to RAM
    "Qwen2.5-Coder-7B-Instruct-GGUF": ModelVRAM(4_400_000_000, 500, "coder-family"),
    # --- Embeddings (CPU puro via backend cpu-llama-cpp desde 2026-07-31) ---
    "embeddinggemma-300m": ModelVRAM(314_000_000, 0, "embedding-cpu"),
    "nomic-embed-text-v1.5": ModelVRAM(262_000_000, 0, "embedding-cpu"),
    "nomic-embed-text": ModelVRAM(262_000_000, 0, "embedding-cpu"),
}

# Modelos que não consomem VRAM (CPU puro via backend cpu-llama-cpp)
CPU_ONLY_MODELS = {
    "embeddinggemma-300m",
    "nomic-embed-text-v1.5",
    "nomic-embed-text",
}

# Overhead adicional por modelo carregado além do primeiro (KV cache compartilhado)
_OVERHEAD_ADDITIONAL_MIB = 150

# ---------------------------------------------------------------------------
# Grupos de afinidade — modelos que compartilham GGUF
# ---------------------------------------------------------------------------

AFFINITY_GROUPS: dict[str, list[str]] = {
    "qwen2.5-family": ["qwen2.5-1.5b-instruct-q4-k-m"],
    "llama3.1-family": ["llama-3.1-8b-q4-k-m"],
    "llama3.2-family": ["llama-3.2-3b-instruct:q4_k_m"],
    "coder-family": ["Qwen2.5-Coder-7B-Instruct-GGUF"],
    "embedding-cpu": ["embeddinggemma-300m", "nomic-embed-text-v1.5", "nomic-embed-text"],
}


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------


def get_vram_mib(model_id: str) -> int:
    """Retorna VRAM estimada em MiB para um modelo.

    Usa o tamanho do GGUF + overhead conhecido (MODEL_VRAM).
    """
    entry = MODEL_VRAM.get(model_id)
    if entry is None:
        return 0
    gguf_mib = entry.gguf_bytes / (1024 * 1024)
    return int(gguf_mib + entry.overhead_mib)


def is_cpu_model(model_id: str) -> bool:
    """True se o modelo roda na CPU (não consome VRAM)."""
    return model_id in CPU_ONLY_MODELS


def get_affinity_group(model_id: str) -> str:
    """Retorna o grupo de afinidade de um modelo."""
    entry = MODEL_VRAM.get(model_id)
    return entry.group if entry else ""


# ---------------------------------------------------------------------------
# nvidia-smi — VRAM real
# ---------------------------------------------------------------------------


# Cache TTL para nvidia-smi (subprocess ~50ms é caro se chamado a cada decisão
# de load/unload). TTL curto (3s) evita usar VRAM obsoleta — o lru_cache
# antigo (maxsize=1, sem expiração) congelava a VRAM no primeiro valor do
# processo inteiro, fazendo as decisões usarem dados velhos.
_NVIDIA_SMI_TTL_S = 3.0
_nvidia_smi_cached_at: float = 0.0
_nvidia_smi_cached_output: str | None = None
_nvidia_smi_lock = threading.Lock()


def _nvidia_smi() -> str | None:
    """Executa nvidia-smi e retorna stdout, com cache TTL de 3s."""
    global _nvidia_smi_cached_at, _nvidia_smi_cached_output

    now = time.monotonic()
    with _nvidia_smi_lock:
        if now - _nvidia_smi_cached_at < _NVIDIA_SMI_TTL_S:
            return _nvidia_smi_cached_output

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.free,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.warning("nvidia-smi falhou: %s", e)
        output = None

    with _nvidia_smi_lock:
        _nvidia_smi_cached_at = time.monotonic()
        _nvidia_smi_cached_output = output
    return output


def check_available_vram() -> dict[str, int]:
    """Retorna VRAM atual em MiB via nvidia-smi.

    Returns:
        {"total_mib": N, "free_mib": N, "used_mib": N}
        Valores zero se nvidia-smi não disponível.
    """
    output = _nvidia_smi()
    if not output:
        # Fallback: assume 6 GB
        return {"total_mib": 6144, "free_mib": 3072, "used_mib": 3072}

    try:
        parts = output.split(",")
        total = int(parts[0].strip())
        free = int(parts[1].strip())
        used = int(parts[2].strip()) if len(parts) > 2 else total - free

        return {
            "total_mib": total,
            "free_mib": free,
            "used_mib": used,
        }
    except (ValueError, IndexError) as e:
        logger.warning("Parse nvidia-smi falhou: %s", e)
        return {"total_mib": 6144, "free_mib": 3072, "used_mib": 3072}


VRAM_BUDGET_MIB = 6 * 1024  # 6144 MiB (6 GB)


def wait_for_vram(needed_mib: int, timeout: float = 30.0, interval: float = 1.0) -> bool:
    """Espera até que a VRAM livre seja >= needed_mib ou timeout."""
    start = time.time()
    while time.time() - start < timeout:
        vram = check_available_vram()
        if vram["free_mib"] >= needed_mib:
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Integração opcional com models_config (quando disponível)
# ---------------------------------------------------------------------------


def build_vram_registry_from_yaml() -> dict[str, ModelVRAM]:
    """Tenta ler as YAMLs reais e construir o registry dinamicamente.

    Retorna dict mesclado: valores das YAMLs substituem MODEL_VRAM hardcoded.
    """
    try:
        from src import models_config as mc

        configs = mc.scan_all_model_configs()
        registry: dict[str, ModelVRAM] = {}

        for name, cfg in configs.items():
            if cfg.disabled or cfg.gguf_bytes == 0:
                continue

            # Modelos CPU não consomem VRAM
            if cfg.backend == mc.BackendType.CPU:
                registry[name] = ModelVRAM(cfg.gguf_bytes, 0, "cpu")
                continue

            if cfg.is_cloud_proxy or cfg.backend in (
                mc.BackendType.LIQUID_AUDIO,
                mc.BackendType.QWEN3_TTS,
                mc.BackendType.UNKNOWN,
            ):
                registry[name] = ModelVRAM(cfg.gguf_bytes, 0, cfg.backend.value)
                continue

            # GPU models: overhead = estimativa - tamanho_gguf
            overhead = max(cfg.vram_estimate_mib - cfg.gguf_mib, 200)
            group = cfg.affinity_group or ""

            registry[name] = ModelVRAM(cfg.gguf_bytes, overhead, group)

        return registry
    except ImportError:
        logger.debug("models_config não disponível, usando fallback hardcoded")
        return dict(MODEL_VRAM)
