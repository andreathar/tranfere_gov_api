"""
Regiões Administrativas do DF — Gráficos geográficos interativos.

8 gráficos usando Plotly Mapbox com basemaps CARTO (carto-positron)
para as 35 Regiões Administrativas do Distrito Federal.
"""

from __future__ import annotations

import logging

import pandas as pd
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import register_chart
from src.graphs.theme import THEME_CARD_BG, aplicar_tema

log = logging.getLogger(__name__)

_RA_QUERY = """
SELECT
    ra_codigo,
    nome_ra,
    COALESCE(populacao_est, 0) AS populacao_est,
    COALESCE(area_km2, 0) AS area_km2,
    COALESCE(densidade, 0) AS densidade,
    COALESCE(latitude, -15.78) AS latitude,
    COALESCE(longitude, -47.93) AS longitude
FROM df_regioes_administrativas
WHERE populacao_est > 0
ORDER BY populacao_est DESC;
"""

_DF_CENTER = dict(lat=-15.78, lon=-47.93)


def _load_ra_data() -> pd.DataFrame | None:
    """Load RA data from PostgreSQL. Returns DataFrame or None."""
    try:
        df: pd.DataFrame = query_df(_RA_QUERY)
        if df.empty:
            return None
        return df
    except Exception:
        log.warning("Erro ao carregar dados das RAs", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# 1. Mapa de Bolhas — População por RA
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_mapa_populacao",
    title="DF — População por Região Administrativa (Mapa)",
    description="Mapa interativo com bolhas proporcionais à população estimada de cada RA. Cor = densidade demográfica.",
    category="Distrito Federal",
)
def chart_df_ra_mapa_populacao() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados de população disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — População por Região Administrativa")

    pop_max = df["populacao_est"].max()
    marker_size = (df["populacao_est"] / pop_max * 60) + 8

    fig = go.Figure(go.Scattermapbox(
        lat=df["latitude"],
        lon=df["longitude"],
        mode="markers",
        marker=dict(
            size=marker_size,
            color=df["densidade"],
            colorscale="Viridis",
            colorbar=dict(title="Densidade", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
            opacity=0.85,
        ),
        text=df["nome_ra"],
        customdata=df[["populacao_est", "area_km2", "densidade"]].values,
        hovertemplate=(
            "<b>%{text}</b><br>"
            "População: %{customdata[0]:,.0f}<br>"
            "Área: %{customdata[1]:.1f} km²<br>"
            "Densidade: %{customdata[2]:,.0f} hab/km²"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=_DF_CENTER, zoom=10),
        paper_bgcolor=THEME_CARD_BG,
        margin=dict(l=0, r=0, t=40, b=0),
        height=550,
    )
    return aplicar_tema(fig, "DF — População por Região Administrativa")


# ---------------------------------------------------------------------------
# 2. Mapa de Bolhas — Área por RA
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_mapa_area",
    title="DF — Área Territorial por Região Administrativa (Mapa)",
    description="Mapa interativo com bolhas proporcionais à área em km² de cada RA. Cor = população total.",
    category="Distrito Federal",
)
def chart_df_ra_mapa_area() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados de área disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — Área Territorial por Região Administrativa")

    area_max = df["area_km2"].max()
    marker_size = (df["area_km2"] / area_max * 60) + 8

    fig = go.Figure(go.Scattermapbox(
        lat=df["latitude"],
        lon=df["longitude"],
        mode="markers",
        marker=dict(
            size=marker_size,
            color=df["populacao_est"],
            colorscale="Blues",
            colorbar=dict(title="População", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
            opacity=0.85,
        ),
        text=df["nome_ra"],
        customdata=df[["populacao_est", "area_km2", "densidade"]].values,
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Área: %{customdata[1]:.1f} km²<br>"
            "População: %{customdata[0]:,.0f}<br>"
            "Densidade: %{customdata[2]:,.0f} hab/km²"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=_DF_CENTER, zoom=10),
        paper_bgcolor=THEME_CARD_BG,
        margin=dict(l=0, r=0, t=40, b=0),
        height=550,
    )
    return aplicar_tema(fig, "DF — Área Territorial por Região Administrativa")


# ---------------------------------------------------------------------------
# 3. Mapa de Calor — Densidade Demográfica
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_mapa_densidade",
    title="DF — Densidade Demográfica por Região Administrativa (Mapa)",
    description="Mapa interativo com cor representando a densidade demográfica (hab/km²) de cada RA.",
    category="Distrito Federal",
)
def chart_df_ra_mapa_densidade() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados de densidade disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — Densidade Demográfica por Região Administrativa")

    marker_size = (df["populacao_est"] / df["populacao_est"].max() * 50) + 10

    fig = go.Figure(go.Scattermapbox(
        lat=df["latitude"],
        lon=df["longitude"],
        mode="markers",
        marker=dict(
            size=marker_size,
            color=df["densidade"],
            colorscale="YlOrRd",
            colorbar=dict(title="Densidade (hab/km²)", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
            opacity=0.9,
        ),
        text=df["nome_ra"],
        customdata=df[["populacao_est", "area_km2", "densidade"]].values,
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Densidade: %{customdata[2]:,.0f} hab/km²<br>"
            "População: %{customdata[0]:,.0f}<br>"
            "Área: %{customdata[1]:.1f} km²"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=_DF_CENTER, zoom=10),
        paper_bgcolor=THEME_CARD_BG,
        margin=dict(l=0, r=0, t=40, b=0),
        height=550,
    )
    return aplicar_tema(fig, "DF — Densidade Demográfica por Região Administrativa")


# ---------------------------------------------------------------------------
# 4. Ranking População (barras horizontais)
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_ranking_populacao",
    title="DF — Ranking de População por Região Administrativa",
    description="Barras horizontais com a população estimada das 35 RAs, ordenadas do maior para o menor.",
    category="Distrito Federal",
)
def chart_df_ra_ranking_populacao() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — Ranking de População por Região Administrativa")

    df = df.sort_values("populacao_est", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["populacao_est"],
        y=df["nome_ra"],
        orientation="h",
        marker=dict(
            color=df["densidade"],
            colorscale="Viridis",
            colorbar=dict(title="Densidade", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
        ),
        text=df["populacao_est"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
        textfont=dict(color="#f8fafc"),
        hovertemplate="<b>%{y}</b><br>População: %{x:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        xaxis=dict(title="População Estimada", color="#f8fafc", gridcolor="#334155"),
        yaxis=dict(color="#f8fafc", automargin=True),
        margin=dict(l=200, r=60, t=40, b=40),
        height=900,
    )
    return aplicar_tema(fig, "DF — Ranking de População por Região Administrativa")


# ---------------------------------------------------------------------------
# 5. Ranking Área (barras horizontais)
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_ranking_area",
    title="DF — Ranking de Área por Região Administrativa",
    description="Barras horizontais com a área territorial (km²) das 35 RAs.",
    category="Distrito Federal",
)
def chart_df_ra_ranking_area() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — Ranking de Área por Região Administrativa")

    df = df.sort_values("area_km2", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["area_km2"],
        y=df["nome_ra"],
        orientation="h",
        marker=dict(
            color=df["area_km2"],
            colorscale="Blues",
            colorbar=dict(title="Área (km²)", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
        ),
        text=df["area_km2"].apply(lambda v: f"{v:,.1f} km²"),
        textposition="outside",
        textfont=dict(color="#f8fafc"),
        hovertemplate="<b>%{y}</b><br>Área: %{x:,.1f} km²<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        xaxis=dict(title="Área (km²)", color="#f8fafc", gridcolor="#334155"),
        yaxis=dict(color="#f8fafc", automargin=True),
        margin=dict(l=200, r=60, t=40, b=40),
        height=900,
    )
    return aplicar_tema(fig, "DF — Ranking de Área por Região Administrativa")


# ---------------------------------------------------------------------------
# 6. Ranking Densidade (barras horizontais)
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_ranking_densidade",
    title="DF — Ranking de Densidade Demográfica por Região Administrativa",
    description="Barras horizontais com a densidade demográfica (hab/km²) das 35 RAs.",
    category="Distrito Federal",
)
def chart_df_ra_ranking_densidade() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — Ranking de Densidade por Região Administrativa")

    df = df.sort_values("densidade", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["densidade"],
        y=df["nome_ra"],
        orientation="h",
        marker=dict(
            color=df["densidade"],
            colorscale="YlOrRd",
            colorbar=dict(title="Densidade", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
        ),
        text=df["densidade"].apply(lambda v: f"{v:,.0f}"),
        textposition="outside",
        textfont=dict(color="#f8fafc"),
        hovertemplate="<b>%{y}</b><br>Densidade: %{x:,.0f} hab/km²<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        xaxis=dict(title="Densidade (hab/km²)", color="#f8fafc", gridcolor="#334155"),
        yaxis=dict(color="#f8fafc", automargin=True),
        margin=dict(l=200, r=60, t=40, b=40),
        height=900,
    )
    return aplicar_tema(fig, "DF — Ranking de Densidade por Região Administrativa")


# ---------------------------------------------------------------------------
# 7. Dispersão População vs Área (bubble chart)
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_comparativo_pop_area",
    title="DF — População vs Área por Região Administrativa",
    description="Gráfico de dispersão: população estimada vs área territorial. Tamanho da bolha = densidade.",
    category="Distrito Federal",
)
def chart_df_ra_comparativo_pop_area() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — População vs Área por Região Administrativa")

    max_dens = df["densidade"].max() if df["densidade"].max() > 0 else 1
    bubble_size = (df["densidade"] / max_dens * 40) + 5

    fig = go.Figure(go.Scatter(
        x=df["area_km2"],
        y=df["populacao_est"],
        mode="markers+text",
        marker=dict(
            size=bubble_size,
            color=df["densidade"],
            colorscale="Viridis",
            colorbar=dict(title="Densidade (hab/km²)", tickfont=dict(color="#f8fafc"),
                          title_font=dict(color="#f8fafc")),
            opacity=0.8,
            line=dict(width=1, color="#f8fafc"),
        ),
        text=df["nome_ra"],
        textposition="top center",
        textfont=dict(size=9, color="#cbd5e1"),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Área: %{x:,.1f} km²<br>"
            "População: %{y:,.0f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        xaxis=dict(title="Área (km²)", color="#f8fafc", gridcolor="#334155"),
        yaxis=dict(title="População Estimada", color="#f8fafc", gridcolor="#334155"),
        margin=dict(l=60, r=40, t=40, b=50),
        height=550,
    )
    return aplicar_tema(fig, "DF — População vs Área por Região Administrativa")


# ---------------------------------------------------------------------------
# 8. Tabela Resumo das 35 RAs
# ---------------------------------------------------------------------------

@register_chart(
    id="df_ra_tabela_resumo",
    title="DF — Tabela Resumo das 35 Regiões Administrativas",
    description="Tabela formatada com todas as métricas demográficas das Regiões Administrativas do DF.",
    category="Distrito Federal",
)
def chart_df_ra_tabela_resumo() -> go.Figure:
    df = _load_ra_data()
    if df is None:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados disponíveis", showarrow=False,
                           font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "DF — Tabela Resumo das Regiões Administrativas")

    df = df.sort_values("populacao_est", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "#"

    fig = go.Figure(go.Table(
        header=dict(
            values=["<b>RA</b>", "<b>População</b>", "<b>Área (km²)</b>",
                    "<b>Densidade (hab/km²)</b>"],
            fill_color="#1e293b",
            font=dict(color="#f8fafc", size=12),
            align="left",
            height=30,
        ),
        cells=dict(
            values=[
                df["nome_ra"],
                df["populacao_est"].apply(lambda v: f"{v:,.0f}"),
                df["area_km2"].apply(lambda v: f"{v:,.1f}"),
                df["densidade"].apply(lambda v: f"{v:,.0f}"),
            ],
            fill_color=[["#0f172a", "#1e293b"] * (len(df) // 2 + 1)][:len(df)],
            font=dict(color="#e2e8f0", size=11),
            align="left",
            height=25,
        ),
    ))

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        margin=dict(l=20, r=20, t=40, b=20),
        height=max(500, len(df) * 28 + 80),
    )
    return aplicar_tema(fig, "DF — Tabela Resumo das 35 Regiões Administrativas")
