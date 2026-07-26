#!/usr/bin/env python3
"""
TransfereGov — Dashboard de Análise Cruzada Fiscal/IBGE.

Cruza dados financeiros municipais (SICONFI/Tesouro) com demográficos (IBGE)
e de transferências (TransfereGov) para visualizar:
  1. Saúde fiscal vs volume de transferências
  2. PIB per capita vs benefícios recebidos
  3. Despesas/Receitas por região
  4. Patrimônio líquido vs transferências

Uso: python3 src/dashboard_cross_fiscal.py [--output output/dashboard_cross_fiscal.html]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import get_connection
from src.formatters import fmt_num, fmt_pct

# ═══════════════════════════════════════════════════════════════════════
# CORES E TEMAS (mesmo padrão dos outros dashboards)
# ═══════════════════════════════════════════════════════════════════════

CORES_REGIAO = {
    "Norte": "#2ecc71",
    "Nordeste": "#3498db",
    "Centro-Oeste": "#f1c40f",
    "Sudeste": "#e74c3c",
    "Sul": "#9b59b6",
}

TEMA = {
    "bg": "#0f172a",
    "card": "#1e293b",
    "card_alt": "#1a2332",
    "text": "#e2e8f0",
    "text_muted": "#64748b",
    "accent": "#3b82f6",
    "accent2": "#8b5cf6",
    "border": "#334155",
    "grid": "#334155",
}

ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]

CORES_FISCAL = {
    "saudavel": "#2ecc71",
    "alerta": "#f39c12",
    "critico": "#e74c3c",
}

# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════


def query_df(conn, sql):
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
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEMA["text_muted"], size=10)),
    )
    fig.update_xaxes(
        gridcolor=TEMA["grid"],
        zerolinecolor=TEMA["grid"],
        tickfont=dict(color=TEMA["text_muted"]),
    )
    fig.update_yaxes(
        gridcolor=TEMA["grid"],
        zerolinecolor=TEMA["grid"],
        tickfont=dict(color=TEMA["text_muted"]),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════
# QUERIES SQL — Cruzamento Fiscal × IBGE × Transferências
# ═══════════════════════════════════════════════════════════════════════

# 1. Saúde fiscal vs volume de transferências
SQL_FISCAL_TRANSFERENCIAS = """
SELECT
    mi.nome AS municipio,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    mi.populacao,
    mi.pib,
    CASE WHEN mi.populacao > 0 THEN ROUND(mi.pib / mi.populacao, 2) ELSE NULL END AS pib_per_capita,
    mf.receitas_orcamentarias,
    mf.despesas_orcamentarias,
    CASE
        WHEN mf.receitas_orcamentarias > 0
        THEN ROUND((mf.despesas_orcamentarias / mf.receitas_orcamentarias)::numeric, 4)
        ELSE NULL
    END AS despesas_receitas_ratio,
    SUM(pa.valor_total) AS valor_transferencias,
    COUNT(*) AS qtd_planos
FROM planos_acao pa
JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
LEFT JOIN municipios_financeiro mf
    ON mi.municipio_id = mf.municipio_id
    AND mf.exercicio = 2025
WHERE mi.populacao IS NOT NULL AND mi.populacao > 0
  AND mf.receitas_orcamentarias IS NOT NULL AND mf.receitas_orcamentarias > 0
GROUP BY mi.nome, mi.regiao, mi.populacao, mi.pib,
         mf.receitas_orcamentarias, mf.despesas_orcamentarias
HAVING SUM(pa.valor_total) > 0
"""

# 2. PIB per capita vs benefícios recebidos (com quadrantes)
SQL_PIB_BENEFICIOS = """
SELECT
    mi.nome AS municipio,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    mi.populacao,
    mi.pib,
    CASE WHEN mi.populacao > 0 THEN ROUND(mi.pib / mi.populacao, 2) ELSE NULL END AS pib_per_capita,
    SUM(pa.valor_total) AS valor_total,
    COUNT(*) AS qtd_planos,
    CASE
        WHEN mi.populacao > 0
        THEN ROUND((SUM(pa.valor_total) / mi.populacao)::numeric, 2)
        ELSE NULL
    END AS valor_per_capita
