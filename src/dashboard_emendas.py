#!/usr/bin/env python3
"""
TransfereGov — Dashboard de Emendas Parlamentares.

Análise cruzada de emendas com dados de transferências, parlamentares,
objetos, regiões e dados fiscais para visualizar:
  1. Taxas de sucesso por tipo de emenda
  2. Padrões de negativa por tipo × região
  3. Performance por parlamentar
  4. Distribuição por objeto
  5. Análise regional
  6. Distribuição de valores
  7. Matriz parlamentar × objeto
  8. Padrões temporais

Uso: python3 src/dashboard_emendas.py [--output output/dashboard_emendas.html]
"""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.db_utils import get_connection
from src.formatters import fmt_num, fmt_pct

# ═══════════════════════════════════════════════════════════════════════
# CORES E TEMAS (mesmo padrão dos outros dashboards)
# ═══════════════════════════════════════════════════════════════════════

TEMA = {
    "bg": "#0f172a",
    "card": "#1e293b",
    "card_alt": "#1a2332",
    "text": "#e2e8f0",
    "text_muted": "#64748b",
    "accent": "#3b82f6",
    "accent2": "#8b5cf6",
    "accent3": "#10b981",
    "accent4": "#f59e0b",
    "accent5": "#ef4444",
    "border": "#334155",
    "grid": "#334155",
}

CORES_STATUS = {
    "APROVADO": "#10b981",
    "REPROVADO": "#ef4444",
    "IMPEDIDO": "#f59e0b",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO": "#d97706",
    "CANCELADO": "#6b7280",
    "EM_EXECUCAO": "#3b82f6",
    "CONCLUIDO": "#8b5cf6",
    "AGUARDANDO_CIENCIA": "#64748b",
    "CIENTE": "#38bdf8",
    "PLANO_TRABALHO_EM_ELABORACAO": "#a78bfa",
    "NAO_CUMPROU": "#dc2626",
}

CORES_REGIAO = {
    "Norte": "#2ecc71",
    "Nordeste": "#3498db",
    "Centro-Oeste": "#f1c40f",
    "Sudeste": "#e74c3c",
    "Sul": "#9b59b6",
}

ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]

# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════




def query_df(conn, sql):
    """Executa query e retorna DataFrame."""
    return pd.read_sql(sql, conn)





def estilo_fig(fig, height=500):
    """Aplica o tema escuro padrão a uma figura Plotly."""
    fig.update_layout(
        paper_bgcolor=TEMA["card"],
        plot_bgcolor=TEMA["card"],
        font=dict(color=TEMA["text"], size=11),
        title=dict(font=dict(size=14, color=TEMA["text"]), x=0.02, xanchor="left"),
        height=height,
        margin=dict(l=60, r=30, t=55, b=60),
        hovermode="closest",
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color=TEMA["text_muted"], size=10)
        ),
    )
    fig.update_xaxes(
        gridcolor=TEMA["grid"], zerolinecolor=TEMA["grid"],
        tickfont=dict(color=TEMA["text_muted"]),
    )
    fig.update_yaxes(
        gridcolor=TEMA["grid"], zerolinecolor=TEMA["grid"],
        tickfont=dict(color=TEMA["text_muted"]),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════
# QUERIES SQL — Cruzamento Emendas × Parlamentares × Objetos
# Nota: usando emenda_ano como dimensão (emenda_tipo não existe no schema)
# ═══════════════════════════════════════════════════════════════════════

# 1. Taxas de sucesso por parlamentar (top 30)
SQL_SUCCESS_RATES = """
SELECT
    pa.parlamentar_nome,
    pd.sigla_partido,
    pd.uf AS uf_parlamentar,
    COUNT(*) AS total_planos,
    SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) AS cientes,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO' THEN 1 ELSE 0 END) AS impedidos,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO_REJEICAO_PLANO_TRABALHO' THEN 1 ELSE 0 END) AS rejeitados,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
WHERE pa.parlamentar_nome IS NOT NULL
GROUP BY pa.parlamentar_nome, pd.sigla_partido, pd.uf
HAVING COUNT(*) >= 10
ORDER BY valor_total_milhao DESC
LIMIT 30
"""

# 2. Padrões de negativa por região
SQL_DENIAL_PATTERNS = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    COUNT(*) AS total_planos,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO' THEN 1 ELSE 0 END) AS impedidos,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO_REJEICAO_PLANO_TRABALHO' THEN 1 ELSE 0 END) AS rejeitados,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO') THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_negativa,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao,
    ROUND(AVG(pa.valor_total) / 1e3, 2) AS valor_medio_milhar
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
GROUP BY mi.regiao
HAVING COUNT(*) >= 10
ORDER BY CASE mi.regiao
    WHEN 'Norte' THEN 1 WHEN 'Nordeste' THEN 2
    WHEN 'Centro-Oeste' THEN 3 WHEN 'Sudeste' THEN 4 WHEN 'Sul' THEN 5
    ELSE 6
