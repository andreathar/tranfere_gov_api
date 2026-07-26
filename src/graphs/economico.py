"""Charts de Análise Econômica Cruzada — dados SICONFI + Saúde + Educação + MCP-Brasil."""

from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import THEME_GRID, THEME_TEXT, TODAS_UFS, aplicar_tema

# ---------------------------------------------------------------------------
# Chart 31 — Emendas × Infraestrutura de Saúde (Leitos/10k por município)
# ---------------------------------------------------------------------------

@register_chart(
    id="saude_leitos_emendas",
    title="31. Emendas × Infraestrutura de Saúde (Leitos/10k hab.)",
    description=(
        "Scatter plot cruzando o volume de emendas recebidas com a "
        "disponibilidade de leitos hospitalares por 10 mil habitantes. "
        "Cor = região; tamanho = população. "
        "Identifica municípios que recebem muitos recursos mas têm baixa capacidade hospitalar."
    ),
    category="Análise Econômica",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS",
        ),
    ],
)
def chart_saude_leitos_emendas(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio, m.uf, m.regiao, m.populacao,
            sm.total_leitos, sm.hospitais, sm.ubs, sm.total_profissionais,
            COALESCE(SUM(v.valor_total), 0)             AS total_emendas,
            ROUND(sm.total_leitos * 10000.0 / NULLIF(m.populacao, 0), 2)  AS leitos_10k,
            ROUND(COALESCE(SUM(v.valor_total), 0) / NULLIF(m.populacao, 0), 2) AS emenda_pc
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        JOIN saude_municipios sm ON m.municipio_id = sm.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND m.populacao > 1000
          AND sm.total_leitos > 0
          AND (%s = 'TODOS' OR m.regiao = %s)
        GROUP BY m.nome, m.uf, m.regiao, m.populacao,
                 sm.total_leitos, sm.hospitais, sm.ubs, sm.total_profissionais
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 150;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de saúde disponíveis para esta região.",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "31. Emendas × Infraestrutura de Saúde")

    df["populacao"] = df["populacao"].clip(lower=1)
    df["regiao"] = df["regiao"].fillna("Outros").astype(str)

    fig = px.scatter(
        df,
        x="total_emendas",
        y="leitos_10k",
        size="populacao",
        color="regiao",
        hover_name="municipio",
        hover_data={
            "uf": True,
            "populacao": ":,.0f",
            "total_leitos": ":,.0f",
            "hospitais": True,
            "ubs": True,
            "emenda_pc": ":,.2f",
            "leitos_10k": ":.2f",
            "regiao": False,
        },
        size_max=45,
        color_discrete_sequence=px.colors.qualitative.Set2,
        labels={
            "total_emendas": "Total de Emendas (R$)",
            "leitos_10k": "Leitos por 10 mil hab.",
            "regiao": "Região",
            "populacao": "População",
        },
        log_x=True,
    )

    # Linha de referência: média nacional de leitos (2.1/10k)
    fig.add_hline(
        y=2.1, line_dash="dash", line_color="#f59e0b", line_width=1.5,
    )
    fig.add_annotation(
        x=0.98, y=2.1, xref="paper", yref="y",
        text="Média Nacional: 2.1 leitos/10k", showarrow=False,
        font=dict(size=10, color="#f59e0b"), xanchor="right", yshift=10,
    )

    return aplicar_tema(fig, "31. Emendas × Infraestrutura de Saúde (Leitos/10k hab.)", 520)


# ---------------------------------------------------------------------------
# Chart 32 — Emendas × Resultado Orçamentário Municipal (Superávit/Déficit)
# ---------------------------------------------------------------------------

@register_chart(
    id="emendas_resultado_orcamentario",
    title="32. Emendas × Resultado Orçamentário Municipal",
    description=(
        "Analisa se municípios com maior dependência de emendas parlamentares "
        "apresentam piores resultados orçamentários. "
        "X = Resultado Primário (R$), Y = Total de Emendas. "
        "Cor = situação fiscal (superávit/déficit)."
    ),
    category="Análise Econômica",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_emendas_resultado_orcamentario(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio, m.uf, m.regiao, m.populacao,
            COALESCE(SUM(v.valor_total), 0)   AS total_emendas,
            mf.resultado_primario,
            mf.receitas_correntes,
            mf.despesas_correntes,
            mf.receitas_transferencias,
            ROUND(100.0 * mf.receitas_transferencias
                  / NULLIF(mf.receitas_correntes, 0), 1) AS pct_dep_transferencias
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND mf.receitas_correntes > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.nome, m.uf, m.regiao, m.populacao,
                 mf.resultado_primario, mf.receitas_correntes,
                 mf.despesas_correntes, mf.receitas_transferencias
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 120;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados fiscais para o filtro selecionado.",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "32. Emendas × Resultado Orçamentário Municipal")

    import pandas as pd
    df["resultado_primario"] = pd.to_numeric(df["resultado_primario"], errors="coerce").fillna(0)
    df["situacao_fiscal"] = df["resultado_primario"].apply(
        lambda x: "✅ Superávit" if x > 0 else "🔴 Déficit"
    )
    df["populacao"] = df["populacao"].clip(lower=1)

    cor_map = {"✅ Superávit": "#22c55e", "🔴 Déficit": "#ef4444"}

    fig = px.scatter(
        df,
        x="resultado_primario",
        y="total_emendas",
        size="populacao",
        color="situacao_fiscal",
        color_discrete_map=cor_map,
        hover_name="municipio",
        hover_data={
            "uf": True,
            "regiao": True,
            "pct_dep_transferencias": ":.1f",
            "receitas_correntes": ":,.0f",
            "despesas_correntes": ":,.0f",
            "resultado_primario": ":,.0f",
            "situacao_fiscal": False,
            "populacao": ":,.0f",
        },
        size_max=40,
        labels={
            "resultado_primario": "Resultado Primário (R$)",
            "total_emendas": "Total de Emendas Recebidas (R$)",
            "situacao_fiscal": "Situação Fiscal",
            "populacao": "População",
        },
    )

    fig.add_vline(x=0, line_dash="solid", line_color="#475569", line_width=1)
    fig.add_annotation(
        x=0, y=0.99, xref="x", yref="paper",
        text="Equilíbrio Fiscal", showarrow=False,
        font=dict(size=10, color="#94a3b8"), xanchor="left", yshift=8,
    )

    return aplicar_tema(fig, "32. Emendas × Resultado Orçamentário Municipal", 520)


# ---------------------------------------------------------------------------
# Chart 33 — Ranking: Receita Per Capita × Emenda Per Capita por UF
# ---------------------------------------------------------------------------

@register_chart(
    id="receita_vs_emenda_per_capita_uf",
    title="33. Receita vs. Emenda Per Capita por Estado (UF)",
    description=(
        "Compara a capacidade de arrecadação própria (Receita Corrente per capita) "
        "com o volume de emendas recebidas per capita por estado. "
        "UFs com alta emenda e baixa receita própria são as mais dependentes."
    ),
    category="Análise Econômica",
)
def chart_receita_vs_emenda_per_capita_uf() -> go.Figure:
    query = """
        SELECT
            m.uf,
            m.regiao,
            SUM(m.populacao) AS populacao_total,
            AVG(mf.receitas_correntes / NULLIF(m.populacao, 0)) AS receita_pc_media,
            SUM(COALESCE(v.valor_total, 0)) AS total_emendas,
            ROUND(SUM(COALESCE(v.valor_total, 0)) / NULLIF(SUM(m.populacao), 0), 2)
                AS emenda_pc
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        LEFT JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL AND m.populacao > 0
        GROUP BY m.uf, m.regiao
        HAVING SUM(COALESCE(v.valor_total, 0)) > 0
        ORDER BY emenda_pc DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados disponíveis.", showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "33. Receita vs. Emenda Per Capita por UF")

    import pandas as pd
    df["receita_pc_media"] = pd.to_numeric(df["receita_pc_media"], errors="coerce").fillna(0)
    df["emenda_pc"] = pd.to_numeric(df["emenda_pc"], errors="coerce").fillna(0)

    REGIAO_CORES = {
        "Norte": "#0ea5e9", "Nordeste": "#f59e0b", "Sudeste": "#22c55e",
        "Sul": "#a855f7", "Centro-Oeste": "#ef4444",
    }
    df["cor"] = df["regiao"].map(REGIAO_CORES).fillna("#64748b")

    fig = go.Figure()

    for regiao in df["regiao"].dropna().unique():
        dfr = df[df["regiao"] == regiao]
        fig.add_trace(go.Scatter(
            x=dfr["receita_pc_media"],
            y=dfr["emenda_pc"],
            mode="markers+text",
            name=regiao,
            text=dfr["uf"],
            textposition="top center",
            textfont=dict(size=10, color=THEME_TEXT),
            marker=dict(
                size=14,
                color=REGIAO_CORES.get(regiao, "#64748b"),
                line=dict(width=1, color="#1e293b"),
                opacity=0.85,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Receita per capita: R$ %{x:,.0f}<br>"
                "Emenda per capita: R$ %{y:,.2f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis=dict(
            title="Receita Corrente Per Capita Média (R$/hab)",
            gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT),
        ),
        yaxis=dict(
            title="Emenda Per Capita (R$/hab)",
            gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT),
        ),
    )

    return aplicar_tema(fig, "33. Receita vs. Emenda Per Capita por Estado (UF)", 520)


# ---------------------------------------------------------------------------
# Chart 34 — Heatmap: Distribuição de Emendas por Situação × Região
# ---------------------------------------------------------------------------

@register_chart(
    id="heatmap_situacao_regiao",
    title="34. Heatmap: Volume de Emendas por Situação × Região",
    description=(
        "Mapa de calor mostrando a distribuição financeira das emendas "
        "parlamentares por situação (IMPEDIDO, EM_EXECUCAO, CONCLUIDO…) "
        "cruzada com cada região geográfica do Brasil."
    ),
    category="Análise Econômica",
)
def chart_heatmap_situacao_regiao() -> go.Figure:
    query = """
        SELECT
            COALESCE(m.regiao, 'Sem Região')   AS regiao,
            v.status_execucao                   AS situacao,
            COUNT(*)                            AS total_planos,
            COALESCE(SUM(v.valor_total), 0)    AS valor_total
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND v.status_execucao IS NOT NULL
        GROUP BY m.regiao, v.status_execucao
        ORDER BY valor_total DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados disponíveis.", showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "34. Heatmap: Emendas por Situação × Região")

    pivot = df.pivot_table(
        index="situacao",
        columns="regiao",
        values="valor_total",
        aggfunc="sum",
        fill_value=0,
    )

    # Ordenar situações por volume total
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

    z_vals = pivot.values.tolist()
    text_vals = [
        [f"R$ {v/1e6:.1f}M" if v > 0 else "" for v in row]
        for row in z_vals
    ]

    fig = go.Figure(go.Heatmap(
        z=z_vals,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=11, color=THEME_TEXT),
        colorscale=[
            [0.0, "#0f172a"],
            [0.2, "#1e3a5f"],
            [0.5, "#1d4ed8"],
            [0.8, "#22c55e"],
            [1.0, "#f59e0b"],
        ],
        hovertemplate=(
            "<b>%{y}</b> — %{x}<br>"
            "Valor: R$ %{z:,.0f}<br>"
            "<extra></extra>"
        ),
        showscale=True,
        colorbar=dict(
            title="Valor (R$)",
            title_font=dict(color=THEME_TEXT),
            tickfont=dict(color=THEME_TEXT),
        ),
    ))

    fig.update_layout(
        xaxis=dict(title="Região", tickfont=dict(color=THEME_TEXT)),
        yaxis=dict(title="Situação da Emenda", tickfont=dict(color=THEME_TEXT)),
    )

    return aplicar_tema(fig, "34. Heatmap: Volume de Emendas por Situação × Região", 500)


# ---------------------------------------------------------------------------
# Chart 35 — PIB per Capita vs Emendas per Capita por UF
# ---------------------------------------------------------------------------

@register_chart(
    id="econ_pib_emendas",
    title="35. PIB per Capita vs Emendas per Capita por UF",
    description=(
        "Scatter plot comparando a riqueza média do estado (PIB per capita IBGE) "
        "com o volume de emendas recebidas por habitante. Estados no canto inferior "
        "direito são ricos e pouco dependem de emendas; no canto superior esquerdo, "
        "pobres e com alta concentração de repasses."
    ),
    category="Análise Econômica",
)
def chart_econ_pib_emendas() -> go.Figure:
    query = """
        SELECT
            m.uf,
            m.regiao,
            AVG(m.pib / NULLIF(m.populacao, 0)) AS pib_per_capita,
            SUM(m.populacao) AS populacao_total,
            SUM(COALESCE(v.valor_total, 0)) AS total_emendas,
            ROUND(
                SUM(COALESCE(v.valor_total, 0)) / NULLIF(SUM(m.populacao), 0), 2
            ) AS emenda_per_capita,
            COUNT(DISTINCT v.beneficiario_nome) AS num_beneficiarios
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND m.pib > 0
          AND m.populacao > 0
        GROUP BY m.uf, m.regiao
        HAVING SUM(COALESCE(v.valor_total, 0)) > 0
        ORDER BY emenda_per_capita DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de PIB disponíveis para cruzamento",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "35. PIB per Capita vs Emendas per Capita por UF")

    import pandas as pd
    df["pib_per_capita"] = pd.to_numeric(df["pib_per_capita"], errors="coerce").fillna(0)
    df["emenda_per_capita"] = pd.to_numeric(df["emenda_per_capita"], errors="coerce").fillna(0)
    df["populacao_total"] = df["populacao_total"].clip(lower=1)

    REGIAO_CORES = {
        "Norte": "#0ea5e9", "Nordeste": "#f59e0b", "Sudeste": "#22c55e",
        "Sul": "#a855f7", "Centro-Oeste": "#ef4444",
    }

    fig = go.Figure()
    for regiao in df["regiao"].dropna().unique():
        dfr = df[df["regiao"] == regiao]
        fig.add_trace(go.Scatter(
            x=dfr["pib_per_capita"],
            y=dfr["emenda_per_capita"],
            mode="markers+text",
            name=regiao,
            text=dfr["uf"],
            textposition="top center",
            textfont=dict(size=10, color=THEME_TEXT),
            marker=dict(
                size=np.sqrt(dfr["populacao_total"] / dfr["populacao_total"].max()) * 50 + 10,
                color=REGIAO_CORES.get(regiao, "#64748b"),
                line=dict(width=1, color="#1e293b"),
                opacity=0.85,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "PIB/hab: R$ %{x:,.0f}<br>"
                "Emendas/hab: R$ %{y:,.2f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        xaxis=dict(
            title="PIB per Capita Médio (R$/hab)",
            gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT),
        ),
        yaxis=dict(
            title="Emendas per Capita (R$/hab)",
            gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT),
        ),
    )

    return aplicar_tema(fig, "35. PIB per Capita vs Emendas per Capita por UF", 520)


# ---------------------------------------------------------------------------
# Chart 36 — IDHM vs Dependência de Transferências
# ---------------------------------------------------------------------------

@register_chart(
    id="econ_idhm_transferencias",
    title="36. IDHM vs Dependência de Transferências por Município",
    description=(
        "Scatter cruzando o Índice de Desenvolvimento Humano Municipal (IDHM) "
        "com a % de receita oriunda de transferências intergovernamentais. "
        "Municípios com baixo IDHM e alta dependência são prioritários para "
        "investimentos em capacitação de receita própria."
    ),
    category="Análise Econômica",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS",
        ),
    ],
)
def chart_econ_idhm_transferencias(regiao_filter: str = "TODOS") -> go.Figure:
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
        WHERE m.pib > 0
          AND m.populacao > 0
          AND mf.arrec_iptu > 0
          AND m.populacao > 10000
          AND (%s = 'TODOS' OR m.regiao = %s)
        ORDER BY m.populacao DESC
        LIMIT 200;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de PIB/IPTU suficientes",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "36. PIB per Capita vs IPTU Arrecadado por Município")

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
                opacity=0.7,
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

    return aplicar_tema(fig, "36. PIB per Capita vs IPTU Arrecadado por Município", 550)


# ---------------------------------------------------------------------------
# Chart 37 — Ranking de Autonomia Fiscal Municipal (Top 30)
# ---------------------------------------------------------------------------

@register_chart(
    id="econ_ranking_autonomia",
    title="37. Ranking de Autonomia Fiscal: Municípios Mais Autônomos",
    description=(
        "Top 30 municípios com maior % de receita própria (impostos + contribuições) "
        "em relação à receita corrente total. Indica a capacidade de financiar "
        "serviços públicos sem depender de transferências federais/estaduais."
    ),
    category="Análise Econômica",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_econ_ranking_autonomia(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...] = (uf_filter, uf_filter) if uf_filter != "TODOS" else ("TODOS", "TODOS")

    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            m.uf,
            m.regiao,
            m.populacao,
            mf.receitas_correntes,
            mf.receitas_capital,
            ROUND(
                mf.receitas_correntes / NULLIF(m.populacao, 0), 2
            ) AS receita_per_capita
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes > 5000000
          AND m.populacao > 10000
          AND (%s = 'TODOS' OR m.uf = %s)
        ORDER BY receita_per_capita DESC
        LIMIT 30;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados suficientes para ranking de autonomia fiscal",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "37. Ranking de Autonomia Fiscal Municipal")

    import pandas as pd
    df["receita_per_capita"] = pd.to_numeric(
        df["receita_per_capita"], errors="coerce"
    ).fillna(0)

    cores = []
    for val in df["receita_per_capita"]:
        q75 = df["receita_per_capita"].quantile(0.75)
        q50 = df["receita_per_capita"].quantile(0.5)
        if val >= q75:
            cores.append("#22c55e")
        elif val >= q50:
            cores.append("#3b82f6")
        else:
            cores.append("#f59e0b")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["receita_per_capita"],
        y=df["municipio_uf"],
        orientation="h",
        marker_color=cores,
        text=df["receita_per_capita"].apply(lambda x: f"R$ {x:,.0f}"),
        textposition="outside",
        textfont=dict(size=10, color=THEME_TEXT),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Receita per capita: R$ %{x:,.0f}<br>"
            "Receita corrente: R$ %{customdata[0]:,.0f}<br>"
            "Receita capital: R$ %{customdata[1]:,.0f}<br>"
            "<extra></extra>"
        ),
        customdata=df[["receitas_correntes", "receitas_capital"]].values,
    ))

    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis=dict(
            title="Receita Corrente per Capita (R$/hab)",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
        ),
    )

    return aplicar_tema(fig, "37. Ranking de Receita per Capita: Top 30 Municípios", 600)