FROM planos_acao pa
JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE mi.populacao IS NOT NULL AND mi.populacao > 0
  AND mi.pib IS NOT NULL AND mi.pib > 0
GROUP BY mi.nome, mi.regiao, mi.populacao, mi.pib
HAVING SUM(pa.valor_total) > 0
"""

# 3. Despesas/Receitas por região (barras agrupadas)
SQL_DESPESAS_RECEITAS_REGIAO = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    ROUND(SUM(mf.receitas_orcamentarias) / 1e6, 2) AS receitas_milhao,
    ROUND(SUM(mf.despesas_orcamentarias) / 1e6, 2) AS despesas_milhao,
    ROUND(SUM(mf.receitas_correntes) / 1e6, 2) AS receitas_correntes_milhao,
    ROUND(SUM(mf.despesas_correntes) / 1e6, 2) AS despesas_correntes_milhao,
    ROUND(SUM(pa.valor_total) / 1e6, 2) AS transferencias_milhao,
    COUNT(DISTINCT mi.municipio_id) AS qtd_municipios,
    CASE
        WHEN SUM(mf.receitas_orcamentarias) > 0
        THEN ROUND((SUM(mf.despesas_orcamentarias) / SUM(mf.receitas_orcamentarias))::numeric, 4)
        ELSE NULL
    END AS ratio_desp_rec
FROM municipios_ibge mi
JOIN municipios_financeiro mf ON mi.municipio_id = mf.municipio_id AND mf.exercicio = 2025
LEFT JOIN beneficiario_ibge_map bm ON mi.municipio_id = bm.municipio_id
LEFT JOIN planos_acao pa ON bm.beneficiario_id = pa.beneficiario_id
WHERE mf.receitas_orcamentarias > 0
GROUP BY mi.regiao
ORDER BY CASE mi.regiao
    WHEN 'Norte' THEN 1 WHEN 'Nordeste' THEN 2
    WHEN 'Centro-Oeste' THEN 3 WHEN 'Sudeste' THEN 4 WHEN 'Sul' THEN 5
    ELSE 6
END
"""

# 4. Patrimônio líquido vs transferências (scatter)
SQL_PATRIMONIO_TRANSFERENCIAS = """
SELECT
    mi.nome AS municipio,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    mi.populacao,
    mf.patrimonio_liquido,
    mf.divida_passiva,
    SUM(pa.valor_total) AS valor_transferencias,
    COUNT(*) AS qtd_planos
FROM planos_acao pa
JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
LEFT JOIN municipios_financeiro mf
    ON mi.municipio_id = mf.municipio_id
    AND mf.exercicio = 2025
WHERE mf.patrimonio_liquido IS NOT NULL
GROUP BY mi.nome, mi.regiao, mi.populacao, mf.patrimonio_liquido, mf.divida_passiva
HAVING SUM(pa.valor_total) > 0
"""

# 5. Resumo fiscal (cards)
SQL_RESUMO_FISCAL = """
SELECT
    COUNT(DISTINCT mf.municipio_id) AS municipios_com_financeiro,
    ROUND(SUM(mf.receitas_orcamentarias) / 1e9, 2) AS receitas_total_bi,
    ROUND(SUM(mf.despesas_orcamentarias) / 1e9, 2) AS despesas_total_bi,
    ROUND(AVG(CASE
        WHEN mf.receitas_orcamentarias > 0
        THEN (mf.despesas_orcamentarias / mf.receitas_orcamentarias)
    END)::numeric, 4) AS ratio_medio,
    ROUND(SUM(mf.patrimonio_liquido) / 1e9, 2) AS patrimonio_total_bi,
    ROUND(SUM(mf.divida_passiva) / 1e9, 2) AS divida_total_bi
FROM municipios_financeiro mf
WHERE mf.exercicio = 2025
"""


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════


