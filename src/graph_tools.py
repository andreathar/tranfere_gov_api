#!/usr/bin/env python3
"""
TransfereGov — Custom MCP Tools for Autonomous Graph Management (Dash 4.3+).

Ferramentas MCP customizadas expostas via @mcp_enabled para permitir que Agentes de IA
gerenciem, inspecionem, criem e auditem os gráficos do sistema em tempo real.
"""

import logging
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
from dash.mcp import mcp_enabled

from src.graph_factory import CHART_REGISTRY, aplicar_tema, query_df, register_chart

log = logging.getLogger("graph_tools")


@mcp_enabled(name="list_registered_charts", expose_docstring=True)
def list_registered_charts() -> list[dict[str, Any]]:
    """
    Retorna a lista completa de gráficos registrados no sistema, incluindo seus IDs, títulos,
    descrições, categorias e os controles interativos disponíveis para filtragem.
    """
    charts = []
    for chart_id, spec in CHART_REGISTRY.items():
        controls = [
            {
                "id": ctrl.id,
                "label": ctrl.label,
                "options": ctrl.options,
                "default": ctrl.default
            }
            for ctrl in spec.controls
        ]
        charts.append({
            "id": chart_id,
            "title": spec.title,
            "description": spec.description,
            "category": spec.category,
            "controls": controls
        })
    return charts


@mcp_enabled(name="inspect_chart_health", expose_docstring=True)
def inspect_chart_health(chart_id: str | None = None) -> list[dict[str, Any]]:
    """
    Audita a saúde de todos os gráficos ou de um gráfico específico pelo ID.
    Retorna se o gráfico é válido (is_ok), número de traces, total de pontos de dados
    e se há algum erro de SQL ou renderização.
    """
    targets = {chart_id: CHART_REGISTRY[chart_id]} if chart_id and chart_id in CHART_REGISTRY else CHART_REGISTRY
    health_report = []

    for c_id, spec in targets.items():
        try:
            fig = spec.builder()
            num_traces = len(fig.data) if fig and hasattr(fig, "data") else 0
            total_points = 0
            has_data = False

            if fig and hasattr(fig, "data"):
                for trace in fig.data:
                    sizes = [
                        len(trace.x) if hasattr(trace, 'x') and trace.x is not None else 0,
                        len(trace.y) if hasattr(trace, 'y') and trace.y is not None else 0,
                        len(trace.values) if hasattr(trace, 'values') and trace.values is not None else 0,
                        len(trace.z) if hasattr(trace, 'z') and trace.z is not None else 0,
                        len(trace.locations) if hasattr(trace, 'locations') and trace.locations is not None else 0,
                        len(trace.lat) if hasattr(trace, 'lat') and trace.lat is not None else 0,
                        len(trace.lon) if hasattr(trace, 'lon') and trace.lon is not None else 0,
                        len(trace.r) if hasattr(trace, 'r') and trace.r is not None else 0,
                        len(trace.theta) if hasattr(trace, 'theta') and trace.theta is not None else 0,
                    ]
                    # Sankey: dados ficam em trace.link.value
                    if hasattr(trace, "link") and trace.link and hasattr(trace.link, "value") and trace.link.value is not None:
                        sizes.append(len(trace.link.value))
                    pts = max(sizes)
                    total_points += pts
                    if pts > 0:
                        has_data = True

            health_report.append({
                "chart_id": c_id,
                "title": spec.title,
                "category": spec.category,
                "is_ok": has_data,
                "num_traces": num_traces,
                "total_points": total_points,
                "status": "OPERACIONAL" if has_data else "SEM DADOS (EMPTY)"
            })
        except Exception as e:
            health_report.append({
                "chart_id": c_id,
                "title": spec.title,
                "category": spec.category,
                "is_ok": False,
                "num_traces": 0,
                "total_points": 0,
                "status": f"ERRO: {str(e)}"
            })

    return health_report


@mcp_enabled(name="get_chart_data_summary", expose_docstring=True)
def get_chart_data_summary(chart_id: str, uf_filter: str = "TODOS", regiao_filter: str = "TODOS") -> dict[str, Any]:
    """
    Executa o gráfico especificado e retorna um resumo estruturado dos dados (resumo estatístico,
    quantidade de registros, traces e categorias) em formato JSON para fácil interpretação pela IA.
    """
    if chart_id not in CHART_REGISTRY:
        return {"error": f"Gráfico '{chart_id}' não encontrado no registro."}

    spec = CHART_REGISTRY[chart_id]
    kwargs = {}
    for ctrl in spec.controls:
        if ctrl.id == "uf_filter":
            kwargs["uf_filter"] = uf_filter
        elif ctrl.id == "regiao_filter":
            kwargs["regiao_filter"] = regiao_filter
        else:
            kwargs[ctrl.id] = ctrl.default

    try:
        fig = spec.builder(**kwargs)
        summary = {
            "chart_id": chart_id,
            "title": spec.title,
            "category": spec.category,
            "applied_params": kwargs,
            "num_traces": len(fig.data) if fig and hasattr(fig, "data") else 0,
            "trace_names": [t.name for t in fig.data if hasattr(t, "name") and t.name]
        }
        return summary
    except Exception as e:
        return {"chart_id": chart_id, "error": str(e)}


@mcp_enabled(name="register_custom_graph", expose_docstring=True)
def register_custom_graph(
    id: str,
    title: str,
    description: str,
    category: str,
    sql_query: str,
    chart_type: str = "bar",
    x_col: str = "",
    y_col: str = ""
) -> dict[str, Any]:
    """
    Permite que Agentes de IA criem e registrem dinamicamente um novo gráfico baseado em consulta SQL.
    Tipos suportados: 'bar', 'scatter', 'pie', 'line'.
    O novo gráfico é imediatamente adicionado ao dashboard e exposto via MCP!
    """
    try:
        def dynamic_builder() -> go.Figure:
            df = query_df(sql_query)
            if df.empty:
                fig = go.Figure()
                fig.add_annotation(text="Sem dados retornados para a consulta SQL", showarrow=False, font=dict(size=16, color="#64748b"))
                return aplicar_tema(fig, title)

            x = x_col if x_col and x_col in df.columns else df.columns[0]
            y = y_col if y_col and y_col in df.columns else (df.columns[1] if len(df.columns) > 1 else df.columns[0])

            if chart_type.lower() == "scatter":
                fig = px.scatter(df, x=x, y=y, title=title)
            elif chart_type.lower() == "pie":
                fig = px.pie(df, names=x, values=y, title=title)
            elif chart_type.lower() == "line":
                fig = px.line(df, x=x, y=y, title=title)
            else: # default bar
                fig = px.bar(df, x=x, y=y, title=title)

            return aplicar_tema(fig, title)

        register_chart(
            id=id,
            title=title,
            description=description,
            category=category
        )(dynamic_builder)

        log.info(f"Novo gráfico dinâmico '{id}' registrado com sucesso por Agente MCP!")
        return {
            "success": True,
            "message": f"Gráfico '{title}' registrado com sucesso!",
            "chart_id": id
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
