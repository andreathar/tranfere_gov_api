#!/usr/bin/env python3
"""
Benchmark de Modelos LocalAI para Geração de Dossiês Parlamentares.

Testa múltiplos modelos com o mesmo prompt de deputado real e compara:
  - Tempo de geração (segundos)
  - Tokens por segundo (estimado)
  - Tamanho da resposta (chars)
  - Score de qualidade automático (cobertura de seções esperadas)
  - Custo de memória (via /backend/monitor)

Uso:
    python3 scripts/benchmark_models.py
    python3 scripts/benchmark_models.py --nome "Afonso Florence" --modelos llama-3.1-8b-dossie qwen3.5-9b-dossie
    python3 scripts/benchmark_models.py --exportar resultado_benchmark.json
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    LOCALAI_BASE_URL,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from src.localai_manager import manager as localai_manager

# ---------------------------------------------------------------------------
# Modelos candidatos para benchmark
# ---------------------------------------------------------------------------
MODELOS_BENCHMARK = [
    {
        "id": "llama-3.1-8b-q4-k-m",
        "label": "Llama 3.1 8B (baseline)",
        "backend": "cuda13-llama-cpp",
        "gpu_layers": 24,
    },
    {
        "id": "llama-3.1-8b-dossie",
        "label": "Llama 3.1 8B (otimizado dossiê)",
        "backend": "cuda13-llama-cpp",
        "gpu_layers": 33,
    },
    {
        "id": "llama-3.2-3b-instruct:q4_k_m",
        "label": "Llama 3.2 3B Q4 (rápido)",
        "backend": "cuda13-llama-cpp",
        "gpu_layers": 999,
    },
    {
        "id": "qwen2.5-1.5b-instruct-q4-k-m",
        "label": "Qwen2.5 1.5B (ultra-rápido)",
        "backend": "cuda13-llama-cpp",
        "gpu_layers": 32,
    },
    {
        "id": "qwen3.5-9b-dossie",
        "label": "Qwen3.5 9B (alta qualidade)",
        "backend": "llama-cpp",
        "gpu_layers": 30,
    },
    {
        "id": "minicpm5-1b-claude-opus-fable5-v2-thinking",
        "label": "MiniCPM5 1B (thinking)",
        "backend": "llama-cpp",
        "gpu_layers": None,
    },
]

# Seções esperadas em um dossiê de qualidade
SECOES_ESPERADAS = [
    "PERFIL",
    "AREAS TEMATICAS",
    "CRUZAMENTO",
    "PADRAO DE VOTO",
    "EMENDAS",
    "PROPOSICOES",
    "INDICADORES",
    "RISCOS",
    "CONCLUSAO",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_deputado_context(nome: str) -> tuple[str, list[str]]:
    """Busca contexto RAG de um deputado via Qdrant + banco."""
    try:
        from qdrant_client import QdrantClient

        from src.enrichers.rag_qdrant_indexer import embed_text

        client = QdrantClient(url=QDRANT_URL)
        embedding = embed_text(nome)
        results = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=embedding,
            limit=20,
            with_payload=True,
        )
        chunks = [r.payload.get("texto", "") for r in results.points if r.payload.get("texto")]
        return nome, chunks
    except Exception as e:
        print(f"⚠️  Qdrant indisponível ({e}), usando contexto de teste.")
        # Contexto sintético para benchmark sem Qdrant
        return nome, [
            f"[PERFIL] {nome} - Deputado Federal, mandato ativo.",
            "[EMENDA] 2024 - R$ 500.000 para Santa Casa Municipal",
            "[EMENDA] 2024 - R$ 1.200.000 para Hospital Regional",
            "[VOTO] SIM - PL 1234/2024 - Reforma Tributária",
            "[VOTO] NAO - PL 5678/2024 - Privatização",
            "[PROPOSICAO] PL 100/2024 - Proteção à Saúde",
        ]


def build_prompt(deputado_nome: str, contexto: list[str]) -> str:
    contexto_str = "\n".join(f"  - {c}" for c in contexto)
    return f"""Voce e um Analista Investigativo especializado em Contas Publicas.
Analise o perfil do deputado federal {deputado_nome} com base nos dados reais abaixo.

CONTEXTO ({len(contexto)} fontes):
{contexto_str}

INSTRUCOES DE ANALISE (Markdown):