def grafico_cards_fiscal(df_resumo):
    """Cards de resumo fiscal no topo do dashboard."""
    r = df_resumo.iloc[0]

    def safe_float(val, default=0.0):
        return float(val) if pd.notna(val) else default

    ratio = safe_float(r["ratio_medio"])
    ratio_pct = ratio * 100
    receitas_bi = safe_float(r["receitas_total_bi"])
    despesas_bi = safe_float(r["despesas_total_bi"])
    patrimonio_bi = safe_float(r["patrimonio_total_bi"])
    divida_bi = safe_float(r["divida_total_bi"])
    n_mun = safe_float(r["municipios_com_financeiro"])

    # Classificar saúde fiscal
    if ratio < 0.9:
        saude = "🟢 Saudável"
        cor_saude = CORES_FISCAL["saudavel"]
    elif ratio < 1.05:
        saude = "🟡 Alerta"
        cor_saude = CORES_FISCAL["alerta"]
    else:
        saude = "🔴 Crítico"
        cor_saude = CORES_FISCAL["critico"]

    return f"""
    <div class="hero">
      <h1>💰 Análise Cruzada Fiscal × Transferências</h1>
      <p class="subtitle">Cruzamento: SICONFI/Tesouro × IBGE × TransfereGov — Dados Financeiros 2025</p>
    </div>
    <div class="cards-row">
      <div class="card">
        <div class="card-icon">🏙️</div>
        <div class="card-num">{fmt_num(n_mun)}</div>
        <div class="card-label">Municípios c/ Dados</div>
        <div class="card-sub">SICONFI/DCA 2025</div>
      </div>
      <div class="card">
        <div class="card-icon">📥</div>
        <div class="card-num">R$ {receitas_bi:.1f} bi</div>
        <div class="card-label">Receitas Totais</div>
      </div>
      <div class="card">
        <div class="card-icon">📤</div>
        <div class="card-num">R$ {despesas_bi:.1f} bi</div>
        <div class="card-label">Despesas Totais</div>
      </div>
      <div class="card">
        <div class="card-icon" style="color: {cor_saude}">⚖️</div>
        <div class="card-num" style="color: {cor_saude}">{fmt_pct(ratio_pct)}</div>
        <div class="card-label">Despesas/Receitas</div>
        <div class="card-sub">{saude}</div>
      </div>
      <div class="card">
        <div class="card-icon">🏛️</div>
        <div class="card-num">R$ {patrimonio_bi:.1f} bi</div>
        <div class="card-label">Patrimônio Líquido</div>
      </div>
      <div class="card">
        <div class="card-icon">💳</div>
        <div class="card-num">R$ {divida_bi:.1f} bi</div>
        <div class="card-label">Dívida Passiva</div>
      </div>
    </div>
    """


