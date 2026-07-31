#!/usr/bin/env python3
"""Benchmark comparativo: vLLM vs LocalAI.

Mede throughput (tok/s), latência (ms), e tempo de first-token
para o mesmo modelo GGUF servido por cada engine.

Uso:
    # LocalAI + vLLM rodando, compara ambos
    ./scripts/benchmark_vllm_vs_localai.py --model gemma-4-e2b

    # Apenas um engine
    ./scripts/benchmark_vllm_vs_localai.py --model llama-3.2-3b --only localai
    ./scripts/benchmark_vllm_vs_localai.py --model qwen2.5-1.5b --only vllm

    # JSON output para análise posterior
    ./scripts/benchmark_vllm_vs_localai.py --model gemma-4-e2b --json results.json

    # Lista modelos disponíveis
    ./scripts/benchmark_vllm_vs_localai.py --list-models
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import httpx

# Permite importar do src/ mesmo rodando como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    LOCALAI_BASE_URL,
    LOCAL_VLLM_BASE_URL,
    LOCAL_VLLM_FORK_DIR,
    LOCAL_VLLM_MODEL_MAP,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Dados
# ------------------------------------------------------------------

PROMPTS = [
    "Explique o que são emendas Pix em 3 parágrafos.",
    "Resuma a situação fiscal do estado de Alagoas com base nos dados disponíveis.",
    "Liste 5 indicadores socioeconômicos importantes para análise de municípios.",
    "O que é a Lei Complementar nº 101/2000 e qual sua importância?",
    "Descreva o fluxo de uma transferência especial da União para os municípios.",
    "Quais são as principais diferenças entre emendas individuais e de bancada?",
    "Analise o impacto das transferências especiais no desenvolvimento regional.",
    "Como funciona o sistema de convênios do governo federal?",
    "Explique o papel do SICONFI no controle fiscal dos municípios.",
    "O que é o TSE e como seus dados podem ser usados para análise política?",
]

SYSTEM_PROMPT = "Você é um analista de dados governamentais brasileiros. Responda de forma técnica e objetiva."


# ------------------------------------------------------------------
# Benchmark
# ------------------------------------------------------------------


@dataclass
class BenchResult:
    engine: str
    model: str
    prompt_idx: int
    prompt_len_chars: int
    response_len_chars: int
    response_len_tokens: int  # estimado (chars / 4)
    latency_total_ms: float
    latency_first_token_ms: float
    throughput_tok_s: float
    error: str | None = None


@dataclass
class BenchSummary:
    engine: str
    model: str
    n_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_throughput_tok_s: float
    avg_first_token_ms: float
    total_tokens: int
    total_time_s: float
    errors: int
    results: list[BenchResult] = field(default_factory=list)

    def table(self) -> str:
        """Formata resultado como tabela."""
        rows = [
            f" Engine:          {self.engine}",
            f" Modelo:          {self.model}",
            f" Requisições:     {self.n_requests}",
            f" Erros:           {self.errors}",
            f" Latência média:  {self.avg_latency_ms:.0f} ms",
            f" Latência P50:    {self.p50_latency_ms:.0f} ms",
            f" Latência P95:    {self.p95_latency_ms:.0f} ms",
            f" Latência P99:    {self.p99_latency_ms:.0f} ms",
            f" First-token:     {self.avg_first_token_ms:.0f} ms",
            f" Throughput:      {self.avg_throughput_tok_s:.1f} tok/s",
            f" Total tokens:    {self.total_tokens}",
            f" Tempo total:     {self.total_time_s:.1f}s",
        ]
        return "\n".join(rows)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def run_benchmark(
    engine: str,
    base_url: str,
    model: str,
    prompts: list[str],
    system: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.1,
    n_warmup: int = 2,
) -> BenchSummary:
    """Executa benchmark contra um engine."""
    logger.info("Benchmark %s @ %s (modelo=%s, %d prompts)", engine, base_url, model, len(prompts))

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    results: list[BenchResult] = []

    # Warmup
    for i in range(n_warmup):
        try:
            messages = [{"role": "user", "content": "Teste de warmup."}]
            with httpx.Client(timeout=120) as client:
                client.post(
                    url,
                    json={"model": model, "messages": messages, "max_tokens": 16, "temperature": 0},
                )
        except Exception:
            pass

    # Benchmark
    for idx, prompt in enumerate(prompts):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        start = time.monotonic()
        first_token = None
        response_chars: list[str] = []

        try:
            with httpx.Client(timeout=300) as client:
                with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                if first_token is None:
                                    first_token = time.monotonic()
                                response_chars.append(delta["content"])
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

            elapsed = time.monotonic() - start
            response_text = "".join(response_chars)
            tok_count = estimate_tokens(response_text)
            first_token_latency = (first_token - start) * 1000 if first_token else elapsed * 1000

            results.append(
                BenchResult(
                    engine=engine,
                    model=model,
                    prompt_idx=idx,
                    prompt_len_chars=len(prompt),
                    response_len_chars=len(response_text),
                    response_len_tokens=tok_count,
                    latency_total_ms=elapsed * 1000,
                    latency_first_token_ms=first_token_latency,
                    throughput_tok_s=tok_count / elapsed if elapsed > 0 else 0,
                )
            )
        except Exception as exc:
            logger.warning("Prompt %d falhou: %s", idx, exc)
            results.append(
                BenchResult(
                    engine=engine,
                    model=model,
                    prompt_idx=idx,
                    prompt_len_chars=len(prompt),
                    response_len_chars=0,
                    response_len_tokens=0,
                    latency_total_ms=0,
                    latency_first_token_ms=0,
                    throughput_tok_s=0,
                    error=str(exc),
                )
            )

    # Sumarizar
    ok_results = [r for r in results if r.error is None]
    latencies = sorted(r.latency_total_ms for r in ok_results)
    first_tokens = sorted(r.latency_first_token_ms for r in ok_results)
    throughputs = sorted(r.throughput_tok_s for r in ok_results)
    total_tokens = sum(r.response_len_tokens for r in ok_results)
    total_time = sum(r.latency_total_ms for r in ok_results) / 1000

    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0.0
        idx = max(0, min(len(data) - 1, int(len(data) * p / 100)))
        return data[idx]

    return BenchSummary(
        engine=engine,
        model=model,
        n_requests=len(ok_results),
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        p99_latency_ms=percentile(latencies, 99),
        avg_throughput_tok_s=sum(throughputs) / len(throughputs) if throughputs else 0,
        avg_first_token_ms=sum(first_tokens) / len(first_tokens) if first_tokens else 0,
        total_tokens=total_tokens,
        total_time_s=total_time,
        errors=len(results) - len(ok_results),
        results=results,
    )


def check_engine(base_url: str, name: str) -> bool:
    """Verifica se um engine está rodando."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/v1/models", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def list_models() -> None:
    """Lista modelos configurados para comparação."""
    print("Modelos no LOCAL_VLLM_MODEL_MAP:\n")
    for name, cfg in LOCAL_VLLM_MODEL_MAP.items():
        path = Path(cfg["gguf_path"])
        status = "✓" if path.is_file() else "✗"
        size = path.stat().st_size if path.is_file() else 0
        size_str = f"{size / 1024**3:.1f}GB" if size else "N/E"
        print(f"  {status} {name}")
        print(f"       path: {cfg['gguf_path']}")
        print(f"       tokenizer: {cfg['tokenizer_id']}")
        print(f"       size: {size_str}")
        print()
    sys.exit(0)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark vLLM vs LocalAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exemplos:
              %(prog)s --model gemma-4-e2b
              %(prog)s --model llama-3.2-3b --only vllm
              %(prog)s --model qwen2.5-1.5b --json result.json
              %(prog)s --list-models
        """),
    )
    parser.add_argument("--model", default="llama-3.2-3b", help="Nome do modelo (default: llama-3.2-3b)")
    parser.add_argument("--only", choices=["localai", "vllm"], help="Testar apenas um engine")
    parser.add_argument("--prompts", type=int, default=10, help="Número de prompts (default: 10)")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max tokens por resposta")
    parser.add_argument("--warmup", type=int, default=2, help="Requisições de warmup")
    parser.add_argument("--json", help="Salvar resultados em arquivo JSON")
    parser.add_argument("--list-models", action="store_true", help="Listar modelos disponíveis")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log detalhado")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.list_models:
        list_models()

    model_name = args.model

    # Resolve o nome do modelo pro vLLM (se tiver mapa) ou usa direto
    vllm_model = model_name
    localai_model = model_name
    if model_name in LOCAL_VLLM_MODEL_MAP:
        vllm_model = Path(LOCAL_VLLM_MODEL_MAP[model_name]["gguf_path"]).stem

    prompts = PROMPTS[: args.prompts]

    summaries: list[BenchSummary] = []

    # --- LocalAI ---
    if args.only in (None, "localai"):
        localai_url = LOCALAI_BASE_URL
        if check_engine(localai_url, "LocalAI"):
            print(f"\n{'='*60}")
            print(f"  LocalAI encontrado em {localai_url}")
            print(f"{'='*60}")
            s = run_benchmark(
                engine="localai",
                base_url=localai_url,
                model=localai_model,
                prompts=prompts,
                system=SYSTEM_PROMPT,
                max_tokens=args.max_tokens,
                n_warmup=args.warmup,
            )
            summaries.append(s)
            print(f"\n{s.table()}\n")
        else:
            print(f"\n  LocalAI não está rodando em {localai_url} (pulando)\n")

    # --- vLLM ---
    if args.only in (None, "vllm"):
        vllm_url = LOCAL_VLLM_BASE_URL
        if check_engine(vllm_url, "vLLM"):
            print(f"\n{'='*60}")
            print(f"  vLLM encontrado em {vllm_url}")
            print(f"{'='*60}")
            s = run_benchmark(
                engine="vllm",
                base_url=vllm_url,
                model=vllm_model,
                prompts=prompts,
                system=SYSTEM_PROMPT,
                max_tokens=args.max_tokens,
                n_warmup=args.warmup,
            )
            summaries.append(s)
            print(f"\n{s.table()}\n")
        else:
            print(f"\n  vLLM não está rodando em {vllm_url} (pulando)\n")

    # --- Comparação ---
    if len(summaries) == 2:
        s1, s2 = summaries
        ratio_lat = s2.avg_latency_ms / s1.avg_latency_ms if s1.avg_latency_ms > 0 else 0
        ratio_tput = s2.avg_throughput_tok_s / s1.avg_throughput_tok_s if s1.avg_throughput_tok_s > 0 else 0
        faster_lat = "vLLM" if ratio_lat < 1 else "LocalAI"
        faster_tput = "vLLM" if ratio_tput > 1 else "LocalAI"

        print(f"\n{'='*60}")
        print(f"  COMPARAÇÃO: LocalAI vs vLLM")
        print(f"{'='*60}")
        print(f"  Latência:     {faster_lat} é {max(ratio_lat, 1/ratio_lat):.1f}x mais rápido")
        print(f"  Throughput:   {faster_tput} é {max(ratio_tput, 1/ratio_tput):.1f}x maior")
        print(f"  First-token:")
        print(f"    LocalAI:    {s1.avg_first_token_ms:.0f} ms")
        print(f"    vLLM:       {s2.avg_first_token_ms:.0f} ms")
        print(f"  Throughput médio:")
        print(f"    LocalAI:    {s1.avg_throughput_tok_s:.1f} tok/s")
        print(f"    vLLM:       {s2.avg_throughput_tok_s:.1f} tok/s")
        print()

    elif len(summaries) == 1:
        print(f"\nApenas {summaries[0].engine} estava rodando.")
        print("Para comparar, inicie ambos os engines e rode novamente.\n")

    # --- JSON ---
    if args.json:
        output = {
            "model": model_name,
            "prompts_count": len(prompts),
            "max_tokens": args.max_tokens,
            "engines": [asdict(s) for s in summaries],
        }
        path = Path(args.json)
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str))
        print(f"Resultados salvos em {path.resolve()}")

    # Exit code: erro se nenhum engine rodou
    if not summaries:
        sys.exit(1)


if __name__ == "__main__":
    main()
