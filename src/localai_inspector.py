"""
Módulo de Observabilidade e Inspeção do LocalAI.

Fornece diagnósticos completos sobre:
- VRAM real alocada via nvidia-smi
- Processos GPU ativos (PIDs e consumo)
- Modelos carregados no LocalAI (OpenAI API /v1/models)
- Leitura estruturada dos logs de erro dos backends llama-cpp
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

import httpx

from config.settings import LOCALAI_BASE_URL

logger = logging.getLogger(__name__)


def get_gpu_status() -> dict[str, Any]:
    """Retorna dados de VRAM e processos ativos na GPU via nvidia-smi."""
    try:
        # VRAM livre / total
        out_gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        gpu_free, gpu_total, gpu_used = 0, 0, 0
        if out_gpu.returncode == 0 and out_gpu.stdout.strip():
            parts = [int(p.strip()) for p in out_gpu.stdout.strip().split(",")]
            if len(parts) >= 3:
                gpu_free, gpu_total, gpu_used = parts[0], parts[1], parts[2]

        # Processos na GPU
        out_apps = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        processes: list[dict[str, Any]] = []
        if out_apps.returncode == 0 and out_apps.stdout.strip():
            for line in out_apps.stdout.strip().splitlines():
                p_parts = [p.strip() for p in line.split(",")]
                if len(p_parts) >= 3:
                    try:
                        processes.append(
                            {
                                "pid": int(p_parts[0]),
                                "name": p_parts[1],
                                "vram_mib": int(p_parts[2]),
                            }
                        )
                    except ValueError:
                        continue

        return {
            "vram_free_mib": gpu_free,
            "vram_total_mib": gpu_total,
            "vram_used_mib": gpu_used,
            "gpu_processes": processes,
        }
    except Exception as exc:
        logger.warning("Falha ao obter status GPU via nvidia-smi: %s", exc)
        return {"error": str(exc), "gpu_processes": []}


def get_container_logs(tail_lines: int = 30) -> list[str]:
    """Lê os últimos logs do backend llama-cpp de dentro do container Docker."""
    container = os.environ.get("LOCALAI_CONTAINER_NAME", "localai-orchestrator")
    try:
        # Encontrar diretório do último processmanager no container
        find_cmd = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                "ls -td /tmp/go-processmanager* 2>/dev/null | head -1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        latest_dir = find_cmd.stdout.strip()
        if not latest_dir:
            return ["Nenhum diretório go-processmanager encontrado no container."]

        # Ler o arquivo stderr desse diretório
        cat_cmd = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "cat",
                f"{latest_dir}/stderr",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if cat_cmd.returncode != 0 or not cat_cmd.stdout:
            return ["Não foi possível ler stderr do backend."]

        lines = cat_cmd.stdout.strip().splitlines()
        return lines[-tail_lines:]
    except Exception as exc:
        return [f"Erro lendo logs do container: {exc}"]


def inspect_health() -> dict[str, Any]:
    """Retorna diagnóstico consolidado do estado do LocalAI e da GPU."""
    gpu = get_gpu_status()
    models_available: list[str] = []
    base_url = LOCALAI_BASE_URL.replace("/v1", "").rstrip("/")

    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            resp = client.get(f"{base_url}/v1/models")
            if resp.status_code == 200:
                models_available = [m["id"] for m in resp.json().get("data", [])]
    except Exception as exc:
        logger.warning("Falha ao consultar /v1/models no LocalAI: %s", exc)

    logs = get_container_logs(tail_lines=15)

    return {
        "localai_url": base_url,
        "models_registered": models_available,
        "gpu": gpu,
        "latest_backend_logs": logs,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(inspect_health(), indent=2, ensure_ascii=False))