def grafico_fiscal_vs_transferencias(df):
    """Scatter: Receitas orçamentárias vs Valor transferências, cor=região, tamanho=população."""
    df = df.copy()
    df["receitas_milhao"] = df["receitas_orcamentarias"] / 1e6
    df["transf_milhao"] = df["valor_transferencias"] / 1e6
    df["pop_mil"] = df["populacao"] / 1000

    # Classificar saúde fiscal
    df["saude_fiscal"] = df["despesas_receitas_ratio"].apply(
        lambda r: (
            "Saudável (<90%)"
            if r is not None and r < 0.9
            else "Alerta (90-105%)"
            if r is not None and r < 1.05
            else "Crítico (>105%)"
            if r is not None
            else "Sem dados"
        )
    )

    fig = px.scatter(
        df,
        x="receitas_milhao",
        y="transf_milhao",
        color="regiao",
        size="pop_mil",
        color_discrete_map=CORES_REGIAO,
        hover_name="municipio",
        hover_data={
            "receitas_milhao": ":.1f",
            "transf_milhao": ":.1f",
            "populacao": True,
            "qtd_planos": True,
            "despesas_receitas_ratio": ":.2f",
            "regiao": False,
        },
        labels={
            "receitas_milhao": "Receitas Orçamentárias (R$ milhões)",
            "transf_milhao": "Transferências Recebidas (R$ milhões)",
            "pop_mil": "População (mil)",
            "regiao": "Região",
        },
        title="💰 Saúde Fiscal vs Volume de Transferências",
        opacity=0.7,
    )

    # Linhas de referência: mediana
    med_rec = df["receitas_milhao"].median()
    med_transf = df["transf_milhao"].median()
    fig.add_hline(y=med_transf, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)
    fig.add_vline(x=med_rec, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)

    # Anotações de quadrante
    fig.add_annotation(
        x=med_rec * 0.3,
        y=med_transf * 2.5,
        text="Baixa receita<br>Alta transferência",
        showarrow=False,
        font=dict(color=TEMA["text_muted"], size=9),
    )
    fig.add_annotation(
        x=med_rec * 2.5,
        y=med_transf * 0.3,
        text="Alta receita<br>Baixa transferência",
        showarrow=False,
        font=dict(color=TEMA["text_muted"], size=9),
    )

    estilo_fig(fig, height=550)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_pib_beneficios(df):
    """Scatter: PIB per capita vs valor per capita, cor=região, quadrantes."""
    df = df.copy()
    df["pib_pc_mil"] = df["pib_per_capita"] / 1000
    df["vpc_mil"] = df["valor_per_capita"] / 1000
    df["pop_mil"] = df["populacao"] / 1000

    fig = px.scatter(
        df,
        x="pib_pc_mil",
        y="vpc_mil",
        color="regiao",
        size="pop_mil",
        color_discrete_map=CORES_REGIAO,
        hover_name="municipio",
        hover_data={
            "pib_per_capita": ":.0f",
            "valor_per_capita": ":.2f",
            "populacao": True,
            "qtd_planos": True,
            "valor_total": ":.0f",
            "regiao": False,
        },
        labels={
            "pib_pc_mil": "PIB per Capita (R$ mil)",
            "vpc_mil": "Valor Transferido per Capita (R$ mil)",
            "pop_mil": "População (mil)",
            "regiao": "Região",
        },
        title="📊 PIB per Capita vs Benefícios Recebidos por Município",
        opacity=0.65,
    )

    # Quadrantes nas medianas
    med_pib = df["pib_pc_mil"].median()
    med_vpc = df["vpc_mil"].median()
    fig.add_hline(y=med_vpc, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)
    fig.add_vline(x=med_pib, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)

    # Anotações
    x_anno = med_pib * 0.25
    fig.add_annotation(
        x=x_anno,
        y=med_vpc * 3,
        text="🔴 Pobre + Alto benefício<br>(foco potencial)",
        showarrow=False,
        font=dict(color="#e74c3c", size=9),
    )
    fig.add_annotation(
        x=med_pib * 3,
        y=med_vpc * 0.2,
        text="🟢 Rico + Baixo benefício",
        showarrow=False,
        font=dict(color="#2ecc71", size=9),
    )
    fig.add_annotation(
        x=med_pib * 3,
        y=med_vpc * 3,
        text="🔵 Rico + Alto benefício",
        showarrow=False,
        font=dict(color="#3498db", size=9),
    )

    estilo_fig(fig, height=550)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_despesas_receitas_regiao(df):
    """Barras agrupadas: Receitas vs Despesas vs Transferências por região."""
    df = df.copy()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Receitas Orçamentárias",
            x=df["regiao"],
            y=df["receitas_milhao"],
            marker_color="#3498db",
            text=[f"R$ {v:.0f}M" for v in df["receitas_milhao"]],
            textposition="auto",
            textfont=dict(size=9),
        )
    )

    fig.add_trace(
        go.Bar(
            name="Despesas Orçamentárias",
            x=df["regiao"],
            y=df["despesas_milhao"],
            marker_color="#e74c3c",
            text=[f"R$ {v:.0f}M" for v in df["despesas_milhao"]],
            textposition="auto",
            textfont=dict(size=9),
        )
    )

    fig.add_trace(
        go.Bar(
            name="Transferências TransfereGov",
            x=df["regiao"],
            y=df["transferencias_milhao"],
            marker_color="#2ecc71",
            text=[f"R$ {v:.0f}M" for v in df["transferencias_milhao"]],
            textposition="auto",
            textfont=dict(size=9),
        )
    )

    fig.update_layout(
        barmode="group",
        title="📊 Receitas vs Despesas vs Transferências por Região (R$ milhões)",
        xaxis=dict(
            title="Região",
            categoryorder="array",
            categoryarray=ORDEM_REGIOES,
        ),
        yaxis=dict(title="R$ milhões"),
        legend=dict(title="Categoria"),
    )

    estilo_fig(fig, height=480)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_patrimonio_transferencias(df):
    """Scatter: Patrimônio líquido vs transferências, cor=região, tamanho=dívida."""
    df = df.copy()
    df["patrimonio_milhao"] = df["patrimonio_liquido"] / 1e6
    df["divida_milhao"] = df["divida_passiva"].clip(lower=0) / 1e6
    df["transf_milhao"] = df["valor_transferencias"] / 1e6
    df["pop_mil"] = df["populacao"] / 1000

    fig = px.scatter(
        df,
        x="patrimonio_milhao",
        y="transf_milhao",
        color="regiao",
        size="divida_milhao",
        color_discrete_map=CORES_REGIAO,
        hover_name="municipio",
        hover_data={
            "patrimonio_milhao": ":.1f",
            "transf_milhao": ":.1f",
            "divida_milhao": ":.1f",
            "populacao": True,
            "qtd_planos": True,
            "regiao": False,
        },
        labels={
            "patrimonio_milhao": "Patrimônio Líquido (R$ milhões)",
            "transf_milhao": "Transferências Recebidas (R$ milhões)",
            "divida_milhao": "Dívida Passiva (R$ milhões)",
            "regiao": "Região",
        },
        title="🏛️ Patrimônio Líquido vs Transferências (tamanho = Dívida Passiva)",
        opacity=0.65,
    )

    # Linhas de referência
    med_pat = df["patrimonio_milhao"].median()
    med_transf = df["transf_milhao"].median()
    fig.add_hline(y=med_transf, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)
    fig.add_vline(x=med_pat, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.4)

    fig.add_annotation(
        x=med_pat * 0.2,
        y=med_transf * 3,
        text="Baixo patrimônio<br>Alta transferência",
        showarrow=False,
        font=dict(color=TEMA["text_muted"], size=9),
    )

    estilo_fig(fig, height=550)
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GERAÇÃO DO HTML
# ═══════════════════════════════════════════════════════════════════════


