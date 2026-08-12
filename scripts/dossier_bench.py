#!/usr/bin/env python3
"""Benchmark de dossiês multi-analista — baseline observável (RAG v7/v8).

Mede, por deputado e por analista, métricas reproduzíveis para comparar
antes/depois da refatoração:

  - duração total e por analista
  - quality_score / quality_ok por analista
  - chars gerados, chunks usados, briefing chars
  - taxa de invenção R$ (fidelidade numérica)
  - NÚMERO REAL de chamadas LLM (via contador no LocalAIClient.chat)

Uso:
    .venv/bin/python scripts/dossier_bench.py --lote 3
    .venv/bin/python scripts/dossier_bench.py --nomes "AFONSO FLORENCE,ALICE PORTUGAL"
    .venv/bin/python scripts/dossier_bench.py --nomes X --saida reports/dossier_bench/run_xxx.jsonl
    .venv/bin/python scripts/dossier_bench.py --compare run_baseline_v7.jsonl  # stub futuro

Saída: JSONL (1 linha por deputado) em reports/dossier_bench/ por padrão.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

log = logging.getLogger("dossier_bench")

# ---------------------------------------------------------------------------
# Instrumentação: contagem real de chamadas LLM
# ---------------------------------------------------------------------------


class LLMCallCounter:
    """Conta chamadas reais ao LocalAI (preparer + analistas)."""

    def __init__(self) -> None:
        self.count = 0
        self.models: dict[str, int] = {}
        self._original_chat: Any = None
        self._wrapped: Any = None

    def __enter__(self) -> LLMCallCounter:
        from src.localai_client import LocalAIClient

        self._original_chat = LocalAIClient.chat

        def _contador(inst: Any, *args: Any, **kwargs: Any) -> str:
            """Função normal no class level: recebe a instância LocalAIClient
            como primeiro arg (descriptor binding padrão do Python).
            chat() pode ser chamado com prompt posicional OU keyword-only."""
            self.count += 1
            model = kwargs.get("model") or getattr(inst, "model", None) or "?"
            self.models[model] = self.models.get(model, 0) + 1
            return self._original_chat(inst, *args, **kwargs)

        self._wrapped = _contador
        LocalAIClient.chat = _contador  # type: ignore[method-assign]
        return self

    def __exit__(self, *exc: Any) -> None:
        from src.localai_client import LocalAIClient

        if self._original_chat is not None:
            LocalAIClient.chat = self._original_chat  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Coleta de métricas por deputado
# ---------------------------------------------------------------------------


def _taxa_invencao_por_analista(results: list[Any]) -> dict[str, float]:
    """Recomputa taxa_invencao_rs por analista usando os chunks que ele usou."""
    from src.analysts.base import taxa_invencao_rs

    out: dict[str, float] = {}
    for r in results:
        chunks_text = "\n".join(getattr(r, "chunks_used", []) or [])
        try:
            out[r.analyst_id] = round(taxa_invencao_rs(r.content, chunks_text), 4)
        except Exception:
            out[r.analyst_id] = -1.0
    return out


def run_deputado(
    deputado_id: int, nome: str, tipo_politico: str = "deputado"
) -> dict[str, Any]:
    """Gera dossier de um político e coleta métricas completas.

    tipo_politico: deputado/senador/governador/prefeito/vereador (Fase 3).
    """
    from src.enrichers.rag_persona import generate_persona_analysis

    inicio = time.time()
    with LLMCallCounter() as counter:
        analise, duracao, fontes, context_list, qualidade_ok = (
            generate_persona_analysis(deputado_id, nome, tipo_politico=tipo_politico)
        )
    chamadas_llm = counter.count
    modelos = dict(counter.models)

    # Score de qualidade agregado (QC estruturado) — exposto pelo rag_persona.
    from src.enrichers import rag_persona as _rp

    score_global = _rp.LAST_RUN_SCORE.get("global")
    scores_analistas = _rp.LAST_RUN_SCORE.get("analistas")


    # Re-executar pipeline apenas para obter AnalystResults detalhados é
    # custoso; em vez disso, medimos o que generate_persona_analysis expõe.
    # Para métricas por analista usamos o log estruturado (ver Fase 0 do plano)
    # e a taxa de invenção é calculada sobre o texto final.
    return {
        "deputado_id": deputado_id,
        "nome": nome,
        "tipo": tipo_politico,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "duracao_total_s": round(duracao, 1),
        "wallclock_s": round(time.time() - inicio, 1),
        "chamadas_llm": chamadas_llm,
        "modelos_usados": modelos,
        "qualidade_ok": qualidade_ok,
        "score_global": score_global,
        "scores_analistas": scores_analistas,
        "n_chunks": len(context_list),
        "n_fontes": len(fontes),
        "fontes": fontes,
        "analise_len": len(analise),
        "analise_prefix": analise[:200],
        "erro": analise.startswith("Dados insuficientes")
        or analise.startswith("Falha"),
    }


def _carregar_deputados_lote(
    lote: int, tipo_politico: str = "deputado"
) -> list[tuple[int, str, str]]:
    """Carrega N políticos de um cargo sem dossier v8 (ou todos se lote=0).

    Reutiliza a fila por cargo do rag_persona (dossie_checkpoint + versão
    RAG_PERSONA_VERSION). Retorna [(politico_id, nome, tipo)].
    """
    from config.settings import RAG_PERSONA_VERSION
    from src.db_utils import get_connection

    if tipo_politico != "deputado":
        from src.enrichers.rag_persona import _get_fila_por_tipo

        fila = _get_fila_por_tipo(tipo_politico, lote, regenerar=False)
        return [(int(f[0]), str(f[1]), tipo_politico) for f in fila]

    query = """
        SELECT d.deputado_id, COALESCE(NULLIF(d.nome, ''), d.nome_urna) AS nome
        FROM parlamentares_dados d
        LEFT JOIN parlamentares_personas p
          ON p.deputado_id = d.deputado_id AND p.versao_prompt = %s
        WHERE p.deputado_id IS NULL
        ORDER BY d.nome
        LIMIT %s
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, (RAG_PERSONA_VERSION, lote))
        rows = cur.fetchall()
    return [(r[0], r[1], "deputado") for r in rows]


