#!/usr/bin/env python3
"""
TransfereGov — Interactive Dash + MCP Server App (Dash 4.3+).

Servidor Dash interativo que expõe gráficos Plotly em tempo real e atua como
um Servidor MCP completo no endpoint /_mcp.

Execução:
    python3 src/dash_app.py
"""

import logging

import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dcc, html
from dash.mcp import configure_mcp_server

from src.db_utils import fig_has_data
from src.graph_factory import CHART_REGISTRY, aplicar_tema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("dash_app")

# 1. Inicializa o aplicativo Dash com o Servidor MCP habilitado
app = Dash(__name__, enable_mcp=True, title="TransfereGov — Plotly MCP Hub")

# 2. Configura a descoberta e contexto de inteligência para Agentes de IA
configure_mcp_server(expose_callback_docstrings=True, include_pages=True)


def safe_build_chart(chart_id: str, **kwargs) -> go.Figure:
    """
    Executa a geração do gráfico de forma ultra-segura.
    Garante que qualquer erro de SQL, dados ausentes ou exceção inesperada
    retorne uma figura estilizada no tema Dark Slate com um aviso informativo,
    NUNCA deixando o gráfico em branco (caixa branca com eixos vazios).
    """
    spec = CHART_REGISTRY.get(chart_id)
    if not spec:
        fig = go.Figure()
        fig.add_annotation(
            text="⚠️ Gráfico não encontrado no Registro",
            showarrow=False,
            font=dict(size=16, color="#ef4444"),
        )
        return aplicar_tema(fig, f"Gráfico #{chart_id}")

    try:
        fig = spec.builder(**kwargs)
        # Verifica se o gráfico gerado possui dados válidos
        if not fig_has_data(fig):
            fig = go.Figure()
            fig.add_annotation(
                text="ℹ️ Dados em sincronização ou insuficientes para o filtro selecionado",
                showarrow=False,
                font=dict(size=16, color="#94a3b8"),
            )
            return aplicar_tema(fig, spec.title)

        return fig

    except Exception as err:
        log.error("Erro ao gerar gráfico '%s': %s", chart_id, err)
        fig = go.Figure()
        fig.add_annotation(
            text=f"⚠️ Erro ao carregar dados do gráfico ({err})",
            showarrow=False,
            font=dict(size=14, color="#f87171"),
        )
        return aplicar_tema(fig, spec.title)


