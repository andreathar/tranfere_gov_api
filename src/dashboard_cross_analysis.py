#!/usr/bin/env python3
"""
TransfereGov — Dashboard de Análise Cruzada de Dados Enriquecidos.

Gera gráficos Plotly interativos cruzando dados de múltiplas fontes:
  - Cobertura do enriquecimento (IBGE, Câmara, CNPJ)
  - Análise regional × situação × valor
  - Padrões parlamentar × região
  - Distribuição por população do município beneficiário
  - Política pública × região
  - Especialização temática por região
  - Desempenho parlamentar por região e partido
  - Mapa de calor: região × situação × objeto

Uso: python3 src/dashboard_cross_analysis.py [--output output/dashboard_cross_analysis.html]
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
# CORES E TEMAS
# ═══════════════════════════════════════════════════════════════════════

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

CORES_REGIAO = {
    "Norte": "#2ecc71",
    "Nordeste": "#3498db",
    "Centro-Oeste": "#f1c40f",
    "Sudeste": "#e74c3c",
    "Sul": "#9b59b6",
}

CORES_CATEGORIA = {
    "positiva": "#2ecc71",
    "negada": "#e74c3c",
    "neutra": "#3498db",
    "em_andamento": "#f39c12",
}

ESCALA_GRADIENTE = [
    [0.0, "#e74c3c"],
    [0.3, "#f39c12"],
    [0.5, "#f1c40f"],
    [0.7, "#2ecc71"],
    [1.0, "#27ae60"],
]

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

ORDem_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]

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
# QUERIES — Análise Cruzada
# ═══════════════════════════════════════════════════════════════════════

# 1. Cobertura do enriquecimento
SQL_COBERTURA = """
SELECT
    (SELECT COUNT(*) FROM planos_acao) AS total_planos,
    (SELECT COUNT(DISTINCT beneficiario_id) FROM planos_acao) AS total_beneficiarios,
    (SELECT COUNT(DISTINCT beneficiario_id) FROM beneficiario_ibge_map) AS mapeados_ibge,
    (SELECT COUNT(DISTINCT deputado_id) FROM parlamentares_dados) AS deputados_enriquecidos,
    (SELECT COUNT(DISTINCT parlamentar_nome) FROM planos_acao
     WHERE parlamentar_nome IS NOT NULL AND parlamentar_nome != '') AS parlamentares_no_dados,
    (SELECT COUNT(*) FROM validacao_cnpj) AS cnpjs_validados,
    (SELECT COUNT(DISTINCT parlamentar_nome) FROM planos_acao pa
     JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
     WHERE pa.parlamentar_nome IS NOT NULL) AS parlamentares_cruzados,
    (SELECT COALESCE(SUM(valor_total), 0) FROM planos_acao) AS valor_total
"""

# 2. Região × Situação × Valor (heatmap principal)
SQL_REGIAO_SITUACAO = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    pa.plano_acao_situacao,
    COUNT(*) AS qtd,
    SUM(pa.valor_total) AS valor
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
GROUP BY mi.regiao, pa.plano_acao_situacao
ORDER BY mi.regiao, qtd DESC
"""

# 3. Região × Política Pública (treemap)
SQL_REGIAO_POLITICA = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    COALESCE(mi.nome, 'Sem município') AS municipio,
    pa.politicas_publicas,
    COUNT(*) AS qtd,
    SUM(pa.valor_total) AS valor,
    COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.politicas_publicas IS NOT NULL AND pa.politicas_publicas != ''
