#!/usr/bin/env python3
"""
Script de Aprendizado e Controle Total de Agentes e Backends no LocalAI.

Demonstra:
  1. Inspeção de estado de memória e backends (/backend/monitor, /v1/models).
  2. Lifecycle Management: descarregamento dinâmico (/backend/shutdown) para troca segura de GPU/CPU.
  3. Execução de Agente Investigativo com Prompt Injetado e Gerenciamento VRAM.
  4. Comparativo de Performance (Qwen 1.5B vs Llama 3.1 8B).
"""

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import LOCALAI_BASE_URL
from src.localai_manager import manager as localai_manager

SYSTEM_PROMPT_AGENTE = """Você é o AGENTE INVESTIGATIVO OFICIAL do TransfereGov API.
Sua missão é realizar auditorias e análises detalhadas do comportamento parlamentar de deputados federais brasileiros.
Analise os dados fornecidos no contexto (Emendas PIX, Votações, Proposições e Dados Financeiros Municipais).
Seja estritamente factual, objetivo e estruture a resposta sempre nas seguintes seções:
1. **PERFIL PARLAMENTAR**
2. **ANÁLISE DE EMENDAS & DESTINAÇÕES**
3. **PADRÃO DE VOTAÇÃO & ALINHAMENTO**
4. **COERÊNCIA LEGISLATIVA**
5. **AVALIAÇÃO DE RISCO & CLIENTELISMO**
6. **SÍNTESE EXECUTIVA**"""


def test_model_agent(model_id: str, label: str, prompt_user: str) -> dict:
    """Executa inferência com gerenciamento de lifecycle de VRAM."""
    print(f"\n🤖 Testando Agente com Modelo: '{label}' ({model_id})")

    # 1. Gerenciamento de ciclo de vida (Unload preventivo de outros modelos)
    localai_manager.ensure_model_loaded(model_id)
    time.sleep(2)

    url = f"{LOCALAI_BASE_URL}/chat/completions"
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENTE},
            {"role": "user", "content": prompt_user},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }

    start = time.time()
    try:
        resp = httpx.post(url, json=payload, timeout=180.0)
        elapsed = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = usage.get("completion_tokens", len(content.split()))
            tps = round(tokens / max(elapsed, 1), 1)

            print(f"  ✅ Resposta em {elapsed:.1f}s | {tokens} tokens ({tps} tok/s)")
            print(f"  📝 Amostra ({len(content)} chars):\n" + "-" * 40)
            print(content[:350] + ("..." if len(content) > 350 else ""))
            print("-" * 40)
            return {"sucesso": True, "tempo": elapsed, "tps": tps, "length": len(content)}
        else:
            print(f"  ❌ Erro HTTP {resp.status_code}: {resp.text[:200]}")
            return {"sucesso": False, "erro": resp.text}
    except Exception as e:
        print(f"  ❌ Exceção: {e}")
        return {"sucesso": False, "erro": str(e)}


def main():
    print("============================================================")
    print("  CONTROLE TOTAL DE AGENTES E BACKENDS NO LOCALAI")
    print("============================================================")

    # Lista modelos disponíveis no servidor LocalAI
    models = localai_manager.get_all_models()
    print(f"\n📋 Modelos registrados no LocalAI ({len(models)}):")
    for m in models:
        print(f"  - {m}")

    prompt_teste = """Deputado Federal: Afonso Florence (PT-BA)
Dados do contexto:
- Emenda 2024: R$ 2.500.000 para Infraestrutura Urbana em Salvador-BA
- Emenda 2024: R$ 800.000 para Saúde em Camaçari-BA
- Voto: SIM ao PL 1234/2024 (Reforma Tributária)
- Voto: NAO ao PL 5678/2024 (Privatização de Ativos)
- Proposição: PL 320/2024 - Incentivo à Agricultura Familiar
Elabore o dossiê investigativo conforme suas instruções de agente."""

    # 1. Testar Agente Rápido (Qwen2.5 1.5B)
    res_rapido = test_model_agent(
        "qwen2.5-1.5b-instruct-q4-k-m", "Agente Rápido (Qwen 1.5B)", prompt_teste
    )

    # 2. Testar Agente Investigativo (Llama 3.1 8B CUDA)
    res_investigativo = test_model_agent(
        "llama-3.1-8b-q4-k-m", "Agente Investigativo (Llama 3.1 8B CUDA)", prompt_teste
    )

    print("\n============================================================")
    print("  RESUMO COMPARATIVO DE PERFORMANCE DOS AGENTES")
    print("============================================================")
    if res_rapido.get("sucesso"):
        print(
            f"Agente Rápido (Qwen 1.5B):        Tempo: {res_rapido['tempo']:.1f}s | Velocidade: {res_rapido['tps']} tok/s"
        )
    if res_investigativo.get("sucesso"):
        print(
            f"Agente Investigativo (Llama 8B):   Tempo: {res_investigativo['tempo']:.1f}s | Velocidade: {res_investigativo['tps']} tok/s"
        )


if __name__ == "__main__":
    main()