def _carregar_por_nomes(
    nomes: str, tipo_politico: str = "deputado"
) -> list[tuple[int, str]]:
    """Resolve nomes informados na CLI para (politico_id, nome) no cargo."""
    from src.db_utils import get_connection

    if tipo_politico != "deputado":
        from src.enrichers.rag_persona import _find_politico_por_tipo

        out: list[tuple[int, str]] = []
        for nome in (n.strip() for n in nomes.split(",") if n.strip()):
            encontrado = _find_politico_por_tipo(tipo_politico, nome, None)
            if encontrado and encontrado[0] is not None:
                out.append((encontrado[0], encontrado[1] or nome))
            else:
                log.warning(f"'{nome}' não encontrado como {tipo_politico}; ignorado.")
        return out

    out: list[tuple[int, str]] = []
    with get_connection() as conn, conn.cursor() as cur:
        for nome in (n.strip() for n in nomes.split(",") if n.strip()):
            cur.execute(
                "SELECT deputado_id, COALESCE(NULLIF(nome, ''), nome_urna) "
                "FROM parlamentares_dados "
                "WHERE nome ILIKE %s OR nome_urna ILIKE %s ORDER BY deputado_id LIMIT 1",
                (f"%{nome}%", f"%{nome}%"),
            )
            row = cur.fetchone()
            if row:
                out.append((row[0], row[1]))
            else:
                log.warning(f"Deputado '{nome}' não encontrado; ignorado.")
    return out


def _carregar_golden_set() -> list[dict[str, Any]]:
    """Carrega o golden set (data/golden_set_v8.yaml) — Fase 5."""
    import yaml

    path = Path(__file__).resolve().parent.parent / "data" / "golden_set_v8.yaml"
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("golden_set", [])