# 3. Monta o Layout Dinâmico baseado nas especificações registradas em graph_factory.py
def build_layout():
    children = [
        html.Header(
            style={
                "marginBottom": "2rem",
                "borderBottom": "1px solid #334155",
                "paddingBottom": "1rem",
            },
            children=[
                html.H1(
                    "TransfereGov Intel — Dash & MCP Analytics Hub",
                    style={"color": "#f8fafc", "fontSize": "2rem", "marginBottom": "0.5rem"},
                ),
                html.P(
                    "Painel analítico automatizado via Plotly Express e servidor MCP (Model Context Protocol).",
                    style={"color": "#94a3b8", "fontSize": "1rem"},
                ),
                html.Div(
                    style={
                        "display": "inline-block",
                        "marginTop": "0.5rem",
                        "padding": "0.3rem 0.8rem",
                        "background": "#1e293b",
                        "borderRadius": "20px",
                        "border": "1px solid #3b82f6",
                        "color": "#60a5fa",
                        "fontSize": "0.85rem",
                    },
                    children=[
                        "⚡ Servidor MCP ativo no endpoint: ",
                        html.Code(
                            "http://localhost:8050/_mcp",
                            style={"color": "#38bdf8", "fontWeight": "bold"},
                        ),
                    ],
                ),
            ],
        )
    ]

    # Agrupar gráficos por categoria
    categories = {}
    for chart_id, spec in CHART_REGISTRY.items():
        if spec.category not in categories:
            categories[spec.category] = []
        categories[spec.category].append((chart_id, spec))

    tabs = []
    for cat, charts in categories.items():
        tab_cards = []
        for chart_id, spec in charts:
            controls_html = []
            default_kwargs = {}
            for ctrl in spec.controls:
                default_kwargs[ctrl.id] = ctrl.default
                controls_html.append(
                    html.Div(
                        style={"marginRight": "1.5rem", "marginBottom": "1rem"},
                        children=[
                            html.Label(
                                ctrl.label,
                                style={
                                    "display": "block",
                                    "fontSize": "0.85rem",
                                    "color": "#94a3b8",
                                    "marginBottom": "0.3rem",
                                },
                            ),
                            dcc.Dropdown(
                                id=f"ctrl-{chart_id}-{ctrl.id}",
                                options=[{"label": opt, "value": opt} for opt in ctrl.options],
                                value=ctrl.default,
                                clearable=False,
                                style={"width": "220px", "color": "#0f172a"},
                            ),
                        ],
                    )
                )

            # Pré-renderiza a figura inicial server-side para carregamento instantâneo
            initial_figure = safe_build_chart(chart_id, **default_kwargs)

            card = html.Div(
                style={
                    "backgroundColor": "#1e293b",
                    "borderRadius": "12px",
                    "padding": "1.5rem",
                    "marginBottom": "2rem",
                    "border": "1px solid #334155",
                },
                children=[
                    html.Div(
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "flex-start",
                        },
                        children=[
                            html.Div(
                                [
                                    html.H2(
                                        spec.title,
                                        style={
                                            "color": "#f8fafc",
                                            "fontSize": "1.25rem",
                                            "marginBottom": "0.3rem",
                                        },
                                    ),
                                    html.P(
                                        spec.description,
                                        style={
                                            "color": "#94a3b8",
                                            "fontSize": "0.85rem",
                                            "marginBottom": "1rem",
                                        },
                                    ),
                                ]
                            ),
                            html.Span(
                                spec.category,
                                style={
                                    "padding": "0.2rem 0.6rem",
                                    "borderRadius": "4px",
                                    "background": "#334155",
                                    "color": "#cbd5e1",
                                    "fontSize": "0.75rem",
                                },
                            ),
                        ],
                    ),
                    html.Div(style={"display": "flex", "flexWrap": "wrap"}, children=controls_html)
                    if controls_html
                    else html.Div(),
                    dcc.Graph(id=f"graph-{chart_id}", figure=initial_figure),
                ],
            )
            tab_cards.append(card)
            
        tabs.append(
            dcc.Tab(
                label=cat,
                children=[html.Div(tab_cards, style={"paddingTop": "2rem"})],
                style={"backgroundColor": "#1e293b", "color": "#94a3b8", "border": "none", "borderBottom": "1px solid #334155"},
                selected_style={"backgroundColor": "#3b82f6", "color": "white", "border": "none", "fontWeight": "bold"}
            )
        )
        
    children.append(dcc.Tabs(tabs, style={"marginBottom": "2rem"}))

    return html.Div(
        style={
            "backgroundColor": "#0f172a",
            "minHeight": "100vh",
            "padding": "2rem",
            "fontFamily": "Inter, sans-serif",
        },
        children=children,
    )


app.layout = build_layout()

# 4. Registra os Callbacks do Dash (que viram MCP Tools automaticamente)
for chart_id, spec in CHART_REGISTRY.items():
    if spec.controls:

        def register_with_ctrl(c_key, ctrl_specs):
            inputs = [Input(f"ctrl-{c_key}-{ctrl.id}", "value") for ctrl in ctrl_specs]

            @callback(Output(f"graph-{c_key}", "figure"), inputs, prevent_initial_call=True)
            def update_graph_ctrl(*args):
                """Gera o gráfico Plotly filtrado pelos parâmetros especificados."""
                kwargs = {ctrl_specs[i].id: args[i] for i in range(len(args))}
                return safe_build_chart(c_key, **kwargs)

        register_with_ctrl(chart_id, spec.controls)

log.info(
    "Registrados %d gráficos interativos e resilientes no Dash MCP Server!", len(CHART_REGISTRY)
)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