def gerar_html(data_str, cards, charts):
    """Monta o HTML completo do dashboard."""
    chart_html = ""
    titulos = [
        (
            "Saúde Fiscal vs Transferências",
            "Receitas orçamentárias vs valor transferido por município",
        ),
        ("PIB per Capita vs Benefícios", "PIB per capita vs valor per capita de transferências"),
        ("Receitas vs Despesas por Região", "Composição fiscal regional com transferências"),
        ("Patrimônio vs Transferências", "Patrimônio líquido vs volume de transferências"),
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
        f'<a href="#g{i}" class="nav-item">{t[0]}</a>' for i, t in enumerate(titulos, 1)
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TransfereGov — Análise Cruzada Fiscal × Transferências 2026</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {TEMA["bg"]};
    color: {TEMA["text"]};
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    line-height: 1.5;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
  .hero {{
    text-align: center;
    padding: 40px 20px 20px;
    background: linear-gradient(135deg, {TEMA["card"]}, {TEMA["card_alt"]});
    border-radius: 16px;
    margin-bottom: 20px;
    border: 1px solid {TEMA["border"]};
  }}
  .hero h1 {{ font-size: 28px; color: {TEMA["accent"]}; margin-bottom: 8px; }}
  .subtitle {{ color: {TEMA["text_muted"]}; font-size: 14px; }}
  .cards-row {{
    display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; margin: 20px 0;
  }}
  .card {{
    background: {TEMA["card"]};
    border: 1px solid {TEMA["border"]};
    border-radius: 12px;
    padding: 20px 24px;
    min-width: 160px;
    text-align: center;
    flex: 1;
    max-width: 200px;
  }}
  .card-icon {{ font-size: 24px; margin-bottom: 4px; }}
  .card-num {{
    font-size: 24px; font-weight: 700; color: {TEMA["accent"]};
    line-height: 1.2;
  }}
  .card-label {{
    font-size: 11px; color: {TEMA["text_muted"]};
    text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;
  }}
  .card-sub {{
    font-size: 11px; color: {TEMA["accent2"]}; margin-top: 2px;
  }}
  .nav {{
    display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;
    padding: 16px; background: {TEMA["card"]};
    border-radius: 12px; margin: 20px 0;
    border: 1px solid {TEMA["border"]};
    position: sticky; top: 10px; z-index: 100;
  }}
  .nav-item {{
    padding: 6px 14px; border-radius: 8px;
    background: {TEMA["bg"]}; color: {TEMA["text_muted"]};
    text-decoration: none; font-size: 12px; font-weight: 500;
    transition: all 0.2s;
    border: 1px solid {TEMA["border"]};
  }}
  .nav-item:hover {{
    background: {TEMA["accent"]}; color: white; border-color: {TEMA["accent"]};
  }}
  .section {{
    background: {TEMA["card"]};
    border: 1px solid {TEMA["border"]};
    border-radius: 12px;
    padding: 24px;
    margin: 20px 0;
  }}
  .section-header {{
    display: flex; align-items: center; gap: 16px; margin-bottom: 16px;
  }}
  .section-num {{
    background: {TEMA["accent"]}; color: white;
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 16px; flex-shrink: 0;
  }}
  .section-header h2 {{
    font-size: 18px; color: {TEMA["text"]}; margin: 0;
  }}
  .section-desc {{
    font-size: 12px; color: {TEMA["text_muted"]}; margin: 2px 0 0;
  }}
  .chart-container {{
    width: 100%; overflow-x: auto;
  }}
  .footer {{
    text-align: center; padding: 30px; color: {TEMA["text_muted"]};
    font-size: 12px; border-top: 1px solid {TEMA["border"]}; margin-top: 30px;
  }}
  .footer strong {{ color: {TEMA["accent"]}; }}
  @media (max-width: 768px) {{
    .cards-row {{ flex-direction: column; align-items: stretch; }}
    .card {{ max-width: 100%; }}
    .nav {{ position: static; }}
  }}
</style>
</head>
<body>
<div class="container">
  {cards}
  <nav class="nav">{nav_items}</nav>
  {chart_html}
  <div class="footer">
    <strong>TransfereGov — Análise Cruzada Fiscal</strong><br>
    Dados: API TransfereGov × SICONFI/Tesouro Nacional × IBGE<br>
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
        description="Dashboard de Análise Cruzada Fiscal × Transferências"
    )
    parser.add_argument(
        "--output",
        default="output/dashboard_cross_fiscal.html",
        help="Caminho do arquivo HTML de saída",
    )
    args = parser.parse_args()

    from datetime import datetime

    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    print("🔌 Conectando ao banco...")
    conn = get_connection()

    print("📥 Carregando dados fiscais cruzados...")
    df_resumo = query_df(conn, SQL_RESUMO_FISCAL)
    df_fiscal = query_df(conn, SQL_FISCAL_TRANSFERENCIAS)
    df_pib = query_df(conn, SQL_PIB_BENEFICIOS)
    df_regiao = query_df(conn, SQL_DESPESAS_RECEITAS_REGIAO)
    df_patrimonio = query_df(conn, SQL_PATRIMONIO_TRANSFERENCIAS)
    conn.close()

    total_mun = int(df_resumo.iloc[0]["municipios_com_financeiro"])
    ratio_medio = (
        float(df_resumo.iloc[0]["ratio_medio"])
        if pd.notna(df_resumo.iloc[0]["ratio_medio"])
        else 0
    )
    print(f"📊 Dados: {total_mun} municípios com dados financeiros, ratio D/R = {ratio_medio:.2%}")

    print("🎨 Gerando gráficos...")
    cards = grafico_cards_fiscal(df_resumo)

    print("  [1/4] Saúde fiscal vs transferências...")
    g1 = grafico_fiscal_vs_transferencias(df_fiscal)

    print("  [2/4] PIB per capita vs benefícios...")
    g2 = grafico_pib_beneficios(df_pib)

    print("  [3/4] Receitas vs despesas por região...")
    g3 = grafico_despesas_receitas_regiao(df_regiao)

    print("  [4/4] Patrimônio vs transferências...")
    g4 = grafico_patrimonio_transferencias(df_patrimonio)

    charts = [g1, g2, g3, g4]

    print("📝 Montando HTML...")
    html = gerar_html(data_str, cards, charts)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Dashboard fiscal salvo: {output_path.resolve()}")
    print(f"📊 {total_mun} municípios • Ratio D/R = {ratio_medio:.2%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