GROUP BY mi.regiao, mi.nome, pa.politicas_publicas
"""

# 4. Parlamentar × Região (scatter com eficiência)
SQL_PARL_REGIAO_EFICIENCIA = """
SELECT
    pa.parlamentar_nome,
    COALESCE(pd.sigla_partido, 'N/I') AS partido,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor,
    ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao NOT IN
        ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','REPROVADO','CANCELADO','NAO_CUMPROU')
        THEN 1 ELSE 0 END) / COUNT(*), 1) AS taxa_sucesso
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pd.sigla_partido, mi.regiao
"""

# 5. Faixa populacional × Situação
SQL_POPULACAO_SITUACAO = """
WITH base AS (
    SELECT
        CASE
            WHEN mi.populacao IS NULL THEN 'Sem dados'
            WHEN mi.populacao < 10000 THEN '01 - < 10 mil'
            WHEN mi.populacao < 50000 THEN '02 - 10-50 mil'
            WHEN mi.populacao < 100000 THEN '03 - 50-100 mil'
            WHEN mi.populacao < 500000 THEN '04 - 100-500 mil'
            ELSE '05 - > 500 mil'
        END AS faixa_pop,
        pa.plano_acao_situacao
    FROM planos_acao pa
    LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
    LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
)
SELECT faixa_pop, plano_acao_situacao, COUNT(*) AS qtd, SUM(0) AS valor
FROM base
GROUP BY faixa_pop, plano_acao_situacao
ORDER BY faixa_pop, qtd DESC
"""

# 6. Objeto × Região (especialização)
SQL_OBJETO_REGIAO = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    o.descricao AS objeto_descricao,
    COUNT(*) AS qtd,
    SUM(pa.valor_total) AS valor,
    ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao NOT IN
        ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','REPROVADO','CANCELADO','NAO_CUMPROU')
        THEN 1 ELSE 0 END) / COUNT(*), 1) AS taxa_sucesso
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
GROUP BY mi.regiao, o.descricao
HAVING COUNT(*) >= 5
"""

# 7. Partido × Região (barras empilhadas)
SQL_PARTIDO_REGIAO = """
SELECT
    COALESCE(pd.sigla_partido, 'N/I') AS partido,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    COUNT(DISTINCT pa.parlamentar_nome) AS deputados,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
  AND pd.sigla_partido IS NOT NULL
GROUP BY pd.sigla_partido, mi.regiao
"""

# 8. Valor per capita por município (cruza valor com população)
SQL_VALOR_PER_CAPITA = """
SELECT
    mi.nome AS municipio,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    mi.populacao,
    SUM(pa.valor_total) AS valor_total,
    COUNT(*) AS planos,
    ROUND((SUM(pa.valor_total) / NULLIF(mi.populacao, 0))::numeric, 2) AS valor_per_capita
FROM planos_acao pa
JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE mi.populacao IS NOT NULL AND mi.populacao > 0
GROUP BY mi.nome, mi.regiao, mi.populacao
HAVING SUM(pa.valor_total) > 0
"""

# 9. Mesorregião × Situação (sankey-like flow)
SQL_MESORREGIAO_STATUS = """
SELECT
    COALESCE(mi.mesorregiao, 'Sem mesorregião') AS mesorregiao,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    pa.plano_acao_situacao,
    COUNT(*) AS qtd,
    SUM(pa.valor_total) AS valor
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE mi.mesorregiao IS NOT NULL
GROUP BY mi.mesorregiao, mi.regiao, pa.plano_acao_situacao
"""


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICOS
# ═══════════════════════════════════════════════════════════════════════


def grafico_cobertura(df):
    """Cards de cobertura do enriquecimento — visão geral multi-fonte."""
    r = df.iloc[0]
    total_b = r["total_beneficiarios"]
    ibge_pct = (r["mapeados_ibge"] / total_b * 100) if total_b > 0 else 0
    parl_cruz_pct = (
        (r["parlamentares_cruzados"] / r["parlamentares_no_dados"] * 100)
        if r["parlamentares_no_dados"] > 0
        else 0
    )

    cards = f"""
    <div class="hero">
      <h1>🔗 Análise Cruzada de Dados Enriquecidos</h1>
      <p class="subtitle">Cruzamento de fontes: API TransfereGov × IBGE × Câmara dos Deputados × BrasilAPI</p>
    </div>
    <div class="cards-row">
      <div class="card">
        <div class="card-icon">📋</div>
        <div class="card-num">{fmt_num(r["total_planos"])}</div>
        <div class="card-label">Planos de Ação</div>
      </div>
      <div class="card">
        <div class="card-icon">🗺️</div>
        <div class="card-num">{fmt_num(r["mapeados_ibge"])}</div>
        <div class="card-label">Mapeados IBGE</div>
        <div class="card-sub">{fmt_pct(ibge_pct)} cobertura</div>
      </div>
      <div class="card">
        <div class="card-icon">🏛️</div>
        <div class="card-num">{fmt_num(r["deputados_enriquecidos"])}</div>
        <div class="card-label">Deputados Câmara</div>
        <div class="card-sub">{fmt_pct(parl_cruz_pct)} cruzados</div>
      </div>
      <div class="card">
        <div class="card-icon">💰</div>
        <div class="card-num">R$ {r["valor_total"] / 1e9:.2f} bi</div>
        <div class="card-label">Valor Total</div>
      </div>
      <div class="card">
        <div class="card-icon">🏢</div>
        <div class="card-num">{fmt_num(r["cnpjs_validados"])}</div>
        <div class="card-label">CNPJs Validados</div>
        <div class="card-sub">BrasilAPI</div>
      </div>
    </div>
    """
    return cards


