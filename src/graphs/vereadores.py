"""Gráficos de Vereadores — Distribuição, Top Votação e UF."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import aplicar_tema

# ---------------------------------------------------------------------------
# Vereadores — Distribuição Partidária (Eleitos 2024)
# ---------------------------------------------------------------------------


@register_chart(
    id="vereadores_partidos",
    title="Distribuição Partidária dos Vereadores Eleitos",
    description=(
        "Quantidade total de vereadores eleitos nas eleições municipais 2024, "
        "agrupados por partido. Base TSE (179k+ registros)."
    ),
    category="Vereadores",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por UF",
            options=["Todas", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
                     "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ",
                     "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"],
            default="Todas",
        ),
    ],
)
def chart_vereadores_partidos(uf_filter: str = "Todas") -> go.Figure:
    where = "WHERE 1=1"
    params: list = []
    if uf_filter and uf_filter != "Todas":
        where += " AND uf = %s"
        params.append(uf_filter.upper())

    query = f"""
        SELECT
            sigla_partido AS partido,
            COUNT(*)      AS total_eleitos
        FROM v_vereadores_eleitos
        {where}
        GROUP BY sigla_partido
        ORDER BY total_eleitos DESC
        LIMIT 25
    """
    df = query_df(query, tuple(params) if params else None)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado de vereadores encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Distribuição Partidária dos Vereadores Eleitos")

    fig = px.bar(
        df,
        x="partido",
        y="total_eleitos",
        text="total_eleitos",
        color="total_eleitos",
        color_continuous_scale="Teal",
        labels={"partido": "Partido", "total_eleitos": "Vereadores Eleitos"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Partido", yaxis_title="Nº Vereadores Eleitos")
    fig = aplicar_tema(fig, "Distribuição Partidária dos Vereadores Eleitos")
    return fig


# ---------------------------------------------------------------------------
# Vereadores — Top 20 por Votos
# ---------------------------------------------------------------------------


@register_chart(
    id="vereadores_top_votos",
    title="Top 20 Vereadores Mais Votados",
    description=(
        "Os 20 vereadores com maior número de votos nas eleições municipais 2024, "
        "com município e partido. Fonte: TSE."
    ),
    category="Vereadores",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por UF",
            options=["Todas", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
                     "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ",
                     "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"],
            default="Todas",
        ),
    ],
)
def chart_vereadores_top_votos(uf_filter: str = "Todas") -> go.Figure:
    where = "WHERE 1=1"
    params: list = []
    if uf_filter and uf_filter != "Todas":
        where += " AND uf = %s"
        params.append(uf_filter.upper())

    query = f"""
        SELECT
            nome_urna,
            municipio_nome,
            uf,
            sigla_partido AS partido,
            votos
        FROM v_vereadores_eleitos
        {where}
        ORDER BY votos DESC
        LIMIT 20
    """
    df = query_df(query, tuple(params) if params else None)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Top 20 Vereadores Mais Votados")

    df["label"] = (
        df["nome_urna"] + " — " + df["municipio_nome"] + "/" + df["uf"]
    )
    df = df.sort_values("votos", ascending=True)

    fig = px.bar(
        df,
        x="votos",
        y="label",
        orientation="h",
        color="partido",
        text="votos",
        labels={"votos": "Votos", "label": "Vereador"},
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(textposition="outside", texttemplate="%{text:,.0f}")
    fig.update_layout(
        height=max(500, len(df) * 35),
        xaxis_title="Votos",
    )
    fig = aplicar_tema(fig, "Top 20 Vereadores Mais Votados")
    return fig


# ---------------------------------------------------------------------------
# Vereadores — Total por UF
# ---------------------------------------------------------------------------


@register_chart(
    id="vereadores_por_uf",
    title="Total de Vereadores Eleitos por UF",
    description=(
        "Quantidade de vereadores eleitos por estado nas eleições municipais 2024. "
        "Mostra a distribuição geográfica dos ~179k vereadores eleitos."
    ),
    category="Vereadores",
)
def chart_vereadores_por_uf() -> go.Figure:
    query = """
        SELECT
            uf,
            COUNT(*)      AS total_eleitos,
            COUNT(DISTINCT municipio_id) AS total_municipios,
            ROUND(AVG(votos)) AS media_votos
        FROM v_vereadores_eleitos
        GROUP BY uf
        ORDER BY total_eleitos DESC
    """
    df = query_df(query)
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Total de Vereadores Eleitos por UF")

    fig = px.bar(
        df,
        x="uf",
        y="total_eleitos",
        color="media_votos",
        text="total_eleitos",
        color_continuous_scale="YlOrRd",
        labels={
            "uf": "UF",
            "total_eleitos": "Vereadores Eleitos",
            "media_votos": "Média de Votos",
        },
    )
    fig.update_traces(textposition="outside", texttemplate="%{text:,.0f}")
    fig.update_layout(
        xaxis_title="UF",
        yaxis_title="Nº Vereadores Eleitos",
    )
    fig = aplicar_tema(fig, "Total de Vereadores Eleitos por UF")
    return fig
