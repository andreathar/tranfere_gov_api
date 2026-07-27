"""Gráficos relacionados às votações nominais da Câmara dos Deputados."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import aplicar_tema

CORES_VOTO = {
    "Sim": "#10b981",       # emerald-500
    "Não": "#ef4444",       # red-500
    "Abstenção": "#64748b", # slate-500
    "Obstrução": "#f59e0b", # amber-500
    "Liberado": "#3b82f6",  # blue-500
    "Art. 17": "#8b5cf6",   # violet-500
}

@register_chart(
    id="votacoes_temas_geral",
    title="Comportamento de Voto por Tema",
    description="Análise de como a Câmara votou (Sim, Não, Abstenção) em cada tema classificado pela IA.",
    category="Parlamentar",
    controls=[
        ControlSpec(
            id="deputado_nome",
            label="Buscar Deputado (Opcional)",
            options=["TODOS"],
            default="TODOS"
        )
    ],
)
def chart_votacoes_temas_geral(deputado_nome: str = "TODOS") -> go.Figure:
    query = """
        SELECT 
            vc.tema,
            v.tipo_voto,
            COUNT(*) as total_votos
        FROM votos_camara v
        JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id
        WHERE vc.tema IS NOT NULL
        AND (%s = 'TODOS' OR v.deputado_urna ILIKE CONCAT('%%', %s, '%%') OR v.deputado_nome ILIKE CONCAT('%%', %s, '%%'))
        GROUP BY vc.tema, v.tipo_voto
        ORDER BY total_votos DESC;
    """
    df = query_df(query, (deputado_nome, deputado_nome, deputado_nome))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "Comportamento de Voto por Tema")

    fig = px.bar(
        df,
        x="total_votos",
        y="tema",
        color="tipo_voto",
        color_discrete_map=CORES_VOTO,
        orientation="h",
        barmode="stack",
        labels={"total_votos": "Quantidade de Votos", "tema": "Tema da Votação", "tipo_voto": "Voto"},
    )
    
    fig.update_layout(yaxis={'categoryorder':'total ascending'})
    return aplicar_tema(fig, "Comportamento de Voto por Tema")