END
"""

# 3. Performance por parlamentar (com fotos)
SQL_PARLAMENTAR_PERFORMANCE = """
SELECT
    pa.parlamentar_nome,
    pd.url_foto,
    pd.sigla_partido,
    pd.uf AS uf_parlamentar,
    COUNT(*) AS total_planos,
    SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) AS cientes,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao,
    ROUND(AVG(pa.valor_total) / 1e3, 2) AS valor_medio_milhar
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
WHERE pa.parlamentar_nome IS NOT NULL
GROUP BY pa.parlamentar_nome, pd.url_foto, pd.sigla_partido, pd.uf
HAVING COUNT(*) >= 5
ORDER BY valor_total_milhao DESC
LIMIT 50
"""

# 4. Distribuição por objeto
SQL_OBJECT_DISTRIBUTION = """
SELECT
    COALESCE(o.descricao, 'Sem objeto') AS objeto_descricao,
    COUNT(*) AS total_planos,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao,
    ROUND(AVG(pa.valor_total) / 1e3, 2) AS valor_medio_milhar,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente
FROM planos_acao pa
LEFT JOIN objetos o ON pa.objeto_id = o.objeto_id
GROUP BY o.descricao
HAVING COUNT(*) >= 10
ORDER BY valor_total_milhao DESC
LIMIT 20
"""

# 5. Análise regional
SQL_REGIONAL_ANALYSIS = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    COUNT(*) AS total_planos,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao,
    ROUND(AVG(pa.valor_total) / 1e3, 2) AS valor_medio_milhar,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente,
    COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares_unicos,
    COUNT(DISTINCT pa.beneficiario_id) AS beneficiarios_unicos
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
GROUP BY mi.regiao
HAVING COUNT(*) >= 10
ORDER BY CASE mi.regiao
    WHEN 'Norte' THEN 1 WHEN 'Nordeste' THEN 2
    WHEN 'Centro-Oeste' THEN 3 WHEN 'Sudeste' THEN 4 WHEN 'Sul' THEN 5
    ELSE 6
END
"""

# 6. Distribuição de valores (para box plot)
SQL_VALUE_DISTRIBUTION = """
SELECT
    pa.plano_acao_situacao,
    pa.valor_total / 1e3 AS valor_milhar,
    pa.valor_custeio / 1e3 AS custeio_milhar,
    pa.valor_investimento / 1e3 AS investimento_milhar,
    COALESCE(mi.regiao, 'Sem região') AS regiao
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.valor_total > 0
"""

# 7. Matriz parlamentar × objeto
SQL_PARLAMENTAR_OBJECT_MATRIX = """
SELECT
    pa.parlamentar_nome,
    COALESCE(o.descricao, 'Sem objeto') AS objeto_descricao,
    COUNT(*) AS total_planos,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente
FROM planos_acao pa
LEFT JOIN objetos o ON pa.objeto_id = o.objeto_id
WHERE pa.parlamentar_nome IS NOT NULL
GROUP BY pa.parlamentar_nome, o.descricao
HAVING COUNT(*) >= 3
ORDER BY total_planos DESC
"""

