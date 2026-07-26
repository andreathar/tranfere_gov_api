"""Charts 1, 2, 7 — Parliamentary analysis."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import CORES_SITUACAO, TODAS_UFS, aplicar_tema


@register_chart(
    id="eficiencia_partidos",
    title="1. Eficiência na Execução de Emendas por Partido",
    description="Proporção do volume de emendas aprovadas/concluídas vs impedidas por partido político.",
    category="Parlamentar",
    controls=[
        ControlSpec(
            id="uf_filter", label="Filtrar por Estado (UF)", options=TODAS_UFS, default="TODOS"
        )
    ],
)
def chart_eficiencia_partidos(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            p.sigla_partido,
            v.status_execucao,
            COUNT(*) as total_planos,
            SUM(v.valor_total) as valor_total
        FROM v_emendas_unificadas v
        JOIN parlamentares_dados p ON v.parlamentar_nome ILIKE CONCAT('%%', p.nome_urna, '%%')
        WHERE (%s = 'TODOS' OR p.uf = %s)
        GROUP BY p.sigla_partido, v.status_execucao
        ORDER BY valor_total DESC
        LIMIT 50;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "1. Eficiência na Execução de Emendas por Partido")

    fig = px.bar(
        df,
        x="sigla_partido",
        y="valor_total",
        color="status_execucao",
        title="1. Eficiência na Execução de Emendas por Partido",
        color_discrete_map=CORES_SITUACAO,
        labels={
            "sigla_partido": "Partido",
            "valor_total": "Valor Total (R$)",
            "status_execucao": "Situação",
        },
    )
    return aplicar_tema(fig, "1. Eficiência na Execução de Emendas por Partido")


@register_chart(
    id="top_parlamentares_valores",
    title="2. Top 15 Deputados por Volume de Emendas",
    description="Ranking dos deputados com maior montante em emendas parlamentares aprovadas.",
    category="Parlamentar",
)
def chart_top_parlamentares() -> go.Figure:
    query = """
        SELECT
            parlamentar_nome,
            SUM(valor_total) as valor_total,
            COUNT(*) as qtd_emendas
        FROM v_emendas_unificadas
        WHERE parlamentar_nome IS NOT NULL
        GROUP BY parlamentar_nome
        ORDER BY valor_total DESC
        LIMIT 15;
    """
    import pandas as pd

    df = query_df(query)
    df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0.0)

    fig = px.bar(
        df,
        x="valor_total",
        y="parlamentar_nome",
        orientation="h",
        text_auto=".2s",
        color="valor_total",
        color_continuous_scale="Viridis",
        labels={"parlamentar_nome": "Deputado", "valor_total": "Valor Total (R$)"},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "2. Top 15 Deputados por Volume de Emendas")


@register_chart(
    id="impedimentos_por_partido",
    title="7. Matriz de Risco: Volume Total vs. Taxa de Rejeição por Partido",
    description="Cruzamento entre a quantidade total alocada por partido e sua respectiva taxa de impedimento técnico/rejeição.",
    category="Análise Parlamentar",
)
def chart_impedimentos_por_partido() -> go.Figure:
    query = """
        SELECT
            COALESCE(pd.sigla_partido, 'OUTROS') as partido,
            COUNT(*) as total_planos,
            SUM(pa.valor_total) as valor_total,
            SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) as impedidos,
            ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) / COUNT(*), 1) as taxa_impedimento_pct
        FROM planos_acao pa
        JOIN parlamentares_dados pd ON pa.parlamentar_nome ILIKE CONCAT('%%', pd.nome_urna, '%%')
        GROUP BY pd.sigla_partido
        HAVING COUNT(*) >= 10
        ORDER BY valor_total DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de partidos não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "7. Matriz de Risco: Volume Total vs. Taxa de Rejeição por Partido"
        )

    fig = px.scatter(
        df,
        x="valor_total",
        y="taxa_impedimento_pct",
        size="total_planos",
        color="taxa_impedimento_pct",
        text="partido",
        color_continuous_scale="OrRd",
        labels={
            "valor_total": "Volume Total Alocado (R$)",
            "taxa_impedimento_pct": "Taxa de Impedimento (%)",
            "partido": "Partido",
        },
        hover_data=["total_planos", "impedidos"],
    )
    fig.update_traces(
        textposition="top center",
        marker=dict(sizeref=2.0 * max(df["total_planos"]) / (40**2), sizemin=8),
    )
    return aplicar_tema(fig, "7. Matriz de Risco: Volume Total vs. Taxa de Rejeição por Partido")
