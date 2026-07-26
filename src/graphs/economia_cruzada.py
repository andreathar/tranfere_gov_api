"""Charts de Análise Econômica Avançada Cruzando Emendas Pix, IBGE e Finanças (SICONFI).

Este módulo contém gráficos avançados que exploram a relação entre o volume
de Emendas Pix recebidas e os indicadores socioeconômicos reais dos municípios.
"""

from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import THEME_GRID, THEME_TEXT, TODAS_UFS, aplicar_tema


@register_chart(
    id="econ_cruz_receita_vs_emenda",
    title="Análise: Receitas Correntes vs Emendas Pix per Capita",
    description=(
        "Scatter plot que cruza a Receita Corrente Municipal per capita com "
        "o volume de Emendas Pix per capita recebidas. Tamanho da bolha "
        "representa a população. Ajuda a responder: O Pix vai para "
        "municípios mais pobres ou mais ricos?"
    ),
    category="Análise Econômica (Avançada)",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS",
        ),
    ],
)
def chart_econ_cruz_receita_vs_emenda(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome, m.uf, m.regiao, m.populacao,
            COALESCE(mf.receitas_correntes, 0) AS receitas_correntes,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            (COALESCE(mf.receitas_correntes, 0) / NULLIF(m.populacao, 0)) AS receita_pc,
            (COALESCE(SUM(v.valor_total), 0) / NULLIF(m.populacao, 0)) AS emenda_pc
        FROM municipios_ibge m
        JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        LEFT JOIN v_emendas_unificadas v ON m.municipio_id = v.beneficiario_ibge
        WHERE m.populacao > 5000
          AND mf.receitas_correntes > 0
          AND (%s = 'TODOS' OR m.regiao = %s)
        GROUP BY m.nome, m.uf, m.regiao, m.populacao, mf.receitas_correntes
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY emenda_pc DESC
        LIMIT 200;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados insuficientes para este cruzamento",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Análise: Receitas Correntes vs Emendas Pix per Capita")

    # Ajuste de tipos
    import pandas as pd

    df["receita_pc"] = pd.to_numeric(df["receita_pc"], errors="coerce").fillna(0)
    df["emenda_pc"] = pd.to_numeric(df["emenda_pc"], errors="coerce").fillna(0)
    df["populacao"] = df["populacao"].clip(lower=1)

    REGIAO_CORES = {
        "Norte": "#0ea5e9",
        "Nordeste": "#f59e0b",
        "Sudeste": "#22c55e",
        "Sul": "#a855f7",
        "Centro-Oeste": "#ef4444",
    }

    fig = go.Figure()
    for regiao in df["regiao"].dropna().unique():
        dfr = df[df["regiao"] == regiao]
        fig.add_trace(
            go.Scatter(
                x=dfr["receita_pc"],
                y=dfr["emenda_pc"],
                mode="markers",
                name=regiao,
                text=dfr["nome"] + " (" + dfr["uf"] + ")",
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Receita Municipal per capita: R$ %{x:,.2f}<br>"
                    "Emenda Pix per capita: R$ %{y:,.2f}<br>"
                    "<extra></extra>"
                ),
                marker=dict(
                    size=np.sqrt(dfr["populacao"] / dfr["populacao"].max()) * 40 + 5,
                    color=REGIAO_CORES.get(regiao, "#64748b"),
                    line=dict(width=1, color="#1e293b"),
                    opacity=0.8,
                ),
            )
        )

    fig.update_layout(
        xaxis=dict(
            title="Receita Corrente do Município per capita (R$)",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
            type="log",
        ),
        yaxis=dict(
            title="Emendas Pix per capita recebidas (R$)",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
            type="log",
        ),
        legend=dict(title="Região", font=dict(color=THEME_TEXT)),
    )
    return aplicar_tema(fig, "Análise: Receitas Correntes vs Emendas Pix per Capita")


@register_chart(
    id="econ_cruz_investimento_vs_emendas",
    title="Impacto do Pix nos Investimentos Municipais",
    description=(
        "Compara o volume total de Despesas de Capital (Investimentos declarados "
        "ao Tesouro/SICONFI) com o volume total de Emendas Pix recebidas."
    ),
    category="Análise Econômica (Avançada)",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_econ_cruz_investimento_vs_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome, m.uf, m.populacao,
            COALESCE(mf.despesas_capital, 0) AS investimentos_municipio,
            COALESCE(SUM(v.valor_total), 0) AS emendas_recebidas,
            (COALESCE(SUM(v.valor_total), 0) / NULLIF(mf.despesas_capital, 0)) * 100 AS pct_financiamento
        FROM municipios_ibge m
        JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        JOIN v_emendas_unificadas v ON m.municipio_id = v.beneficiario_ibge
        WHERE mf.despesas_capital > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.nome, m.uf, m.populacao, mf.despesas_capital
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY investimentos_municipio DESC
        LIMIT 100;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados insuficientes para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Impacto do Pix nos Investimentos Municipais")

    import pandas as pd

    df["investimentos_municipio"] = pd.to_numeric(df["investimentos_municipio"], errors="coerce")
    df["emendas_recebidas"] = pd.to_numeric(df["emendas_recebidas"], errors="coerce")
    df["populacao"] = pd.to_numeric(df["populacao"], errors="coerce").clip(lower=1)
    df["pct_financiamento"] = pd.to_numeric(df["pct_financiamento"], errors="coerce").fillna(0)

    # Cap percentage at 200% for color scaling
    df["cor_intensidade"] = df["pct_financiamento"].clip(upper=200)

    fig = px.scatter(
        df,
        x="investimentos_municipio",
        y="emendas_recebidas",
        size="populacao",
        color="cor_intensidade",
        hover_name="nome",
        hover_data={
            "uf": True,
            "investimentos_municipio": ":,.0f",
            "emendas_recebidas": ":,.0f",
            "pct_financiamento": ":.1f",
            "cor_intensidade": False,
        },
        color_continuous_scale="Viridis",
        labels={
            "investimentos_municipio": "Investimentos Próprios (Desp. Capital R$)",
            "emendas_recebidas": "Total Emendas Pix (R$)",
            "cor_intensidade": "Impacto (%)",
        },
    )

    fig.update_layout(
        xaxis=dict(type="log", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(type="log", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        coloraxis_colorbar=dict(
            title=dict(text="% Emendas sobre<br>Investimento", font=dict(color=THEME_TEXT)),
            tickfont=dict(color=THEME_TEXT),
        ),
    )
    return aplicar_tema(fig, "Impacto do Pix nos Investimentos Municipais")