1. **PERFIL**: Nome, partido, UF. Contexto político.
2. **AREAS TEMATICAS**: Principais áreas de atuação por volume de verbas.
3. **CRUZAMENTO DE DADOS**: Conecte votos com emendas e proposições.
4. **PADRAO DE VOTO**: Alinhamento político, dissensos notáveis.
5. **EMENDAS PIX**: Municípios beneficiados, concentração de verbas.
6. **PROPOSICOES LEGISLATIVAS**: Temas, volume, coerência com emendas.
7. **INDICADORES DE RISCO**: Sinais de clientelismo, irregularidades ou fisiologismo.
8. **CONCLUSAO**: Síntese de 3-5 linhas do perfil investigativo.

Seja direto e objetivo. Use apenas os dados fornecidos."""


def score_qualidade(texto: str) -> dict[str, Any]:
    """Avalia cobertura das seções esperadas no dossiê gerado."""
    texto_upper = texto.upper()
    encontradas = [s for s in SECOES_ESPERADAS if s in texto_upper]
    score = len(encontradas) / len(SECOES_ESPERADAS) * 100
    palavras = len(texto.split())
    # Penaliza textos muito curtos (< 200 palavras) ou muito longos (> 2000)
    densidade = min(palavras / 400, 1.0) * 20  # bônus até 20 pts por densidade
    # Verifica se menciona dados numéricos (R$, %)
    tem_numeros = bool(re.search(r"R\$\s*[\d.,]+|[\d.,]+%", texto))
    numeros_bonus = 10 if tem_numeros else 0
    return {
        "score_total": min(round(score + densidade + numeros_bonus, 1), 100),
        "secoes_encontradas": encontradas,
        "secoes_ausentes": [s for s in SECOES_ESPERADAS if s not in texto_upper],
        "palavras": palavras,
        "tem_dados_numericos": tem_numeros,
    }


def call_model(model_id: str, prompt: str, timeout: int = 300) -> dict[str, Any]:
    """Chama o modelo via API OpenAI-compatible do LocalAI."""
    url = f"{LOCALAI_BASE_URL}/chat/completions"
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": "Voce e um analista investigativo especializado em transparência pública brasileira.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 2048,
        "stream": False,
    }

    start = time.time()
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {
                "sucesso": False,
                "erro": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "tempo_segundos": elapsed,
            }

        data = resp.json()
        texto = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return {
            "sucesso": True,
            "texto": texto,
            "tempo_segundos": round(elapsed, 1),
            "tokens_prompt": usage.get("prompt_tokens", 0),
            "tokens_completion": usage.get("completion_tokens", 0),
            "tokens_por_segundo": round(
                usage.get("completion_tokens", len(texto.split())) / max(elapsed, 1), 1
            ),
        }
    except httpx.TimeoutException:
        return {"sucesso": False, "erro": "TIMEOUT", "tempo_segundos": timeout}
    except Exception as e:
        return {"sucesso": False, "erro": str(e), "tempo_segundos": time.time() - start}


def unload_all_models():
    """Descarrega todos os modelos para garantir medição limpa."""
    base = LOCALAI_BASE_URL.replace("/v1", "")
    try:
        resp = httpx.get(f"{base}/v1/models", timeout=5)
        modelos = [m["id"] for m in resp.json().get("data", [])]
        for m in modelos:
            httpx.post(f"{base}/backend/shutdown", json={"model": m}, timeout=10)
        print(f"  ✓ {len(modelos)} modelos descarregados da memória.")
    except Exception as e:
        print(f"  ⚠️  Não foi possível limpar modelos: {e}")


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------


def run_benchmark(
    deputado_nome: str,
    modelos_ids: list[str] | None,
    exportar: str | None,
):
    print(f"\n{'=' * 60}")
    print("  BENCHMARK DE MODELOS LOCALAI")
    print(f"  Deputado: {deputado_nome}")
    print(f"{'=' * 60}\n")

    # Filtra modelos
    modelos = [m for m in MODELOS_BENCHMARK if modelos_ids is None or m["id"] in modelos_ids]
    if not modelos:
        print("Nenhum modelo selecionado.")
        return

    print(f"Modelos a testar: {len(modelos)}")
    print(f"Buscando contexto RAG para '{deputado_nome}'...")
    nome, contexto = get_deputado_context(deputado_nome)
    prompt = build_prompt(nome, contexto)

    print(f"Contexto: {len(contexto)} chunks ({len(prompt)} chars no prompt)\n")

    resultados = []

    for i, modelo in enumerate(modelos, 1):
        mid = modelo["id"]
        label = modelo["label"]
        print(f"[{i}/{len(modelos)}] {label} ({mid})")

        # Usa LocalAIManager para garantir exclusividade de memória antes da invocação
        print(f"  → Garantindo exclusividade de VRAM para {mid}...")
        localai_manager.ensure_model_loaded(mid)
        time.sleep(2)

        print(f"  → Gerando dossiê com {mid}...")
        resultado = call_model(mid, prompt)

        if resultado["sucesso"]:
            qualidade = score_qualidade(resultado["texto"])
            print(f"  ✓ Concluído em {resultado['tempo_segundos']}s")
            print(f"    Score qualidade: {qualidade['score_total']}/100")
            print(f"    Seções ausentes: {qualidade['secoes_ausentes']}")
            print(
                f"    Palavras: {qualidade['palavras']} | Tokens/s: {resultado.get('tokens_por_segundo', '?')}"
            )
            resultados.append(
                {
                    "modelo_id": mid,
                    "modelo_label": label,
                    **resultado,
                    "qualidade": qualidade,
                }
            )
        else:
            print(f"  ✗ FALHOU: {resultado['erro']}")
            resultados.append(
                {
                    "modelo_id": mid,
                    "modelo_label": label,
                    **resultado,
                    "qualidade": None,
                }
            )

        print()

    # ---------------------------------------------------------------------------
    # Tabela de resultados
    # ---------------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  RESULTADO FINAL DO BENCHMARK")
    print(f"{'=' * 60}")
    print(f"{'Modelo':<40} {'Score':>6} {'Tempo':>8} {'Tok/s':>6} {'Palavras':>8}")
    print("-" * 70)

    ok = [r for r in resultados if r.get("sucesso")]
    ok.sort(key=lambda r: r["qualidade"]["score_total"] if r.get("qualidade") else 0, reverse=True)

    for r in resultados:
        q = r.get("qualidade")
        score = f"{q['score_total']:.0f}/100" if q else "FALHOU"
        tempo = f"{r.get('tempo_segundos', '?')}s"
        tps = f"{r.get('tokens_por_segundo', '?')}"
        palavras = str(q["palavras"]) if q else "-"
        print(f"{r['modelo_label']:<40} {score:>6} {tempo:>8} {tps:>6} {palavras:>8}")

    if ok:
        melhor = ok[0]
        print(
            f"\n🏆 Melhor qualidade: {melhor['modelo_label']} (score {melhor['qualidade']['score_total']}/100)"
        )
        mais_rapido = min(ok, key=lambda r: r["tempo_segundos"])
        print(f"⚡ Mais rápido: {mais_rapido['modelo_label']} ({mais_rapido['tempo_segundos']}s)")

        if melhor["modelo_id"] != mais_rapido["modelo_id"]:
            razao = mais_rapido["tempo_segundos"] / max(melhor["tempo_segundos"], 1)
            print(f"   (melhor qualidade é {1 / razao:.1f}x mais lento que o mais rápido)")

    # Exportar
    if exportar:
        with open(exportar, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)
        print(f"\n📊 Resultados exportados para: {exportar}")

    # Imprime o melhor dossiê gerado
    if ok:
        melhor = ok[0]
        print(f"\n{'=' * 60}")
        print(f"  DOSSIÊ GERADO PELO MELHOR MODELO: {melhor['modelo_label']}")
        print(f"{'=' * 60}")
        print(melhor["texto"][:3000])
        if len(melhor["texto"]) > 3000:
            print(f"\n[... +{len(melhor['texto']) - 3000} chars omitidos ...]")


def main():
    parser = argparse.ArgumentParser(description="Benchmark de modelos LocalAI para dossiês.")
    parser.add_argument(
        "--nome", default="Afonso Florence", help="Nome do deputado para o benchmark."
    )
    parser.add_argument(
        "--modelos",
        nargs="+",
        default=None,
        metavar="MODEL_ID",
        help="IDs dos modelos a testar (padrão: todos).",
    )
    parser.add_argument(
        "--exportar", default=None, metavar="ARQUIVO.json", help="Exportar resultados como JSON."
    )
    args = parser.parse_args()

    run_benchmark(
        deputado_nome=args.nome,
        modelos_ids=args.modelos,
        exportar=args.exportar,
    )


if __name__ == "__main__":
    main()
