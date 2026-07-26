"""Charts 29-30 — Prefeitos: Emendas Per Capita e Partidos."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, THEME_CARD_BG, THEME_GRID, THEME_TEXT, aplicar_tema


# ---------------------------------------------------------------------------
# Chart 29 — Ranking de Prefeituras: Emendas Per Capita
# ---------------------------------------------------------------------------

@register_chart(
    id="ranking_prefeituras_emendas_per_capita",
    title="29. Ranking de Prefeituras: Emendas Per Capita",
    description=(
        "Ranking dos 30 municípios com maior valor de emendas parlamentares per capita. "
        "Cruza dados do TransfereGov com a população estimada do IBGE."
    ),
    category="Prefeitos",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_ranking_prefeituras_emendas_per_capita(
    uf_filter: str = "TODOS",
) -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            m.populacao,
            COUNT(*) AS total_emendas,
            SUM(v.valor_total) AS valor_total_emendas,
            ROUND(
                SUM(v.valor_total) / NULLIF(m.populacao, 0),
                4
            ) AS emendas_per_capita
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m
            ON v.beneficiario_ibge = m.municipio_id
        WHERE m.populacao > 0
          AND v.beneficiario_ibge IS NOT NULL
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.municipio_id, m.nome, m.uf, m.populacao
        HAVING SUM(v.valor_total) > 0
        ORDER BY emendas_per_capita DESC
        LIMIT 30;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "29. Ranking de Prefeituras: Emendas Per Capita",
        )

    chart_height = max(600, len(df) * 25)

    fig = px.bar(
        df,
        x="emendas_per_capita",
        y="municipio",
        orientation="h",
        color="emendas_per_capita",
        color_continuous_scale=["#1e293b", "#22d3ee", "#22c55e"],
        text_auto=".4f",
        labels={
            "emendas_per_capita": "Emendas Per Capita (R$)",
            "municipio": "Município",
            "total_emendas": "Qtd. Emendas",
            "valor_total_emendas": "Valor Total (R$)",
            "populacao": "População",
            "uf": "UF",
        },
        hover_data=["total_emendas", "valor_total_emendas", "populacao", "uf"],
        template="plotly_dark",
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        height=chart_height,
        coloraxis_colorbar=dict(title="R$/hab"),
    )

    return aplicar_tema(
        fig,
        "29. Ranking de Prefeituras: Emendas Per Capita",
        altura=chart_height,
    )


# ---------------------------------------------------------------------------
# Chart 30 — Total de Emendas por Partido (Prefeitos)
# ---------------------------------------------------------------------------

@register_chart(
    id="prefeitos_emendas_por_partido",
    title="30. Total de Emendas por Partido (Prefeitos)",
    description=(
        "Volume total de emendas recebidas por município, agregado pelo partido "
        "do prefeito eleito em 2024."
    ),
    category="Prefeitos",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_prefeitos_emendas_por_partido(
    uf_filter: str = "TODOS",
) -> go.Figure:
    query = """
        SELECT
            pd.sigla_partido AS partido,
            COUNT(DISTINCT pd.municipio_id) AS total_municipios,
            COALESCE(SUM(em.valor_total), 0) AS total_emendas
        FROM prefeitos_dados pd
        LEFT JOIN (
            SELECT
                bm.municipio_id,
                SUM(pa.valor_total) AS valor_total
            FROM planos_acao pa
            JOIN beneficiarios b
                ON pa.beneficiario_id = b.beneficiario_id
            JOIN beneficiario_ibge_map bm
                ON b.beneficiario_id = bm.beneficiario_id
            GROUP BY bm.municipio_id
        ) em ON pd.municipio_id = em.municipio_id
        WHERE (%s = 'TODOS' OR pd.uf = %s)
        GROUP BY pd.sigla_partido
        HAVING COALESCE(SUM(em.valor_total), 0) > 0
        ORDER BY total_emendas DESC;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "30. Total de Emendas por Partido (Prefeitos)",
        )

    import pandas as pd
    df["total_emendas"] = pd.to_numeric(df["total_emendas"], errors="coerce").fillna(0.0)

    fig = px.bar(
        df,
        x="partido",
        y="total_emendas",
        color="partido",
        color_discrete_sequence=px.colors.qualitative.D3,
        text_auto=".2s",
        labels={
            "partido": "Partido",
            "total_emendas": "Total de Emendas (R$)",
            "total_municipios": "Municípios",
        },
        hover_data=["total_municipios"],
        template="plotly_dark",
    )
    fig.update_layout(
        height=500,
        xaxis={"categoryorder": "total descending"},
        showlegend=False,
    )

    return aplicar_tema(
        fig,
        "30. Total de Emendas por Partido (Prefeitos)",
        altura=500,
    )