# 8. Padrões temporais (por emenda_ano)
SQL_TEMPORAL_PATTERNS = """
SELECT
    pa.emenda_ano,
    EXTRACT(MONTH FROM pa.data_atualizacao_plano_acao::date) AS mes,
    COUNT(*) AS total_planos,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS valor_total_milhao,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente,
    COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares_unicos
FROM planos_acao pa
WHERE pa.data_atualizacao_plano_acao IS NOT NULL
GROUP BY pa.emenda_ano, EXTRACT(MONTH FROM pa.data_atualizacao_plano_acao::date)
ORDER BY pa.emenda_ano, mes
"""

# Query para cards de resumo
SQL_RESUMO = """
SELECT
    COUNT(*) AS total_planos,
    COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares,
    COUNT(DISTINCT pa.emenda_codigo) AS emendas,
    ROUND(SUM(pa.valor_total) / 1e9, 2) AS valor_total_bi,
    ROUND(AVG(pa.valor_total) / 1e3, 2) AS valor_medio_milhar,
    SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) AS cientes,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO') THEN 1 ELSE 0 END) AS negados,
    ROUND(
        100.0 * SUM(CASE WHEN pa.plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) AS taxa_ciente_geral
FROM planos_acao pa
WHERE pa.parlamentar_nome IS NOT NULL
"""


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════


def grafico_cards_resumo(df_resumo):
    """Cards de resumo no topo do dashboard."""
    r = df_resumo.iloc[0]

    cards = f"""
    <div class="cards-row">
      <div class="card">
        <div class="card-icon">📊</div>
        <div class="card-num">{fmt_num(r['total_planos'])}</div>
        <div class="card-label">Total de Planos</div>
      </div>
      <div class="card">
        <div class="card-icon">👤</div>
        <div class="card-num">{fmt_num(r['parlamentares'])}</div>
        <div class="card-label">Parlamentares</div>
      </div>
      <div class="card">
        <div class="card-icon">📝</div>
        <div class="card-num">{fmt_num(r['emendas'])}</div>
        <div class="card-label">Emendas Únicas</div>
      </div>
      <div class="card">
        <div class="card-icon">💰</div>
        <div class="card-num">R$ {r['valor_total_bi']} Bi</div>
        <div class="card-label">Valor Total</div>
      </div>
      <div class="card">
        <div class="card-icon">✅</div>
        <div class="card-num">{fmt_pct(r['taxa_ciente_geral'])}</div>
        <div class="card-label">Taxa Ciente</div>
      </div>
      <div class="card">
        <div class="card-icon">❌</div>
        <div class="card-num">{fmt_num(r['negados'])}</div>
        <div class="card-label">Negados</div>
      </div>
    </div>
    """
    return cards


