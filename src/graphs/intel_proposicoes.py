import plotly.express as px
import pandas as pd
from src.graphs.registry import register_chart
from src.graphs.theme import aplicar_tema
from src.db_utils import query_df

@register_chart(
    id="emendas_vs_proposicoes",
    title="Emendas PIX vs Proposições (Atividade Legislativa)",
    description="Cruza o valor total recebido por cada parlamentar com o volume de proposições.",
    category="Inteligência Política"
)
def grafico_emendas_vs_proposicoes():
    """
    Cruza o valor total recebido por cada parlamentar (Emendas PIX)
    com o total de proposições registradas na Câmara.
    """
    df = query_df("""
        WITH emendas AS (
            SELECT parlamentar_nome, SUM(valor_total) as valor_recebido
            FROM planos_acao
            WHERE parlamentar_nome IS NOT NULL
            GROUP BY parlamentar_nome
        ),
        proposicoes AS (
            SELECT parlamentar_nome, COUNT(*) as qtd_proposicoes
            FROM parlamentar_proposicoes
            GROUP BY parlamentar_nome
        )
        SELECT 
            e.parlamentar_nome,
            e.valor_recebido,
            COALESCE(p.qtd_proposicoes, 0) as qtd_proposicoes
        FROM emendas e
        LEFT JOIN proposicoes p ON e.parlamentar_nome = p.parlamentar_nome
        WHERE p.qtd_proposicoes > 0 OR e.valor_recebido > 0
    """)

    if df.empty:
        return px.scatter(title="Sem dados suficientes")

    # Formatação de texto para o hover
    df['valor_formatado'] = df['valor_recebido'].apply(lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Criar bolhas com variação de tamanho, cor baseado no valor_recebido
    fig = px.scatter(
        df,
        x="qtd_proposicoes",
        y="valor_recebido",
        hover_name="parlamentar_nome",
        hover_data={"qtd_proposicoes": True, "valor_recebido": False, "valor_formatado": True, "parlamentar_nome": False},
        labels={
            "qtd_proposicoes": "Volume de Proposições (Últimos 30 dias)",
            "valor_recebido": "Total em Emendas PIX (R$)"
        },
        template=GRAPH_THEME
    )
    
    # Textos seletivos para não poluir
    df['text'] = df.apply(lambda row: row['parlamentar_nome'] if row['qtd_proposicoes'] > 3 or row['valor_recebido'] > 10000000 else '', axis=1)
    
    fig.update_traces(
        mode='markers+text',
        text=df['text'],
        textposition='top center', 
        marker=dict(size=14, opacity=0.8, color="#ff4b4b", line=dict(width=1, color="white"))
    )
    
    fig.update_layout(
        yaxis_type="log", # Facilita visualização de grandes variações de R$
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        title_font=dict(size=18, color="white")
    )
    return fig
