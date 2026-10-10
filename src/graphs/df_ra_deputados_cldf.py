"""
Regiões Administrativas do DF × Deputados Distritais (CLDF) — Gráficos cruzados.

3 gráficos usando Plotly Mapbox/Bar/Table cruzando os polígonos/demografia das
35 RAs (``df_regioes_administrativas``) com o impacto legislativo e
orçamentário dos deputados distritais (``cldf_deputado_ra_impacto`` e
``cldf_ra_emendas_resumo``, populadas por
``src.enrichers.deputado_ra_impacto``).
"""

from __future__ import annotations

import logging

import pandas as pd
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import register_chart
from src.graphs.theme import THEME_CARD_BG, aplicar_tema

log = logging.getLogger(__name__)

_DF_CENTER = dict(lat=-15.78, lon=-47.93)

_RA_EMENDAS_QUERY = """
SELECT
    ra.nome_ra,
    COALESCE(ra.latitude, -15.78) AS latitude,
    COALESCE(ra.longitude, -47.93) AS longitude,
    COALESCE(res.total_emendas, 0) AS total_emendas,
    COALESCE(res.vl_emenda, 0) AS vl_emenda,
    COALESCE(res.vl_liquidado, 0) AS vl_liquidado,
    CASE WHEN COALESCE(res.vl_emenda, 0) > 0
         THEN ROUND(100.0 * res.vl_liquidado / res.vl_emenda, 1)
         ELSE 0 END AS pct_execucao,
    top.nome_candidato AS deputado_top,
    top.sigla_partido AS partido_top,
    top.total_proposicoes AS proposicoes_top
FROM df_regioes_administrativas ra
LEFT JOIN cldf_ra_emendas_resumo res ON res.ra_codigo = ra.ra_codigo
LEFT JOIN LATERAL (
    SELECT nome_candidato, sigla_partido, total_proposicoes
    FROM cldf_deputado_ra_impacto imp
    WHERE imp.ra_codigo = ra.ra_codigo
    ORDER BY total_proposicoes DESC
    LIMIT 1
) top ON true
ORDER BY vl_emenda DESC;
"""

_TOP_DEPUTADOS_QUERY = """
SELECT nome_ra, nome_candidato, sigla_partido, total_proposicoes
FROM cldf_deputado_ra_impacto
ORDER BY total_proposicoes DESC
LIMIT 20;
"""


def _load_ra_emendas() -> pd.DataFrame | None:
    """Carrega RA x emendas x deputado top. Retorna DataFrame ou None."""
    try:
        df: pd.DataFrame = query_df(_RA_EMENDAS_QUERY)
        return None if df.empty else df
    except Exception:
        log.warning("Erro ao carregar RA x emendas x deputados", exc_info=True)
        return None


def _load_top_deputados() -> pd.DataFrame | None:
    """Carrega ranking deputado x RA por proposições. Retorna DataFrame ou None."""
    try:
        df: pd.DataFrame = query_df(_TOP_DEPUTADOS_QUERY)
        return None if df.empty else df
    except Exception:
        log.warning("Erro ao carregar ranking deputado x RA", exc_info=True)
        return None


def _figura_vazia(titulo: str, mensagem: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=mensagem, showarrow=False, font=dict(size=16, color="#64748b"))
    return aplicar_tema(fig, titulo)


# ---------------------------------------------------------------------------
# 1. Mapa de bolhas — Emendas orçamentárias por RA (execução %)
# ---------------------------------------------------------------------------


@register_chart(
    id="df_ra_mapa_emendas_cldf",
    title="DF — Emendas da CLDF por Região Administrativa (Mapa)",
    description=(
        "Mapa com bolhas proporcionais ao valor total de emendas orçamentárias da "
        "Câmara Legislativa do DF por RA. Cor = % de execução (liquidado/empenhado)."
    ),
    category="Distrito Federal",
)
def chart_df_ra_mapa_emendas_cldf() -> go.Figure:
    titulo = "DF — Emendas da CLDF por Região Administrativa"
    df = _load_ra_emendas()
    if df is None or df["vl_emenda"].sum() == 0:
        return _figura_vazia(titulo, "Sem dados de emendas por RA disponíveis")

    valor_max = df["vl_emenda"].max() or 1
    marker_size = (df["vl_emenda"] / valor_max * 55) + 8

    fig = go.Figure(
        go.Scattermapbox(
            lat=df["latitude"],
            lon=df["longitude"],
            mode="markers",
            marker=dict(
                size=marker_size,
                color=df["pct_execucao"],
                colorscale="RdYlGn",
                cmin=0,
                cmax=100,
                colorbar=dict(
                    title="% Execução",
                    tickfont=dict(color="#f8fafc"),
                    title_font=dict(color="#f8fafc"),
                ),
                opacity=0.85,
            ),
            text=df["nome_ra"],
            customdata=df[
                ["vl_emenda", "vl_liquidado", "pct_execucao", "deputado_top", "partido_top"]
            ].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Emendas: R$ %{customdata[0]:,.0f}<br>"
                "Liquidado: R$ %{customdata[1]:,.0f} (%{customdata[2]:.1f}%)<br>"
                "Deputado + atuante: %{customdata[3]} (%{customdata[4]})"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=_DF_CENTER, zoom=10),
        paper_bgcolor=THEME_CARD_BG,
        margin=dict(l=0, r=0, t=40, b=0),
        height=550,
    )
    return aplicar_tema(fig, titulo)


