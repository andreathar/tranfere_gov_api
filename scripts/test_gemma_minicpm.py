#!/usr/bin/env python3
"""
Benchmark de Modelos Adicionais: Gemma 4 E2B e MiniCPM5 1B.

Testa a velocidade, estabilidade e capacidade analítica dos modelos Gemma 4 e MiniCPM5 no LocalAI.
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


def test_model(model_id: str, label: str, prompt_user: str) -> dict:
    """Executa inferência testando modelo e descarregando anteriores."""
    print(f"\n🤖 Testando Modelo: '{label}' ({model_id})")

    # Gerenciamento de ciclo de vida
    localai_manager.ensure_model_loaded(model_id)
    time.sleep(2)

    url = f"{LOCALAI_BASE_URL}/chat/completions"
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_AGENTE},
            {"role": "user", "content": prompt_user},
        ],
        "temperature": 0.4,
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
            return {
                "sucesso": True,
                "modelo": label,
                "tempo": elapsed,
                "tps": tps,
                "length": len(content),
            }
        else:
            print(f"  ❌ Erro HTTP {resp.status_code}: {resp.text[:200]}")
            return {"sucesso": False, "modelo": label, "erro": resp.text, "tempo": elapsed}
    except Exception as e:
        print(f"  ❌ Exceção: {e}")
        return {"sucesso": False, "modelo": label, "erro": str(e), "tempo": time.time() - start}


def main():
    print("============================================================")
    print("  TESTANDO MODELOS GEMMA 4 E2B E MINICPM5 1B NO LOCALAI")
    print("============================================================")

    prompt_teste = """Deputado Federal: Afonso Florence (PT-BA)
Dados do contexto:
- Emenda 2024: R$ 2.500.000 para Infraestrutura Urbana em Salvador-BA
- Emenda 2024: R$ 800.000 para Saúde em Camaçari-BA
- Voto: SIM ao PL 1234/2024 (Reforma Tributária)
- Voto: NAO ao PL 5678/2024 (Privatização de Ativos)
- Proposição: PL 320/2024 - Incentivo à Agricultura Familiar
Elabore o dossiê investigativo conforme suas instruções de agente."""

    modelos_para_testar = [
        ("gemma-4-e2b-it", "Gemma 4 E2B Instruct"),
        ("minicpm5-1b-claude-opus-fable5-v2-thinking", "MiniCPM5 1B Thinking (V2)"),
        ("minicpm5-1b-claude-opus-fable5-thinking", "MiniCPM5 1B Thinking (V1)"),
    ]

    resultados = []
    for mid, label in modelos_para_testar:
        res = test_model(mid, label, prompt_teste)
        resultados.append(res)

    print("\n============================================================")
    print("  RESUMO COMPARATIVO DOS MODELOS TESTADOS")
    print("============================================================")
    for r in resultados:
        if r.get("sucesso"):
            print(
                f"{r['modelo']:<35} | Tempo: {r['tempo']:.1f}s | Velocidade: {r['tps']} tok/s | Chars: {r['length']}"
            )
        else:
            print(f"{r['modelo']:<35} | FALHOU ({r.get('erro', 'erro')[:40]})")


if __name__ == "__main__":
    main()
