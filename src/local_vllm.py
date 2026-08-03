"""Gerenciamento de servidor vLLM local — start, stop, health, benchmark.

Uso:
    from src.local_vllm import LocalVLLM

    vllm = LocalVLLM()
    vllm.start("llama-3.2-3b")       # sobe server em background
    vllm.wait_until_ready()           # aguarda health check
    resp = vllm.chat("Olá!")          # OpenAI-compatível
    vllm.stop()                       # derruba server
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from config.settings import (
    LOCAL_VLLM_BASE_URL,
    LOCAL_VLLM_FORK_DIR,
    LOCAL_VLLM_GPU_MEM_UTIL,
    LOCAL_VLLM_MAX_MODEL_LEN,
    LOCAL_VLLM_MODEL_MAP,
    LOCAL_VLLM_MODELS_DIR,
    LOCAL_VLLM_PORT,
    LOCAL_VLLM_TIMEOUT,
)


class ModelFormat(Enum):
    """Formato do modelo — GGUF nativo ou HuggingFace."""

    GGUF = "gguf"
    HF = "hf"


@dataclass
class ModelInfo:
    """Informações do modelo resolvido para passar ao vLLM."""

    path: str  # path local .gguf ou HF model ID
    format: ModelFormat
    tokenizer: str = "auto"
    quantization: str | None = None  # ex: "bitsandbytes" para BNB 4bit


logger = logging.getLogger(__name__)


@dataclass
class VLLMInstance:
    """Estado do processo vLLM server."""

    model_name: str
    process: subprocess.Popen | None = None
    base_url: str = LOCAL_VLLM_BASE_URL
    pid: int | None = None
    ready: bool = False
    start_time: float = 0.0


class LocalVLLM:
    """Gerencia ciclo de vida do servidor vLLM local.

    Permite iniciar/parar servidores vLLM, verificar saúde,
    e fazer inferência via API compatível OpenAI.

    Exemplos:
        # Gerenciamento manual
        vllm = LocalVLLM()
        vllm.start("llama-3.2-3b")
        print(vllm.chat("Qual é a capital do Brasil?"))

        # Context manager
        with LocalVLLM() as vllm:
            vllm.start("gemma-4-e2b")
            print(vllm.chat("Explique PagedAttention", max_tokens=256))

        # Apenas cliente (server já rodando)
        client = LocalVLLM(manage_process=False)
        print(client.chat("Olá"))
    """

    def __init__(
        self,
        base_url: str | None = None,
        manage_process: bool = True,
        fork_dir: str | None = None,
    ):
        self.base_url = (base_url or LOCAL_VLLM_BASE_URL).rstrip("/")
        self.manage_process = manage_process
        self.fork_dir = Path(fork_dir or LOCAL_VLLM_FORK_DIR)
        self._instance: VLLMInstance | None = None
        self._client = httpx.Client(timeout=LOCAL_VLLM_TIMEOUT)

    # ------------------------------------------------------------------
    # Cycle: start / stop / restart
    # ------------------------------------------------------------------

    def start(
        self,
        model_name: str,
        *,
        port: int | None = None,
        gpu_mem: float | None = None,
        max_len: int | None = None,
        wait: bool = True,
        wait_timeout: float = 120.0,
    ) -> VLLMInstance:
        """Inicia servidor vLLM com o modelo especificado.

        Args:
            model_name: Nome lógico do modelo (ex: "llama-3.2-3b")
                       ou path direto para arquivo .gguf
            port: Porta HTTP (default: LOCAL_VLLM_PORT)
            gpu_mem: Fração da VRAM (0.0-1.0, default: 0.88)
            max_len: Máximo de tokens no contexto
            wait: Se True, aguarda servidor ficar pronto
            wait_timeout: Timeout para aguardar pronto

        Returns:
            VLLMInstance com estado do servidor
        """
        if self._instance and self._instance.ready:
            logger.warning("vLLM já está rodando. Use stop() primeiro.")
            return self._instance

        model_info = self._resolve_model(model_name)
        port = port or LOCAL_VLLM_PORT
        gpu_mem = gpu_mem or LOCAL_VLLM_GPU_MEM_UTIL
        max_len = max_len or LOCAL_VLLM_MAX_MODEL_LEN

        if model_info.format == ModelFormat.GGUF:
            served_name = Path(model_info.path).stem
        else:
            served_name = model_info.path.split("/")[-1]

        logger.info(
            "Iniciando vLLM: modelo=%s formato=%s porta=%d gpu_mem=%.2f",
            model_info.path,
            model_info.format.value,
            port,
            gpu_mem,
        )

        # Verifica se a porta já está ocupada
        if self._check_port_in_use(port):
            raise RuntimeError(
                f"Porta {port} já está em uso. " "Pare o processo ou configure LOCAL_VLLM_PORT."
            )

        if not self.manage_process:
            raise RuntimeError("manage_process=False mas servidor não está rodando.")

        cmd = [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            model_info.path,
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--gpu-memory-utilization",
            str(gpu_mem),
            "--max-model-len",
            str(max_len),
            "--served-model-name",
            served_name,
            "--api-key",
            "not-set",
            "--trust-remote-code",
        ]

        # Flags específicas por formato
        if model_info.format == ModelFormat.GGUF:
            cmd += ["--tokenizer", model_info.tokenizer]
        elif model_info.quantization:
            cmd += ["--load-format", model_info.quantization]

        # VRAM-saving: enforce_eager se GPU tiver pouca memória
        if gpu_mem <= 0.6:
            cmd += ["--enforce-eager", "--max-num-seqs", "4"]
        else:
            cmd += ["--enable-prefix-caching"]

        # Redireciona stdout/stderr para log
        log_path = self.fork_dir / "vllm_server.log"
        log_file = open(log_path, "a")  # noqa: SIM115

        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

        self._instance = VLLMInstance(
            model_name=model_name,
            process=process,
            base_url=f"http://localhost:{port}",
            pid=process.pid,
            start_time=time.monotonic(),
        )

        if wait:
            self.wait_until_ready(timeout=wait_timeout)

        return self._instance

    def stop(self) -> None:
        """Para o servidor vLLM."""
        if not self._instance or not self._instance.process:
            logger.debug("Nenhum servidor vLLM rodando para parar.")
            return

        proc = self._instance.process
        logger.info("Parando vLLM (PID %d)...", proc.pid)

        # Tenta SIGTERM primeiro, depois SIGKILL
        try:
            os.kill(proc.pid, signal.SIGTERM)
            proc.wait(timeout=15)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                pass

        self._instance.ready = False
        self._instance.process = None
        logger.info("vLLM parado.")

    def restart(
        self,
        model_name: str | None = None,
        **kwargs,
    ) -> VLLMInstance:
        """Reinicia servidor vLLM."""
        self.stop()
        model = model_name or (self._instance.model_name if self._instance else None)
        if not model:
            raise ValueError("Nenhum modelo especificado para restart.")
        return self.start(model, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
        self._client.close()

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------

    def wait_until_ready(self, timeout: float = 120.0, interval: float = 2.0) -> bool:
        """Aguarda o servidor vLLM ficar pronto (health check)."""
        if not self._instance:
            return False

        url = f"{self._instance.base_url}/v1/models"
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            try:
                resp = self._client.get(url, timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        elapsed = time.monotonic() - self._instance.start_time
                        self._instance.ready = True
                        models_list = [m["id"] for m in models]
                        logger.info(
                            "vLLM pronto em %.1fs. Modelos: %s",
                            elapsed,
                            models_list,
                        )
                        return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(interval)

        logger.warning("Timeout (%.0fs) aguardando vLLM ficar pronto.", timeout)
        return False

    def is_ready(self) -> bool:
        """Verifica se servidor está respondendo."""
        if self._instance and self._instance.ready:
            return True
        try:
            resp = self._client.get(f"{self.base_url}/v1/models", timeout=5)
            ready = resp.status_code == 200
            if ready and self._instance:
                self._instance.ready = True
            return ready
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def status(self) -> dict[str, Any]:
        """Relatório de status do servidor vLLM."""
        result: dict[str, Any] = {
            "running": False,
            "ready": False,
            "base_url": self.base_url,
            "model": None,
            "pid": None,
        }

        if self._instance:
            result["running"] = self._instance.process is not None
            result["ready"] = self._instance.ready
            result["model"] = self._instance.model_name
            result["pid"] = self._instance.pid
            if self._instance.start_time:
                elapsed = time.monotonic() - self._instance.start_time
                result["uptime_seconds"] = round(elapsed, 1)

        # Tenta health check ao vivo
        try:
            resp = self._client.get(f"{self.base_url}/v1/models", timeout=5)
            if resp.status_code == 200:
                result["ready"] = True
                result["running"] = True
                models = resp.json().get("data", [])
                result["models_loaded"] = [m["id"] for m in models]
                result["models_count"] = len(models)
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

        result["healthy"] = result.get("ready", False)
        return result

    # ------------------------------------------------------------------
    # Inference (OpenAI-compatible)
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Chat completion via API compatível OpenAI."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or (self._instance.model_name if self._instance else "default"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=LOCAL_VLLM_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def generate(
        self,
        prompts: list[str],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> list[str]:
        """Geração em lote (usa o engine offline, não o server)."""
        # Para batch real offline, usar vllm.LLM direto.
        # Aqui faz chamadas sequenciais via API.
        results = []
        for prompt in prompts:
            results.append(
                self.chat(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            )
        return results

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _resolve_model(self, name: str) -> ModelInfo:
        """Resolve nome lógico → ModelInfo (GGUF path ou HF model ID)."""
        # Se o nome já é um path de arquivo existente
        if Path(name).is_file():
            fmt = ModelFormat.GGUF if name.endswith(".gguf") else ModelFormat.HF
            return ModelInfo(
                path=str(Path(name).resolve()),
                format=fmt,
                tokenizer=os.environ.get("TOKENIZER_ID", "auto"),
            )

        # Busca no mapa de modelos
        if name in LOCAL_VLLM_MODEL_MAP:
            entry = LOCAL_VLLM_MODEL_MAP[name]
            # Prioridade: hf_model_id > gguf_path
            if "hf_model_id" in entry:
                return ModelInfo(
                    path=entry["hf_model_id"],
                    format=ModelFormat.HF,
                    quantization=entry.get("quantization"),
                )
            # Fallback: GGUF
            gguf = entry.get("gguf_path")
            if gguf and Path(gguf).is_file():
                return ModelInfo(
                    path=str(Path(gguf).resolve()),
                    format=ModelFormat.GGUF,
                    tokenizer=entry.get("tokenizer_id", "auto"),
                )
            raise FileNotFoundError(
                f"Modelo '{name}' configurado mas não encontrado:\n"
                f"  hf_model_id={entry.get('hf_model_id')}\n"
                f"  gguf_path={entry.get('gguf_path')}\n"
                "Verifique se o caminho existe ou o HF model ID está correto."
            )

        # Tenta encontrar por substring nos diretório de modelos GGUF
        models_dir = Path(LOCAL_VLLM_MODELS_DIR)
        matches = sorted(models_dir.rglob(f"*{name}*.gguf"))
        if matches:
            return ModelInfo(
                path=str(matches[0]),
                format=ModelFormat.GGUF,
                tokenizer="auto",
            )

        # Tenta interpretar como HF model ID diretamente
        if "/" in name and not name.startswith("/"):
            return ModelInfo(
                path=name,
                format=ModelFormat.HF,
            )

        raise ValueError(
            f"Modelo '{name}' não encontrado.\n"
            f"Modelos configurados: {list(LOCAL_VLLM_MODEL_MAP.keys())}\n"
            "Ou use: path/.gguf, HF model ID (org/model), nome do mapa."
        )

    @staticmethod
    def _check_port_in_use(port: int) -> bool:
        """Verifica se porta está ocupada."""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main():
    """CLI para gerenciar vLLM local."""
    import argparse

    parser = argparse.ArgumentParser(description="Gerencia servidor vLLM local")
    sub = parser.add_subparsers(dest="comando")

    # start
    start_p = sub.add_parser("start", help="Inicia servidor vLLM")
    start_p.add_argument("modelo", help="Nome do modelo ou path .gguf")
    start_p.add_argument("--port", type=int, default=LOCAL_VLLM_PORT)
    start_p.add_argument("--gpu-mem", type=float, default=LOCAL_VLLM_GPU_MEM_UTIL)
    start_p.add_argument("--max-len", type=int, default=LOCAL_VLLM_MAX_MODEL_LEN)
    start_p.add_argument("--no-wait", action="store_true", help="Não aguardar ready")

    # stop
    sub.add_parser("stop", help="Para servidor vLLM")

    # status
    sub.add_parser("status", help="Status do servidor")

    # chat
    chat_p = sub.add_parser("chat", help="Envia mensagem para o servidor")
    chat_p.add_argument("mensagem", help="Texto da mensagem")
    chat_p.add_argument("--model", help="Nome do modelo (opcional)")
    chat_p.add_argument("--system", help="Mensagem de sistema")
    chat_p.add_argument("--max-tokens", type=int, default=512)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    vllm = LocalVLLM()

    if args.comando == "start":
        inst = vllm.start(
            args.modelo,
            port=args.port,
            gpu_mem=args.gpu_mem,
            max_len=args.max_len,
            wait=not args.no_wait,
        )
        print(f"vLLM rodando em {inst.base_url} (PID {inst.pid})")
        if inst.ready:
            print("Pronto para receber requisições.")

    elif args.comando == "stop":
        vllm.stop()
        print("vLLM parado.")

    elif args.comando == "status":
        st = vllm.status()
        print(json.dumps(st, indent=2, default=str))

    elif args.comando == "chat":
        if not vllm.is_ready():
            print("Servidor vLLM não está rodando. Use 'start' primeiro.")
            sys.exit(1)
        resp = vllm.chat(args.mensagem, model=args.model, max_tokens=args.max_tokens)
        print(resp)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
