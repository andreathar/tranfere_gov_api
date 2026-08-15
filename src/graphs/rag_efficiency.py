"""Chart — Eficiência do RAG v7 (visão investidor).

Lê as tabelas ``rag_efficiency_runs`` e ``rag_efficiency_metrics``
(migration_040) e apresenta, de forma visual, o quão eficiente o pipeline
RAG é ao recuperar dados de políticos (hit rate / MRR) e ao gerar respostas
fiéis ao contexto recuperado (faithfulness / utilização de contexto), além
da profundidade de emergência medida offline pelo Logit Lens.

Gráficos:
  1. rag_eff_score_timeline           — evolução do score composto por run
  2. rag_eff_retrieval_vs_faithfulness — quadrante recuperação × fidelidade (último run)
  3. rag_eff_emergence_depth          — histograma da camada de emergência (Logit Lens)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import register_chart
from src.graphs.theme import aplicar_tema

_EMPTY_MSG = (
    "Sem dados de eficiência RAG ainda. "
    "Rode ./run.sh rag-efficiency para gerar o primeiro run."
)
_EMPTY_EMERGENCE_MSG = (
    "Sem medições de emergência (Logit Lens) ainda. "
    "Rode ./run.sh logit-lens-runner --run-id 1 após ./run.sh rag-efficiency."
)
_QUADRANTE = 0.7  # 70% — bom na recuperação e na fidelidade
_CORES_TIPO: dict[str, str] = {
    "deputado": "#1565c0",
    "senador": "#4527a0",
    "governador": "#2e7d32",
    "prefeito": "#ef6c00",
    "vereador": "#c62828",
}
_COR_TIPO_PADRAO = "#546e7a"


def _s(valor: object) -> str:
    """Converte valor de linha itertuples em texto seguro (None -> '')."""
    return "" if valor is None else str(valor)


def _fig_vazio(mensagem: str) -> go.Figure:
    """Figura de estado vazio com mensagem centralizada."""
    fig = go.Figure()
    fig.add_annotation(
        text=mensagem,
        showarrow=False,
        font={"size": 15, "color": "#90a4ae"},
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
    )
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        height=350,
    )
    return fig


@register_chart(
    id="rag_eff_score_timeline",
    title="Eficiência RAG ao longo do tempo",
    description=(
        "Score composto (0-100) por execução do coletor: 40% recuperação "
        "(hit rate), 40% fidelidade da geração e 20% utilização de contexto. "
        "A linha contínua é o score global; as tracejadas, recuperação e "
        "fidelidade (0-100). Linha de referência em 70 = mínimo de aprovação."
    ),
    category="Auditoria",
)
def chart_rag_eff_score_timeline() -> go.Figure:
    """Evolução do score de eficiência do RAG entre execuções."""
    df = query_df(
        """
        SELECT id, run_date, model_name, golden_set_version, total_questions,
               global_efficiency_score, avg_retrieval_hit_rate,
               avg_generation_faithfulness
        FROM rag_efficiency_runs
        ORDER BY run_date ASC
        """
    )
    if df.empty:
        return _fig_vazio(_EMPTY_MSG)

    df["run_date"] = pd.to_datetime(df["run_date"])
    for col in (
        "global_efficiency_score",
        "avg_retrieval_hit_rate",
        "avg_generation_faithfulness",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    labels = [d.strftime("%d/%m %H:%M") for d in df["run_date"]]

    hover = [
        (
            f"Run #{r.id} · {r.run_date:%d/%m/%Y %H:%M}<br>"
            f"Modelo: {r.model_name}<br>Versão golden: {r.golden_set_version}<br>"
            f"Perguntas: {r.total_questions}"
        )
        for r in df.itertuples(index=False)
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=df["avg_retrieval_hit_rate"] * 100,
            mode="lines+markers",
            name="Recuperação (hit rate)",
            line={"color": "#1565c0", "width": 2, "dash": "dot"},
            hovertemplate="%{y:.1f}%<extra>%{text}</extra>",
            text=hover,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=df["avg_generation_faithfulness"] * 100,
            mode="lines+markers",
            name="Fidelidade (faithfulness)",
            line={"color": "#2e7d32", "width": 2, "dash": "dot"},
            hovertemplate="%{y:.1f}%<extra>%{text}</extra>",
            text=hover,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=df["global_efficiency_score"],
            mode="lines+markers",
            name="Score global",
            line={"color": "#c62828", "width": 3},
            marker={"size": 9},
            hovertemplate="%{y:.1f}/100<extra>%{text}</extra>",
            text=hover,
        )
    )
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="#90a4ae",
        annotation_text="mín. aprovação (70)",
        annotation_position="top left",
        annotation_font_color="#90a4ae",
    )
    fig.update_layout(
        xaxis_title="Execução (run)",
        yaxis_title="Score (0-100)",
        yaxis={"range": [0, 105]},
        legend={"orientation": "h", "y": -0.25},
    )
    return aplicar_tema(fig, "Eficiência RAG ao longo do tempo")


@register_chart(
    id="rag_eff_retrieval_vs_faithfulness",
    title="Recuperação vs Fidelidade (último run)",
    description=(
        "Uma bolha por pergunta do último run de eficiência: eixo X = hit "
        "rate da recuperação (o contexto certo foi encontrado no Qdrant), "
        "eixo Y = fidelidade da resposta (o modelo usou o contexto certo), "
        "tamanho = utilização de contexto. O quadrante superior direito é o "
        "ideal (recuperação ≥ 70% E fidelidade ≥ 70%)."
    ),
    category="Auditoria",
)
def chart_rag_eff_retrieval_vs_faithfulness() -> go.Figure:
    """Dispersão recuperação × fidelidade por pergunta (último run)."""
    df = query_df(
        """
        SELECT politico_id, tipo_politico, question, expected_answer,
               actual_answer, hit_rate_at_k, mrr_at_k, faithfulness_score,
               context_utilization_score
        FROM rag_efficiency_metrics
        WHERE run_id = (SELECT MAX(id) FROM rag_efficiency_runs)
        ORDER BY hit_rate_at_k DESC, faithfulness_score DESC
        """
    )
    if df.empty:
        return _fig_vazio(_EMPTY_MSG)

    df["hit_rate_at_k"] = pd.to_numeric(df["hit_rate_at_k"], errors="coerce")
    df["faithfulness_score"] = pd.to_numeric(df["faithfulness_score"], errors="coerce")
    df["context_utilization_score"] = pd.to_numeric(
        df["context_utilization_score"], errors="coerce"
    ).fillna(0.0)

    hover = [
        (
            f"{_s(r.tipo_politico)} #{r.politico_id}<br>"
            f"<b>{_s(r.question)}</b><br>Esperado: {_s(r.expected_answer)}<br>"
            f"Resposta: {_s(r.actual_answer)[:80]}<br>"
            f"MRR: {_s(r.mrr_at_k) if pd.notna(r.mrr_at_k) else '-'}"
        )
        for r in df.itertuples(index=False)
    ]

    fig = go.Figure()
    tipos = [t for t in df["tipo_politico"].dropna().unique() if t]
    for tipo in tipos:
        sub = df[df["tipo_politico"] == tipo]
        fig.add_trace(
            go.Scatter(
                x=sub["hit_rate_at_k"],
                y=sub["faithfulness_score"],
                mode="markers",
                name=str(tipo),
                marker={
                    "size": sub["context_utilization_score"] * 45 + 12,
                    "sizemode": "area",
                    "sizemin": 8,
                    "color": _CORES_TIPO.get(str(tipo), _COR_TIPO_PADRAO),
                    "opacity": 0.8,
                    "line": {"color": "white", "width": 1},
                },
                hovertemplate="%{text}<extra>hit %{x:.2f} · fidelidade %{y:.2f}</extra>",
                text=hover,
            )
        )

    total = len(df)
    top_right = int(
        ((df["hit_rate_at_k"] >= _QUADRANTE) & (df["faithfulness_score"] >= _QUADRANTE)).sum()
    )
    pct = 100.0 * top_right / total if total else 0.0
    fig.add_vline(
        x=_QUADRANTE,
        line_dash="dash",
        line_color="#8fa3b8",
        annotation_text="recuperação ≥ 70%",
        annotation_position="top left",
    )
    fig.add_hline(
        y=_QUADRANTE,
        line_dash="dash",
        line_color="#8fa3b8",
        annotation_text="fidelidade ≥ 70%",
        annotation_position="top right",
    )
    fig.add_annotation(
        text=f"{total} perguntas · {pct:.0f}% no quadrante ideal (superior direito)",
        xref="paper",
        yref="paper",
        x=0.02,
        y=1.06,
        showarrow=False,
        font={"size": 12, "color": "#2e7d32"},
    )
    fig.update_layout(
        xaxis_title="Recuperação (hit rate 0-1)",
        yaxis_title="Fidelidade (faithfulness 0-1)",
        xaxis={"range": [0, 1.05]},
        yaxis={"range": [0, 1.05]},
        legend={"orientation": "h", "y": -0.25},
    )
    return aplicar_tema(fig, "Recuperação vs Fidelidade (último run)")


@register_chart(
    id="rag_eff_emergence_depth",
    title="Profundidade de emergência (Logit Lens)",
    description=(
        "Histograma da camada (layer) do modelo Llama em que o token da "
        "resposta esperada emerge, medido offline pelo Logit Lens. Camada "
        "menor = o modelo 'sabe' a resposta cedo a partir do contexto "
        "recuperado (grounding forte); camada alta/tardia = resposta fraca "
        "ou adivinhada (risco de alucinação)."
    ),
    category="Auditoria",
)
def chart_rag_eff_emergence_depth() -> go.Figure:
    """Distribuição da camada de emergência do token alvo (último run)."""
    df = query_df(
        """
        SELECT emergence_layer, total_layers, target_token_prob, question,
               tipo_politico
        FROM rag_efficiency_metrics
        WHERE emergence_layer IS NOT NULL
        ORDER BY id DESC
        LIMIT 100
        """
    )
    if df.empty:
        return _fig_vazio(_EMPTY_EMERGENCE_MSG)

    df["emergence_layer"] = pd.to_numeric(df["emergence_layer"], errors="coerce")
    df["target_token_prob"] = pd.to_numeric(df["target_token_prob"], errors="coerce")
    mediana = float(df["emergence_layer"].median())

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=df["emergence_layer"],
            nbinsx=16,
            marker_color="#4527a0",
            hovertemplate="Camada %{x} · %{y} perguntas<extra></extra>",
        )
    )
    fig.add_vline(
        x=mediana,
        line_dash="dash",
        line_color="#c62828",
        annotation_text=f"mediana L{mediana:.0f}",
        annotation_position="top right",
    )
    fig.update_layout(
        xaxis_title="Camada de emergência (layer)",
        yaxis_title="Nº de perguntas",
        bargap=0.05,
    )
    return aplicar_tema(fig, "Profundidade de emergência (Logit Lens)")
