"""Logit Lens Probe — auditoria visual da eficiência do RAG v7.

Mede, com logprobs reais do LLM (LocalAI/vLLM), quanto o contexto recuperado
do Qdrant reduz a incerteza da geração:

  1. Context-gain: entropia do 1º token da resposta SEM contexto vs COM
     contexto RAG (colapso de incerteza em %).
  2. Trajetória de confiança: prob do top-1 ao longo da geração (commit depth,
     dips de incerteza = zonas de risco de alucinação).
  3. Atribuição de fonte: quais chunk types venceram o RRF multi-query.

Gera relatório Plotly em output/logit_lens/ e JSON bruto em output/json/.

Uso:
    .venv/bin/python -m src.logit_lens_probe --nome "AFONSO FLORENCE"
    .venv/bin/python -m src.logit_lens_probe --politico-id 4291 \
        --pergunta "Qual o partido do parlamentar?" --max-tokens 128
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config.settings import OUTPUT_DIR, OUTPUT_JSON, RAG_LLM_MODEL
from src.db_utils import get_connection
from src.enrichers.rag_persona import (
    _find_politico_por_tipo,
    search_context_multiquery,
)
from src.localai_client import ChatLogprobs, LocalAIClient, TokenLogprob, get_localai_client

log = logging.getLogger(__name__)

PROBES_DEFAULT = {
    "deputado": [
        "Qual o partido político do parlamentar?",
        "Quantas emendas PIX o parlamentar enviou?",
        "Qual o total em reais das emendas PIX do parlamentar?",
        "Qual o principal município beneficiado pelas emendas do parlamentar?",
        "O parlamentar é base do governo ou oposição?",
    ],
    "senador": [
        "Qual o partido político do senador?",
        "Qual o total em reais das emendas PIX do senador?",
        "O senador é base do governo ou oposição?",
    ],
    "governador": [
        "Qual o partido político do governador?",
        "Qual a coligação que elegeu o governador?",
        "Quantas emendas PIX a UF recebeu?",
    ],
    "prefeito": [
        "Qual o partido político do prefeito?",
        "Quantas emendas PIX o município recebeu?",
        "Qual o total em reais das emendas PIX do município?",
    ],
    "vereador": [
        "Qual o partido político do vereador?",
        "O vereador votou com o governo nas votações?",
    ],
}

WINDOW_COMMIT = 5
THRESHOLD_COMMIT = 0.9
THRESHOLD_DIP = 0.5

_SISTEMA = (
    "Você é um analista imparcial de dados públicos do Congresso Nacional. "
    "Responda objetivamente. Se não houver informação suficiente, responda "
    "'não sei'."
)


@dataclass
class ProbeResult:
    pergunta: str
    top1_sem_contexto: float
    top1_com_contexto: float
    entropia_sem_contexto: float
    entropia_com_contexto: float
    commit_depth: int
    dips_incerteza: int
    resposta_sem_contexto: str
    resposta_com_contexto: str
    top_tokens_sem_contexto: list[tuple[str, float]] = field(default_factory=list)
    top_tokens_com_contexto: list[tuple[str, float]] = field(default_factory=list)

    @property
    def context_gain(self) -> float:
        """Colapso de entropia (%) — o quão decisivo foi o contexto recuperado."""
        h_none = self.entropia_sem_contexto
        if h_none <= 1e-6:
            return 0.0
        return max(0.0, (h_none - self.entropia_com_contexto) / h_none) * 100.0


def resolve_politico(
    tipo: str, nome: str | None, politico_id: int | None
) -> tuple[int | None, str | None, int | None]:
    """Resolve (politico_id, nome_real, parlamentar_id) pelo nome ou ID."""
    if tipo == "deputado":
        with get_connection() as conn, conn.cursor() as cur:
            if politico_id:
                cur.execute(
                    "SELECT deputado_id, nome, parlamentar_id FROM parlamentares_dados "
                    "WHERE deputado_id = %s OR parlamentar_id = %s LIMIT 1",
                    (politico_id, politico_id),
                )
            elif nome:
                cur.execute(
                    "SELECT deputado_id, nome, parlamentar_id FROM parlamentares_dados "
                    "WHERE nome ILIKE %s LIMIT 1",
                    (f"%{nome}%",),
                )
            else:
                return None, None, None
            row = cur.fetchone()
        if row:
            return int(row[0]), row[1], int(row[2]) if row[2] else None
        return None, None, None
    return _find_politico_por_tipo(tipo, nome or "", politico_id)


def commit_depth(tokens: list[TokenLogprob], window: int = WINDOW_COMMIT) -> int:
    """Tokens até a prob do top-1 estabilizar acima do limiar (janela móvel)."""
    if not tokens:
        return 0
    probs = [t.prob for t in tokens]
    for i in range(len(probs)):
        lo = max(0, i - window + 1)
        if sum(probs[lo : i + 1]) / (i - lo + 1) >= THRESHOLD_COMMIT:
            return i + 1
    return len(probs)


def uncertainty_dips(tokens: list[TokenLogprob]) -> int:
    """Tokens com top-1 prob abaixo do limiar (zonas de risco de alucinação)."""
    return sum(1 for t in tokens if t.prob < THRESHOLD_DIP)


def _top_tokens(chat: ChatLogprobs, top_logprobs: int) -> list[tuple[str, float]]:
    if not chat.tokens or not chat.tokens[0].top_logprobs:
        return []
    return chat.tokens[0].top_logprobs[:top_logprobs]


def probe_question(
    client: LocalAIClient,
    model: str,
    pergunta: str,
    contexto: str,
    max_tokens: int,
    top_logprobs: int,
    nome: str,
) -> ProbeResult:
    """Compara a resposta SEM contexto vs COM contexto RAG para uma pergunta."""
    prompt_base = f"{pergunta}\nSobre: {nome}."
    sem = client.chat_with_logprobs(
        prompt_base,
        system=_SISTEMA,
        model=model,
        max_tokens=max_tokens,
        top_logprobs=top_logprobs,
    )
    com = client.chat_with_logprobs(
        f"Contexto:\n{contexto}\n\nPergunta: {pergunta}\nSobre: {nome}.\n"
        "Responda com base SOMENTE no contexto.",
        system=_SISTEMA,
        model=model,
        max_tokens=max_tokens,
        top_logprobs=top_logprobs,
    )

    def _stats(chat: ChatLogprobs) -> tuple[float, float, int, int]:
        first_prob = chat.tokens[0].prob if chat.tokens else 0.0
        first_entropy = chat.tokens[0].entropy if chat.tokens else 0.0
        return (
            first_prob,
            first_entropy,
            commit_depth(chat.tokens),
            uncertainty_dips(chat.tokens),
        )

    p1_sem, h_sem, _, _ = _stats(sem)
    p1_com, h_com, cd, dips = _stats(com)
    return ProbeResult(
        pergunta=pergunta,
        top1_sem_contexto=p1_sem,
        top1_com_contexto=p1_com,
        entropia_sem_contexto=h_sem,
        entropia_com_contexto=h_com,
        commit_depth=cd,
        dips_incerteza=dips,
        resposta_sem_contexto=sem.text.strip(),
        resposta_com_contexto=com.text.strip(),
        top_tokens_sem_contexto=_top_tokens(sem, top_logprobs),
        top_tokens_com_contexto=_top_tokens(com, top_logprobs),
    )


def build_attribution(
    dep_id: int, tipo: str
) -> tuple[list[str], list[dict[str, Any]]]:
    """Roda a recuperação real (RRF multi-query) e agrega chunks por tipo."""
    context_list, scored = search_context_multiquery(dep_id, tipo_politico=tipo)
    tipos: dict[str, dict[str, Any]] = {}
    for texto, rrf in scored:
        tipo_chunk = texto.split("]")[0].lstrip("[") if "]" in texto else "unknown"
        t = tipos.setdefault(
            tipo_chunk,
            {"tipo": tipo_chunk, "count": 0, "rrf_soma": 0.0, "rrf_max": 0.0},
        )
        t["count"] += 1
        t["rrf_soma"] += rrf
        t["rrf_max"] = max(t["rrf_max"], rrf)
    rows = sorted(tipos.values(), key=lambda x: -x["count"])
    for t in rows:
        t["rrf_media"] = round(t["rrf_soma"] / max(t["count"], 1), 4)
    return context_list, rows


def _load_best_question(
    client: LocalAIClient,
    model: str,
    perguntas: list[str],
    contexto: str,
    max_tokens: int,
    top_logprobs: int,
    nome: str,
) -> ChatLogprobs:
    """Gera a resposta com contexto da pergunta de maior context-gain."""
    melhor: ProbeResult | None = None
    for pergunta in perguntas:
        r = probe_question(
            client, model, pergunta, contexto, max_tokens, top_logprobs, nome
        )
        if melhor is None or r.context_gain > melhor.context_gain:
            melhor = r
    assert melhor is not None
    return client.chat_with_logprobs(
        f"Contexto:\n{contexto}\n\nPergunta: {melhor.pergunta}\nSobre: {nome}.\n"
        "Responda com base SOMENTE no contexto.",
        system=_SISTEMA,
        model=model,
        max_tokens=max_tokens * 2,
        top_logprobs=top_logprobs,
    )


def build_report(
    tipo: str,
    nome: str,
    dep_id: int,
    perguntas: list[str],
    results: list[ProbeResult],
    trajetoria: ChatLogprobs,
    attribution: list[dict[str, Any]],
    model: str,
) -> dict[str, Any]:
    """Monta o relatório final (resumo + trajetória + atribuição)."""
    mean_gain = sum(r.context_gain for r in results) / max(len(results), 1)
    mean_commit = sum(r.commit_depth for r in results) / max(len(results), 1)
    total_dips = sum(r.dips_incerteza for r in results)
    ganho = max(results, key=lambda r: r.context_gain) if results else None
    return {
        "tipo": tipo,
        "nome": nome,
        "politico_id": dep_id,
        "modelo": model,
        "n_perguntas": len(results),
        "eficiencia_recuperacao_pct": round(mean_gain, 1),
        "commit_depth_medio_tokens": round(mean_commit, 1),
        "dips_incerteza_total": total_dips,
        "melhor_context_gain_pct": round(ganho.context_gain, 1) if ganho else 0.0,
        "melhor_pergunta": ganho.pergunta if ganho else "",
        "perguntas": [
            {
                "pergunta": r.pergunta,
                "context_gain_pct": round(r.context_gain, 1),
                "top1_sem_contexto": round(r.top1_sem_contexto, 4),
                "top1_com_contexto": round(r.top1_com_contexto, 4),
                "entropia_sem_contexto": round(r.entropia_sem_contexto, 4),
                "entropia_com_contexto": round(r.entropia_com_contexto, 4),
                "commit_depth_tokens": r.commit_depth,
                "dips_incerteza": r.dips_incerteza,
                "resposta_sem_contexto": r.resposta_sem_contexto,
                "resposta_com_contexto": r.resposta_com_contexto,
            }
            for r in results
        ],
        "trajetoria_confianca": [
            {"token": t.token, "prob_top1": round(t.prob, 4), "entropia": round(t.entropy, 4)}
            for t in trajetoria.tokens
        ],
        "atribuicao_fonte": attribution,
    }


def _fig_context_gain(results: list[ProbeResult]) -> Any:
    import plotly.graph_objects as go

    labels = [f"Q{i + 1}" for i in range(len(results))]
    sem = [r.entropia_sem_contexto for r in results]
    com = [r.entropia_com_contexto for r in results]
    ganhos = [r.context_gain for r in results]
    fig = go.Figure(
        data=[
            go.Bar(name="Sem contexto", x=labels, y=sem, marker_color="#8fa3b8"),
            go.Bar(name="Com contexto RAG", x=labels, y=com, marker_color="#2e7d32"),
        ]
    )
    fig.update_layout(
        barmode="group",
        title="Context-gain por pergunta — entropia do 1º token (menor = mais certo)",
        xaxis_title="Pergunta",
        yaxis_title="Entropia (bits)",
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=1.02,
        y=1.0,
        xanchor="left",
        text="Δ entropia (contexto) %: " + ", ".join(f"Q{i + 1}: {g:.0f}%" for i, g in enumerate(ganhos)),
        showarrow=False,
        font=dict(size=10),
    )
    return fig


def _fig_trajetoria(trajetoria: ChatLogprobs, titulo: str) -> Any:
    import plotly.graph_objects as go

    probs = [t.prob for t in trajetoria.tokens]
    if not probs:
        return go.Figure()
    fig = go.Figure(
        data=[
            go.Scatter(
                y=probs,
                mode="lines+markers",
                name="Prob top-1",
                line=dict(color="#1565c0", width=2),
            )
        ]
    )
    fig.add_hline(y=THRESHOLD_COMMIT, line_dash="dash", line_color="#2e7d32",
                  annotation_text="commit")
    fig.add_hline(y=THRESHOLD_DIP, line_dash="dash", line_color="#c62828",
                  annotation_text="zona de risco")
    fig.update_layout(
        title=f"Trajetória de confiança — {titulo}",
        xaxis_title="Token gerado",
        yaxis_title="Probabilidade do top-1",
        yaxis=dict(range=[0, 1]),
    )
    return fig


def _fig_logit_lens(r: ProbeResult) -> Any:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=1, cols=2, subplot_titles=("Sem contexto", "Com contexto RAG"))
    for col, tokens, color in (
        (1, r.top_tokens_sem_contexto, "#8fa3b8"),
        (2, r.top_tokens_com_contexto, "#2e7d32"),
    ):
        toks = [t[0] for t in tokens][::-1]
        probs = [t[1] for t in tokens][::-1]
        fig.add_trace(
            go.Bar(x=probs, y=toks, orientation="h", marker_color=color, showlegend=False),
            row=1,
            col=col,
        )
    fig.update_layout(
        title=f"Logit lens (top-K do 1º token) — {r.pergunta[:60]}",
        height=340,
    )
    return fig


def _fig_atribuicao(attribution: list[dict[str, Any]]) -> Any:
    import plotly.graph_objects as go

    if not attribution:
        return go.Figure()
    tipos = [a["tipo"] for a in attribution]
    counts = [a["count"] for a in attribution]
    rrf = [a["rrf_media"] for a in attribution]
    fig = go.Figure(
        data=[
            go.Bar(name="Chunks no contexto", x=tipos, y=counts, marker_color="#4527a0"),
            go.Scatter(name="RRF médio", x=tipos, y=rrf, mode="lines+markers",
                       yaxis="y2", line=dict(color="#ef6c00", width=2)),
        ]
    )
    fig.update_layout(
        title="Atribuição de fonte — chunk types que venceram o RRF",
        xaxis_title="Tipo de chunk",
        yaxis_title="Chunks no contexto",
        yaxis2=dict(title="RRF médio", overlaying="y", side="right"),
    )
    return fig


def _save_fig(fig: Any, path: Path) -> None:
    try:
        fig.write_html(path)
    except Exception as exc:  # pragma: no cover
        log.warning("Falha ao salvar %s: %s", path, exc)


def _print_resumo(relatorio: dict[str, Any]) -> None:
    print("\n" + "=" * 78)
    print(" LOGIT LENS — EFICIÊNCIA DO RAG v7 ".center(78, "="))
    print(
        f" {relatorio['nome']} ({relatorio['tipo']}, ID {relatorio['politico_id']}) "
        f"| modelo: {relatorio['modelo']} ".center(78, "-")
    )
    print("=" * 78)
    print(f"  Eficiência de recuperação (colapso de entropia): "
          f"{relatorio['eficiencia_recuperacao_pct']:.1f}%")
    print(f"  Commit médio do modelo: {relatorio['commit_depth_medio_tokens']:.1f} tokens "
          f"(janela {WINDOW_COMMIT})")
    print(f"  Dips de incerteza (risco de alucinação): {relatorio['dips_incerteza_total']}")
    print(f"  Melhor pergunta: {relatorio['melhor_pergunta'][:70]} "
          f"(ganho {relatorio['melhor_context_gain_pct']:.1f}%)")
    print("-" * 78)
    for p in relatorio["perguntas"]:
        print(
            f"  [Q] {p['pergunta'][:60]}\n"
            f"      sem ctx: top1={p['top1_sem_contexto']:.2f} "
            f"entropia={p['entropia_sem_contexto']:.3f} | "
            f"com ctx: top1={p['top1_com_contexto']:.2f} "
            f"entropia={p['entropia_com_contexto']:.3f} | "
            f"ganho={p['context_gain_pct']:.0f}% | commit={p['commit_depth_tokens']} "
            f"| dips={p['dips_incerteza']}"
        )
    if relatorio["atribuicao_fonte"]:
        print("-" * 78)
        print("  FONTES que venceram o RRF:")
        for a in relatorio["atribuicao_fonte"][:8]:
            print(f"    [{a['tipo']}] {a['count']} chunks | RRF médio {a['rrf_media']:.3f}")
    print("=" * 78 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Logit lens probe — auditoria visual da eficiência do RAG v7"
    )
    parser.add_argument("--nome", type=str, help="Nome do político")
    parser.add_argument("--politico-id", type=int, help="ID do político no cargo")
    parser.add_argument(
        "--tipo",
        default="deputado",
        choices=("deputado", "senador", "governador", "prefeito", "vereador"),
        help="Cargo do político (default: deputado)",
    )
    parser.add_argument(
        "--pergunta", action="append", default=[], help="Pergunta factual (repetível)"
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--top-logprobs", type=int, default=5)
    parser.add_argument("--modelo", type=str, default=None, help="Modelo LLM")
    parser.add_argument("--no-save", action="store_true", help="Não gerar arquivos")
    args = parser.parse_args()

    model = args.modelo or RAG_LLM_MODEL
    dep_id, nome_real, _parl_id = resolve_politico(args.tipo, args.nome, args.politico_id)
    if dep_id is None or nome_real is None:
        log.error("Político não encontrado (use --nome ou --politico-id).")
        return

    try:
        from src.localai_manager import manager as localai_manager

        localai_manager.ensure_model_loaded(model)
    except Exception as exc:  # pragma: no cover
        log.warning("ensure_model_loaded falhou (%s) — continuando mesmo assim.", exc)

    client = get_localai_client()

    log.info(
        f"Recuperando contexto RAG multi-query para {nome_real} "
        f"({args.tipo} ID: {dep_id})..."
    )
    contexto, attribution = build_attribution(dep_id, args.tipo)
    if len(contexto) < 3:
        log.warning(
            f"Poucos chunks recuperados ({len(contexto)}). "
            "Indexe mais dados com ./run.sh cron-qdrant."
        )
    contexto_texto = "\n\n".join(contexto)
    log.info(f"Contexto: {len(contexto)} chunks, {len(contexto_texto)} chars.")

    perguntas = args.pergunta or PROBES_DEFAULT[args.tipo]
    results = [
        probe_question(
            client,
            model,
            p,
            contexto_texto,
            args.max_tokens,
            args.top_logprobs,
            nome_real,
        )
        for p in perguntas
    ]

    trajetoria = _load_best_question(
        client, model, perguntas, contexto_texto, args.max_tokens, args.top_logprobs, nome_real
    )

    relatorio = build_report(
        args.tipo, nome_real, dep_id, perguntas, results, trajetoria, attribution, model
    )
    _print_resumo(relatorio)

    if args.no_save:
        return

    fig_dir = OUTPUT_DIR / "logit_lens"
    fig_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"rag_eff_{args.tipo}_{dep_id}_{stamp}"
    _save_fig(_fig_context_gain(results), fig_dir / f"{base}_context_gain.html")
    _save_fig(_fig_trajetoria(trajetoria, nome_real), fig_dir / f"{base}_confianca.html")
    if results:
        melhor = max(results, key=lambda r: r.context_gain)
        _save_fig(_fig_logit_lens(melhor), fig_dir / f"{base}_logit_lens.html")
    _save_fig(_fig_atribuicao(attribution), fig_dir / f"{base}_fontes.html")

    OUTPUT_JSON.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_JSON / f"logit_lens_{args.tipo}_{dep_id}_{stamp}.json"
    json_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    log.info("Relatório JSON salvo em %s", json_path)
    log.info("HTMLs salvos em %s/", fig_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    main()
