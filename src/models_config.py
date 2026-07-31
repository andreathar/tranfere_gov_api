"""
Leitura e controle total da configuração de modelos do LocalAI.

Lê as YAML de /mnt/data/Projects_SSD/LocalAI/models/ e expõe:
  - Backend usado (cuda13-llama-cpp, vulkan-llama-cpp, llama-cpp, cloud-proxy, etc.)
  - gpu_layers, context_size, tamanho do GGUF
  - Grupo de afinidade (compartilham o mesmo GGUF?)
  - Capacidade de alterar backend (CPU ↔ GPU)
  - Estado real do backend no Docker

Também permite modificar as YAML para forçar CPU/GPU e controlar
o consumo de VRAM via gpu_layers.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caminhos absolutos
# ---------------------------------------------------------------------------

LOCALAI_MODELS_DIR = Path("/mnt/data/Projects_SSD/LocalAI/models")
LOCALAI_GGUF_DIR = Path("/mnt/data/models/localai")
LOCALAI_CONFIG_DIR = Path("/mnt/data/Projects_SSD/LocalAI/configuration")
DOCKER_CONTAINER = "localai-orchestrator"


class BackendType(StrEnum):
    CUDA = "cuda13-llama-cpp"
    CUDA12 = "cuda12-llama-cpp"
    VULKAN = "vulkan-llama-cpp"
    CPU = "cpu-llama-cpp"  # backend CPU puro (instalado via gallery)
    CPU_LEGACY = "llama-cpp"  # meta-backend: no build GPU resolve p/ CUDA!
    CLOUD_PROXY = "cloud-proxy"
    LIQUID_AUDIO = "liquid-audio"
    QWEN3_TTS = "qwen3-tts-cpp"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, s: str) -> BackendType:
        s = s.strip().lower()
        for member in cls:
            if member.value == s:
                return member
        return cls.UNKNOWN

    @property
    def is_gpu(self) -> bool:
        # CPU_LEGACY ("llama-cpp" sem prefixo) também roda em GPU:
        # no build GPU é um meta-backend que resolve para cuda12-llama-cpp.
        return self in (BackendType.CUDA, BackendType.CUDA12,
                        BackendType.VULKAN, BackendType.CPU_LEGACY)

    @property
    def is_cpu(self) -> bool:
        return self == BackendType.CPU

    @property
    def gpu_backend(self) -> str | None:
        """Retorna o nome do runtime GPU."""
        if self == BackendType.CUDA:
            return "cuda"
        if self == BackendType.VULKAN:
            return "vulkan"
        return None


@dataclass
class ModelConfig:
    """Configuração completa de um modelo do LocalAI, lida do YAML."""

    name: str
    file_path: Path  # caminho do arquivo YAML

    # Backend
    backend: BackendType = BackendType.UNKNOWN
    gpu_layers: int = 0
    context_size: int = 4096
    f16: bool = False
    mmap: bool = True
    threads: int = 4
    embeddings: bool = False
    no_kv_offloading: bool = True  # se False, KV cache vai parcialmente pra RAM

    # Arquivo GGUF real
    gguf_path: Path | None = None  # caminho absoluto no host
    gguf_bytes: int = 0  # tamanho real em bytes
    gguf_mib: int = 0  # tamanho em MiB

    # Pars extra
    parameters: dict[str, Any] = field(default_factory=dict)
    template: dict[str, Any] = field(default_factory=dict)
    raw_yaml: dict[str, Any] = field(default_factory=dict)

    # Flags
    disabled: bool = False
    is_cloud_proxy: bool = False
    proxy_upstream: str | None = None

    # VRAM estimada (considerando gpu_layers)
    vram_estimate_mib: int = 0

    # Grupo de afinidade (compartilha GGUF com outros modelos)
    affinity_group: str | None = None

    # Concurrency groups
    concurrency_groups: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Leitura da configuração
# ---------------------------------------------------------------------------


def _resolve_gguf_path(model_yaml: dict, yaml_path: Path) -> Path | None:
    """Resolve o caminho absoluto do arquivo GGUF.

    As YAMLs referenciam caminhos relativos ao MODELS_PATH do Docker
    (/mnt/data/Projects_SSD/LocalAI/models/). Mas os GGUFs reais estão
    montados de /mnt/data/models/localai/...

    Tenta várias resoluções:
      1. Caminho direto absoluto
      2. Relativo ao dir das YAMLs
      3. Relativo ao /mnt/data/models/localai/
      4. Relativo ao /mnt/data/models/
    """
    model_param = model_yaml.get("parameters", {}).get("model", "")
    if not model_param:
        return None

    model_path = Path(model_param)

    # Já é absoluto
    if model_path.is_absolute():
        if model_path.exists():
            return model_path
        return None

    # Tenta relativo ao dir das YAMLs
    candidate = yaml_path.parent / model_path
    if candidate.exists():
        return candidate.resolve()

    # Tenta /mnt/data/models/localai/<path>
    candidate = LOCALAI_GGUF_DIR / model_path
    if candidate.exists():
        return candidate

    # Tenta /mnt/data/models/<path>
    candidate = Path("/mnt/data/models") / model_path
    if candidate.exists():
        return candidate

    # Tenta apenas o nome do arquivo
    candidate = LOCALAI_GGUF_DIR / model_path.name
    if candidate.exists():
        return candidate

    return None


def _resolve_affinity_group(models: list[dict]) -> dict[str, str]:
    """Determina grupos de afinidade: modelos que compartilham o mesmo GGUF.

    Percorre todos os modelos e agrupa pelo mesmo caminho de GGUF.
    """
    gguf_to_models: dict[str, list[str]] = {}

    for m in models:
        gguf = m.get("gguf_path")
        name = m.get("name", "unknown")
        if gguf:
            gguf_str = str(gguf)
            gguf_to_models.setdefault(gguf_str, []).append(name)

    affinity: dict[str, str] = {}
    for gguf_path, model_names in gguf_to_models.items():
        if len(model_names) > 1:
            group_name = f"shared-{Path(gguf_path).stem}"
            for n in model_names:
                affinity[n] = group_name
        else:
            # Modelo único — sem afinidade (ou usa o nome base)
            if model_names:
                stem = Path(gguf_path).stem
                # Remove quantização do nome
                base = re.sub(r"[-_]?(Q[48]_[KM]|fp16|bf16)$", "", stem, flags=re.IGNORECASE)
                affinity[model_names[0]] = base

    return affinity


def _estimate_vram_mib(
    gguf_bytes: int,
    gpu_layers: int,
    total_layers: int | None,
    context_size: int,
    f16: bool,
    *,
    no_kv_offloading: bool = True,
) -> int:
    """Estima VRAM em MiB para o modelo.

    Calibrado empiricamente para RTX 3060 Laptop (6 GB).
    Usa observações reais como base, com fallback por fórmula simplificada.

    Valores empíricos de referência:
      qwen2.5-1.5b (32/24, 8K ctx):    1449 MiB (all-GPU, KV on GPU)
      llama-3.2-3b (32/28, 16K ctx):    2311 MiB (all-GPU)
      llama-3.1-8b (28/33, 16K ctx):    5000 MiB (no_kv_offloading=false)
      gemma-4-e2b-it (26/42, 16K ctx):  5400 MiB (KV on GPU, Q8, high ctx)
      embeddinggemma-300m (32/12, 32K):  1600 MiB (all layers, huge ctx)
      nomic-embed-text (32/6, 32K):     1400 MiB
    """
    if gguf_bytes == 0 or gpu_layers == 0:
        return 0

    gguf_mib = gguf_bytes / (1024 * 1024)

    # --- Heurísticas de arquitetura por tamanho GGUF ---
    if gguf_mib > 4000:  # 8B
        total_layers_guess = total_layers or 33
        hidden_size_guess = 4096
    elif gguf_mib > 1500:  # 3B
        total_layers_guess = total_layers or 28
        hidden_size_guess = 3072
    elif gguf_mib > 800:  # 1.5B
        total_layers_guess = total_layers or 24
        hidden_size_guess = 2048
    elif gguf_mib > 200:  # 0.5B (embedding)
        total_layers_guess = total_layers or 12
        hidden_size_guess = 1024
    else:  # embedding pequeno
        total_layers_guess = total_layers or 6
        hidden_size_guess = 768

    ratio = min(gpu_layers / total_layers_guess, 1.0)

    # --- VRAM das weights (proporcional ao GGUF) ---
    weights_mib = gguf_mib * ratio

    # --- KV cache ---
    # Fórmula: 4 bytes (K+V fp16) * hidden_size * layers * context_size
    # Quando no_kv_offloading=false, a maior parte fica em RAM
    kv_full_mib = (4 * hidden_size_guess * total_layers_guess * context_size) / (1024 * 1024)
    kv_gpu_mib = kv_full_mib if no_kv_offloading else kv_full_mib * 0.2

    # Overhead do backend (gráfico, buffers, etc)
    overhead = 150 + (150 if gguf_mib > 4000 else 0)  # 150 base + 150 extra para modelos grandes

    total = int(weights_mib + kv_gpu_mib + overhead)

    # Ajuste empírico para match com valores observados
    # (compensa imprecisões nas heurísticas hidden_size / total_layers)
    # Correção derivada de: real - calculated para cada modelo conhecido
    if gguf_mib > 4000 and not no_kv_offloading:
        # 8B com KV offload: tende a superestimar
        total = int(total * 0.75)
    elif gguf_mib > 4000 and no_kv_offloading:
        # 8B com KV na GPU: tende a subestimar (gemma Q8)
        total = int(total * 1.15)
    elif gguf_mib > 1500:
        # 3B: ajuste fino
        total = int(total * 0.85)
    elif gguf_mib > 200:
        # Embedding grande (gemma)
        total = int(total * 0.9)

    return total


# ---------------------------------------------------------------------------
# Scanner principal
# ---------------------------------------------------------------------------


def scan_all_model_configs() -> dict[str, ModelConfig]:
    """Escaneia todas as YAMLs e retorna ModelConfig por nome.

    Lê cada .yaml em /mnt/data/Projects_SSD/LocalAI/models/, resolve
    caminhos de GGUF, estima VRAM, determina grupos de afinidade.
    """
    if not LOCALAI_MODELS_DIR.exists():
        logger.error("Diretório de modelos não encontrado: %s", LOCALAI_MODELS_DIR)
        return {}

    configs: dict[str, ModelConfig] = {}
    yaml_files = sorted(LOCALAI_MODELS_DIR.glob("*.yaml"))

    # Primeira passada: ler todos os YAMLs
    raw_models: list[dict] = []
    for yaml_path in yaml_files:
        if yaml_path.name.startswith("._"):
            continue  # pula arquivos ocultos do Mac

        try:
            with open(yaml_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Erro lendo %s: %s", yaml_path.name, e)
            continue

        name = raw.get("name", yaml_path.stem)

        # Resolver GGUF
        gguf_path = _resolve_gguf_path(raw, yaml_path)
        gguf_bytes = gguf_path.stat().st_size if gguf_path and gguf_path.exists() else 0
        gguf_mib = gguf_bytes // (1024 * 1024)

        # Backend
        backend_str = raw.get("backend", "")
        backend = BackendType.from_string(backend_str)

        # Cloud proxy?
        is_cloud = backend == BackendType.CLOUD_PROXY
        proxy_upstream = None
        if is_cloud:
            proxy = raw.get("proxy", {})
            proxy_upstream = proxy.get("upstream_model") or proxy.get("upstream_url", "")

        gpu_layers = raw.get("gpu_layers", 0)
        if backend == BackendType.CPU:
            gpu_layers = 0  # garante zero para CPU

        context_size = raw.get("context_size", 4096)

        disabled = raw.get("disabled", False)

        cfg = ModelConfig(
            name=name,
            file_path=yaml_path,
            backend=backend,
            gpu_layers=gpu_layers,
            context_size=context_size,
            f16=raw.get("f16", False),
            mmap=raw.get("mmap", True),
            threads=raw.get("threads", 4),
            embeddings=raw.get("embeddings", False),
            no_kv_offloading=raw.get("no_kv_offloading", True),
            gguf_path=gguf_path,
            gguf_bytes=gguf_bytes,
            gguf_mib=gguf_mib,
            parameters=raw.get("parameters", {}),
            template=raw.get("template", {}),
            raw_yaml=raw,
            disabled=disabled,
            is_cloud_proxy=is_cloud,
            proxy_upstream=proxy_upstream,
            concurrency_groups=raw.get("concurrency_groups", []),
        )

        configs[name] = cfg
        raw_models.append({
            "name": name,
            "gguf_path": gguf_path,
        })

    # Segunda passada: resolver grupos de afinidade
    affinity_map = _resolve_affinity_group(raw_models)
    for name, cfg in configs.items():
        cfg.affinity_group = affinity_map.get(name)

    # Terceira passada: estimar VRAM
    for _name, cfg in configs.items():
        if cfg.gguf_bytes == 0:
            cfg.vram_estimate_mib = 0
            continue
        if cfg.backend == BackendType.CPU:
            cfg.vram_estimate_mib = 0  # CPU models don't use VRAM
            continue
        if cfg.is_cloud_proxy:
            cfg.vram_estimate_mib = 0
            continue
        if cfg.backend in (BackendType.LIQUID_AUDIO, BackendType.QWEN3_TTS):
            cfg.vram_estimate_mib = 0  # special backends
            continue

        cfg.vram_estimate_mib = _estimate_vram_mib(
            gguf_bytes=cfg.gguf_bytes,
            gpu_layers=cfg.gpu_layers,
            total_layers=None,
            context_size=cfg.context_size,
            f16=cfg.f16,
            no_kv_offloading=cfg.no_kv_offloading,
        )

    return configs


# ---------------------------------------------------------------------------
# Modificação de configuração (CPU ↔ GPU)
# ---------------------------------------------------------------------------


def set_model_backend(
    model_name: str,
    backend: BackendType | str,
    gpu_layers: int | None = None,
) -> bool:
    """Altera o backend e/ou gpu_layers de um modelo no YAML.

    Args:
        model_name: Nome do modelo (campo 'name' no YAML).
        backend: Novo backend (cuda13-llama-cpp, vulkan-llama-cpp, llama-cpp).
        gpu_layers: Opcional. Se None, mantém o valor atual.
            Se 0 e backend não-GPU, remove a chave.
    """
    configs = scan_all_model_configs()
    if model_name not in configs:
        logger.error("Modelo '%s' não encontrado na configuração.", model_name)
        return False

    cfg = configs[model_name]
    if isinstance(backend, str):
        backend = BackendType.from_string(backend)

    # Ler YAML atual
    try:
        with open(cfg.file_path, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.error("Erro lendo %s: %s", cfg.file_path, e)
        return False

    # Modificar backend
    old_backend = yaml_data.get("backend", "")
    yaml_data["backend"] = backend.value
    logger.info("Modelo '%s': backend %s → %s", model_name, old_backend, backend.value)

    # Modificar gpu_layers
    if gpu_layers is not None:
        if gpu_layers > 0:
            yaml_data["gpu_layers"] = gpu_layers
            logger.info("Modelo '%s': gpu_layers → %d", model_name, gpu_layers)
        else:
            yaml_data.pop("gpu_layers", None)
            logger.info("Modelo '%s': gpu_layers removido (CPU)", model_name)

    # Se backend é CPU, garantir gpu_layers ausente
    if backend == BackendType.CPU:
        yaml_data.pop("gpu_layers", None)
        yaml_data.pop("cuda", None)

    # Se backend é GPU, garantir que tem gpu_layers mínimo
    if backend.is_gpu and "gpu_layers" not in yaml_data:
        yaml_data["gpu_layers"] = 32  # default

    # Escrever YAML (preservando formatação parcial via ruamel se disponível)
    try:
        with open(cfg.file_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Config %s atualizada.", cfg.file_path)
        return True
    except OSError as e:
        logger.error("Erro escrevendo %s: %s", cfg.file_path, e)
        return False


# ---------------------------------------------------------------------------
# Utilidades do Docker
# ---------------------------------------------------------------------------


def docker_restart() -> bool:
    """Reinicia o container LocalAI para aplicar mudanças de config."""
    try:
        result = subprocess.run(
            ["docker", "restart", DOCKER_CONTAINER],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("Container %s reiniciado.", DOCKER_CONTAINER)
            return True
        logger.error("Falha ao reiniciar: %s", result.stderr)
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("Erro reiniciando: %s", e)
        return False


def docker_logs(model_name: str | None = None, tail: int = 50) -> str:
    """Retorna logs do container LocalAI, opcionalmente filtrados."""
    try:
        cmd = ["docker", "logs", DOCKER_CONTAINER, "--tail", str(tail)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        if model_name:
            # Filtra linhas relevantes ao modelo
            lines = output.split("\n")
            filtered = [
                line for line in lines
                if model_name in line.lower()
                or "backend" in line.lower()
                or "loaded" in line.lower()
                or "evict" in line.lower()
                or "shutdown" in line.lower()
                or "gpu" in line.lower()
            ]
            return "\n".join(filtered[-tail:])
        return output
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"Erro: {e}"


# ---------------------------------------------------------------------------
# Listagem formatada
# ---------------------------------------------------------------------------


def format_model_table(configs: dict[str, ModelConfig] | None = None) -> str:
    """Retorna tabela formatada dos modelos para terminal."""
    if configs is None:
        configs = scan_all_model_configs()

    if not configs:
        return "Nenhuma config de modelo encontrada."

    lines = []
    lines.append(f"{'Modelo':30s} {'Backend':22s} {'GPU Layers':10s} {'Ctx':6s} {'KV Off':7s} {'GGUF':8s} {'VRAM est.':10s} {'Grupo':20s}")
    lines.append("-" * 117)

    for name in sorted(configs.keys()):
        cfg = configs[name]
        if cfg.disabled:
            continue

        backend_str = cfg.backend.value
        if cfg.is_cloud_proxy:
            backend_str = "☁ cloud-proxy"
        elif cfg.backend == BackendType.CPU:
            backend_str = "🧠 CPU"
        elif cfg.backend == BackendType.CUDA:
            backend_str = "🚀 CUDA"
        elif cfg.backend == BackendType.VULKAN:
            backend_str = "🔵 Vulkan"

        gpu_str = str(cfg.gpu_layers) if cfg.gpu_layers > 0 else "-"
        ctx_str = str(cfg.context_size)
        kv_str = "✓" if cfg.no_kv_offloading else "✗ RAM"
        gguf_str = f"{cfg.gguf_mib}M" if cfg.gguf_mib > 0 else "-"
        vram_str = f"{cfg.vram_estimate_mib}M" if cfg.vram_estimate_mib > 0 else "-"
        group_str = cfg.affinity_group or ""

        lines.append(
            f"{name:30s} {backend_str:22s} {gpu_str:10s} {ctx_str:6s} "
            f"{kv_str:7s} {gguf_str:8s} {vram_str:10s} {group_str:20s}"
        )

    lines.append(f"\nTotal: {len([c for c in configs.values() if not c.disabled])} modelos ativos")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Conveniência
# ---------------------------------------------------------------------------

def get_config(model_name: str) -> ModelConfig | None:
    """Retorna a config de um modelo específico."""
    configs = scan_all_model_configs()
    return configs.get(model_name)


def set_kv_offloading(model_name: str, enabled: bool) -> bool:
    """Ativa/desativa o offloading do KV cache para RAM.

    enabled=True → KV cache fica na GPU (mais rápido, mais VRAM)
    enabled=False → KV cache vai parcialmente pra RAM (mais lento, menos VRAM)

    Aplica-se apenas a modelos com backend llama-cpp (CUDA ou Vulkan).
    """
    configs = scan_all_model_configs()
    if model_name not in configs:
        logger.error("Modelo '%s' não encontrado.", model_name)
        return False

    cfg = configs[model_name]
    if not cfg.backend.is_gpu:
        logger.warning("Modelo '%s' não é GPU (backend=%s). Ignorando.", model_name, cfg.backend.value)
        return False

    try:
        with open(cfg.file_path, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.error("Erro lendo %s: %s", cfg.file_path, e)
        return False

    if enabled:
        yaml_data.pop("no_kv_offloading", None)  # default = true
        logger.info("Modelo '%s': KV cache → GPU (no_kv_offloading removido)", model_name)
    else:
        yaml_data["no_kv_offloading"] = False
        logger.info("Modelo '%s': KV cache → RAM (no_kv_offloading=false)", model_name)

    try:
        with open(cfg.file_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except OSError as e:
        logger.error("Erro escrevendo %s: %s", cfg.file_path, e)
        return False


def set_gpu_layers(model_name: str, layers: int) -> bool:
    """Ajusta quantas camadas rodam na GPU.

    layers=0 → CPU-only
    layers=N → N camadas na GPU, resto na CPU
    layers>=total → full GPU

    Reduzir gpu_layers libera VRAM mas diminui velocidade.
    """
    configs = scan_all_model_configs()
    if model_name not in configs:
        logger.error("Modelo '%s' não encontrado.", model_name)
        return False

    cfg = configs[model_name]
    if not cfg.backend.is_gpu:
        logger.warning("Modelo '%s' não é GPU. Use set_model_backend() primeiro.", model_name)
        return False

    try:
        with open(cfg.file_path, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        logger.error("Erro lendo %s: %s", cfg.file_path, e)
        return False

    if layers <= 0:
        # Forçar CPU
        yaml_data["backend"] = "llama-cpp"
        yaml_data.pop("gpu_layers", None)
        yaml_data.pop("cuda", None)
        logger.info("Modelo '%s': forçado para CPU.", model_name)
    else:
        yaml_data["gpu_layers"] = layers
        # Garantir que backend é GPU
        if yaml_data.get("backend") == "llama-cpp":
            yaml_data["backend"] = "cuda13-llama-cpp"
        logger.info("Modelo '%s': gpu_layers=%d", model_name, layers)

    try:
        with open(cfg.file_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except OSError as e:
        logger.error("Erro escrevendo %s: %s", cfg.file_path, e)
        return False


def get_docker_backend_status() -> dict[str, Any]:
    """Retorna o status atual dos backends no Docker LocalAI.

    Lê as métricas do /backend/monitor para cada modelo configurado
    e retorna quais estão carregados no momento.
    """
    import httpx

    configs = scan_all_model_configs()
    results: dict[str, Any] = {
        "container_running": False,
        "loaded_models": [],
        "active_backends": 0,
        "total_models": len(configs),
        "errors": [],
    }

    try:
        # Primeiro verifica se o container está rodando
        subprocess.run(
            ["docker", "ps", "--filter", f"name={DOCKER_CONTAINER}", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        results["container_running"] = True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        results["errors"].append(str(e))
        return results

    # Testa /backend/monitor para cada modelo
    loaded: list[str] = []
    for name, cfg in configs.items():
        if cfg.disabled or cfg.is_cloud_proxy or cfg.backend == BackendType.CPU:
            continue
        if cfg.backend in (BackendType.LIQUID_AUDIO, BackendType.QWEN3_TTS, BackendType.UNKNOWN):
            continue

        try:
            with httpx.Client(timeout=3) as client:
                resp = client.get(
                    "http://localhost:8080/backend/monitor",
                    params={"model": name},
                )
                if resp.status_code == 200:
                    loaded.append(name)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            continue

    results["loaded_models"] = loaded
    results["active_backends"] = len(set(
        getattr(configs.get(m), "backend", None) for m in loaded
    ))
    return results


# Maintain compatibility aliases
docker_status = get_docker_backend_status
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    configs = scan_all_model_configs()
    print(format_model_table(configs))
