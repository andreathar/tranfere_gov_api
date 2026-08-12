"""Gráficos de Senadores — Atividade Legislativa, Partidos e UF."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import aplicar_tema

# ---------------------------------------------------------------------------
# Senadores — Ranking por Atividade Legislativa
# ---------------------------------------------------------------------------


@register_chart(
    id="senadores_atividade",
    title="Ranking de Senadores por Atividade Legislativa",
    description=(
        "Total de votações + relatorias dos 81 senadores em exercício. "
        "Dados da API Senado (senadores_dados)."
    ),
    category="Senadores",
    controls=[
        ControlSpec(
            id="limit",
            label="Nº de Senadores",
            options=["10", "20", "40", "81"],
            default="20",
        ),
    ],
)
def chart_senadores_atividade(limit: str = "20") -> go.Figure:
    n = int(limit)
    query = """
        SELECT
            nome_parlamentar,
            sigla_partido,
            uf,
            COALESCE(total_votacoes, 0)  AS total_votacoes,
            COALESCE(total_relatorias, 0) AS total_relatorias,
            COALESCE(total_votacoes, 0) + COALESCE(total_relatorias, 0) AS atividade_total
        FROM senadores_dados
        ORDER BY atividade_total DESC
        LIMIT %s
    """
    df = query_df(query, (n,))
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado de senadores encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Ranking de Senadores por Atividade Legislativa")

    df["label"] = df["nome_parlamentar"] + " (" + df["sigla_partido"] + ")"
    df = df.sort_values("atividade_total", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["label"],
        x=df["total_relatorias"],
        name="Relatorias",
        orientation="h",
        marker=dict(color="#8b5cf6"),
    ))
    fig.add_trace(go.Bar(
        y=df["label"],
        x=df["total_votacoes"],
        name="Votações",
        orientation="h",
        marker=dict(color="#3b82f6"),
    ))

    chart_height = max(400, len(df) * 30)
    fig.update_layout(
        barmode="stack",
        height=chart_height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig = aplicar_tema(fig, "Ranking de Senadores por Atividade Legislativa")
    return fig


# ---------------------------------------------------------------------------
# Senadores — Distribuição Partidária
# ---------------------------------------------------------------------------


@register_chart(
    id="senadores_partidos",
    title="Distribuição Partidária dos Senadores",
    description=(
        "Quantidade de senadores em exercício por partido. "
        "Fonte: senadores_dados (API Senado)."
    ),
    category="Senadores",
)
def chart_senadores_partidos() -> go.Figure:
    query = """
        SELECT
            sigla_partido,
            COUNT(*) AS total
        FROM senadores_dados
        GROUP BY sigla_partido
        ORDER BY total DESC
    """
    df = query_df(query)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Distribuição Partidária dos Senadores")

    fig = px.pie(
        df,
        names="sigla_partido",
        values="total",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig.update_traces(textinfo="percent+label", textfont_size=11)
    fig = aplicar_tema(fig, "Distribuição Partidária dos Senadores")
    return fig


# ---------------------------------------------------------------------------
# Senadores — Distribuição por UF
# ---------------------------------------------------------------------------


@register_chart(
    id="senadores_por_uf",
    title="Senadores em Exercício por UF",
    description=(
        "Contagem de senadores por estado, mostrando a distribuição geográfica "
        "dos 81 senadores (3 por estado)."
    ),
    category="Senadores",
)
def chart_senadores_por_uf() -> go.Figure:
    query = """
        SELECT
            uf,
            COUNT(*) AS total,
            ROUND(AVG(COALESCE(total_votacoes, 0) + COALESCE(total_relatorias, 0))) AS media_atividade
        FROM senadores_dados
        GROUP BY uf
        ORDER BY total DESC, uf
    """
    df = query_df(query)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Senadores em Exercício por UF")

    fig = px.bar(
        df,
        x="uf",
        y="total",
        color="media_atividade",
        text="total",
        color_continuous_scale="Blues",
        labels={"uf": "UF", "total": "Senadores", "media_atividade": "Média Atividade"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="UF", yaxis_title="Nº Senadores")
    fig = aplicar_tema(fig, "Senadores em Exercício por UF")
    return fig
