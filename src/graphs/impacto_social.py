"""Charts 20, 21 — Impact/Social analysis (health & education)."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, aplicar_tema

# Média nacional de leitos por 10 mil habitantes (Fonte: MS/DataSUS)
BRASIL_MEDIA_LEITOS = 2.1

# Meta IDEB nacional (Plano Nacional de Educação)
META_IDEB_NACIONAL = 5.0


# ---------------------------------------------------------------------------
# Chart 20 — Impacto na Saúde: Leitos por R$ Repassado via Emendas
# ---------------------------------------------------------------------------


@register_chart(
    id="impacto_saude",
    title="20. Impacto na Saúde: Leitos por R$ Repassado via Emendas",
    description=(
        "Scatter plot cruzando investimento per capita em emendas parlamentares "
        "com a disponibilidade de leitos hospitalares por 10 mil habitantes. "
        "Tamanho do ponto = volume total de emendas."
    ),
    category="Impacto Social",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS",
        ),
    ],
)
def chart_impacto_saude(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            COALESCE(NULLIF(m.regiao, ''), 'Outros') AS regiao,
            COALESCE(m.populacao, 0) AS populacao,
            COALESCE(sm.total_leitos, 0) AS total_leitos,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            COUNT(DISTINCT v.codigo_emenda) AS qtd_emendas
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        LEFT JOIN saude_municipios sm ON m.municipio_id = sm.municipio_id
        WHERE (%s = 'TODOS' OR m.regiao = %s)
          AND v.beneficiario_ibge IS NOT NULL
          AND COALESCE(m.populacao, 0) > 0
        GROUP BY m.nome, m.uf, m.regiao, m.populacao, sm.total_leitos
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 120;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado de saúde encontrado para a região selecionado. "
            "Execute o enriquecedor de saúde primeiro.",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "20. Impacto na Saúde: Leitos por R$ Repassado via Emendas")

    # Computed metrics
    df["leitos_por_10k"] = (df["total_leitos"] / df["populacao"]) * 10_000
    df["emendas_per_capita"] = df["total_emendas"] / df["populacao"]
    df["regiao"] = df["regiao"].fillna("Não Informado").astype(str)

    fig = px.scatter(
        df,
        x="emendas_per_capita",
        y="leitos_por_10k",
        size="total_emendas",
        color="regiao",
        hover_name="municipio",
        hover_data={
            "uf": True,
            "populacao": ":,.0f",
            "total_leitos": ":,.0f",
            "total_emendas": ":.2f",
            "emendas_per_capita": ":.4f",
            "leitos_por_10k": ":.2f",
            "regiao": False,
        },
        labels={
            "emendas_per_capita": "Emendas Per Capita (R$/hab)",
            "leitos_por_10k": "Leitos por 10 mil hab.",
            "regiao": "Região",
            "total_emendas": "Total Emendas (R$)",
        },
        size_max=45,
    )

    # Horizontal line at national average (2.1 leitos per 10k)
    fig.add_hline(
        y=BRASIL_MEDIA_LEITOS,
        line_dash="dash",
        line_color="#f59e0b",
        line_width=2,
    )
    fig.add_annotation(
        x=0.98,
        y=BRASIL_MEDIA_LEITOS,
        xref="paper",
        yref="y",
        text=f"Média Nacional: {BRASIL_MEDIA_LEITOS} leitos/10k",
        showarrow=False,
        font=dict(size=11, color="#f59e0b"),
        xanchor="right",
        yshift=12,
    )

    return aplicar_tema(fig, "20. Impacto na Saúde: Leitos por R$ Repassado via Emendas")


# ---------------------------------------------------------------------------
# Chart 21 — IDEB × Investimento em Educação via Emendas
# ---------------------------------------------------------------------------


@register_chart(
    id="ideb_vs_emendas",
    title="21. IDEB × Investimento em Educação via Emendas",
    description=(
        "Scatter plot relacionando o IDEB médio municipal (anos iniciais + finais) "
        "com o volume total de emendas destinadas ao município. "
        "Tamanho do ponto = matrículas totais."
    ),
    category="Impacto Social",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_ideb_vs_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            COALESCE(em.ideb_initial_years, 0) AS ideb_initial_years,
            COALESCE(em.ideb_final_years, 0) AS ideb_final_years,
            COALESCE(em.matriculas_totais, 0) AS matriculas_totais,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            COUNT(DISTINCT v.codigo_emenda) AS qtd_emendas
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN educacao_municipios em ON m.municipio_id = em.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND em.ideb_initial_years IS NOT NULL
        GROUP BY m.nome, m.uf, em.ideb_initial_years, em.ideb_final_years, em.matriculas_totais
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 120;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado educacional (IDEB) encontrado para o estado selecionado. "
            "Execute o enriquecedor de educação primeiro.",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "21. IDEB × Investimento em Educação via Emendas")

    # IDEB médio = (anos iniciais + anos finais) / 2
    df["ideb_medio"] = (df["ideb_initial_years"] + df["ideb_final_years"]) / 2

    fig = px.scatter(
        df,
        x="total_emendas",
        y="ideb_medio",
        size="matriculas_totais",
        color="uf",
        hover_name="municipio",
        hover_data={
            "uf": True,
            "ideb_initial_years": ":.2f",
            "ideb_final_years": ":.2f",
            "ideb_medio": ":.2f",
            "matriculas_totais": ":,.0f",
            "total_emendas": ":.2f",
        },
        labels={
            "total_emendas": "Total de Emendas (R$)",
            "ideb_medio": "IDEB Médio",
            "uf": "UF",
            "matriculas_totais": "Matrículas Totais",
        },
        size_max=45,
    )

    # Horizontal line at national IDEB target (5.0)
    fig.add_hline(
        y=META_IDEB_NACIONAL,
        line_dash="dash",
        line_color="#f59e0b",
        line_width=2,
    )
    fig.add_annotation(
        x=0.98,
        y=META_IDEB_NACIONAL,
        xref="paper",
        yref="y",
        text=f"Meta IDEB Nacional: {META_IDEB_NACIONAL}",
        showarrow=False,
        font=dict(size=11, color="#f59e0b"),
        xanchor="right",
        yshift=12,
    )

    return aplicar_tema(fig, "21. IDEB × Investimento em Educação via Emendas")
