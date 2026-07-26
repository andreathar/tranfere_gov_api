"""Charts 3, 6, 24 — Socioeconomic analysis."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, aplicar_tema


@register_chart(
    id="socioeconomico_idhm",
    title="3. Relação IDHM Municipal vs. Volume de Emendas",
    description="Mapeamento de investimentos: verifica se os repasses beneficiam municípios com menor IDHM.",
    category="Socioeconômico",
)
def chart_socioeconomico_idhm() -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio, m.uf, bm.municipio_id,
            SUM(v.valor_total) AS valor_total,
            COUNT(v.codigo_emenda) AS total_emendas
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        GROUP BY m.nome, m.uf, bm.municipio_id
        ORDER BY valor_total DESC LIMIT 30;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados de IDHM / IBGE em processamento", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "3. Relação IDHM Municipal vs. Volume de Emendas")

    fig = px.scatter(
        df, x="total_emendas", y="valor_total", size="valor_total", color="uf",
        hover_name="municipio",
        labels={"total_emendas": "Quantidade de Emendas", "valor_total": "Valor Total (R$)", "uf": "Estado"},
    )
    return aplicar_tema(fig, "3. Relação IDHM Municipal vs. Volume de Emendas")


@register_chart(
    id="investimento_per_capita_idhm",
    title="6. Repasse Per Capita (R$/hab) vs. Dependência Fiscal Municipal",
    description=(
        "Scatter plot cruzando o repasse per capita de emendas parlamentares "
        "com o índice de dependência fiscal do município (% receitas provenientes "
        "de transferências). Tamanho da bolha = população."
    ),
    category="Socioeconômico",
    controls=[ControlSpec(
        id="regiao_filter",
        label="Filtrar por Região",
        options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
        default="TODOS",
    )],
)
def chart_investimento_per_capita(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            COALESCE(NULLIF(m.regiao, ''), 'Outros') AS regiao,
            m.populacao,
            COALESCE(SUM(v.valor_total), 0)           AS total_emendas,
            ROUND(COALESCE(SUM(v.valor_total), 0) / NULLIF(m.populacao, 0), 2) AS valor_per_capita,
            mf.receitas_correntes,
            mf.receitas_transferencias,
            ROUND(
                100.0 * mf.receitas_transferencias / NULLIF(mf.receitas_correntes, 0),
                1
            ) AS pct_dependencia
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        LEFT JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND m.populacao > 0
          AND mf.receitas_correntes > 0
          AND (%s = 'TODOS' OR m.regiao = %s)
        GROUP BY m.nome, m.uf, m.regiao, m.populacao,
                 mf.receitas_correntes, mf.receitas_transferencias
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
          AND mf.receitas_transferencias > 0
        ORDER BY valor_per_capita DESC LIMIT 80;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados fiscais municipais para esta região",
            showarrow=False, font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "6. Repasse Per Capita vs. Dependência Fiscal")

    df["regiao"] = df["regiao"].astype(str).fillna("Não Informado")
    df["populacao"] = df["populacao"].clip(lower=1)
    df["pct_dependencia"] = pd.to_numeric(df["pct_dependencia"], errors="coerce").fillna(0)

    fig = px.scatter(
        df,
        x="pct_dependencia",
        y="valor_per_capita",
        size="populacao",
        color="regiao",
        hover_name="municipio",
        hover_data={
            "uf": True,
            "populacao": ":,.0f",
            "total_emendas": ":,.0f",
            "pct_dependencia": ":.1f",
            "valor_per_capita": ":,.2f",
            "regiao": False,
        },
        size_max=45,
        color_discrete_sequence=px.colors.qualitative.Set2,
        labels={
            "pct_dependencia": "Dependência Fiscal (% receitas de transferências)",
            "valor_per_capita": "Emenda Per Capita (R$/hab)",
            "regiao": "Região",
            "populacao": "População",
        },
    )

    # Reference line at 50% dependency
    fig.add_vline(
        x=50,
        line_dash="dash",
        line_color="#f59e0b",
        line_width=1.5,
    )
    fig.add_annotation(
        x=50, y=0.97, xref="x", yref="paper",
        text="50% dependência", showarrow=False,
        font=dict(size=10, color="#f59e0b"), xanchor="left",
    )

    return aplicar_tema(fig, "6. Repasse Per Capita vs. Dependência Fiscal Municipal", 500)



@register_chart(
    id="vulnerabilidade_social",
    title="24. Vulnerabilidade Fiscal × Indicadores Sociais (Radar Multi-Indicador)",
    description="Gráfico radar/spider que compara municípios em múltiplas dimensões: dependência fiscal, investimento em saúde, educação e emendas parlamentares.",
    category="Socioeconômico",
    controls=[ControlSpec(id="uf_filter", label="Filtrar por Estado (UF)", options=TODAS_UFS, default="TODOS")],
)
def chart_vulnerabilidade_social(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio, m.uf, m.populacao,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            mf.receitas_correntes, mf.receitas_transferencias,
            sm.total_leitos, em.ideb_initial_years
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        LEFT JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        LEFT JOIN saude_municipios sm ON m.municipio_id = sm.municipio_id
        LEFT JOIN educacao_municipios em ON m.municipio_id = em.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND mf.receitas_correntes > 0
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.nome, m.uf, m.populacao, mf.receitas_correntes,
                 mf.receitas_transferencias, sm.total_leitos, em.ideb_initial_years
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC LIMIT 10;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados suficientes para gerar radar. Execute os enriquecedores primeiro.", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "24. Vulnerabilidade Fiscal × Indicadores Sociais")

    from src.graphs.theme import THEME_CARD_BG, THEME_GRID, THEME_TEXT

    categories = [
        "Dependência de\nTransferências", "Investimento\nPer Capita",
        "Infraestrutura\nSaúde", "IDEB\nMunicipal", "Captação\nEmendas",
    ]
    fig = go.Figure()
    colors = px.colors.qualitative.Set2

    for idx, (_, row) in enumerate(df.iterrows()):
        dep_transf = (100 * row["receitas_transferencias"] / row["receitas_correntes"]
                      if row["receitas_correntes"] > 0 and pd.notna(row["receitas_transferencias"]) else 0)
        invest_pc = (row["total_emendas"] / row["populacao"] * 1000 if row["populacao"] > 0 else 0)
        saude = row["total_leitos"] if pd.notna(row["total_leitos"]) else 0
        ideb = row["ideb_initial_years"] if pd.notna(row["ideb_initial_years"]) else 0
        emendas_norm = min(row["total_emendas"] / 1e6, 100)

        max_dep = max(100, dep_transf)
        max_invest = max(10, invest_pc)
        max_saude = max(100, saude)
        max_ideb = max(10, ideb)
        max_emendas = max(100, emendas_norm)

        values = [
            dep_transf / max_dep * 100, invest_pc / max_invest * 100,
            saude / max_saude * 100, ideb / max_ideb * 100, emendas_norm / max_emendas * 100,
        ]
        values.append(values[0])

        fig.add_trace(go.Scatterpolar(
            r=values, theta=categories + [categories[0]], fill="toself",
            name=f"{row['municipio']} ({row['uf']})",
            line=dict(color=colors[idx % len(colors)]), opacity=0.6,
        ))

    fig.update_layout(
        polar=dict(
            bgcolor=THEME_CARD_BG,
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT, size=9)),
            angularaxis=dict(gridcolor=THEME_GRID, tickfont=dict(color=THEME_TEXT, size=10)),
        ),
        showlegend=True,
        legend=dict(bgcolor="rgba(15, 23, 42, 0.7)", bordercolor="#475569", borderwidth=1, font=dict(color=THEME_TEXT, size=10)),
    )
    return aplicar_tema(fig, "24. Vulnerabilidade Fiscal × Indicadores Sociais (Radar)", 550)
