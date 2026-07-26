"""Charts 35-40 — Análise Financeira Municipal (SICONFI/DCA).

Gráficos de patrimônio, endividamento, eficiência fiscal, resultado
orçamentário e composição de receitas/despesas.
"""
from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import THEME_GRID, THEME_TEXT, TODAS_UFS, aplicar_tema

# ---------------------------------------------------------------------------
# Chart 35 — Evolução do Patrimônio Líquido por UF
# ---------------------------------------------------------------------------

@register_chart(
    id="fin_evolucao_patrimonio",
    title="35. Evolução do Patrimônio Líquido por UF",
    description=(
        "Série temporal do patrimônio líquido médio dos municípios por estado. "
        "Indica a capacidade acumulada de geração de riqueza e solvência do setor público municipal."
    ),
    category="Finanças Municipais",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_fin_evolucao_patrimonio(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.uf,
            mf.exercicio,
            AVG(mf.receitas_correntes) AS media_receitas,
            COUNT(*) AS num_municipios
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes IS NOT NULL
          AND mf.receitas_correntes > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.uf, mf.exercicio
        HAVING COUNT(*) >= 3
        ORDER BY mf.exercicio, m.uf;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de receitas disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "35. Evolução das Receitas Correntes por UF")

    df["exercicio"] = df["exercicio"].astype(str)

    if uf_filter == "TODOS":
        top_ufs = (
            df.groupby("uf")["media_receitas"]
            .mean()
            .nlargest(10)
            .index.tolist()
        )
        df = df[df["uf"].isin(top_ufs)]

    cores_ufs = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel
    df_pivot = df.pivot_table(index="exercicio", columns="uf", values="media_receitas")

    fig = go.Figure()
    for i, uf in enumerate(df_pivot.columns):
        fig.add_trace(go.Scatter(
            x=df_pivot.index,
            y=df_pivot[uf],
            mode="lines+markers",
            name=uf,
            line=dict(color=cores_ufs[i % len(cores_ufs)], width=2),
            marker=dict(size=6),
            hovertemplate=(
                f"<b>{uf}</b><br>"
                "Exercício: %{x}<br>"
                "Receitas correntes média: R$ %{y:,.0f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis=dict(title="Exercício", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="Receitas Correntes Média (R$)", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        legend=dict(font=dict(size=10)),
    )
    return aplicar_tema(fig, "35. Evolução das Receitas Correntes por UF", altura=500)


# ---------------------------------------------------------------------------
# Chart 36 — Endividamento Municipal: Dívida Passiva vs Ativo Imobilizado
# ---------------------------------------------------------------------------

@register_chart(
    id="fin_endividamento_ativo",
    title="36. Endividamento: Dívida Passiva vs Ativo Imobilizado",
    description=(
        "Scatter plot cruzando o passivo consolidado com o ativo imobilizado dos municípios. "
        "Municípios acima da diagonal possuem mais dívida do que bens — risco de insolvência."
    ),
    category="Finanças Municipais",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_fin_endividamento_ativo(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            m.uf,
            m.regiao,
            m.populacao,
            COALESCE(mf.despesas_correntes, 0) AS despesas_correntes,
            COALESCE(mf.despesas_capital, 0) AS despesas_capital,
            COALESCE(mf.receitas_correntes, 0) AS receitas_correntes
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.despesas_correntes > 0
          AND mf.despesas_capital > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY mf.despesas_correntes DESC
        LIMIT 120;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de endividamento disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "36. Endividamento: Dívida Passiva vs Ativo Imobilizado")

    df["populacao"] = df["populacao"].clip(lower=1)
    df["ratio_desp_cap"] = np.where(
        df["despesas_correntes"] > 0,
        df["despesas_capital"] / df["despesas_correntes"],
        0,
    )
    df["risco"] = df["ratio_desp_cap"].apply(
        lambda x: "🟢 Equilibrado" if 0.1 < x < 0.5 else ("🟡 Muito Corrente" if x <= 0.1 else "🔴 Alto Capital")
    )

    fig = px.scatter(
        df,
        x="despesas_correntes",
        y="despesas_capital",
        size="populacao",
        color="risco",
        hover_name="municipio_uf",
        hover_data={
            "ratio_desp_cap": ":.2f",
            "receitas_correntes": ":,.0f",
            "populacao": ":,.0f",
            "risco": False,
        },
        color_discrete_map={
            "🟢 Equilibrado": "#22c55e",
            "🟡 Muito Corrente": "#f59e0b",
            "🔴 Alto Capital": "#ef4444",
        },
        labels={
            "despesas_correntes": "Despesas Correntes (R$)",
            "despesas_capital": "Despesas de Capital (R$)",
        },
        size_max=35,
    )

    max_val = max(df["despesas_correntes"].max(), df["despesas_capital"].max(), 1)
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val * 0.5],
        mode="lines",
        name="Referência 50%",
        line=dict(color="#ef4444", width=1, dash="dash"),
        showlegend=True,
    ))

    fig.add_annotation(
        x=max_val * 0.1, y=max_val * 0.05,
        text="<b>Investimento Baixo</b><br>Capital < 10% Corrente",
        showarrow=False, font=dict(size=10, color="#f59e0b"),
        bgcolor="rgba(245,158,11,0.1)", borderwidth=0,
    )
    fig.add_annotation(
        x=max_val * 0.1, y=max_val * 0.4,
        text="<b>Investimento Forte</b><br>Capital > 40% Corrente",
        showarrow=False, font=dict(size=10, color="#22c55e"),
        bgcolor="rgba(34,197,94,0.1)", borderwidth=0,
    )

    return aplicar_tema(fig, "36. Endividamento: Dívida Passiva vs Ativo Imobilizado", 550)


# ---------------------------------------------------------------------------
# Chart 37 — Eficiência Fiscal: Despesas Financeiras / Receitas Correntes
# ---------------------------------------------------------------------------

@register_chart(
    id="fin_eficiencia_fiscal",
    title="37. Eficiência Fiscal: Custo da Dívida por Estado",
    description=(
        "Razão entre despesas financeiras (juros, amortização) e receitas correntes. "
        "Municípios com % alto dedicam parte significativa da receita ao serviço da dívida."
    ),
    category="Finanças Municipais",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_fin_eficiencia_fiscal(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            m.uf,
            m.populacao,
            COALESCE(mf.despesas_financeiras, 0) AS despesas_financeiras,
            mf.receitas_correntes,
            ROUND(
                100.0 * COALESCE(mf.despesas_financeiras, 0)
                / NULLIF(mf.receitas_correntes, 0), 2
            ) AS custo_divida_pct
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.despesas_financeiras IS NOT NULL
          AND mf.receitas_correntes > 1000000
          AND COALESCE(mf.despesas_financeiras, 0) > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY custo_divida_pct DESC
        LIMIT 40;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de despesas financeiras disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "37. Eficiência Fiscal: Custo da Dívida por Estado")

    fig = px.bar(
        df,
        x="custo_divida_pct",
        y="municipio_uf",
        orientation="h",
        color="custo_divida_pct",
        color_continuous_scale=[
            [0.0, "#22c55e"],
            [0.3, "#f59e0b"],
            [0.7, "#f97316"],
            [1.0, "#ef4444"],
        ],
        text_auto=".1f",
        hover_data={
            "despesas_financeiras": ":,.0f",
            "receitas_correntes": ":,.0f",
            "populacao": ":,.0f",
        },
        labels={
            "custo_divida_pct": "Custo da Dívida (% Receita Corrente)",
            "municipio_uf": "Município (UF)",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})

    # Referência: 5% é limite prudencial do Tesouro Nacional
    fig.add_vline(x=5, line_dash="dot", line_color="#ef4444", line_width=1)
    fig.add_annotation(
        x=5, y=0, xref="x", yref="paper",
        text="Limite prudencial: 5%",
        showarrow=False, font=dict(size=10, color="#ef4444"),
        xanchor="left", yshift=8,
    )

    return aplicar_tema(fig, "37. Eficiência Fiscal: Custo da Dívida por Estado", altura=550)


# ---------------------------------------------------------------------------
# Chart 38 — Heatmap: Resultado Primário por UF × Exercício
# ---------------------------------------------------------------------------

@register_chart(
    id="fin_resultado_primario_heatmap",
    title="38. Heatmap: Resultado Primário por UF × Exercício",
    description=(
        "Mapa de calor mostrando o resultado primário médio (Receita - Despesa) "
        "dos municípios de cada estado ao longo dos exercícios. "
        "Verde = superávit; vermelho = déficit."
    ),
    category="Finanças Municipais",
)
def chart_fin_resultado_primario_heatmap() -> go.Figure:
    query = """
        SELECT
            m.uf,
            mf.exercicio,
            AVG(COALESCE(mf.receitas_correntes, 0) - COALESCE(mf.despesas_correntes, 0)) AS resultado_medio
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes IS NOT NULL
          AND mf.despesas_correntes IS NOT NULL
        GROUP BY m.uf, mf.exercicio
        HAVING COUNT(*) >= 3
        ORDER BY m.uf, mf.exercicio;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de resultado disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "38. Heatmap: Resultado Corrente por UF × Exercício")

    pivot = df.pivot_table(
        index="uf", columns="exercicio", values="resultado_medio",
        aggfunc="mean", fill_value=0,
    )

    text_vals = [
        [f"R$ {v/1e6:+.1f}M" if abs(v) > 1e6 else f"R$ {v/1e3:+.0f}k" if abs(v) > 1e3 else f"R$ {v:+,.0f}"
         for v in row]
        for row in pivot.values
    ]

    fig = go.Figure(go.Heatmap(
        z=pivot.values.tolist(),
        x=[str(c) for c in pivot.columns],
        y=pivot.index.tolist(),
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=10, color=THEME_TEXT),
        colorscale=[
            [0.0, "#dc2626"],
            [0.35, "#fca5a5"],
            [0.5, "#1e293b"],
            [0.65, "#86efac"],
            [1.0, "#16a34a"],
        ],
        zmid=0,
        hovertemplate=(
            "<b>%{y}</b> — %{x}<br>"
            "Resultado primário médio: R$ %{z:,.0f}<br>"
            "<extra></extra>"
        ),
        showscale=True,
        colorbar=dict(
            title="Resultado (R$)",
            title_font=dict(color=THEME_TEXT),
            tickfont=dict(color=THEME_TEXT),
        ),
    ))

    fig.update_layout(
        xaxis=dict(title="Exercício", tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="Estado (UF)", tickfont=dict(color=THEME_TEXT)),
    )

    return aplicar_tema(fig, "38. Heatmap: Resultado Corrente por UF × Exercício")


# ---------------------------------------------------------------------------
# Chart 39 — Decomposição Receitas vs Despesas por Região (Stacked Bar)
# ---------------------------------------------------------------------------

@register_chart(
    id="fin_composicao_receitas_despesas",
    title="39. Composição de Receitas vs Despesas por Região",
    description=(
        "Compara a estrutura de receitas (correntes, capital, transferências) com as "
        "despesas (correntes, capital, financeiras) agregadas por região geográfica."
    ),
    category="Finanças Municipais",
)
def chart_fin_composicao_receitas_despesas() -> go.Figure:
    query = """
        SELECT
            m.regiao,
            SUM(COALESCE(mf.receitas_correntes, 0)) AS total_receitas_correntes,
            SUM(COALESCE(mf.receitas_capital, 0)) AS total_receitas_capital,
            SUM(COALESCE(mf.receitas_transferencias, 0)) AS total_transferencias,
            SUM(COALESCE(mf.despesas_correntes, 0)) AS total_despesas_correntes,
            SUM(COALESCE(mf.despesas_capital, 0)) AS total_despesas_capital,
            SUM(COALESCE(mf.despesas_financeiras, 0)) AS total_despesas_financeiras
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes > 0
        GROUP BY m.regiao
        ORDER BY total_receitas_correntes DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados financeiros suficientes",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "39. Composição de Receitas vs Despesas por Região")

    # Receitas side
    receitas_cols = {
        "Receitas Correntes (Próprias)": "total_receitas_correntes",
        "Receitas de Capital": "total_receitas_capital",
        "Transferências": "total_transferencias",
    }
    receitas_colors = ["#3b82f6", "#06b6d4", "#10b981"]

    # Despesas side
    despesas_cols = {
        "Despesas Correntes": "total_despesas_correntes",
        "Despesas de Capital": "total_despesas_capital",
        "Despesas Financeiras": "total_despesas_financeiras",
    }
    despesas_colors = ["#f97316", "#ef4444", "#a855f7"]

    fig = go.Figure()

    for (label, col), color in zip(receitas_cols.items(), receitas_colors):
        fig.add_trace(go.Bar(
            x=df["regiao"],
            y=df[col],
            name=f"📦 {label}",
            marker_color=color,
            offsetgroup="Receitas",
        ))

    for (label, col), color in zip(despesas_cols.items(), despesas_colors):
        fig.add_trace(go.Bar(
            x=df["regiao"],
            y=-df[col],  # Negative to mirror
            name=f"📤 {label}",
            marker_color=color,
            offsetgroup="Despesas",
            opacity=0.85,
        ))

    fig.update_layout(
        barmode="relative",
        yaxis=dict(
            title="Valores (R$)",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
            zeroline=True,
            zerolinecolor="#475569",
            tickvals=[-5e10, -2.5e10, 0, 2.5e10, 5e10],
            ticktext=["-R$ 50bi", "-R$ 25bi", "0", "R$ 25bi", "R$ 50bi"],
        ),
        xaxis=dict(tickfont=dict(color=THEME_TEXT)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            font=dict(size=10, color=THEME_TEXT),
        ),
        annotations=[
            dict(x=0.25, y=-0.12, xref="paper", yref="paper",
                 text="← DESPESAS", showarrow=False,
                 font=dict(size=12, color="#ef4444")),
            dict(x=0.75, y=-0.12, xref="paper", yref="paper",
                 text="RECEITAS →", showarrow=False,
                 font=dict(size=12, color="#22c55e")),
        ],
    )

    return aplicar_tema(fig, "39. Composição de Receitas vs Despesas por Região", 550)


# ---------------------------------------------------------------------------
# Chart 40 — Autonomia Fiscal: % Receita Própria por Município
# ---------------------------------------------------------------------------

@register_chart(
    id="fin_autonomia_fiscal_uf",
    title="40. Autonomia Fiscal: % Receita Própria vs Transferências por UF",
    description=(
        "Gráfico de barras empilhadas mostrando a composição percentual da receita "
        "corrente: (1) impostos e contribuições próprias, (2) cotas-partes, "
        "(3) transferências intergovernamentais. Estados no topo são mais autônomos."
    ),
    category="Finanças Municipais",
)
def chart_fin_autonomia_fiscal_uf() -> go.Figure:
    query = """
        SELECT
            m.uf,
            AVG(
                100.0 * COALESCE(mf.receitas_correntes, 0)
                / NULLIF(mf.receitas_correntes + mf.receitas_capital, 0)
            ) AS pct_correntes,
            AVG(
                100.0 * COALESCE(mf.receitas_capital, 0)
                / NULLIF(mf.receitas_correntes + mf.receitas_capital, 0)
            ) AS pct_capital,
            AVG(mf.receitas_correntes) AS media_receita,
            COUNT(*) AS num_municipios
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes > 1000000
          AND mf.receitas_capital IS NOT NULL
        GROUP BY m.uf
        HAVING COUNT(*) >= 5
        ORDER BY pct_correntes DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados suficientes para composição de receitas",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "40. Composição de Receitas por UF")

    import pandas as pd
    df["pct_correntes"] = pd.to_numeric(df["pct_correntes"], errors="coerce").fillna(0)
    df["pct_capital"] = pd.to_numeric(df["pct_capital"], errors="coerce").fillna(0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["uf"],
        y=df["pct_correntes"],
        name="Receitas Correntes (Operacionais)",
        marker_color="#22c55e",
    ))
    fig.add_trace(go.Bar(
        x=df["uf"],
        y=df["pct_capital"],
        name="Receitas de Capital (Investimentos)",
        marker_color="#3b82f6",
    ))

    fig.update_layout(
        barmode="stack",
        yaxis=dict(
            title="% da Receita Total",
            range=[0, 105],
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
        ),
        xaxis=dict(title="Estado (UF)", tickfont=dict(color=THEME_TEXT)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            font=dict(size=10, color=THEME_TEXT),
        ),
    )

    fig.add_hline(y=80, line_dash="dot", line_color="#f59e0b", line_width=1)
    fig.add_annotation(
        x=1, y=80, xref="paper", yref="y",
        text="80% — Receitas Correntes",
        showarrow=False, font=dict(size=10, color="#f59e0b"),
        xanchor="right", yshift=8,
    )

    return aplicar_tema(fig, "40. Composição de Receitas: Correntes vs Capital por UF", 500)