# ---------------------------------------------------------------------------
# 2. Ranking — Deputados mais atuantes por RA (proposições)
# ---------------------------------------------------------------------------


@register_chart(
    id="df_ra_ranking_deputados_cldf",
    title="DF — Deputados Distritais Mais Atuantes por RA",
    description=(
        "Top 20 combinações deputado × RA por número de proposições que citam a "
        "região, coloridas por partido."
    ),
    category="Distrito Federal",
)
def chart_df_ra_ranking_deputados_cldf() -> go.Figure:
    titulo = "DF — Deputados Distritais Mais Atuantes por RA"
    df = _load_top_deputados()
    if df is None:
        return _figura_vazia(titulo, "Sem dados de proposições por RA disponíveis")

    df = df.sort_values("total_proposicoes", ascending=True)
    rotulo = df["nome_candidato"] + " — " + df["nome_ra"]

    fig = go.Figure(
        go.Bar(
            x=df["total_proposicoes"],
            y=rotulo,
            orientation="h",
            marker=dict(
                color=df["sigla_partido"].astype("category").cat.codes, colorscale="Turbo"
            ),
            text=df["sigla_partido"],
            textposition="outside",
            textfont=dict(color="#f8fafc"),
            hovertemplate="<b>%{y}</b><br>Proposições: %{x}<br>Partido: %{text}<extra></extra>",
        )
    )

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        xaxis=dict(title="Total de Proposições", color="#f8fafc", gridcolor="#334155"),
        yaxis=dict(color="#f8fafc", automargin=True),
        margin=dict(l=260, r=60, t=40, b=40),
        height=700,
    )
    return aplicar_tema(fig, titulo)


# ---------------------------------------------------------------------------
# 3. Tabela cruzada — RA × Emendas × Deputado mais atuante
# ---------------------------------------------------------------------------


@register_chart(
    id="df_ra_tabela_emendas_deputados",
    title="DF — Tabela Cruzada: RA, Emendas CLDF e Deputado Mais Atuante",
    description=(
        "Tabela com valor de emendas orçamentárias, % de execução e o deputado "
        "distrital mais atuante (por proposições) em cada RA."
    ),
    category="Distrito Federal",
)
def chart_df_ra_tabela_emendas_deputados() -> go.Figure:
    titulo = "DF — RA × Emendas CLDF × Deputado Mais Atuante"
    df = _load_ra_emendas()
    if df is None:
        return _figura_vazia(titulo, "Sem dados disponíveis")

    df = df.sort_values("vl_emenda", ascending=False).reset_index(drop=True)

    fig = go.Figure(
        go.Table(
            header=dict(
                values=[
                    "<b>RA</b>",
                    "<b>Emendas (R$)</b>",
                    "<b>% Execução</b>",
                    "<b>Deputado Mais Atuante</b>",
                    "<b>Partido</b>",
                ],
                fill_color="#1e293b",
                font=dict(color="#f8fafc", size=12),
                align="left",
                height=30,
            ),
            cells=dict(
                values=[
                    df["nome_ra"],
                    df["vl_emenda"].apply(lambda v: f"{v:,.0f}"),
                    df["pct_execucao"].apply(lambda v: f"{v:.1f}%"),
                    df["deputado_top"].fillna("—"),
                    df["partido_top"].fillna("—"),
                ],
                fill_color=[["#0f172a", "#1e293b"] * (len(df) // 2 + 1)][: len(df)],
                font=dict(color="#e2e8f0", size=11),
                align="left",
                height=25,
            ),
        )
    )

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        margin=dict(l=20, r=20, t=40, b=20),
        height=max(500, len(df) * 28 + 80),
    )
    return aplicar_tema(fig, titulo)