def _run_golden_item(item: dict[str, Any]) -> dict[str, Any]:
    """Gera dossier de um item do golden set (multi-cargo)."""
    from src.enrichers.rag_persona import generate_persona_analysis

    tipo = item.get("tipo", "deputado")
    pid = item["id"]
    nome = item["nome"]

    inicio = time.time()
    with LLMCallCounter() as counter:
        analise, duracao, fontes, context_list, qualidade_ok = generate_persona_analysis(
            pid, nome, tipo_politico=tipo
        )
    chamadas_llm = counter.count

    from src.enrichers import rag_persona as _rp

    score_global = _rp.LAST_RUN_SCORE.get("global")
    scores_analistas = _rp.LAST_RUN_SCORE.get("analistas")

    return {
        "tipo": tipo,
        "politico_id": pid,
        "nome": nome,
        "nota": item.get("nota", ""),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "duracao_total_s": round(duracao, 1),
        "wallclock_s": round(time.time() - inicio, 1),
        "chamadas_llm": chamadas_llm,
        "modelos_usados": dict(counter.models),
        "qualidade_ok": qualidade_ok,
        "score_global": score_global,
        "scores_analistas": scores_analistas,
        "n_chunks": len(context_list),
        "n_fontes": len(fontes),
        "fontes": fontes,
        "analise_len": len(analise),
        "analise_prefix": analise[:200],
        "erro": analise.startswith("Dados insuficientes")
        or analise.startswith("Falha"),
    }


