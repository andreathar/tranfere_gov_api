"""Chart — Radar do Diário Oficial."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import aplicar_tema


@register_chart(
    id="radar_diario_timeline",
    title="Radar do Diário Oficial: Timeline de Atos Extraídos por IA",
    description="Monitoramento inteligente de publicações governamentais. O eixo Y representa o Tipo do Ato. Bolhas maiores indicam volume financeiro (quando aplicável).",
    category="Inteligência Política",
    controls=[
        ControlSpec(
            id="fonte_filter",
            label="Fonte da Publicação",
            options=["TODOS", "FEDERAL", "MUNICIPAL"],
            default="TODOS",
        )
    ],
)
def chart_radar_diario_timeline(fonte_filter: str = "TODOS") -> go.Figure:
    where_clause = ""
    params: tuple = ()
    if fonte_filter != "TODOS":
        where_clause = "WHERE fonte = %s"
        params = (fonte_filter,)

    query = f"""
        SELECT
            data_publicacao,
            tipo_ato,
            orgao,
            COALESCE(valor_financeiro, 0) as valor_financeiro,
            resumo_ia,
            fonte
        FROM diario_oficial_atos
        {where_clause}
        ORDER BY data_publicacao ASC
    """

    df = query_df(query, params)

    if df.empty:
        # Se não há dados, retorna figura vazia para o framework adicionar o aviso
        return go.Figure()

    # Ajusta valor para escalar as bolhas no gráfico
    # Adicionamos um valor base pequeno para que atos sem valor (0) ainda apareçam
    df["tamanho_bolha"] = df["valor_financeiro"].apply(
        lambda v: max(10, min(50, v / 100000 + 10)) if v > 0 else 10
    )

    # Prepara hover text HTML
    df["hover_text"] = df.apply(
        lambda r: (
            f"<b>{r['tipo_ato']}</b><br>"
            f"Órgão: {r['orgao']}<br>"
            f"Data: {r['data_publicacao']}<br>"
            f"Valor: R$ {r['valor_financeiro']:,.2f}<br>"
            f"Resumo IA: {r['resumo_ia'][:100]}..."
        ),
        axis=1,
    )

    fig = px.scatter(
        df,
        x="data_publicacao",
        y="tipo_ato",
        size="tamanho_bolha",
        color="tipo_ato",
        hover_name="hover_text",
        title="Atos do Diário Oficial no Tempo",
    )

    fig.update_traces(
        hovertemplate="%{hovertext}<extra></extra>",
        marker=dict(line=dict(width=1, color="DarkSlateGrey")),
    )

    fig.update_layout(
        xaxis_title="Data de Publicação",
        yaxis_title="Classificação (LLM)",
        showlegend=False,
        hovermode="closest",
    )

    return aplicar_tema(fig, "Radar do Diário Oficial: Timeline de Atos Extraídos por IA")
