import os
import subprocess

import modal

# App Modal para servir o vLLM
app = modal.App("transferegov-vllm")

# Volume persistente para cache do modelo (evita redownload em cold starts)
model_volume = modal.Volume.from_name("llama-cache", create_if_missing=True)
CACHE_PATH = "/root/model_cache"

# Modelo escolhido
MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"

# Configuração de GPU: 2x A100 80GB — Llama 70B FP8 (~70GB) cabe folgado
GPU_CONFIG = "A100-80GB:2"

# Imagem com vLLM + huggingface_hub para download
vllm_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "vllm==0.6.1.post2",
    "transformers==4.45.1",
    "huggingface_hub",
)


@app.function(
    image=vllm_image,
    gpu=GPU_CONFIG,
    volumes={CACHE_PATH: model_volume},
    scaledown_window=10 * 60,  # 10 min após última req (evita cold starts frequentes)
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=1800,  # 30 min para download + load do modelo
)
@modal.concurrent(max_inputs=150)
@modal.web_server(8000, startup_timeout=1800)
def serve():
    """
    Inicializa o servidor FastAPI embutido do vLLM como um subprocesso,
    escutando na porta 8000 (exigida pelo decorator @modal.web_server).
    Usa volume persistente para cache do modelo entre cold starts.
    """
    api_key = os.environ.get("MODAL_VLLM_TOKEN")
    if not api_key:
        raise RuntimeError(
            "MODAL_VLLM_TOKEN não definido. Configure o Secret no Modal "
            "(ex.: modal.Secret.from_name('...')) antes de servir o endpoint."
        )

    # Verifica se o modelo já está em cache (usa marker file pra evitar download parcial)
    model_path = os.path.join(CACHE_PATH, MODEL.replace("/", "--"))
    marker_file = os.path.join(model_path, ".download_complete")
    if not os.path.exists(marker_file):
        print(f"Fazendo download do modelo {MODEL} para {model_path}...")
        os.makedirs(model_path, exist_ok=True)
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=MODEL,
            local_dir=model_path,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        # Cria marker de download completo e persiste no volume
        with open(marker_file, "w") as f:
            f.write("ok")
        model_volume.commit()
        print("Download concluído!")
    else:
        print(f"Modelo {MODEL} encontrado em cache ({model_path})")

    cmd = [
        "python",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model_path,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--tensor-parallel-size",
        "2",
        "--max-model-len",
        "32768",
        "--quantization",
        "fp8",
        "--api-key",
        api_key,
        "--download-dir",
        CACHE_PATH,  # usa cache volume para weights
        "--served-model-name",
        MODEL,  # expõe nome limpo no API (não o path do cache)
        "--guided-decoding-backend",
        "lm-format-enforcer",  # evita outlines (pyairports faltando)
    ]

    print(f"Iniciando vLLM OpenAI Server com o modelo {MODEL} (FP8, 2xA100-80GB)...")
    subprocess.Popen(cmd)
