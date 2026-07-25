#!/usr/bin/env python3
"""
TransfereGov — Gerador Modular de Gráficos Interativos e Dashboards.

Módulo especializado para geração de gráficos Plotly interativos com tema escuro (Dark Slate),
suporte a múltiplas modalidades de emendas (Transferências Especiais/Pix, Convênios, OGU)
e cruzamento com dados socioeconômicos (IBGE, Câmara, BACEN).

Uso:
  python3 src/graph_generator.py [--output output/dashboard_cross_interactive.html]
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.settings import OUTPUT_DIR
from src.db_utils import get_connection

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DE LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------------------------------------------------------------------
# PALETA DE CORES E TOKENS DE DESIGN
# ---------------------------------------------------------------------------
THEME_BG = "#121826"
THEME_CARD_BG = "#1e293b"
THEME_TEXT = "#f8fafc"
THEME_GRID = "#334155"

CORES_REGIAO = {
    "Norte": "#2ecc71",
    "Nordeste": "#3498db",
    "Centro-Oeste": "#f1c40f",
    "Sudeste": "#e74c3c",
    "Sul": "#9b59b6",
    "Não informado": "#95a5a6",
}

CORES_SITUACAO = {
    "CIENTE": "#3498db",
    "IMPEDIDO": "#e74c3c",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO": "#e67e22",
    "REPROVADO": "#9b59b6",
    "CANCELADO": "#95a5a6",
    "EM_EXECUCAO": "#2ecc71",
    "CONCLUIDO": "#1abc9c",
    "NAO_CUMPROU": "#34495e",
}

CORES_MODALIDADE = {
    "Transferência Especial (Pix)": "#00d2d3",
    "Convênio Voluntário (SICONV)": "#ff9ff3",
    "Execução Direta / OGU": "#feca57",
}


def conectar_db():
    """Cria conexão com o banco PostgreSQL transferegov_db."""
    return get_connection()


def aplicar_layout_base(fig: go.Figure, titulo: str, altura: int = 500) -> go.Figure:
    """Aplica o tema escuro padrão (Dark Slate) e estilização de alta qualidade."""
    fig.update_layout(
        title={
            "text": f"<b>{titulo}</b>",
            "y": 0.95,
            "x": 0.02,
            "xanchor": "left",
            "yanchor": "top",
            "font": {"size": 18, "color": THEME_TEXT},
        },
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        font={"family": "Inter, Roboto, sans-serif", "color": THEME_TEXT},
        height=altura,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            bgcolor="rgba(15, 23, 42, 0.6)",
            bordercolor="#475569",
            borderwidth=1,
            font=dict(color=THEME_TEXT, size=11),
        ),
    )
    fig.update_xaxes(
        gridcolor=THEME_GRID,
        zerolinecolor=THEME_GRID,
        tickfont=dict(color=THEME_TEXT),
        title_font=dict(color=THEME_TEXT),
    )
    fig.update_yaxes(
        gridcolor=THEME_GRID,
        zerolinecolor=THEME_GRID,
        tickfont=dict(color=THEME_TEXT),
        title_font=dict(color=THEME_TEXT),
    )
    return fig


def gerar_grafico_sunburst_regional(df: pd.DataFrame) -> go.Figure:
    """Gera gráfico Sunburst hierárquico: Região -> Estado (UF) -> Situação -> Valor."""
    if df.empty:
        return go.Figure()

    df_filtered = df.dropna(subset=["ibge_regiao", "parlamentar_uf", "situacao_display", "valor_total"])

    fig = px.sunburst(
        df_filtered,
        path=["ibge_regiao", "parlamentar_uf", "situacao_display"],
        values="valor_total",
        color="ibge_regiao",
        color_discrete_map=CORES_REGIAO,
    )

    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>Valor Total: R$ %{value:,.2f}<br>Proporção: %{percentParent:.1%}"
    )
    return aplicar_layout_base(fig, "Distribuição Hierárquica Regional e Situação dos Planos", altura=550)


def gerar_heatmap_situacao_objeto(df: pd.DataFrame) -> go.Figure:
    """Gera Mapa de Calor: Região × Situação de Execução."""
    if df.empty:
        return go.Figure()

    pivot = df.pivot_table(
        index="ibge_regiao",
        columns="situacao_display",
        values="valor_total",
        aggfunc="sum",
        fill_value=0,
    )

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values / 1e6,  # em milhões
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Viridis",
            colorbar=dict(title="R$ (Milhões)", tickfont=dict(color=THEME_TEXT)),
            hovertemplate="Região: %{y}<br>Situação: %{x}<br>Valor: R$ %{z:.2f}M<extra></extra>",
        )
    )
    return aplicar_layout_base(fig, "Mapa de Calor: Alocação Financeira por Região e Situação (R$ Milhões)")


def gerar_scatter_socioeconomico(df: pd.DataFrame) -> go.Figure:
    """Gera gráfico de dispersão: População do Município vs. Valor de Emendas Recebido."""
    if df.empty or "ibge_populacao" not in df.columns:
        return go.Figure()

    df_valido = df.dropna(subset=["ibge_populacao", "valor_total", "ibge_regiao"]).copy()
    df_valido = df_valido[df_valido["ibge_populacao"] > 0]

    fig = px.scatter(
        df_valido,
        x="ibge_populacao",
        y="valor_total",
        color="ibge_regiao",
        color_discrete_map=CORES_REGIAO,
        hover_name="municipio_nome",
        hover_data={
            "parlamentar_nome": True,
            "valor_total": ":,.2f",
            "ibge_populacao": ":,",
        },
        log_x=True,
        log_y=True,
    )

    fig.update_traces(marker=dict(size=9, opacity=0.7, line=dict(width=0.5, color="white")))
    fig.update_xaxes(title_text="População do Município (Escala Log)")
    fig.update_yaxes(title_text="Valor Total da Emenda (R$ - Escala Log)")
    return aplicar_layout_base(fig, "Correlação: População do Município Beneficiário vs. Valor Recebido")


def gerar_bar_ranking_parlamentares(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Gera gráfico de barras horizontal: Top N Parlamentares por Valor de Emendas."""
    if df.empty:
        return go.Figure()

    top_parlamentares = (
        df.groupby(["parlamentar_nome", "parlamentar_partido"])["valor_total"]
        .sum()
        .reset_index()
        .sort_values(by="valor_total", ascending=True)
        .tail(top_n)
    )

    top_parlamentares["label"] = (
        top_parlamentares["parlamentar_nome"] + " (" + top_parlamentares["parlamentar_partido"].fillna("S/P") + ")"
    )

    fig = go.Figure(
        go.Bar(
            x=top_parlamentares["valor_total"] / 1e6,
            y=top_parlamentares["label"],
            orientation="h",
            marker=dict(color="#3498db", line=dict(color="#2980b9", width=1)),
            text=(top_parlamentares["valor_total"] / 1e6).map("R$ {:.2f}M".format),
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>Valor Total: R$ %{x:.2f} Milhões<extra></extra>",
        )
    )
    fig.update_xaxes(title_text="Valor Total (R$ Milhões)")
    return aplicar_layout_base(fig, f"Top {top_n} Parlamentares com Maior Volume de Emendas Pix")