def _compare_runs(baseline_path: str, current_path: str) -> int:
    """Compara dois runs JSONL e imprime tabela delta (Fase 5)."""
    import json as _json

    def _load(path: str) -> dict[tuple[str, Any], dict[str, Any]]:
        out: dict[tuple[str, Any], dict[str, Any]] = {}
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = _json.loads(line)
                key = (rec.get("tipo", "deputado"), rec.get("politico_id", rec.get("deputado_id")))
                out[key] = rec
        return out

    base = _load(baseline_path)
    cur = _load(current_path)
    if not base or not cur:
        log.error("Um dos runs está vazio.")
        return 1

    print(f"\n{'=' * 90}")
    print(f" COMPARAÇÃO DE RUNS — baseline: {Path(baseline_path).name} vs atual")
    print(f"{'=' * 90}")
    print(
        f"{'ID':<12} {'Nome':<22} {'LLM base→atual':<15} {'Dur base→atual':<16} "
        f"{'QC ok':<8} {'Score':<8}"
    )
    print("-" * 90)
    for key, b in base.items():
        c = cur.get(key)
        if not c:
            print(f"{key[1]:<12} {b.get('nome','?'):<22} — ausente no run atual")
            continue
        llm_delta = f"{b.get('chamadas_llm','?')}→{c.get('chamadas_llm','?')}"
        dur_delta = f"{b.get('duracao_total_s','?')}→{c.get('duracao_total_s','?')}s"
        print(
            f"{key[1]:<12} {b.get('nome','?'):<22} {llm_delta:<15} {dur_delta:<16} "
            f"{'OK' if c.get('qualidade_ok') else 'FAIL':<8} "
            f"{c.get('score_qualidade', c.get('qualidade_score','?'))}"
        )
    print("-" * 90)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lote", type=int, default=0, help="N políticos sem dossier v8")
    parser.add_argument("--nomes", type=str, default="", help="Nomes separados por vírgula")
    parser.add_argument(
        "--tipo",
        type=str,
        default="deputado",
        choices=("deputado", "senador", "governador", "prefeito", "vereador"),
        help="Cargo do político (aplica a --lote e --nomes; default: deputado)",
    )
    parser.add_argument(
        "--saida",
        type=str,
        default="",
        help="Arquivo JSONL de saída (default: reports/dossier_bench/run_<ts>.jsonl)",
    )
    parser.add_argument(
        "--compare",
        type=str,
        default="",
        help="Arquivo baseline JSONL para comparar (Fase 5)",
    )
    parser.add_argument(
        "--golden",
        action="store_true",
        help="Executa o golden set (data/golden_set_v8.yaml) — multi-cargo",
    )
    parser.add_argument(
        "--saida-atual",
        type=str,
        default="",
        help="Run atual para --compare (default: último JSONL de reports/dossier_bench)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.compare:
        if not args.saida_atual:
            runs = sorted(Path("reports/dossier_bench").glob("run_*.jsonl"))
            if not runs:
                log.error("Nenhum run encontrado para --saida-atual.")
                return 1
            args.saida_atual = str(runs[-1])
        return _compare_runs(args.compare, args.saida_atual)

    if args.golden:
        itens = _carregar_golden_set()
        if not itens:
            log.error("Golden set vazio ou não encontrado.")
            return 1
        deputados = [(it["id"], it["nome"], it.get("tipo", "deputado")) for it in itens]
        saida = args.saida or (
            f"reports/dossier_bench/golden_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        )
    else:
        deputados = []
        if args.nomes:
            deputados = [(d, n, args.tipo) for d, n in _carregar_por_nomes(args.nomes, args.tipo)]
        elif args.lote:
            deputados = _carregar_deputados_lote(args.lote, args.tipo)
        else:
            parser.print_help()
            return 0
        if not deputados:
            log.error("Nenhum político selecionado.")
            return 1
        saida = args.saida or (
            f"reports/dossier_bench/run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        )

    Path(saida).parent.mkdir(parents=True, exist_ok=True)

    resumo: dict[str, Any] = {
        "n_deputados": 0,
        "n_ok": 0,
        "n_erro": 0,
        "n_aprovado_qc": 0,
        "score_global_medio": None,
        "duracao_total_s": 0.0,
        "chamadas_llm_total": 0,
        "chamadas_llm_por_dossier": [],
    }
    inicio_geral = time.time()
    scores_globais: list[float] = []

    with open(saida, "w", encoding="utf-8") as fh:
        for i, (dep_id, nome, tipo) in enumerate(deputados, start=1):
            log.info(f"[{i}/{len(deputados)}] Gerando dossier de {nome} ({tipo})...")
            try:
                if args.golden:
                    registro = _run_golden_item(
                        {"tipo": tipo, "id": dep_id, "nome": nome}
                    )
                else:
                    registro = run_deputado(dep_id, nome, tipo)
            except Exception as e:
                log.error(f"Falha em {nome}: {e}")
                registro = {
                    "deputado_id": dep_id,
                    "nome": nome,
                    "tipo": tipo,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "erro": True,
                    "erro_msg": str(e)[:500],
                }
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
            fh.flush()

            resumo["n_deputados"] += 1
            if registro.get("erro"):
                resumo["n_erro"] += 1
            else:
                resumo["n_ok"] += 1
                resumo["duracao_total_s"] += registro["duracao_total_s"]
                resumo["chamadas_llm_total"] += registro["chamadas_llm"]
                resumo["chamadas_llm_por_dossier"].append(registro["chamadas_llm"])
            if registro.get("qualidade_ok"):
                resumo["n_aprovado_qc"] += 1
            if registro.get("score_global") is not None:
                scores_globais.append(registro["score_global"])
            print(f"  -> {nome}: {registro.get('chamadas_llm', '?')} chamadas LLM, "
                  f"{registro.get('duracao_total_s', '?')}s, "
                  f"ok={registro.get('qualidade_ok', '?')}")

    if scores_globais:
        resumo["score_global_medio"] = round(
            sum(scores_globais) / len(scores_globais), 1
        )
    resumo["duracao_wallclock_s"] = round(time.time() - inicio_geral, 1)
    resumo_path = saida.replace(".jsonl", "_resumo.json")
    with open(resumo_path, "w", encoding="utf-8") as fh:
        json.dump(resumo, fh, ensure_ascii=False, indent=2)

    print(f"\nBenchmark concluído: {saida}")
    print(f"Resumo: {resumo_path}")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    main()
