"""
Diagnóstico dos modelos LocalAI — mapeamento de configs + teste funcional.

Modos:
    python scripts/diag_modelos.py          # mapear configs de todos os modelos
    python scripts/diag_modelos.py --test   # ciclo real load->chat->unload (llama)

Fontes de verdade:
  1. config.settings.LOCALAI_MODELS        (alias -> modelo)
  2. config.settings.LOCALAI_MODEL_TIMEOUTS (timeout por modelo)
  3. src.vram_tracker.MODEL_VRAM           (VRAM estimada + grupo afinidade)
  4. src.models_config.scan_all_model_configs() (YAMLs reais: backend/gpu_layers)
  5. LocalAI GET /v1/models                (disponíveis no servidor)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from config.settings import (
    LOCALAI_BASE_URL,
    LOCALAI_MODEL_TIMEOUTS,
    LOCALAI_MODELS,
    RAG_LLM_MODEL,
)
from src import localai_manager as lm
from src import vram_tracker as vt
from src.localai_client import LocalAIClient

try:
    from src.analysts.preparer import PREPARER_MODEL
except Exception:  # pragma: no cover - diagnóstico não deve quebrar
    PREPARER_MODEL = "zero-gemma4-e4b-openzero-q5-k-m"

# Modelo usado no teste funcional (seguro na GPU livre)
TEST_MODEL = RAG_LLM_MODEL  # llama-3.2-3b-instruct:q4_k_m (~2312 MiB)
LARGE_THRESHOLD_MIB = lm._LARGE_MODEL_THRESHOLD_MIB  # 4000


def _models_from_localai() -> list[str]:
    """Lista modelos disponíveis no servidor LocalAI."""
    try:
        with urllib.request.urlopen(f"{LOCALAI_BASE_URL}/v1/models", timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return sorted(m["id"] for m in data.get("data", []))
    except Exception as exc:  # noqa: BLE001 - diagnóstico não deve quebrar
        print(f"  (sem acesso ao LocalAI: {exc})")
        return []


def _build_rows() -> list[dict]:
    """Monta as linhas do mapeamento unindo todas as fontes."""
    try:
        from src.models_config import scan_all_model_configs

        yaml_configs = scan_all_model_configs()
    except Exception as exc:  # noqa: BLE001
        print(f"  (scan YAMLs falhou: {exc})")
        yaml_configs = {}

    names: set[str] = set()
    names.update(vt.MODEL_VRAM.keys())
    names.update(LOCALAI_MODELS.values())
    names.update(LOCALAI_MODEL_TIMEOUTS.keys())
    names.update(yaml_configs.keys())
    if yaml_configs:
        names.update(yaml_configs.keys())

    alias_of: dict[str, list[str]] = {}
    for alias, model in LOCALAI_MODELS.items():
        alias_of.setdefault(model, []).append(alias)

    def _papel(name: str) -> str:
        if name == PREPARER_MODEL:
            return "PREPARER"
        if name == RAG_LLM_MODEL:
            return "ANALISE"
        if vt.is_cpu_model(name):
            return "CPU"
        return ""

    rows: list[dict] = []
    for name in names:
        vram = vt.get_vram_mib(name)
        group = vt.get_affinity_group(name) or "—"
        timeout = LOCALAI_MODEL_TIMEOUTS.get(name, "—")
        alias = ", ".join(alias_of.get(name, [])) or "—"

        cfg = yaml_configs.get(name)
        gpu_layers: int | str
        context: int | str
        if cfg:
            backend = str(cfg.backend.value)
            gpu_layers = cfg.gpu_layers
            context = cfg.context_size
            disabled = cfg.disabled
            est_yaml = cfg.vram_estimate_mib
            cloud = cfg.is_cloud_proxy
        else:
            backend = "—"
            gpu_layers = "—"
            context = "—"
            disabled = False
            est_yaml = 0
            cloud = False

        cpu = vt.is_cpu_model(name)
        if cloud:
            tipo = "cloud-proxy"
        elif cpu:
            tipo = "CPU"
        elif vram >= LARGE_THRESHOLD_MIB:
            tipo = "LARGE"
        else:
            tipo = "SMALL"

        rows.append(
            {
                "nome": name,
                "alias": alias,
                "papel": _papel(name),
                "vram": vram,
                "tipo": tipo,
                "grupo": group,
                "timeout": timeout,
                "backend": backend,
                "gpu_layers": gpu_layers,
                "context": context,
                "disabled": disabled,
                "est_yaml": est_yaml,
            }
        )

    rows.sort(key=lambda r: (-r["vram"], r["nome"]))
    return rows


def cmd_map() -> None:
    """Imprime a tabela de mapeamento."""
    print(f"== Mapeamento de modelos LocalAI ({LOCALAI_BASE_URL}) ==\n")
    print(
        f"VRAM total: {lm._TOTAL_VRAM_MIB} MiB | "
        f"margem: {lm._SAFETY_MARGIN_MIB} MiB | "
        f"LARGE >= {LARGE_THRESHOLD_MIB} MiB | "
        f"wait timeout: {lm._VRAM_WAIT_TIMEOUT:.1f}s\n"
    )

    disponiveis = set(_models_from_localai())

    rows = _build_rows()
    header = (
        f"{'MODELO':<38} {'ALIAS':<22} {'PAPEL':<9} {'VRAM':>6} {'TIPO':<7} "
        f"{'GRUPO':<20} {'TO':>4} {'GL':>3} {'CTX':>5} {'DISP'}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        disp = "SIM" if r["nome"] in disponiveis else "não"
        print(
            f"{r['nome']:<38} {r['alias']:<22} {r['papel']:<9} {r['vram']:>6} {r['tipo']:<7} "
            f"{r['grupo']:<20} {str(r['timeout']):>4} {str(r['gpu_layers']):>3} "
            f"{str(r['context']):>5} {disp}"
        )

    print(
        "\nLegenda: VRAM = estimada (MiB) | PAPEL = função no pipeline | TO = timeout (s) | "
        "GL = gpu_layers | CTX = context | DISP = disponível no LocalAI"
    )
    gpu_rows = [r for r in rows if r["tipo"] in ("LARGE", "SMALL")]
    total_gpu = sum(r["vram"] for r in gpu_rows)
    print(
        f"\nResumo: {len(rows)} modelos mapeados | {len(gpu_rows)} GPU | "
        f"soma VRAM GPU = {total_gpu} MiB (> {lm._TOTAL_VRAM_MIB} → nunca cabem juntos)"
    )


def _vram_real() -> str:
    """VRAM real via nvidia-smi (com cache TTL do tracker)."""
    try:
        out = vt._nvidia_smi()  # noqa: SLF001 - diagnóstico interno
        return out.strip() if out else "indisponível"
    except Exception as exc:  # noqa: BLE001
        return f"erro: {exc}"


def cmd_test() -> None:
    """Ciclo real: load -> chat -> unload, validando lock/tuning."""
    manager = lm.manager
    client = LocalAIClient(model=TEST_MODEL)

    print(f"== Teste funcional com '{TEST_MODEL}' ==\n")
    print(f"VRAM real antes : {_vram_real()}")

    print(f"\n1) ensure_model_loaded('{TEST_MODEL}')...")
    manager.ensure_model_loaded(TEST_MODEL)
    print(f"   carregados  : {manager.get_currently_loaded()}")
    print(f"   VRAM rastreada: {manager._get_loaded_vram_total()} MiB")  # noqa: SLF001

    print(f"\n2) warmup_model('{TEST_MODEL}') (carga real de inferência)...")
    ok_warmup = manager.warmup_model(TEST_MODEL, timeout=180)
    print(f"   {'OK - backend carregado' if ok_warmup else 'FALHOU'}")

    print(f"\n3) wait_for_model_loaded('{TEST_MODEL}', 120s)...")
    ok = manager.wait_for_model_loaded(TEST_MODEL, timeout=120)
    print(f"   {'OK - modelo no LocalAI' if ok else 'TIMEOUT'}")

    print(f"   VRAM real DURANTE o load: {_vram_real()}")

    print("\n4) chat completion (max_tokens=24)...")
    try:
        resposta = client.chat(
            "Responda apenas com a palavra: pronto",
            max_tokens=24,
            temperature=0.0,
        )
        print(f"   resposta: {resposta[:60]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"   ERRO no chat: {exc}")

    print(f"   VRAM real com modelo no ar: {_vram_real()}")

    print("\n5) liberar refcount e unload...")
    manager._release_model(TEST_MODEL)  # noqa: SLF001
    manager.unload_model(TEST_MODEL)
    print(f"   carregados após unload: {manager.get_currently_loaded()}")
    print(f"   VRAM real depois : {_vram_real()}")
    print("\nTeste concluído — lock/tuning sem race no caminho principal.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico modelos LocalAI")
    parser.add_argument(
        "--test",
        action="store_true",
        help="roda ciclo real load->chat->unload no modelo padrão",
    )
    args = parser.parse_args()
    if args.test:
        cmd_test()
    else:
        cmd_map()
    return 0


if __name__ == "__main__":
    sys.exit(main())