def grafico_regiao_situacao_heatmap(df):
    """Heatmap: Região × Situação (quantidade de planos)."""
    pivot = df.pivot_table(
        index="regiao", columns="plano_acao_situacao", values="qtd", aggfunc="sum", fill_value=0
    )
    # Reorder rows
    for reg in reversed(ORDem_REGIOES):
        if reg not in pivot.index:
            pivot.loc[reg] = 0
    pivot = pivot.loc[[r for r in ORDem_REGIOES if r in pivot.index]]

    fig = px.imshow(
        pivot,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="YlOrRd",
        labels=dict(x="Situação", y="Região", color="Qtd Planos"),
        title="🗺️ Região × Situação — Distribuição dos Planos de Ação",
    )
    fig.update_traces(texttemplate="%{z:,.0f}", textfont_size=11)
    estilo_fig(fig, height=350)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_regiao_valor_bar(df):
    """Barras empilhadas: valor total por região, segmentado por categoria."""
    # Agregar por região e categoria
    df["categoria"] = df["plano_acao_situacao"].map(
        lambda s: (
            "negada"
            if s
            in (
                "IMPEDIDO",
                "IMPEDIDO_REJEICAO_PLANO_TRABALHO",
                "REPROVADO",
                "CANCELADO",
                "NAO_CUMPROU",
            )
            else "em_andamento"
            if s in ("CIENTE",)
            else "positiva"
        )
    )
    agg = df.groupby(["regiao", "categoria"])["valor"].sum().reset_index()
    agg["valor_milhao"] = agg["valor"] / 1e6

    # Filter to known regions
    agg = agg[agg["regiao"].isin(ORDem_REGIOES)]

    fig = px.bar(
        agg,
        x="regiao",
        y="valor_milhao",
        color="categoria",
        barmode="stack",
        color_discrete_map=CORES_CATEGORIA,
        labels={"regiao": "Região", "valor_milhao": "R$ milhões", "categoria": "Categoria"},
        title="💰 Valor por Região × Categoria (Positiva / Neutra / Negada)",
        category_orders={"regiao": ORDem_REGIOES},
    )
    fig.update_layout(
        legend=dict(
            title=dict(text="Categoria"),
            traceorder="reversed",
        )
    )
    # Rename traces for better legend labels
    rename_map = {
        "positiva": "✅ Positiva (EM_EXECUCAO, CONCLUIDO)",
        "neutra": "🔵 Neutra (CIENTE)",
        "negada": "❌ Negada (IMPEDIDO, REPROVADO, etc.)",
        "em_andamento": "🟡 Em Andamento",
    }
    for trace in fig.data:  # type: ignore[union-attr]
        trace_name = getattr(trace, "name", None)
        if trace_name in rename_map:
            trace_name = rename_map[trace_name]
    estilo_fig(fig, height=420)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_treemap_regiao_politica(df):
    """Treemap: Região → Município → Política Pública (valor)."""
    # Top regiões → top municípios
    df_valid = df[df["regiao"].isin(ORDem_REGIOES)].copy()
    df_valid["valor_milhao"] = df_valid["valor"] / 1e6
    # Simplificar política
    df_valid["politica_short"] = df_valid["politicas_publicas"].str[:40]
    # Top 50 municípios por valor
    top_mun = df_valid.groupby("municipio")["valor"].sum().nlargest(50).index
    df_top = df_valid[df_valid["municipio"].isin(top_mun)].copy()

    # Pre-format text for display
    df_top["display_text"] = df_top.apply(
        lambda r: f"{r['municipio'][:30]}<br>R$ {r['valor_milhao']:.1f}M", axis=1
    )

    fig = px.treemap(
        df_top,
        path=["regiao", "municipio", "politica_short"],
        values="valor_milhao",
        color="regiao",
        color_discrete_map=CORES_REGIAO,
        title="🌳 Treemap: Região → Município → Política Pública (R$ milhões)",
        custom_data=["valor_milhao", "politica_short"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>R$ %{customdata[0]:.1f}M",
        textfont_size=11,
        hovertemplate="<b>%{label}</b><br>Política: %{customdata[1]}<br>Valor: R$ %{customdata[0]:.1f}M<extra></extra>",
    )
    estilo_fig(fig, height=600)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_parl_regiao_scatter(df):
    """Scatter: Planos × Valor por parlamentar, cor = região, tamanho = taxa sucesso."""
    # Agregar por parlamentar (pegar região dominante)
    parl_agg = (
        df.groupby(["parlamentar_nome", "partido"])
        .agg(
            planos=("planos", "sum"),
            valor=("valor", "sum"),
            taxa_media=("taxa_sucesso", "mean"),
            regiao_principal=(
                "regiao",
                lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "N/I",
            ),
        )
        .reset_index()
    )

    # Top 50 por valor
    top = parl_agg.nlargest(50, "valor")

    fig = px.scatter(
        top,
        x="planos",
        y="valor",
        color="regiao_principal",
        size="taxa_media",
        color_discrete_map=CORES_REGIAO,
        hover_name="parlamentar_nome",
        hover_data={"partido": True, "taxa_media": ":.1f%", "regiao_principal": True},
        labels={
            "planos": "Qtd Planos",
            "valor": "Valor Total (R$)",
            "regiao_principal": "Região Dominante",
            "taxa_media": "Taxa Sucesso",
        },
        title="🔍 Parlamentares: Volume vs Valor — Cor por Região Dominante",
    )
    estilo_fig(fig, height=500)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_populacao_situacao(df):
    """Barras empilhadas: Faixa populacional × Situação."""
    # Calcular % por faixa
    df_total = df.groupby("faixa_pop")["qtd"].sum().reset_index()
    df_total.columns = ["faixa_pop", "total"]
    df_merged = df.merge(df_total, on="faixa_pop")
    df_merged["pct"] = df_merged["qtd"] / df_merged["total"] * 100

    fig = px.bar(
        df_merged,
        x="faixa_pop",
        y="pct",
        color="plano_acao_situacao",
        barmode="stack",
        color_discrete_map=CORES_SITUACAO,
        labels={
            "faixa_pop": "Faixa Populacional",
            "pct": "% dos Planos",
            "plano_acao_situacao": "Situação",
        },
        title="👥 Faixa Populacional do Município × Situação dos Planos",
        category_orders={
            "faixa_pop": [
                "01 - < 10 mil",
                "02 - 10-50 mil",
                "03 - 50-100 mil",
                "04 - 100-500 mil",
                "05 - > 500 mil",
                "Sem dados",
            ]
        },
    )
    fig.update_layout(
        yaxis=dict(title="% dos Planos", ticksuffix="%"),
        legend=dict(title="Situação"),
    )
    estilo_fig(fig, height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_objeto_regiao_heatmap(df):
    """Heatmap: Top Objetos × Regiões — valor em R$ milhões."""
    # Top 15 objetos por valor total
    top_obj = df.groupby("objeto_descricao")["valor"].sum().nlargest(15).index
    df_top = df[df["objeto_descricao"].isin(top_obj) & df["regiao"].isin(ORDem_REGIOES)]

    pivot = (
        df_top.pivot_table(
            index="objeto_descricao", columns="regiao", values="valor", aggfunc="sum", fill_value=0
        )
        / 1e6
    )

    # Abbreviate object names
    pivot.index = [
        c.split(" - ")[0] + " - " + c.split(" - ")[1][:30] if " - " in c else c[:35]
        for c in pivot.index
    ]

    fig = px.imshow(
        pivot,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="Blues",
        labels=dict(x="Região", y="Objeto", color="R$ milhões"),
        title="🎯 Especialização Temática: Objeto × Região (R$ milhões)",
    )
    fig.update_traces(texttemplate="%{z:.1f}M", textfont_size=10)
    estilo_fig(fig, height=550)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_partido_regiao(df):
    """Barras agrupadas: Top partidos × Região."""
    # Top 12 partidos por valor
    partido_valor = df.groupby("partido")["valor"].sum().nlargest(12).index
    df_top = df[df["partido"].isin(partido_valor) & df["regiao"].isin(ORDem_REGIOES)]
    df_top["valor_milhao"] = df_top["valor"] / 1e6

    fig = px.bar(
        df_top,
        x="partido",
        y="valor_milhao",
        color="regiao",
        barmode="group",
        color_discrete_map=CORES_REGIAO,
        labels={"partido": "Partido", "valor_milhao": "R$ milhões", "regiao": "Região"},
        title="🏛️ Partidos × Região — Distribuição do Valor (Top 12 Partidos)",
        category_orders={"regiao": ORDem_REGIOES},
    )
    estilo_fig(fig, height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_valor_per_capita(df):
    """Scatter: População vs Valor Per Capita, cor = região."""
    df["valor_pc_mil"] = df["valor_per_capita"] / 1000
    df["pop_mil"] = df["populacao"] / 1000

    fig = px.scatter(
        df,
        x="pop_mil",
        y="valor_pc_mil",
        color="regiao",
        color_discrete_map=CORES_REGIAO,
        hover_name="municipio",
        hover_data={
            "populacao": True,
            "valor_total": ":.0f",
            "planos": True,
            "valor_per_capita": ":.2f",
        },
        labels={
            "pop_mil": "População (mil hab.)",
            "valor_pc_mil": "Valor Per Capita (R$ mil)",
            "regiao": "Região",
        },
        title="💎 Valor Per Capita por Município — Tamanho = População",
        opacity=0.6,
    )
    # Add quadrant lines
    median_pop = df["pop_mil"].median()
    median_vpc = df["valor_pc_mil"].median()
    fig.add_hline(y=median_vpc, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.5)
    fig.add_vline(x=median_pop, line_dash="dash", line_color=TEMA["text_muted"], opacity=0.5)
    fig.add_annotation(
        x=median_pop * 1.5,
        y=median_vpc * 1.5,
        text="Alta capita<br>Alta pop",
        showarrow=False,
        font=dict(color=TEMA["text_muted"], size=9),
    )
    fig.add_annotation(
        x=median_pop * 0.3,
        y=median_vpc * 1.5,
        text="Alta capita<br>Baixa pop",
        showarrow=False,
        font=dict(color=TEMA["text_muted"], size=9),
    )
    estilo_fig(fig, height=500)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_sankey_mesorregiao(df):
    """Sankey: Região → Mesorregião → Situação (top mesorregiões)."""
    # Calcular label e valor
    df_valid = df[df["regiao"].isin(ORDem_REGIOES)].copy()

    # Mapear situação para categoria simplificada
    def cat_sit(s):
        if s in (
            "IMPEDIDO",
            "IMPEDIDO_REJEICAO_PLANO_TRABALHO",
            "REPROVADO",
            "CANCELADO",
            "NAO_CUMPROU",
        ):
            return "❌ Negada"
        elif s in ("EM_EXECUCAO", "CONCLUIDO"):
            return "✅ Aprovada"
        elif s == "CIENTE":
            return "🔵 Ciente"
        else:
            return "🟡 Outra"

    df_valid["sit_cat"] = df_valid["plano_acao_situacao"].apply(cat_sit)

    # Top 10 mesorregiões
    top_mesos = df_valid.groupby("mesorregiao")["qtd"].sum().nlargest(10).index
    df_top = df_valid[df_valid["mesorregiao"].isin(top_mesos)]

    # Aggregate
    agg = df_top.groupby(["regiao", "mesorregiao", "sit_cat"])["qtd"].sum().reset_index()

    # Build Sankey nodes and links
    regioes = sorted(agg["regiao"].unique())
    mesos = sorted(agg["mesorregiao"].unique())
    cats = sorted(agg["sit_cat"].unique())

    nodes = regioes + mesos + cats
    node_idx = {n: i for i, n in enumerate(nodes)}

    sources, targets, values, colors = [], [], [], []
    reg_colors = {
        "Norte": "rgba(46,204,113,0.5)",
        "Nordeste": "rgba(52,152,219,0.5)",
        "Centro-Oeste": "rgba(241,196,15,0.5)",
        "Sudeste": "rgba(231,76,60,0.5)",
        "Sul": "rgba(155,89,182,0.5)",
    }

    for _, row in agg.iterrows():
        sources.append(node_idx[row["regiao"]])
        targets.append(node_idx[row["mesorregiao"]])
        values.append(row["qtd"])
        colors.append(reg_colors.get(row["regiao"], "rgba(149,165,166,0.3)"))

    for _, row in agg.iterrows():
        sources.append(node_idx[row["mesorregiao"]])
        targets.append(node_idx[row["sit_cat"]])
        values.append(row["qtd"])
        colors.append("rgba(149,165,166,0.2)")

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color=TEMA["border"], width=0.5),
                label=nodes,
                color=[TEMA["accent"]] * len(regioes)
                + [TEMA["accent2"]] * len(mesos)
                + [
                    CORES_CATEGORIA.get("positiva", "#2ecc71"),
                    CORES_CATEGORIA.get("negada", "#e74c3c"),
                    CORES_CATEGORIA.get("neutra", "#3498db"),
                    "#f39c12",
                ][: len(cats)],
            ),
            link=dict(source=sources, target=targets, value=values, color=colors),
        )
    )
    fig.update_layout(
        title="🌊 Fluxo: Região → Mesorregião → Situação dos Planos",
        paper_bgcolor=TEMA["card"],
        font=dict(color=TEMA["text"], size=11),
        height=550,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GERAÇÃO DO HTML
# ═══════════════════════════════════════════════════════════════════════


def gerar_html(data_str, cards, charts):
    """Monta o HTML completo do dashboard."""
    chart_html = ""
    titulos = [
        ("Cobertura do Enriquecimento", "Visão geral das fontes de dados cruzadas"),
        ("Região × Situação", "Distribuição de planos por região e situação"),
        ("Valor por Região × Categoria", "Valores agregados: positiva, neutra, negada"),
        ("Treemap Regional", "Detalhamento região → município → política"),
        ("Parlamentar × Região", "Scatter de volume vs valor, cor = região dominante"),
        ("Faixa Populacional", "Análise por porte do município beneficiário"),
        ("Objeto × Região", "Especialização temática por região"),
        ("Partido × Região", "Distribuição partidária regional"),
        ("Valor Per Capita", "Municípios: população vs valor per capita"),
        ("Fluxo Regional", "Sankey: região → mesorregião → situação"),
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
<title>TransfereGov — Análise Cruzada de Dados Enriquecidos 2026</title>
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
    min-width: 180px;
    text-align: center;
    flex: 1;
    max-width: 220px;
  }}
  .card-icon {{ font-size: 24px; margin-bottom: 4px; }}
  .card-num {{
    font-size: 26px; font-weight: 700; color: {TEMA["accent"]};
    line-height: 1.2;
  }}
  .card-label {{
    font-size: 12px; color: {TEMA["text_muted"]};
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
    <strong>TransfereGov — Análise Cruzada</strong><br>
    Dados: API TransfereGov × IBGE × Câmara dos Deputados × BrasilAPI<br>
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
        description="Dashboard de Análise Cruzada de Dados Enriquecidos"
    )
    parser.add_argument(
        "--output",
        default="output/dashboard_cross_analysis.html",
        help="Caminho do arquivo HTML de saída",
    )
    args = parser.parse_args()

    from datetime import datetime

    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    print("🔌 Conectando ao banco...")
    conn = get_connection()

    print("📥 Carregando dados cruzados...")
    df_cobertura = query_df(conn, SQL_COBERTURA)
    df_reg_sit = query_df(conn, SQL_REGIAO_SITUACAO)
    df_reg_pol = query_df(conn, SQL_REGIAO_POLITICA)
    df_parl_reg = query_df(conn, SQL_PARL_REGIAO_EFICIENCIA)
    df_pop_sit = query_df(conn, SQL_POPULACAO_SITUACAO)
    df_obj_reg = query_df(conn, SQL_OBJETO_REGIAO)
    df_part_reg = query_df(conn, SQL_PARTIDO_REGIAO)
    df_vpc = query_df(conn, SQL_VALOR_PER_CAPITA)
    df_meso = query_df(conn, SQL_MESORREGIAO_STATUS)
    conn.close()

    total_reg = len(df_reg_sit)
    total_parl = df_parl_reg["parlamentar_nome"].nunique()
    print(f"📊 Dados: {total_reg} registros região×situação, {total_parl} parlamentares")

    print("🎨 Gerando gráficos...")
    cards = grafico_cobertura(df_cobertura)

    print("  [1/10] Região × Situação heatmap...")
    g1 = grafico_regiao_situacao_heatmap(df_reg_sit)

    print("  [2/10] Valor por região × categoria...")
    g2 = grafico_regiao_valor_bar(df_reg_sit)

    print("  [3/10] Treemap regional...")
    g3 = grafico_treemap_regiao_politica(df_reg_pol)

    print("  [4/10] Parlamentar × região scatter...")
    g4 = grafico_parl_regiao_scatter(df_parl_reg)

    print("  [5/10] Faixa populacional × situação...")
    g5 = grafico_populacao_situacao(df_pop_sit)

    print("  [6/10] Objeto × região heatmap...")
    g6 = grafico_objeto_regiao_heatmap(df_obj_reg)

    print("  [7/10] Partido × região...")
    g7 = grafico_partido_regiao(df_part_reg)

    print("  [8/10] Valor per capita scatter...")
    g8 = grafico_valor_per_capita(df_vpc)

    print("  [9/10] Sankey mesorregião...")
    g9 = grafico_sankey_mesorregiao(df_meso)

    charts = [g1, g2, g3, g4, g5, g6, g7, g8, g9]

    print("📝 Montando HTML...")
    # Add a 10th summary chart: bar of enrichment coverage
    coverage = df_cobertura.iloc[0]
    total_b = coverage["total_beneficiarios"]
    sources = ["IBGE Mapeados", "Deputados Câmara", "Cruzados Parl.", "CNPJs Validados"]
    vals = [
        coverage["mapeados_ibge"],
        coverage["deputados_enriquecidos"],
        coverage["parlamentares_cruzados"],
        coverage["cnpjs_validados"],
    ]
    pcts = [v / total_b * 100 if total_b > 0 else 0 for v in vals]

    fig_cov = go.Figure(
        go.Bar(
            x=pcts,
            y=sources,
            orientation="h",
            text=[f"{fmt_num(v)} ({fmt_pct(p)})" for v, p in zip(vals, pcts)],
            textposition="auto",
            marker=dict(color=[TEMA["accent"], "#2ecc71", "#8b5cf6", "#f39c12"]),
        )
    )
    fig_cov.update_layout(
        title="📊 Cobertura do Enriquecimento por Fonte",
        xaxis=dict(title="% do Total de Beneficiários", ticksuffix="%"),
        yaxis=dict(autorange="reversed"),
    )
    estilo_fig(fig_cov, height=280)
    g10 = fig_cov.to_html(full_html=False, include_plotlyjs=False)
    charts.append(g10)

    html = gerar_html(data_str, cards, charts)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Dashboard salvo: {output_path.resolve()}")
    print(
        f"📊 {fmt_num(coverage['total_planos'])} planos • "
        f"{fmt_num(total_parl)} parlamentares • "
        f"R$ {coverage['valor_total'] / 1e9:.2f} bilhões"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