def gerar_dashboard_html_completo(output_path: Path):
    """Executa queries no banco e compila um dashboard HTML completo interativo."""
    logging.info("Carregando dados de v_planos_enriquecidos...")
    conn = conectar_db()
    try:
        df = pd.read_sql_query("SELECT * FROM v_planos_enriquecidos", conn)
    finally:
        conn.close()

    logging.info(f"Dados carregados: {len(df)} registros.")

    fig_sunburst = gerar_grafico_sunburst_regional(df)
    fig_heatmap = gerar_heatmap_situacao_objeto(df)
    fig_scatter = gerar_scatter_socioeconomico(df)
    fig_ranking = gerar_bar_ranking_parlamentares(df)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TransfereGov — Dashboard Interativo de Análise Cruzada</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: {THEME_BG};
            color: {THEME_TEXT};
            margin: 0;
            padding: 24px;
        }}
        .header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 24px 32px;
            border-radius: 12px;
            border: 1px solid #334155;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 26px;
            color: #38bdf8;
        }}
        .header p {{
            margin: 0;
            color: #94a3b8;
            font-size: 14px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }}
        @media (max-width: 1100px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
        .card {{
            background-color: {THEME_CARD_BG};
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 TransfereGov — Painel de Análise Cruzada de Emendas e Transferências</h1>
        <p>Análise de Transferências Especiais (Emendas Pix), perfil de parlamentares e correlação socioeconômica IBGE.</p>
    </div>

    <div class="grid">
        <div class="card">{fig_sunburst.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class="card">{fig_heatmap.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class="card">{fig_scatter.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class="card">{fig_ranking.to_html(full_html=False, include_plotlyjs=False)}</div>
    </div>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
    logging.info(f"Dashboard HTML gerado com sucesso em: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerador de Gráficos e Dashboard TransfereGov")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "dashboard_cross_interactive.html"),
        help="Caminho do arquivo HTML de saída",
    )
    args = parser.parse_args()
    gerar_dashboard_html_completo(Path(args.output))