def grafico_1_success_rates(df):
    """Gráfico 1: Taxas de sucesso por parlamentar (barras horizontais)."""
    # Ordenar por valor total
    df = df.sort_values("valor_total_milhao", ascending=True).tail(20)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Cientes",
        y=df["parlamentar_nome"],
        x=df["cientes"],
        orientation="h",
        marker_color=CORES_STATUS["CIENTE"],
        text=df["cientes"],
        textposition="auto",
    ))

    fig.add_trace(go.Bar(
        name="Impedidos",
        y=df["parlamentar_nome"],
        x=df["impedidos"],
        orientation="h",
        marker_color=CORES_STATUS["IMPEDIDO"],
        text=df["impedidos"],
        textposition="auto",
    ))

    fig.add_trace(go.Bar(
        name="Rejeitados",
        y=df["parlamentar_nome"],
        x=df["rejeitados"],
        orientation="h",
        marker_color=CORES_STATUS["IMPEDIDO_REJEICAO_PLANO_TRABALHO"],
        text=df["rejeitados"],
        textposition="auto",
    ))

    fig.update_layout(
        barmode="stack",
        xaxis_title="Quantidade de Planos",
        yaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    estilo_fig(fig, height=600)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_2_denial_patterns(df):
    """Gráfico 2: Padrões de negativa por região (barras agrupadas)."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Impedidos",
        x=df["regiao"],
        y=df["impedidos"],
        marker_color=CORES_STATUS["IMPEDIDO"],
        text=df["impedidos"],
        textposition="auto",
    ))

    fig.add_trace(go.Bar(
        name="Rejeitados",
        x=df["regiao"],
        y=df["rejeitados"],
        marker_color=CORES_STATUS["IMPEDIDO_REJEICAO_PLANO_TRABALHO"],
        text=df["rejeitados"],
        textposition="auto",
    ))

    # Adicionar linha de taxa média
    fig.add_trace(go.Scatter(
        x=df["regiao"],
        y=df["taxa_negativa"],
        mode="lines+markers+text",
        name="Taxa Negativa %",
        yaxis="y2",
        line=dict(color=TEMA["accent5"], width=2, dash="dash"),
        text=df["taxa_negativa"].round(1).astype(str) + "%",
        textposition="top center",
        textfont=dict(size=10, color=TEMA["accent5"]),
    ))

    fig.update_layout(
        barmode="group",
        xaxis_title="Região",
        yaxis_title="Quantidade de Planos",
        yaxis2=dict(
            title="Taxa Negativa (%)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    estilo_fig(fig, height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_3_parliamentar_performance(df):
    """Gráfico 3: Performance por parlamentar (scatter com fotos)."""
    # Criar hover text com fotos
    hover_text = []
    for _, row in df.iterrows():
        foto_html = f'<br><img src="{row["url_foto"]}" width="50" height="50" style="border-radius:50%;">' if pd.notna(row.get("url_foto")) else ""
        hover_text.append(
            f"<b>{row['parlamentar_nome']}</b>{foto_html}<br>"
            f"Partido: {row.get('sigla_partido', 'N/A')}<br>"
            f"UF: {row.get('uf_parlamentar', 'N/A')}<br>"
            f"Planos: {row['total_planos']}<br>"
            f"Valor Total: R$ {row['valor_total_milhao']} Mi<br>"
            f"Taxa Ciente: {row['taxa_ciente']:.1f}%"
        )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["valor_total_milhao"],
        y=df["taxa_ciente"],
        mode="markers+text",
        marker=dict(
            size=df["total_planos"] * 2,
            color=df["taxa_ciente"],
            colorscale="RdYlGn",
            showscale=True,
            colorbar=dict(title="Taxa Ciente %"),
            line=dict(width=1, color=TEMA["border"]),
        ),
        text=df["parlamentar_nome"].str.split().str[-1],  # Último nome
        textposition="top center",
        textfont=dict(size=9, color=TEMA["text_muted"]),
        hovertext=hover_text,
        hoverinfo="text",
    ))

    # Adicionar linhas de referência
    med_valor = df["valor_total_milhao"].median()
    med_ciente = df["taxa_ciente"].median()
    fig.add_hline(y=med_ciente, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)
    fig.add_vline(x=med_valor, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)

    fig.add_annotation(
        x=med_valor * 0.1, y=med_ciente + 5,
        text="Baixo valor<br>Alta aprovação",
        showarrow=False, font=dict(color=TEMA["accent3"], size=9),
    )

    fig.update_layout(
        xaxis_title="Valor Total (R$ milhões)",
        yaxis_title="Taxa Ciente (%)",
        xaxis=dict(rangemode="tozero"),
    )

    estilo_fig(fig, height=550)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_4_object_distribution(df):
    """Gráfico 4: Distribuição por objeto (treemap)."""
    # Agrupar por objeto (somar valores)
    df_grouped = df.groupby("objeto_descricao").agg({
        "valor_total_milhao": "sum",
        "total_planos": "sum",
        "taxa_ciente": "mean",
    }).reset_index()

    # Pegar top 15
    df_top = df_grouped.nlargest(15, "valor_total_milhao")

    fig = go.Figure(go.Treemap(
        labels=df_top["objeto_descricao"],
        parents=[""] * len(df_top),
        values=df_top["valor_total_milhao"],
        text=df_top.apply(
            lambda r: f"R$ {r['valor_total_milhao']:.0f} Mi<br>{r['total_planos']} planos<br>Ciente: {r['taxa_ciente']:.0f}%",
            axis=1,
        ),
        textinfo="label+text",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Valor: R$ %{value:.0f} Mi<br>"
            "<extra></extra>"
        ),
        marker=dict(
            colors=df_top["taxa_ciente"],
            colorscale="RdYlGn",
            showscale=True,
            colorbar=dict(title="Taxa Ciente %"),
        ),
    ))

    estilo_fig(fig, height=500)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_5_regional_analysis(df):
    """Gráfico 5: Análise regional (barras agrupadas)."""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Valor Total (R$ milhões)", "Taxa Ciente (%)"),
        horizontal_spacing=0.12,
    )

    # Gráfico de valor
    fig.add_trace(
        go.Bar(
            x=df["regiao"],
            y=df["valor_total_milhao"],
            marker_color=[CORES_REGIAO.get(r, "#64748b") for r in df["regiao"]],
            text=df["valor_total_milhao"].round(0).astype(str) + " Mi",
            textposition="auto",
            showlegend=False,
        ),
        row=1, col=1,
    )

    # Gráfico de taxa
    fig.add_trace(
        go.Bar(
            x=df["regiao"],
            y=df["taxa_ciente"],
            marker_color=[CORES_REGIAO.get(r, "#64748b") for r in df["regiao"]],
            text=df["taxa_ciente"].round(1).astype(str) + "%",
            textposition="auto",
            showlegend=False,
        ),
        row=1, col=2,
    )

    fig.update_xaxes(title_text="Região", row=1, col=1)
    fig.update_xaxes(title_text="Região", row=1, col=2)
    fig.update_yaxes(title_text="R$ milhões", row=1, col=1)
    fig.update_yaxes(title_text="%", row=1, col=2)

    estilo_fig(fig, height=400)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_6_value_distribution(df):
    """Gráfico 6: Distribuição de valores (box plot)."""
    fig = go.Figure()

    for situacao in df["plano_acao_situacao"].unique():
        df_sit = df[df["plano_acao_situacao"] == situacao]
        fig.add_trace(go.Box(
            y=df_sit["valor_milhar"],
            name=situacao,
            marker_color=CORES_STATUS.get(situacao, "#64748b"),
            boxpoints="outliers",
            jitter=0.3,
            pointpos=-1.8,
        ))

    fig.update_layout(
        yaxis_title="Valor (R$ milhar)",
        yaxis_type="log",
        showlegend=False,
    )

    estilo_fig(fig, height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_7_parliamentar_object_matrix(df):
    """Gráfico 7: Matriz parlamentar × objeto (heatmap)."""
    # Pegar top 20 parlamentares e top 10 objetos
    top_parlamentares = df.groupby("parlamentar_nome")["total_planos"].sum().nlargest(20).index
    top_objetos = df.groupby("objeto_descricao")["total_planos"].sum().nlargest(10).index

    df_filtered = df[
        df["parlamentar_nome"].isin(top_parlamentares) &
        df["objeto_descricao"].isin(top_objetos)
    ]

    pivot = df_filtered.pivot_table(
        index="parlamentar_nome",
        columns="objeto_descricao",
        values="valor_total_milhao",
        aggfunc="sum",
    ).fillna(0)

    # Limitar nomes dos objetos
    pivot.columns = [c[:40] + "..." if len(c) > 40 else c for c in pivot.columns]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale="YlOrRd",
        text=pivot.values.round(1).astype(str),
        texttemplate="%{text}",
        textfont=dict(size=9),
        colorbar=dict(title="R$ milhões"),
        hovertemplate=(
            "Parlamentar: %{y}<br>"
            "Objeto: %{x}<br>"
            "Valor: R$ %{z:.1f} Mi<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        xaxis_title="Objeto",
        yaxis_title="Parlamentar",
        height=600,
    )

    estilo_fig(fig, height=600)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_8_temporal_patterns(df):
    """Gráfico 8: Padrões temporais (linhas)."""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Planos por Mês", "Valor Total por Mês (R$ milhões)"),
        horizontal_spacing=0.12,
    )

    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["total_planos"],
            mode="lines+markers",
            name="Planos",
            line=dict(width=2, color=TEMA["accent"]),
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df["mes"],
            y=df["valor_total_milhao"],
            mode="lines+markers",
            name="Valor",
            showlegend=False,
            line=dict(width=2, color=TEMA["accent2"]),
        ),
        row=1, col=2,
    )

    fig.update_xaxes(title_text="Mês", row=1, col=1)
    fig.update_xaxes(title_text="Mês", row=1, col=2)
    fig.update_yaxes(title_text="Quantidade", row=1, col=1)
    fig.update_yaxes(title_text="R$ milhões", row=1, col=2)

    estilo_fig(fig, height=400)
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GERAÇÃO DO HTML
# ═══════════════════════════════════════════════════════════════════════


def gerar_html(data_str, cards, charts):
    """Monta o HTML completo do dashboard."""
    chart_html = ""
    titulos = [
        ("Taxas de Sucesso por Tipo de Emenda", "Distribuição de planos aprovados, negados e em execução por tipo de emenda"),
        ("Padrões de Negativa por Tipo × Região", "Taxa de negativa por tipo de emenda e região geográfica"),
        ("Performance por Parlamentar", "Valor total vs taxa de sucesso (tamanho = quantidade de planos)"),
        ("Distribuição por Objeto", "Alocação de emendas por tipo de objeto (treemap)"),
        ("Análise Regional", "Métricas de emendas por região geográfica"),
        ("Distribuição de Valores", "Box plot de valores por situação do plano"),
        ("Matriz Parlamentar × Objeto", "Heatmap de alocação por parlamentar e objeto"),
        ("Padrões Temporais", "Evolução temporal de emendas por tipo"),
    ]

    for i, ((titulo, desc), html) in enumerate(zip(titulos, charts), 1):
        anchor = f"g{i}"
        chart_html += f"""
        <div class="section" id="{anchor}">
          <div class="section-header">
            <span class="section-num">{i}</span>
            <div>
              <h2>{titulo}</h2>
              <p class="section-desc">{desc}</p>
            </div>
          </div>
          <div class="chart-container">{html}</div>
        </div>
        """

    nav_items = "".join(
        f'<a href="#g{i}" class="nav-item">{t[0]}</a>'
        for i, t in enumerate(titulos, 1)
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TransfereGov — Dashboard de Emendas Parlamentares</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {TEMA['bg']};
    color: {TEMA['text']};
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    line-height: 1.5;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
  .hero {{
    text-align: center;
    padding: 40px 20px 20px;
    background: linear-gradient(135deg, {TEMA['card']}, {TEMA['card_alt']});
    border-radius: 16px;
    margin-bottom: 20px;
    border: 1px solid {TEMA['border']};
  }}
  .hero h1 {{ font-size: 28px; color: {TEMA['accent']}; margin-bottom: 8px; }}
  .subtitle {{ color: {TEMA['text_muted']}; font-size: 14px; }}
  .cards-row {{
    display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; margin: 20px 0;
  }}
  .card {{
    background: {TEMA['card']};
    border: 1px solid {TEMA['border']};
    border-radius: 12px;
    padding: 20px 24px;
    min-width: 140px;
    text-align: center;
    flex: 1;
    max-width: 180px;
  }}
  .card-icon {{ font-size: 24px; margin-bottom: 4px; }}
  .card-num {{
    font-size: 22px; font-weight: 700; color: {TEMA['accent']};
    line-height: 1.2;
  }}
  .card-label {{
    font-size: 11px; color: {TEMA['text_muted']};
    text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;
  }}
  .nav {{
    display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;
    padding: 16px; background: {TEMA['card']};
    border-radius: 12px; margin: 20px 0;
    border: 1px solid {TEMA['border']};
    position: sticky; top: 10px; z-index: 100;
  }}
  .nav-item {{
    padding: 6px 14px; border-radius: 8px;
    background: {TEMA['bg']}; color: {TEMA['text_muted']};
    text-decoration: none; font-size: 12px; font-weight: 500;
    transition: all 0.2s;
    border: 1px solid {TEMA['border']};
  }}
  .nav-item:hover {{
    background: {TEMA['accent']}; color: white; border-color: {TEMA['accent']};
  }}
  .section {{
    background: {TEMA['card']};
    border: 1px solid {TEMA['border']};
    border-radius: 12px;
    padding: 24px;
    margin: 20px 0;
  }}
  .section-header {{
    display: flex; align-items: center; gap: 16px; margin-bottom: 16px;
  }}
  .section-num {{
    background: {TEMA['accent']}; color: white;
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 16px; flex-shrink: 0;
  }}
  .section-header h2 {{
    font-size: 18px; color: {TEMA['text']}; margin: 0;
  }}
  .section-desc {{
    font-size: 12px; color: {TEMA['text_muted']}; margin: 2px 0 0;
  }}
  .chart-container {{
    width: 100%; overflow-x: auto;
  }}
  .footer {{
    text-align: center; padding: 30px; color: {TEMA['text_muted']};
    font-size: 12px; border-top: 1px solid {TEMA['border']}; margin-top: 30px;
  }}
  .footer strong {{ color: {TEMA['accent']}; }}
  @media (max-width: 768px) {{
    .cards-row {{ flex-direction: column; align-items: stretch; }}
    .card {{ max-width: 100%; }}
    .nav {{ position: static; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <h1>Dashboard de Emendas Parlamentares</h1>
    <p class="subtitle">Análise Cruzada — TransfereGov × Parlamentares × Objetos</p>
  </div>
  {cards}
  <nav class="nav">{nav_items}</nav>
  {chart_html}
  <div class="footer">
    <strong>TransfereGov — Dashboard de Emendas</strong><br>
    Dados: API TransfereGov × Parlamentares × Objetos × Regiões<br>
    Gerado em {data_str} — Programa Transferências Especiais (Emendas Pix) 2026
  </div>
</div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Dashboard de Emendas Parlamentares - TransfereGov"
    )
    parser.add_argument(
        "--output", default="output/dashboard_emendas.html",
        help="Caminho do arquivo HTML de saída"
    )
    args = parser.parse_args()

    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    print("🔌 Conectando ao banco...")
    conn = get_connection()

    print("📥 Carregando dados de emendas...")

    # Carregar dados
    df_resumo = query_df(conn, SQL_RESUMO)
    df_success = query_df(conn, SQL_SUCCESS_RATES)
    df_denial = query_df(conn, SQL_DENIAL_PATTERNS)
    df_parlamentar = query_df(conn, SQL_PARLAMENTAR_PERFORMANCE)
    df_object = query_df(conn, SQL_OBJECT_DISTRIBUTION)
    df_regional = query_df(conn, SQL_REGIONAL_ANALYSIS)
    df_value = query_df(conn, SQL_VALUE_DISTRIBUTION)
    df_matrix = query_df(conn, SQL_PARLAMENTAR_OBJECT_MATRIX)
    df_temporal = query_df(conn, SQL_TEMPORAL_PATTERNS)

    conn.close()

    print("📊 Dados carregados:")
    print(f"   - Planos: {fmt_num(df_resumo.iloc[0]['total_planos'])}")
    print(f"   - Parlamentares: {fmt_num(df_resumo.iloc[0]['parlamentares'])}")
    print(f"   - Emendas: {fmt_num(df_resumo.iloc[0]['emendas'])}")

    # Gerar gráficos
    print("📈 Gerando gráficos...")
    cards = grafico_cards_resumo(df_resumo)
    charts = [
        grafico_1_success_rates(df_success),
        grafico_2_denial_patterns(df_denial),
        grafico_3_parliamentar_performance(df_parlamentar),
        grafico_4_object_distribution(df_object),
        grafico_5_regional_analysis(df_regional),
        grafico_6_value_distribution(df_value),
        grafico_7_parliamentar_object_matrix(df_matrix),
        grafico_8_temporal_patterns(df_temporal),
    ]

    # Gerar HTML
    print("📝 Gerando HTML...")
    html = gerar_html(data_str, cards, charts)

    # Salvar
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(f"✅ Dashboard gerado: {output_path}")
    print(f"   Tamanho: {output_path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
