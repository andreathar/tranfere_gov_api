"""Charts 32-34 — Arrecadação de Impostos Municipais (RREO Anexo 03)."""

from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import THEME_GRID, THEME_TEXT, TODAS_UFS, aplicar_tema

# ---------------------------------------------------------------------------
# Chart 32 — Arrecadação de Impostos: Top 20 Municípios
# ---------------------------------------------------------------------------

@register_chart(
    id="arrecadacao_impostos_municipios",
    title="32. Arrecadação de Impostos: Top 20 Municípios",
    description=(
        "IPTU, ISS, Cota-Parte ICMS e Cota-Parte FPM dos 20 municípios "
        "com maior arrecadação própria (RREO Anexo 03)."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_arrecadacao_impostos_municipios(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            COALESCE(mf.arrec_iptu, 0) AS iptu,
            COALESCE(mf.arrec_iss, 0) AS iss,
            COALESCE(mf.arrec_cota_icms, 0) AS cota_icms,
            COALESCE(mf.arrec_cota_fpm, 0) AS cota_fpm,
            COALESCE(mf.arrec_receitas_correntes, 0) AS receitas_correntes
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
                + COALESCE(mf.arrec_cota_icms, 0) + COALESCE(mf.arrec_cota_fpm, 0))
            DESC
        LIMIT 20;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de arrecadação disponíveis (execute siconfi --rreo)",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "32. Arrecadação de Impostos: Top 20 Municípios")

    # Preparar para grouped bar
    df["label"] = df["municipio"] + " (" + df["uf"] + ")"
    df_melt = df.melt(
        id_vars=["label"],
        value_vars=["iptu", "iss", "cota_icms", "cota_fpm"],
        var_name="Imposto",
        value_name="Valor (R$)",
    )
    df_melt["Imposto"] = df_melt["Imposto"].map({
        "iptu": "IPTU",
        "iss": "ISS",
        "cota_icms": "Cota-Parte ICMS",
        "cota_fpm": "Cota-Parte FPM",
    })

    cores_impostos = {
        "IPTU": "#f59e0b",
        "ISS": "#3b82f6",
        "Cota-Parte ICMS": "#10b981",
        "Cota-Parte FPM": "#8b5cf6",
    }

    fig = px.bar(
        df_melt,
        x="label",
        y="Valor (R$)",
        color="Imposto",
        barmode="group",
        color_discrete_map=cores_impostos,
        labels={"label": "Município (UF)", "Valor (R$)": "Arrecadação (R$)"},
    )
    fig.update_xaxes(tickangle=-45)
    return aplicar_tema(fig, "32. Arrecadação de Impostos: Top 20 Municípios", altura=550)


# ---------------------------------------------------------------------------
# Chart 33 — Dependência de Transferências vs. Impostos Próprios
# ---------------------------------------------------------------------------

@register_chart(
    id="arrecadacao_dependencia_transferencias",
    title="33. Dependência de Transferências vs. Impostos Próprios",
    description=(
        "Scatter: eixo X = % de receita de impostos próprios, eixo Y = % de "
        "receita de transferências. Municípios no canto inferior direito são "
        "mais autônomos financeiramente."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_arrecadacao_dependencia(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            ROUND(100.0 * (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
                        + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0))
                   / NULLIF(mf.arrec_receitas_correntes, 0), 2) AS impostos_proprios_pct,
            ROUND(100.0 * COALESCE(mf.arrec_transferencias, 0)
                   / NULLIF(mf.arrec_receitas_correntes, 0), 2) AS transferencias_pct,
            COALESCE(mf.arrec_receitas_correntes, 0) AS receitas_correntes
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
          AND mf.arrec_receitas_correntes > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY receitas_correntes DESC
        LIMIT 100;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de arrecadação disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "33. Dependência de Transferências vs. Impostos Próprios")

    # Bubble size: log of receitas_correntes for visual balance
    import numpy as np
    df["tamanho"] = np.log10(df["receitas_correntes"].clip(lower=1)) * 3

    fig = px.scatter(
        df,
        x="impostos_proprios_pct",
        y="transferencias_pct",
        color="uf",
        size="tamanho",
        hover_name="municipio",
        hover_data={
            "uf": True,
            "impostos_proprios_pct": ":.1f",
            "transferencias_pct": ":.1f",
            "receitas_correntes": ":.0f",
            "tamanho": False,
        },
        labels={
            "impostos_proprios_pct": "Impostos Próprios (%)",
            "transferencias_pct": "Transferências (%)",
            "uf": "UF",
        },
    )

    # Add quadrant lines at 50%
    fig.add_hline(y=50, line_dash="dot", line_color="#475569", line_width=1)
    fig.add_vline(x=50, line_dash="dot", line_color="#475569", line_width=1)

    # Quadrant labels
    fig.add_annotation(
        x=75, y=5, text="<b>Autônomo</b><br>Alta arrecadação<br>Baixa dependência",
        showarrow=False, font=dict(size=10, color="#22c55e"),
        bgcolor="rgba(34,197,94,0.1)", borderwidth=0,
    )
    fig.add_annotation(
        x=25, y=95, text="<b>Dependente</b><br>Baixa arrecadação<br>Alta dependência",
        showarrow=False, font=dict(size=10, color="#ef4444"),
        bgcolor="rgba(239,68,68,0.1)", borderwidth=0,
    )

    return aplicar_tema(
        fig,
        "33. Dependência de Transferências vs. Impostos Próprios",
        altura=550,
    )


# ---------------------------------------------------------------------------
# Chart 34 — Composição da Receita por UF (Stacked)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrecadacao_composicao_uf",
    title="34. Composição Média da Receita por UF",
    description=(
        "Receita média por município, decomposta em: Impostos próprios "
        "(IPTU+ISS+ITBI+IRRF), Cotas-partes (ICMS+IPVA+FPM) e "
        "Transferências. Mostra a estrutura fiscal de cada estado."
    ),
    category="Arrecadação",
)
def chart_arrecadacao_composicao_uf() -> go.Figure:
    query = """
        SELECT
            m.uf,
            AVG(COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
              + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0))
                AS media_impostos_proprios,
            AVG(COALESCE(mf.arrec_cota_icms, 0) + COALESCE(mf.arrec_cota_ipva, 0)
              + COALESCE(mf.arrec_cota_itr, 0) + COALESCE(mf.arrec_cota_fpm, 0))
                AS media_cotas_partes,
            AVG(COALESCE(mf.arrec_transferencias, 0))
                AS media_transferencias,
            COUNT(*) AS num_municipios
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
        GROUP BY m.uf
        HAVING COUNT(*) >= 3
        ORDER BY (AVG(COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
                    + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0))
                + AVG(COALESCE(mf.arrec_cota_icms, 0) + COALESCE(mf.arrec_cota_ipva, 0)
                    + COALESCE(mf.arrec_cota_itr, 0) + COALESCE(mf.arrec_cota_fpm, 0))
                + AVG(COALESCE(mf.arrec_transferencias, 0))) DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de arrecadação suficientes",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "34. Composição Média da Receita por UF")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["uf"],
        y=df["media_impostos_proprios"],
        name="Impostos Próprios",
        marker_color="#f59e0b",
    ))
    fig.add_trace(go.Bar(
        x=df["uf"],
        y=df["media_cotas_partes"],
        name="Cotas-Partes (ICMS/IPVA/FPM)",
        marker_color="#3b82f6",
    ))
    fig.add_trace(go.Bar(
        x=df["uf"],
        y=df["media_transferencias"],
        name="Transferências",
        marker_color="#10b981",
    ))

    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Receita Média por Município (R$)")
    fig.update_xaxes(title_text="Estado (UF)")

    return aplicar_tema(
        fig,
        "34. Composição Média da Receita por UF",
        altura=550,
    )


# ---------------------------------------------------------------------------
# Chart 35 — Evolução da Arrecadação IPTU por UF (Temporal)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_evolucao_iptu_uf",
    title="35. Evolução da Arrecadação IPTU por UF",
    description=(
        "Série temporal da arrecadação total de IPTU (Imposto sobre "
        "Propriedade Predial e Territorial Urbana) agregada por estado. "
        "Indica a capacidade de mobilização tributária própria ao longo do tempo."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_arrec_evolucao_iptu_uf(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.uf,
            mf.exercicio,
            SUM(COALESCE(mf.arrec_iptu, 0)) AS total_iptu,
            COUNT(*) AS num_municipios
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL AND mf.arrec_iptu > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.uf, mf.exercicio
        HAVING SUM(COALESCE(mf.arrec_iptu, 0)) > 0
        ORDER BY mf.exercicio, m.uf;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de IPTU disponíveis (execute siconfi --rreo)",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "35. Evolução da Arrecadação IPTU por UF")

    df["exercicio"] = df["exercicio"].astype(str)

    if uf_filter == "TODOS":
        # Top 10 UFs by total IPTU
        top_ufs = (
            df.groupby("uf")["total_iptu"]
            .sum()
            .nlargest(10)
            .index.tolist()
        )
        df = df[df["uf"].isin(top_ufs)]

    cores = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel

    fig = go.Figure()
    for i, uf in enumerate(sorted(df["uf"].unique())):
        df_uf = df[df["uf"] == uf].sort_values("exercicio")
        fig.add_trace(go.Scatter(
            x=df_uf["exercicio"],
            y=df_uf["total_iptu"],
            mode="lines+markers",
            name=uf,
            line=dict(color=cores[i % len(cores)], width=2),
            marker=dict(size=6),
            hovertemplate=(
                f"<b>{uf}</b><br>"
                "Exercício: %{x}<br>"
                "IPTU arrecadado: R$ %{y:,.0f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis=dict(title="Exercício", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="Arrecadação IPTU Total (R$)", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        legend=dict(font=dict(size=10)),
    )
    return aplicar_tema(fig, "35. Evolução da Arrecadação IPTU por UF", altura=500)


# ---------------------------------------------------------------------------
# Chart 36 — Impostos Próprios Per Capita por Município (Top 25)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_impostos_per_capita",
    title="36. Impostos Próprios Per Capita: Top 25 Municípios",
    description=(
        "Ranking dos 25 municípios com maior arrecadação de impostos próprios "
        "(IPTU+ISS+ITBI+IRRF) por habitante. Indica capacidade de arrecadação "
        "efetiva e formalização econômica municipal."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_arrec_impostos_per_capita(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            m.uf,
            m.populacao,
            (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
             + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0)) AS impostos_proprios,
            ROUND(
                (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
                 + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0))
                / NULLIF(m.populacao, 0), 2
            ) AS impostos_per_capita
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
          AND m.populacao > 10000
          AND (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)
               + COALESCE(mf.arrec_itbi, 0) + COALESCE(mf.arrec_irrf, 0)) > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY impostos_per_capita DESC
        LIMIT 25;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de arrecadação disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "36. Impostos Próprios Per Capita por Município")

    # Color by quartile
    import pandas as pd
    df["impostos_per_capita"] = pd.to_numeric(df["impostos_per_capita"], errors="coerce").fillna(0)
    quartis = df["impostos_per_capita"].quantile([0.25, 0.5, 0.75])

    def _color(val):
        if val >= quartis.iloc[2]:
            return "#22c55e"
        elif val >= quartis.iloc[1]:
            return "#3b82f6"
        elif val >= quartis.iloc[0]:
            return "#f59e0b"
        return "#ef4444"

    df["cor"] = df["impostos_per_capita"].apply(_color)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["impostos_per_capita"],
        y=df["municipio_uf"],
        orientation="h",
        marker_color=df["cor"],
        text=df["impostos_per_capita"].apply(lambda x: f"R$ {x:,.2f}"),
        textposition="outside",
        textfont=dict(size=10, color=THEME_TEXT),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Impostos per capita: R$ %{x:,.2f}<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis=dict(
            title="Impostos Próprios Per Capita (R$/hab)",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
        ),
    )

    return aplicar_tema(fig, "36. Impostos Próprios Per Capita: Top 25 Municípios", 600)


# ---------------------------------------------------------------------------
# Chart 37 — Receita Patrimonial vs Receita de Serviços (Scatter)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_patrimonial_vs_servicos",
    title="37. Receita Patrimonial vs Receita de Serviços",
    description=(
        "Scatter comparando receita patrimonial (aluguéis, juros, dividendos) "
        "com receita de serviços (taxas, tarifas, ISS). Municípios com alta "
        "receita patrimonial podem ter patrimônio público significativo."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_arrec_patrimonial_vs_servicos(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            m.uf,
            m.populacao,
            COALESCE(mf.arrec_receita_patrimonial, 0) AS receita_patrimonial,
            COALESCE(mf.arrec_receita_servicos, 0) AS receita_servicos,
            COALESCE(mf.arrec_iss, 0) AS iss
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_receita_patrimonial IS NOT NULL
          AND mf.arrec_receita_servicos IS NOT NULL
          AND (COALESCE(mf.arrec_receita_patrimonial, 0) + COALESCE(mf.arrec_receita_servicos, 0)) > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY (COALESCE(mf.arrec_receita_patrimonial, 0) + COALESCE(mf.arrec_receita_servicos, 0)) DESC
        LIMIT 100;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de receita patrimonial/serviços disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "37. Receita Patrimonial vs Receita de Serviços")

    df["populacao"] = df["populacao"].clip(lower=1)

    # Ratio for color
    import pandas as pd
    df["receita_patrimonial"] = pd.to_numeric(df["receita_patrimonial"], errors="coerce").fillna(0)
    df["receita_servicos"] = pd.to_numeric(df["receita_servicos"], errors="coerce").fillna(0)
    df["ratio_pat_serv"] = np.where(
        df["receita_servicos"] > 0,
        df["receita_patrimonial"] / df["receita_servicos"],
        0,
    )
    df["perfil"] = df["ratio_pat_serv"].apply(
        lambda x: "🏛️ Patrimonial" if x > 2 else ("⚖️ Equilibrado" if x > 0.5 else "🏪 Serviços")
    )

    fig = px.scatter(
        df,
        x="receita_servicos",
        y="receita_patrimonial",
        size="populacao",
        color="perfil",
        hover_name="municipio_uf",
        hover_data={
            "iss": ":,.0f",
            "populacao": ":,.0f",
            "perfil": False,
        },
        color_discrete_map={
            "🏛️ Patrimonial": "#a855f7",
            "⚖️ Equilibrado": "#3b82f6",
            "🏪 Serviços": "#f59e0b",
        },
        labels={
            "receita_servicos": "Receita de Serviços (R$)",
            "receita_patrimonial": "Receita Patrimonial (R$)",
        },
        size_max=40,
    )

    # Diagonal
    max_val = max(
        df["receita_servicos"].max(),
        df["receita_patrimonial"].max(),
        1,
    )
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode="lines",
        name="Linha de igualdade",
        line=dict(color="#475569", width=1, dash="dot"),
        showlegend=True,
    ))

    return aplicar_tema(fig, "37. Receita Patrimonial vs Receita de Serviços", 550)


# ---------------------------------------------------------------------------
# Chart 38 — Heatmap: Arrecadação IPTU × ISS por UF
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_heatmap_iptu_iss_uf",
    title="38. Heatmap: IPTU vs ISS por Estado",
    description=(
        "Mapa de calor comparando a arrecadação total de IPTU (imposto sobre "
        "propriedade) com ISS (imposto sobre serviços) por UF. Revela a "
        "especialização fiscal: estados industriais vs. turísticos."
    ),
    category="Arrecadação",
)
def chart_arrec_heatmap_iptu_iss_uf() -> go.Figure:
    query = """
        SELECT
            m.uf,
            SUM(COALESCE(mf.arrec_iptu, 0)) AS total_iptu,
            SUM(COALESCE(mf.arrec_iss, 0)) AS total_iss
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
        GROUP BY m.uf
        HAVING SUM(COALESCE(mf.arrec_iptu, 0)) + SUM(COALESCE(mf.arrec_iss, 0)) > 0
        ORDER BY (SUM(COALESCE(mf.arrec_iptu, 0)) + SUM(COALESCE(mf.arrec_iss, 0))) DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de IPTU/ISS disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "38. Heatmap: IPTU vs ISS por Estado")

    fig = go.Figure(go.Heatmap(
        z=[df["total_iptu"].tolist(), df["total_iss"].tolist()],
        x=df["uf"].tolist(),
        y=["IPTU (Propriedade)", "ISS (Serviços)"],
        text=[
            [f"R$ {v/1e9:.1f}bi" if v >= 1e9 else f"R$ {v/1e6:.0f}mi" for v in df["total_iptu"]],
            [f"R$ {v/1e9:.1f}bi" if v >= 1e9 else f"R$ {v/1e6:.0f}mi" for v in df["total_iss"]],
        ],
        texttemplate="%{text}",
        textfont=dict(size=11, color=THEME_TEXT),
        colorscale=[
            [0.0, "#0f172a"],
            [0.3, "#1e3a5f"],
            [0.6, "#3b82f6"],
            [1.0, "#f59e0b"],
        ],
        hovertemplate=(
            "<b>%{x}</b> — %{y}<br>"
            "Arrecadação: R$ %{z:,.0f}<br>"
            "<extra></extra>"
        ),
        showscale=True,
        colorbar=dict(
            title="Arrecadação (R$)",
            title_font=dict(color=THEME_TEXT),
            tickfont=dict(color=THEME_TEXT),
        ),
    ))

    fig.update_layout(
        xaxis=dict(title="Estado (UF)", tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="Tipo de Imposto", tickfont=dict(color=THEME_TEXT)),
    )

    return aplicar_tema(fig, "38. Heatmap: IPTU vs ISS por Estado", 350)


# ---------------------------------------------------------------------------
# Chart 39 — Decomposição: Composição Percentual dos Impostos por UF (Donut)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_composicao_percentual_impostos",
    title="39. Composição Percentual dos Impostos por UF",
    description=(
        "Gráfico de barras 100% empilhadas mostrando a fatia de cada tipo "
        "de imposto (IPTU, ISS, ITBI, IRRF, ICMS, IPVA, FPM) na arrecadação "
        "total de cada UF. Revela dependência de fontes específicas."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_arrec_composicao_percentual_impostos(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.uf,
            SUM(COALESCE(mf.arrec_iptu, 0)) AS iptu,
            SUM(COALESCE(mf.arrec_iss, 0)) AS iss,
            SUM(COALESCE(mf.arrec_itbi, 0)) AS itbi,
            SUM(COALESCE(mf.arrec_irrf, 0)) AS irrf,
            SUM(COALESCE(mf.arrec_cota_icms, 0)) AS cota_icms,
            SUM(COALESCE(mf.arrec_cota_ipva, 0)) AS cota_ipva,
            SUM(COALESCE(mf.arrec_cota_fpm, 0)) AS cota_fpm,
            SUM(COALESCE(mf.arrec_cota_itr, 0)) AS cota_itr
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.uf
        HAVING SUM(COALESCE(mf.arrec_iptu, 0) + mf.arrec_iss + mf.arrec_itbi
                 + mf.arrec_irrf + mf.arrec_cota_icms + mf.arrec_cota_ipva
                 + mf.arrec_cota_fpm + mf.arrec_cota_itr) > 0
        ORDER BY SUM(COALESCE(mf.arrec_iptu, 0) + mf.arrec_iss + mf.arrec_itbi
                 + mf.arrec_irrf + mf.arrec_cota_icms + mf.arrec_cota_ipva
                 + mf.arrec_cota_fpm + mf.arrec_cota_itr) DESC;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de composição de impostos",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "39. Composição Percentual dos Impostos por UF")

    # Calcular totais e percentuais
    import pandas as pd
    for col in ["iptu", "iss", "itbi", "irrf", "cota_icms", "cota_ipva", "cota_fpm", "cota_itr"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["total"] = df[["iptu", "iss", "itbi", "irrf", "cota_icms", "cota_ipva", "cota_fpm", "cota_itr"]].sum(axis=1)
    df = df[df["total"] > 0]

    # Calcular percentuais
    for col in ["iptu", "iss", "itbi", "irrf", "cota_icms", "cota_ipva", "cota_fpm", "cota_itr"]:
        df[f"{col}_pct"] = 100.0 * df[col] / df["total"]

    cores = {
        "IPTU": "#f59e0b", "ISS": "#3b82f6", "ITBI": "#06b6d4", "IRRF": "#8b5cf6",
        "Cota ICMS": "#10b981", "Cota IPVA": "#ec4899", "Cota FPM": "#a855f7", "Cota ITR": "#64748b",
    }

    fig = go.Figure()
    for col_name, label, color in [
        ("iptu_pct", "IPTU", cores["IPTU"]),
        ("iss_pct", "ISS", cores["ISS"]),
        ("itbi_pct", "ITBI", cores["ITBI"]),
        ("irrf_pct", "IRRF", cores["IRRF"]),
        ("cota_icms_pct", "Cota ICMS", cores["Cota ICMS"]),
        ("cota_ipva_pct", "Cota IPVA", cores["Cota IPVA"]),
        ("cota_fpm_pct", "Cota FPM", cores["Cota FPM"]),
        ("cota_itr_pct", "Cota ITR", cores["Cota ITR"]),
    ]:
        if df[col_name].sum() > 0:
            fig.add_trace(go.Bar(
                x=df["uf"],
                y=df[col_name],
                name=label,
                marker_color=color,
            ))

    fig.update_layout(
        barmode="stack",
        yaxis=dict(
            title="% da Arrecadação Total",
            range=[0, 105],
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
        ),
        xaxis=dict(title="Estado (UF)", tickfont=dict(color=THEME_TEXT)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            font=dict(size=9, color=THEME_TEXT),
        ),
    )

    return aplicar_tema(fig, "39. Composição Percentual dos Impostos por UF", 550)


# ---------------------------------------------------------------------------
# Chart 40 — Cota-Parte ICMS: Top 15 Estados (Barra + Texto)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_cota_icms_ranking",
    title="40. Cota-Parte ICMS: Top 15 Estados",
    description=(
        "Ranking dos estados que mais recebem de cota-parte do ICMS "
        "(Imposto sobre Circulação de Mercadorias e Serviços). "
        "O ICMS é o maior imposto estadual e sua cota-parte é a principal "
        "fonte de receita própria dos municípios."
    ),
    category="Arrecadação",
)
def chart_arrec_cota_icms_ranking() -> go.Figure:
    query = """
        SELECT
            m.uf,
            SUM(COALESCE(mf.arrec_cota_icms, 0)) AS total_cota_icms,
            COUNT(*) AS num_municipios,
            ROUND(AVG(COALESCE(mf.arrec_cota_icms, 0)), 2) AS media_por_municipio
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_cota_icms IS NOT NULL AND mf.arrec_cota_icms > 0
        GROUP BY m.uf
        ORDER BY total_cota_icms DESC
        LIMIT 15;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de cota-parte ICMS disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "40. Cota-Parte ICMS: Top 15 Estados")

    fig = px.bar(
        df,
        x="total_cota_icms",
        y="uf",
        orientation="h",
        text_auto=".2s",
        color="total_cota_icms",
        color_continuous_scale="Greens",
        labels={
            "total_cota_icms": "Cota-Parte ICMS Total (R$)",
            "uf": "Estado",
        },
        hover_data={
            "num_municipios": True,
            "media_por_municipio": ":,.0f",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    fig.update_layout(coloraxis_showscale=False)

    return aplicar_tema(fig, "40. Cota-Parte ICMS: Top 15 Estados", 500)


# ---------------------------------------------------------------------------
# Chart 41 — IPTU per Capita vs IDHM (Scatter)
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_iptu_vs_idhm",
    title="41. IPTU per Capita vs IDHM Municipal",
    description=(
        "Scatter cruzando a arrecadação de IPTU por habitante com o IDHM "
        "(Índice de Desenvolvimento Humano Municipal). Municípios com alto "
        "IDHM e baixa arrecadação de IPTU podem ter espaço para ampliar "
        "a base de cálculo tributária."
    ),
    category="Arrecadação",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS",
        ),
    ],
)
def chart_arrec_iptu_vs_idhm(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            m.regiao,
            m.populacao,
            ROUND(m.pib / NULLIF(m.populacao, 0), 2) AS pib_per_capita,
            COALESCE(mf.arrec_iptu, 0) AS arrec_iptu,
            ROUND(
                COALESCE(mf.arrec_iptu, 0) / NULLIF(m.populacao, 0), 2
            ) AS iptu_per_capita
        FROM municipios_ibge m
        JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL
          AND mf.arrec_iptu > 0
          AND m.pib > 0
          AND m.populacao > 5000
          AND (%s = 'TODOS' OR m.regiao = %s)
        ORDER BY m.populacao DESC
        LIMIT 200;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados suficientes de IPTU/PIB",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "41. IPTU per Capita vs PIB per Capita")

    import pandas as pd
    df["pib_per_capita"] = pd.to_numeric(df["pib_per_capita"], errors="coerce").fillna(0)
    df["iptu_per_capita"] = pd.to_numeric(df["iptu_per_capita"], errors="coerce").fillna(0)
    df["populacao"] = df["populacao"].clip(lower=1)

    REGIAO_CORES = {
        "Norte": "#0ea5e9", "Nordeste": "#f59e0b", "Sudeste": "#22c55e",
        "Sul": "#a855f7", "Centro-Oeste": "#ef4444",
    }

    fig = go.Figure()
    for regiao in df["regiao"].dropna().unique():
        dfr = df[df["regiao"] == regiao]
        fig.add_trace(go.Scatter(
            x=dfr["pib_per_capita"],
            y=dfr["iptu_per_capita"],
            mode="markers",
            name=regiao,
            marker=dict(
                size=np.sqrt(dfr["populacao"] / dfr["populacao"].max()) * 40 + 8,
                color=REGIAO_CORES.get(regiao, "#64748b"),
                opacity=0.75,
                line=dict(width=1, color="#1e293b"),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "PIB/hab: R$ %{x:,.0f}<br>"
                "IPTU/hab: R$ %{y:,.2f}<br>"
                "<extra></extra>"
            ),
            customdata=dfr[["municipio"]].values,
        ))

    fig.update_layout(
        xaxis=dict(title="PIB per Capita (R$/hab)", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="IPTU per Capita (R$/hab)", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
    )

    return aplicar_tema(fig, "41. IPTU per Capita vs PIB per Capita", 520)


# ---------------------------------------------------------------------------
# Chart 42 — Box Plot: Distribuição IPTU por Região
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_iptu_distribuicao_regiao",
    title="42. Distribuição do IPTU por Região (Box Plot)",
    description=(
        "Box plot mostrando a dispersão da arrecadação de IPTU por município "
        "em cada região geográfica. Identifica municípios outliers com "
        "arrecadação anormalmente alta ou baixa para sua região."
    ),
    category="Arrecadação",
)
def chart_arrec_iptu_distribuicao_regiao() -> go.Figure:
    query = """
        SELECT
            m.regiao,
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            COALESCE(mf.arrec_iptu, 0) AS arrec_iptu
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL AND mf.arrec_iptu > 0
          AND m.regiao IS NOT NULL;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de IPTU por região",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "42. Distribuição do IPTU por Região")

    import pandas as pd
    df["arrec_iptu"] = pd.to_numeric(df["arrec_iptu"], errors="coerce").fillna(0)

    fig = px.box(
        df,
        x="regiao",
        y="arrec_iptu",
        color="regiao",
        points="outliers",
        hover_name="municipio_uf",
        labels={
            "arrec_iptu": "Arrecadação IPTU (R$)",
            "regiao": "Região Geográfica",
        },
    )

    # Log scale para melhor visualização
    fig.update_layout(yaxis_type="log")

    return aplicar_tema(fig, "42. Distribuição do IPTU por Região (Box Plot)", 500)


# ---------------------------------------------------------------------------
# Chart 43 — FPM: Cota-Parte por Faixa Populacional
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_fpm_faixa_populacional",
    title="43. Cota-Parte FPM por Faixa Populacional",
    description=(
        "Mostra como a cota-parte do FPM (Fundo de Partilha Municipal) "
        "se distribui por faixa populacional. O FPM privilegia municípios "
        "pequenos — este gráfico verifica essa regressividade."
    ),
    category="Arrecadação",
)
def chart_arrec_fpm_faixa_populacional() -> go.Figure:
    query = """
        SELECT
            CASE
                WHEN m.populacao < 10000 THEN 'Até 10 mil'
                WHEN m.populacao < 50000 THEN '10-50 mil'
                WHEN m.populacao < 100000 THEN '50-100 mil'
                WHEN m.populacao < 500000 THEN '100-500 mil'
                WHEN m.populacao < 1000000 THEN '500k-1 mi'
                ELSE 'Acima de 1 milhão'
            END AS faixa_pop,
            CASE
                WHEN m.populacao < 10000 THEN 1
                WHEN m.populacao < 50000 THEN 2
                WHEN m.populacao < 100000 THEN 3
                WHEN m.populacao < 500000 THEN 4
                WHEN m.populacao < 1000000 THEN 5
                ELSE 6
            END AS ordem,
            COUNT(*) AS num_municipios,
            AVG(COALESCE(mf.arrec_cota_fpm, 0)) AS media_fpm,
            SUM(COALESCE(mf.arrec_cota_fpm, 0)) AS total_fpm,
            AVG(COALESCE(mf.arrec_cota_fpm, 0) / NULLIF(m.populacao, 0)) AS fpm_per_capita
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_cota_fpm IS NOT NULL AND mf.arrec_cota_fpm > 0
          AND m.populacao > 0
        GROUP BY faixa_pop, ordem
        ORDER BY ordem;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de FPM disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "43. Cota-Parte FPM por Faixa Populacional")

    import pandas as pd
    df["media_fpm"] = pd.to_numeric(df["media_fpm"], errors="coerce").fillna(0)
    df["fpm_per_capita"] = pd.to_numeric(df["fpm_per_capita"], errors="coerce").fillna(0)

    fig = go.Figure()

    # Barras: FPM médio por município
    fig.add_trace(go.Bar(
        x=df["faixa_pop"],
        y=df["media_fpm"],
        name="FPM Médio por Município",
        marker_color="#3b82f6",
        yaxis="y",
    ))

    # Linha: FPM per capita
    fig.add_trace(go.Scatter(
        x=df["faixa_pop"],
        y=df["fpm_per_capita"],
        name="FPM per Capita (R$/hab)",
        mode="lines+markers",
        line=dict(color="#f59e0b", width=3),
        marker=dict(size=10),
        yaxis="y2",
    ))

    # Anotação: número de municípios
    for _, row in df.iterrows():
        fig.add_annotation(
            x=row["faixa_pop"], y=row["media_fpm"],
            text=f"{int(row['num_municipios'])} mun.",
            showarrow=False,
            font=dict(size=9, color="#94a3b8"),
            yshift=15, yref="y",
        )

    fig.update_layout(
        yaxis=dict(
            title="FPM Médio por Município (R$)",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
        ),
        yaxis2=dict(
            title="FPM per Capita (R$/hab)",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color="#f59e0b"),
        ),
        xaxis=dict(title="Faixa Populacional", tickfont=dict(color=THEME_TEXT)),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            font=dict(size=10, color=THEME_TEXT),
        ),
    )

    return aplicar_tema(fig, "43. Cota-Parte FPM por Faixa Populacional", 520)


# ---------------------------------------------------------------------------
# Chart 44 — IPTU vs ISS: Especialização Fiscal por Região
# ---------------------------------------------------------------------------

@register_chart(
    id="arrec_iptu_iss_regiao",
    title="44. IPTU vs ISS por Região: Especialização Fiscal",
    description=(
        "Scatter com cada ponto = um município. Eixo X = arrecadação de IPTU "
        "(propriedade), eixo Y = ISS (serviços). Regiões com pontos acima da "
        "diagonal são mais dependentes de ISS (economia de serviços); abaixo, "
        "de IPTU (economia imobiliária)."
    ),
    category="Arrecadação",
)
def chart_arrec_iptu_iss_regiao() -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            m.regiao,
            m.populacao,
            COALESCE(mf.arrec_iptu, 0) AS iptu,
            COALESCE(mf.arrec_iss, 0) AS iss
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_iptu IS NOT NULL AND mf.arrec_iss IS NOT NULL
          AND (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)) > 100000
          AND m.populacao > 10000
        ORDER BY (COALESCE(mf.arrec_iptu, 0) + COALESCE(mf.arrec_iss, 0)) DESC
        LIMIT 300;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados suficientes de IPTU/ISS",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "44. IPTU vs ISS por Região")

    import pandas as pd
    df["iptu"] = pd.to_numeric(df["iptu"], errors="coerce").fillna(0)
    df["iss"] = pd.to_numeric(df["iss"], errors="coerce").fillna(0)
    df["populacao"] = df["populacao"].clip(lower=1)

    REGIAO_CORES = {
        "Norte": "#0ea5e9", "Nordeste": "#f59e0b", "Sudeste": "#22c55e",
        "Sul": "#a855f7", "Centro-Oeste": "#ef4444",
    }

    fig = go.Figure()
    for regiao in df["regiao"].dropna().unique():
        dfr = df[df["regiao"] == regiao]
        fig.add_trace(go.Scatter(
            x=dfr["iptu"],
            y=dfr["iss"],
            mode="markers",
            name=regiao,
            marker=dict(
                size=np.sqrt(dfr["populacao"] / dfr["populacao"].max()) * 35 + 6,
                color=REGIAO_CORES.get(regiao, "#64748b"),
                opacity=0.7,
                line=dict(width=1, color="#1e293b"),
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "IPTU: R$ %{x:,.0f}<br>"
                "ISS: R$ %{y:,.0f}<br>"
                "<extra></extra>"
            ),
            customdata=dfr[["municipio"]].values,
        ))

    # Diagonal de referência
    max_val = max(df["iptu"].max(), df["iss"].max(), 1)
    fig.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode="lines", name="IPTU = ISS",
        line=dict(color="#475569", width=1, dash="dot"),
        showlegend=True,
    ))

    fig.add_annotation(
        x=max_val * 0.05, y=max_val * 0.9,
        text="<b>主导 ISS</b><br>Economia de serviços",
        showarrow=False, font=dict(size=10, color="#3b82f6"),
        bgcolor="rgba(59,130,246,0.08)", borderwidth=0,
    )
    fig.add_annotation(
        x=max_val * 0.9, y=max_val * 0.05,
        text="<b>主导 IPTU</b><br>Economia imobiliária",
        showarrow=False, font=dict(size=10, color="#f59e0b"),
        bgcolor="rgba(245,158,11,0.08)", borderwidth=0,
    )

    fig.update_layout(
        xaxis=dict(title="IPTU Arrecadado (R$)", type="log", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="ISS Arrecadado (R$)", type="log", gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT)),
    )

    return aplicar_tema(fig, "44. IPTU vs ISS por Região: Especialização Fiscal", 550)
