"""Charts 22-23 — Temporal trends and parliamentary-electoral analysis."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, THEME_GRID, THEME_TEXT, aplicar_tema


# ---------------------------------------------------------------------------
# Chart 22 — Tendência Temporal: Volume de Repasses e Indicadores Econômicos
# ---------------------------------------------------------------------------

@register_chart(
    id="tendencia_temporal",
    title="22. Tendência Temporal: Volume de Repasses e Indicadores Econômicos",
    description=(
        "Evolução mensal do volume total de repasses (barras) e quantidade de "
        "parlamentares distintos envolvidos (linha) ao longo do tempo."
    ),
    category="Temporal",
    controls=[
        ControlSpec(
            id="ano_filter",
            label="Filtrar por Ano",
            options=["TODOS", "2024", "2025", "2026"],
            default="TODOS",
        ),
    ],
)
def chart_tendencia_temporal(ano_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...]
    if ano_filter != "TODOS":
        params = (ano_filter, ano_filter)
    else:
        params = (ano_filter, "9999")

    query = """
        SELECT
            TO_CHAR(DATE_TRUNC('month', pa.extracted_at), 'YYYY-MM') AS mes,
            COUNT(*)                          AS total_planos,
            COALESCE(SUM(pa.valor_total), 0)  AS valor_total,
            COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares
        FROM planos_acao pa
        WHERE (%s = 'TODOS'
               OR EXTRACT(YEAR FROM pa.extracted_at) = %s::INTEGER)
        GROUP BY DATE_TRUNC('month', pa.extracted_at)
        ORDER BY mes;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o período selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "22. Tendência Temporal: Volume de Repasses e Indicadores Econômicos",
            altura=500,
        )

    fig = go.Figure()

    # Primary trace — valor total as bars (left y-axis)
    fig.add_trace(
        go.Bar(
            x=df["mes"],
            y=df["valor_total"],
            name="Valor Total (R$)",
            marker_color="#3b82f6",
            yaxis="y",
        )
    )

    # Secondary trace — parlamentares as line+markers (right y-axis)
    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["parlamentares"],
            name="Parlamentares Distintos",
            mode="lines+markers",
            line=dict(color="#f59e0b", width=2),
            marker=dict(size=6),
            yaxis="y2",
        )
    )

    fig.update_layout(
        barmode="stack",
        xaxis=dict(
            title="Mês",
            gridcolor=THEME_GRID,
            tickfont=dict(color=THEME_TEXT),
        ),
        yaxis=dict(
            title="Valor Total (R$)",
            titlefont=dict(color="#3b82f6"),
            tickfont=dict(color="#3b82f6"),
            gridcolor=THEME_GRID,
        ),
        yaxis2=dict(
            title="Parlamentares Distintos",
            titlefont=dict(color="#f59e0b"),
            tickfont=dict(color="#f59e0b"),
            overlaying="y",
            side="right",
            gridcolor="rgba(0,0,0,0)",
        ),
    )

    return aplicar_tema(
        fig,
        "22. Tendência Temporal: Volume de Repasses e Indicadores Econômicos",
        altura=500,
    )


# ---------------------------------------------------------------------------
# Chart 23 — Resultado Eleitoral × Distribuição de Emendas
# ---------------------------------------------------------------------------

@register_chart(
    id="eleicao_emendas",
    title="23. Resultado Eleitoral × Distribuição de Emendas",
    description=(
        "Relação entre quantidade de emendas por município, volume financeiro e "
        "tamanho populacional, colorido por partido predominante."
    ),
    category="Análise Parlamentar",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_eleicao_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome                                   AS municipio,
            m.uf,
            m.municipio_id,
            COALESCE(mi.populacao, 0)                 AS populacao,
            p.sigla_partido,
            p.situacao,
            COUNT(DISTINCT v.id)                      AS qtd_emendas,
            COALESCE(SUM(v.valor_total), 0)           AS total_emendas
        FROM v_emendas_unificadas v
        JOIN beneficiarios b
            ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm
            ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m
            ON bm.municipio_id = m.municipio_id
        LEFT JOIN parlamentares_dados p
            ON v.parlamentar_nome ILIKE CONCAT('%%', p.nome_urna, '%%')
        LEFT JOIN municipios_ibge mi
            ON m.municipio_id = mi.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
        GROUP BY
            m.nome, m.uf, m.municipio_id,
            mi.populacao,
            p.sigla_partido, p.situacao
        HAVING COUNT(DISTINCT v.id) > 0
        ORDER BY total_emendas DESC;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o estado selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "23. Resultado Eleitoral × Distribuição de Emendas",
        )

    # Determine top-10 parties by total_emendas; collapse the rest to "OUTROS"
    partido_totals = (
        df.groupby("sigla_partido", dropna=False)["total_emendas"]
        .sum()
        .sort_values(ascending=False)
    )
    top_partidos = set(partido_totals.index[:10]) if len(partido_totals) >= 10 else set(partido_totals.index)
    df["partido_grupo"] = df["sigla_partido"].apply(
        lambda x: x if x in top_partidos and x is not None else "OUTROS"
    )

    fig = px.scatter(
        df,
        x="qtd_emendas",
        y="total_emendas",
        size="populacao",
        color="partido_grupo",
        hover_name="municipio",
        hover_data=["uf", "situacao", "populacao"],
        size_max=50,
        labels={
            "qtd_emendas": "Quantidade de Emendas",
            "total_emendas": "Valor Total (R$)",
            "populacao": "População",
            "partido_grupo": "Partido",
        },
    )

    return aplicar_tema(
        fig,
        "23. Resultado Eleitoral × Distribuição de Emendas",
    )
