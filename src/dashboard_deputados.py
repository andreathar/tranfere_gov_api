#!/usr/bin/env python3
"""
TransfereGov — Dashboard de Competência e Eficiência dos Parlamentares.

Gera 10 gráficos criativos e interativos (Plotly) para avaliar o desempenho
dos deputados federais na gestão das Transferências Especiais (Emendas Pix).

Uso:
    python3 src/dashboard_deputados.py [--output output/dashboard_deputados.html]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS


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

CORES_PARTIDO = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel1

# Paleta gradiente para eficiência (vermelho → amarelo → verde)
ESCALA_EFICIENCIA = [
    [0.0, "#e74c3c"],
    [0.25, "#f39c12"],
    [0.5, "#f1c40f"],
    [0.75, "#2ecc71"],
    [1.0, "#27ae60"],
]

TEMA = {
    "bg": "#0f172a",
    "card": "#1e293b",
    "text": "#e2e8f0",
    "text_muted": "#64748b",
    "accent": "#3b82f6",
    "border": "#1e293b",
}


# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════

def get_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )


def query_df(conn, sql):
    return pd.read_sql(sql, conn)


def fmt_brl(valor):
    if pd.isna(valor) or valor is None:
        return "R$ 0"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_num(valor):
    if pd.isna(valor) or valor is None:
        return "0"
    return f"{int(valor):,}".replace(",", ".")


def fmt_pct(valor):
    if pd.isna(valor) or valor is None:
        return "0%"
    return f"{valor:.1f}%"


def estilo_fig(fig, height=450):
    """Aplica o tema escuro padrão a uma figura Plotly."""
    fig.update_layout(
        paper_bgcolor=TEMA["card"],
        plot_bgcolor=TEMA["card"],
        font=dict(color=TEMA["text"], size=11),
        title=dict(font=dict(size=15, color=TEMA["text"])),
        height=height,
        margin=dict(l=60, r=30, t=50, b=60),
        hovermode="closest",
    )
    fig.update_xaxes(
        gridcolor="#334155", zerolinecolor="#334155", tickfont=dict(color=TEMA["text_muted"])
    )
    fig.update_yaxes(
        gridcolor="#334155", zerolinecolor="#334155", tickfont=dict(color=TEMA["text_muted"])
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════
# QUERIES
# ═══════════════════════════════════════════════════════════════════════

SQL_RESUMO = """
SELECT
    COUNT(*) AS total_planos,
    COUNT(DISTINCT parlamentar_nome) AS total_parlamentares,
    COUNT(DISTINCT beneficiario_id) AS total_municipios,
    COUNT(DISTINCT objeto_id) AS total_objetos,
    SUM(valor_total) AS valor_total
FROM planos_acao
"""

SQL_EFICIENCIA_PARLAMENTAR = """
SELECT
    pa.parlamentar_nome,
    COALESCE(pd.sigla_partido, 'N/I') AS partido,
    COALESCE(pd.uf, 'N/I') AS parlamentar_uf,
    COUNT(*) AS total_planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    COUNT(DISTINCT pa.objeto_id) AS objetos,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','REPROVADO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) AS negados,
    ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao NOT IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','REPROVADO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) / COUNT(*), 1) AS taxa_sucesso,
    ROUND((SUM(pa.valor_total) / NULLIF(COUNT(DISTINCT pa.beneficiario_id), 0))::numeric, 2) AS valor_por_municipio,
    ROUND((SUM(pa.valor_total) / NULLIF(COUNT(*), 0))::numeric, 2) AS valor_medio_plano
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pd.sigla_partido, pd.uf
ORDER BY valor_total DESC
"""

SQL_PARLAMENTAR_REGIAO = """
SELECT
    pa.parlamentar_nome,
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    COUNT(*) AS planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, mi.regiao
ORDER BY valor DESC
"""

SQL_PARTIDO_EFICIENCIA = """
SELECT
    COALESCE(pd.sigla_partido, 'N/I') AS partido,
    COUNT(DISTINCT pa.parlamentar_nome) AS deputados,
    COUNT(*) AS total_planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor_total,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    ROUND(AVG(sub.taxa_sucesso)::numeric, 1) AS taxa_sucesso_media,
    ROUND((SUM(pa.valor_total) / NULLIF(COUNT(DISTINCT pa.parlamentar_nome), 0))::numeric, 2) AS valor_por_deputado,
    ROUND((SUM(pa.valor_total) / NULLIF(COUNT(DISTINCT pa.beneficiario_id), 0))::numeric, 2) AS valor_por_municipio
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
LEFT JOIN (
    SELECT
        parlamentar_nome,
        100.0 * SUM(CASE WHEN plano_acao_situacao NOT IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','REPROVADO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) / COUNT(*) AS taxa_sucesso
    FROM planos_acao
    WHERE parlamentar_nome IS NOT NULL AND parlamentar_nome != ''
    GROUP BY parlamentar_nome
) sub ON pa.parlamentar_nome = sub.parlamentar_nome
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
  AND pd.sigla_partido IS NOT NULL
GROUP BY pd.sigla_partido
ORDER BY valor_total DESC
"""

SQL_PARLAMENTAR_OBJETO = """
SELECT
    pa.parlamentar_nome,
    o.objeto_id,
    LEFT(o.descricao, 50) AS objeto_descricao,
    COUNT(*) AS planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, o.objeto_id, o.descricao
ORDER BY valor DESC
"""

SQL_IMPEDIMENTO = """
SELECT
    pa.parlamentar_nome,
    COALESCE(pd.sigla_partido, 'N/I') AS partido,
    COUNT(*) AS total_planos,
    SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO') THEN 1 ELSE 0 END) AS impedidos,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO' THEN 1 ELSE 0 END) AS impedido_tecnico,
    SUM(CASE WHEN pa.plano_acao_situacao = 'IMPEDIDO_REJEICAO_PLANO_TRABALHO' THEN 1 ELSE 0 END) AS impedido_rejeicao,
    ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS taxa_impedimento,
    ROUND(SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO') THEN pa.valor_total ELSE 0 END)::numeric, 2) AS valor_impedido
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pd.sigla_partido
HAVING COUNT(*) >= 3
ORDER BY taxa_impedimento DESC
"""

SQL_REGIAO_SITUACAO = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    pa.plano_acao_situacao,
    COUNT(*) AS planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor
FROM planos_acao pa
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
GROUP BY mi.regiao, pa.plano_acao_situacao
ORDER BY regiao, valor DESC
"""

SQL_OBJETO_TREEMAP = """
SELECT
    COALESCE(mi.regiao, 'Sem região') AS regiao,
    o.objeto_id,
    LEFT(o.descricao, 60) AS objeto_descricao,
    COUNT(*) AS planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor,
    ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao NOT IN ('IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO','REPROVADO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS taxa_sucesso
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
GROUP BY mi.regiao, o.objeto_id, o.descricao
ORDER BY valor DESC
"""

SQL_TOP_MUNICIPIOS = """
SELECT
    pa.parlamentar_nome,
    COALESCE(pd.sigla_partido, 'N/I') AS partido,
    b.nome AS municipio,
    b.uf,
    COUNT(*) AS planos,
    ROUND(SUM(pa.valor_total)::numeric, 2) AS valor
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != ''
GROUP BY pa.parlamentar_nome, pd.sigla_partido, b.nome, b.uf
ORDER BY valor DESC
"""


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 1 — Dispersão: Eficiência vs Volume
# ═══════════════════════════════════════════════════════════════════════

def grafico_eficiencia_vs_volume(df):
    """
    Scatter plot: Taxa de Sucesso (%) vs Valor Total (R$).
    Cada bolha = 1 deputado. Tamanho = nº municípios. Cor = partido.
    Mostra quem entrega muito com alta taxa de aprovação.
    """
    df = df[df["total_planos"] >= 3].copy()  # filtrar ruído
    df["label"] = df["parlamentar_nome"].str.title()
    df["valor_milhao"] = df["valor_total"] / 1_000_000

    fig = px.scatter(
        df,
        x="taxa_sucesso",
        y="valor_milhao",
        size="municipios",
        color="partido",
        hover_name="parlamentar_nome",
        hover_data={
            "taxa_sucesso": ":.1f",
            "valor_milhao": ":.2f",
            "municipios": True,
            "objetos": True,
            "total_planos": True,
            "partido": True,
        },
        labels={
            "taxa_sucesso": "Taxa de Sucesso (%)",
            "valor_milhao": "Valor Total (R$ milhões)",
            "municipios": "Municípios Atendidos",
            "partido": "Partido",
        },
        title="🎯 Eficiência vs Volume — Quem Entrega Mais e Melhor?",
        color_discrete_sequence=CORES_PARTIDO,
        size_max=40,
        opacity=0.8,
    )

    # Linhas de referência
    med_x = df["taxa_sucesso"].median()
    med_y = df["valor_milhao"].median()
    fig.add_vline(x=med_x, line_dash="dash", line_color="#64748b", opacity=0.5)
    fig.add_hline(y=med_y, line_dash="dash", line_color="#64748b", opacity=0.5)

    # Anotação dos quadrantes
    fig.add_annotation(x=98, y=df["valor_milhao"].max() * 0.95,
                       text="🏆 Alta entrega + Alta eficiência",
                       showarrow=False, font=dict(color="#2ecc71", size=10))
    fig.add_annotation(x=98, y=df["valor_milhao"].min() + 1,
                       text="📈 Alta eficiência, baixo volume",
                       showarrow=False, font=dict(color="#3498db", size=10))
    fig.add_annotation(x=df["taxa_sucesso"].min() + 1, y=df["valor_milhao"].max() * 0.95,
                       text="💰 Alto volume, baixa eficiência",
                       showarrow=False, font=dict(color="#e74c3c", size=10))

    fig.update_traces(marker=dict(line=dict(width=1, color="white")))
    fig = estilo_fig(fig, height=600)
    fig.update_xaxes(range=[df["taxa_sucesso"].min() - 2, 101])
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 2 — Top 30 Parlamentares por Valor com Taxa de Sucesso
# ═══════════════════════════════════════════════════════════════════════

def grafico_top_parlamentares(df):
    """
    Barras horizontais: Top 30 deputados por valor total.
    Cor = gradiente de eficiência (vermelho=baixa, verde=alta).
    """
    top = df.head(30).copy()
    top = top.sort_values("valor_total", ascending=True)
    top["label"] = top["parlamentar_nome"].str.title()
    top["valor_milhao"] = top["valor_total"] / 1_000_000
    top["txt_partido"] = top["partido"] + " | " + top["taxa_sucesso"].astype(str) + "%"

    fig = px.bar(
        top,
        x="valor_milhao",
        y="label",
        orientation="h",
        color="taxa_sucesso",
        color_continuous_scale=ESCALA_EFICIENCIA,
        text="txt_partido",
        hover_data={
            "valor_milhao": ":.2f",
            "taxa_sucesso": ":.1f",
            "municipios": True,
            "objetos": True,
            "total_planos": True,
            "negados": True,
        },
        labels={
            "valor_milhao": "Valor Total (R$ milhões)",
            "taxa_sucesso": "Taxa de Sucesso (%)",
            "label": "Parlamentar",
        },
        title="🏅 Top 30 Parlamentares por Valor — Cor = Taxa de Sucesso",
    )

    fig.update_traces(
        texttemplate="%{text}",
        textposition="outside",
        textfont=dict(size=9),
        hovertemplate="<b>%{y}</b><br>"
                      + "Valor: R$ %{customdata[0]:,.2f} milhões<br>"
                      + "Sucesso: %{customdata[1]:.1f}%<br>"
                      + "Municípios: %{customdata[2]}<br>"
                      + "Objetos: %{customdata[3]}<br>"
                      + "Planos: %{customdata[4]}<br>"
                      + "Negados: %{customdata[5]}<extra></extra>",
    )
    # Pass customdata
    top["customdata"] = top[["valor_milhao", "taxa_sucesso", "municipios",
                              "objetos", "total_planos", "negados"]].values.tolist()
    fig.update_traces(customdata=top["customdata"])

    fig = estilo_fig(fig, height=700)
    fig.update_layout(margin=dict(l=200, r=180), coloraxis_colorbar=dict(
        title="Sucesso %", tickfont=dict(color=TEMA["text_muted"])
    ))
    fig.update_xaxes(showgrid=True, gridcolor="#334155")
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 3 — Mapa de Calor: Parlamentar × Região
# ═══════════════════════════════════════════════════════════════════════

def grafico_parlamentar_regiao(df):
    """
    Heatmap: Top 25 deputados (por valor) × Regiões do Brasil.
    Revela padrões regionais de atuação — quem concentra em quais regiões.
    """
    top_parl = df.groupby("parlamentar_nome")["valor"].sum().nlargest(25).index
    df_filt = df[df["parlamentar_nome"].isin(top_parl)].copy()
    df_filt["parlamentar_nome"] = df_filt["parlamentar_nome"].str.title()

    pivot = df_filt.pivot_table(
        index="parlamentar_nome", columns="regiao",
        values="valor", aggfunc="sum", fill_value=0
    )

    # Ordem desejada das regiões
    ordem_regioes = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Sem região"]
    for r in ordem_regioes:
        if r not in pivot.columns:
            pivot[r] = 0
    pivot = pivot[[c for c in ordem_regioes if c in pivot.columns]]

    # Ordenar por valor total
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False).drop(columns="total")

    # Converter para milhões para legibilidade
    pivot_milhoes = pivot / 1_000_000

    fig = px.imshow(
        pivot_milhoes,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale="YlOrRd",
        labels=dict(x="Região", y="Parlamentar", color="R$ milhões"),
        title="🗺️ Mapa de Calor — Parlamentar vs Região (R$ milhões)",
    )

    fig = estilo_fig(fig, height=650)
    fig.update_layout(
        xaxis=dict(side="top", tickfont=dict(size=12)),
        yaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=180, r=30),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 4 — Comparativo Partidário
# ═══════════════════════════════════════════════════════════════════════

def grafico_partidos(df):
    """
    Gráfico combinado: por partido — valor total (barras) + taxa de sucesso (linha)
    + municípios por deputado (bolhas).
    """
    df = df.sort_values("valor_total", ascending=False).head(15).copy()
    df["valor_milhao"] = df["valor_total"] / 1_000_000
    df["label_partido"] = df["partido"] + " (" + df["deputados"].astype(str) + " dep.)"
    df["municipios_por_dep"] = (df["municipios"] / df["deputados"]).round(0)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Barras: valor total
    fig.add_trace(
        go.Bar(
            x=df["label_partido"],
            y=df["valor_milhao"],
            name="Valor Total (R$ milhões)",
            marker_color="#3b82f6",
            opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Valor: R$ %{y:.1f}M<extra></extra>",
        ),
        secondary_y=False,
    )

    # Linha: taxa de sucesso média
    fig.add_trace(
        go.Scatter(
            x=df["label_partido"],
            y=df["taxa_sucesso_media"],
            name="Taxa de Sucesso Média (%)",
            marker=dict(color="#2ecc71", size=10),
            line=dict(color="#2ecc71", width=3),
            mode="lines+markers",
            hovertemplate="<b>%{x}</b><br>Sucesso: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="🏛️ Comparativo Partidário — Valor vs Eficiência",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(tickangle=45)
    fig.update_yaxes(title_text="Valor Total (R$ milhões)", secondary_y=False)
    fig.update_yaxes(title_text="Taxa de Sucesso Média (%)", secondary_y=True,
                      range=[80, 100])

    fig = estilo_fig(fig, height=500)
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 5 — Concentração vs Capilaridade
# ═══════════════════════════════════════════════════════════════════════

def grafico_concentracao(df):
    """
    Scatter: nº de municípios vs valor médio por município.
    Mostra quem concentra recursos em poucos municípios (alta intensidade)
    vs quem espalha por muitos (capilaridade).
    """
    df = df[df["total_planos"] >= 3].copy()
    df["label"] = df["parlamentar_nome"].str.title()
    df["valor_milhao_por_mun"] = df["valor_por_municipio"] / 1_000_000

    fig = px.scatter(
        df,
        x="municipios",
        y="valor_milhao_por_mun",
        size="total_planos",
        color="taxa_sucesso",
        color_continuous_scale=ESCALA_EFICIENCIA,
        hover_name="parlamentar_nome",
        hover_data={
            "municipios": True,
            "valor_milhao_por_mun": ":.2f",
            "taxa_sucesso": ":.1f",
            "total_planos": True,
            "partido": True,
        },
        labels={
            "municipios": "Número de Municípios Atendidos",
            "valor_milhao_por_mun": "Valor Médio por Município (R$ milhões)",
            "taxa_sucesso": "Taxa de Sucesso (%)",
            "total_planos": "Total de Planos",
        },
        title="🌐 Concentração vs Capilaridade — Estratégia de Alocação",
        size_max=35,
        opacity=0.8,
    )

    fig.update_traces(marker=dict(line=dict(width=1, color="white")))
    fig = estilo_fig(fig, height=550)

    # Anotações explicativas
    x_max = df["municipios"].max()
    y_max = df["valor_milhao_por_mun"].max()
    fig.add_annotation(x=x_max * 0.8, y=y_max * 0.95,
                       text="🔵 Capilaridade: muitos municípios, baixo valor por município",
                       showarrow=False, font=dict(color="#3498db", size=9))
    fig.add_annotation(x=x_max * 0.15, y=y_max * 0.95,
                       text="🔴 Concentração: poucos municípios, alto valor por município",
                       showarrow=False, font=dict(color="#e74c3c", size=9))

    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 6 — Matriz Parlamentar × Objeto de Execução
# ═══════════════════════════════════════════════════════════════════════

def grafico_parlamentar_objeto(df):
    """
    Heatmap: Top 20 deputados × Top 15 objetos.
    Revela especialização temática — quem investe em quê.
    """
    top_parl = df.groupby("parlamentar_nome")["valor"].sum().nlargest(20).index
    top_obj = df.groupby("objeto_descricao")["valor"].sum().nlargest(15).index

    df_filt = df[
        df["parlamentar_nome"].isin(top_parl) &
        df["objeto_descricao"].isin(top_obj)
    ].copy()
    df_filt["parlamentar_nome"] = df_filt["parlamentar_nome"].str.title()

    pivot = df_filt.pivot_table(
        index="parlamentar_nome", columns="objeto_descricao",
        values="valor", aggfunc="sum", fill_value=0
    ) / 1_000_000

    # Abreviar nomes dos objetos
    pivot.columns = [c.split(" - ")[0] + " - " + c.split(" - ")[1][:25]
                     if " - " in c else c[:30] for c in pivot.columns]

    fig = px.imshow(
        pivot,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="Viridis",
        labels=dict(x="Objeto de Execução", y="Parlamentar", color="R$ milhões"),
        title="🎯 Matriz de Especialização — Parlamentar vs Objeto (R$ milhões)",
    )

    fig = estilo_fig(fig, height=650)
    fig.update_layout(
        xaxis=dict(side="top", tickfont=dict(size=8), tickangle=45),
        yaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=180, r=30, b=200),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 7 — Taxa de Impedimento — Top 20
# ═══════════════════════════════════════════════════════════════════════

def grafico_impedimento(df):
    """
    Barras horizontais: Top 20 deputados com MAIOR taxa de impedimento.
    Mostra quem está tendo planos barrados — dividido entre impedimento
    técnico e rejeição do plano de trabalho.
    """
    top = df.head(20).copy()
    top = top.sort_values("taxa_impedimento", ascending=True)
    top["label"] = top["parlamentar_nome"].str.title()
    top["pct_tecnico"] = (top["impedido_tecnico"] / top["total_planos"] * 100).round(1)
    top["pct_rejeicao"] = (top["impedido_rejeicao"] / top["total_planos"] * 100).round(1)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=top["label"],
        x=top["pct_tecnico"],
        name="Impedido Técnico",
        orientation="h",
        marker_color="#e74c3c",
        hovertemplate="<b>%{y}</b><br>Impedido Técnico: %{x:.1f}%<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        y=top["label"],
        x=top["pct_rejeicao"],
        name="Rejeição Plano de Trabalho",
        orientation="h",
        marker_color="#e67e22",
        hovertemplate="<b>%{y}</b><br>Rejeição: %{x:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title="🚫 Top 20 — Taxa de Impedimento por Parlamentar",
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="% dos Planos Impedidos"),
    )

    fig = estilo_fig(fig, height=600)
    fig.update_layout(margin=dict(l=200, r=60))
    fig.update_xaxes(range=[0, 105])
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 8 — Distribuição Regional com Situação (100% Stacked)
# ═══════════════════════════════════════════════════════════════════════

def grafico_regiao_situacao(df):
    """
    Barras empilhadas 100%: por região, proporção de cada situação.
    Mostra onde os planos são mais barrados vs aprovados.
    """
    # Agrupar situações em categorias
    df["categoria"] = df["plano_acao_situacao"].map({
        "CIENTE": "✅ Ciente / Aprovado",
        "APROVADO": "✅ Ciente / Aprovado",
        "EM_EXECUCAO": "✅ Ciente / Aprovado",
        "CONCLUIDO": "✅ Ciente / Aprovado",
        "IMPEDIDO": "🚫 Impedido",
        "IMPEDIDO_REJEICAO_PLANO_TRABALHO": "🚫 Impedido",
        "REPROVADO": "🚫 Impedido",
        "CANCELADO": "❌ Cancelado",
        "NAO_CUMPROU": "❌ Cancelado",
    }).fillna("Outros")

    df_agg = df.groupby(["regiao", "categoria"]).agg(
        planos=("planos", "sum"),
        valor=("valor", "sum"),
    ).reset_index()

    # Calcular percentual dentro de cada região
    df_agg["pct"] = df_agg.groupby("regiao")["planos"].transform(
        lambda x: x / x.sum() * 100
    )

    cores_cat = {
        "✅ Ciente / Aprovado": "#2ecc71",
        "🚫 Impedido": "#e74c3c",
        "❌ Cancelado": "#95a5a6",
        "Outros": "#3498db",
    }

    ordem_regioes = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Sem região"]
    df_agg["regiao"] = pd.Categorical(df_agg["regiao"], categories=ordem_regioes, ordered=True)
    df_agg = df_agg.dropna(subset=["regiao"]).sort_values("regiao")

    fig = px.bar(
        df_agg,
        x="regiao",
        y="pct",
        color="categoria",
        color_discrete_map=cores_cat,
        text="pct",
        hover_data={"planos": ":,", "valor": ":.2f"},
        labels={
            "regiao": "Região",
            "pct": "Percentual (%)",
            "categoria": "Situação",
            "planos": "Planos",
            "valor": "Valor (R$)",
        },
        title="📊 Distribuição Regional — Proporção por Situação",
    )

    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="inside",
        textfont=dict(size=10, color="white"),
    )
    fig = estilo_fig(fig, height=450)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 9 — Radar de Competência — Top 10 Parlamentares
# ═══════════════════════════════════════════════════════════════════════

def grafico_radar_competencia(df):
    """
    Radar chart: compara Top 10 deputados em 5 dimensões normalizadas:
    - Valor Total, Municípios, Objetos, Taxa de Sucesso, Valor/Município
    """
    top = df.head(10).copy()
    top["nome_curto"] = top["parlamentar_nome"].str.title().str.split().str[0]

    # Dimensões para o radar
    dimensoes = ["valor_total", "municipios", "objetos", "taxa_sucesso", "valor_por_municipio"]
    rotulos = ["Valor Total", "Municípios", "Objetos", "Taxa Sucesso", "Valor/Município"]

    # Normalização min-max para cada dimensão
    df_norm = top[dimensoes].copy()
    for col in dimensoes:
        mn, mx = df_norm[col].min(), df_norm[col].max()
        if mx > mn:
            df_norm[col] = (df_norm[col] - mn) / (mx - mn) * 100
        else:
            df_norm[col] = 50

    fig = go.Figure()

    for i, (_, row) in enumerate(top.iterrows()):
        valores = df_norm.iloc[i].tolist()
        valores += valores[:1]  # fechar o polígono

        fig.add_trace(go.Scatterpolar(
            r=valores,
            theta=rotulos + [rotulos[0]],
            name=top["parlamentar_nome"].str.title().iloc[i],
            line=dict(width=2),
            opacity=0.8,
            fill="toself",
            fillcolor=f"rgba({(i*50)%255}, {(i*80+100)%255}, {(i*120+50)%255}, 0.1)",
        ))

    fig.update_layout(
        title="🏆 Radar de Competência — Top 10 Parlamentares (normalizado)",
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(color=TEMA["text_muted"]),
                gridcolor="#334155",
            ),
            bgcolor=TEMA["card"],
            angularaxis=dict(
                tickfont=dict(color=TEMA["text"], size=11),
                gridcolor="#334155",
            ),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            font=dict(size=9),
        ),
    )

    fig = estilo_fig(fig, height=600)
    fig.update_layout(margin=dict(l=80, r=80, t=60, b=120))
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# GRÁFICO 10 — Treemap: Objetos de Execução por Região
# ═══════════════════════════════════════════════════════════════════════

def grafico_objeto_treemap(df):
    """
    Treemap hierárquico: Região → Objeto → Valor.
    Cor = taxa de sucesso (verde=alta, vermelha=baixa).
    Tamanho = valor total.
    """
    # Pegar top objetos por região
    df_top = df.groupby(["regiao", "objeto_descricao"]).agg(
        valor=("valor", "sum"),
        planos=("planos", "sum"),
        taxa_sucesso=("taxa_sucesso", "mean"),
    ).reset_index()

    # Limitar para visualização
    df_top = df_top.sort_values("valor", ascending=False).head(80)

    # Abreviar nomes
    df_top["objeto_curto"] = df_top["objeto_descricao"].apply(
        lambda x: x[:45] + "..." if len(x) > 45 else x
    )

    fig = px.treemap(
        df_top,
        path=["regiao", "objeto_curto"],
        values="valor",
        color="taxa_sucesso",
        color_continuous_scale=ESCALA_EFICIENCIA,
        color_continuous_midpoint=95,
        hover_data={
            "valor": ":.2f",
            "planos": True,
            "taxa_sucesso": ":.1f",
        },
        labels={
            "regiao": "Região",
            "objeto_curto": "Objeto",
            "valor": "Valor (R$)",
            "taxa_sucesso": "Sucesso (%)",
        },
        title="📦 Mapa de Áreas — Objetos de Execução por Região (tamanho = valor, cor = sucesso)",
    )

    fig.update_traces(
        textinfo="label+value+percent root",
        texttemplate="<b>%{label}</b><br>R$ %{value:,.0f}",
        hovertemplate="<b>%{label}</b><br>"
                      + "Valor: R$ %{value:,.2f}<br>"
                      + "Planos: %{customdata[0]}<br>"
                      + "Sucesso: %{customdata[1]:.1f}%<extra></extra>",
    )

    # Preparar customdata
    df_top["customdata"] = df_top[["planos", "taxa_sucesso"]].values.tolist()
    fig.update_traces(customdata=df_top["customdata"])

    fig = estilo_fig(fig, height=650)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ═══════════════════════════════════════════════════════════════════════
# HTML TEMPLATE
# ═══════════════════════════════════════════════════════════════════════

def gerar_html(data_str, cards, *charts):
    nomes_charts = [
        "eficiencia_vs_volume",
        "top_parlamentares",
        "parlamentar_regiao",
        "partidos",
        "concentracao",
        "parlamentar_objeto",
        "impedimento",
        "regiao_situacao",
        "radar_competencia",
        "objeto_treemap",
    ]

    secoes = []
    descricoes = [
        ("🎯 Eficiência vs Volume", "Cada bolha é um deputado. O eixo X mostra a taxa de sucesso dos planos; o Y, o valor total gerido. "
         "O tamanho da bolha indica quantos municípios foram atendidos. O quadrante superior direito revela os parlamentares "
         "que combinam alta entrega com alta eficiência — o verdadeiro 'quadrante de ouro'."),

        ("🏅 Top 30 por Valor com Eficiência", "Os maiores gestores de recursos, ordenados por valor total. "
         "A cor de cada barra reflete a taxa de sucesso: verde = alta eficiência, vermelho = muitos planos barrados. "
         "O rótulo mostra partido e taxa de sucesso."),

        ("🗺️ Mapa de Calor — Parlamentar vs Região", "Onde cada deputado está alocando recursos? Este heatmap revela padrões regionais: "
         "há deputados que concentram investimentos em sua própria região (forte correlação geográfica) e outros que distribuem "
         "recursos pelo país."),

        ("🏛️ Comparativo Partidário", "Desempenho coletivo por partido. As barras mostram o valor total gerido; a linha verde, "
         "a taxa de sucesso média dos deputados da legenda. Revela quais partidos são mais eficientes na gestão das emendas."),

        ("🌐 Concentração vs Capilaridade", "Estratégia de alocação: deputados que concentram recursos em poucos municípios "
         "(alto valor por município, canto superior esquerdo) vs. quem espalha por muitos municípios (capilaridade, "
         "canto inferior direito). A cor indica a taxa de sucesso."),

        ("🎯 Matriz de Especialização", "Quais tipos de objeto cada deputado prioriza? Este heatmap cruzado mostra a "
         "especialização temática — pavimentação, saúde, educação, infraestrutura hídrica, etc. Deputados com atuação "
         "diversificada vs. especialistas setoriais."),

        ("🚫 Taxa de Impedimento", "Quem está tendo planos barrados? O gráfico mostra os 20 deputados com maior "
         "percentual de planos impedidos, divididos entre impedimento técnico (vermelho) e rejeição do plano de trabalho "
         "(laranja). Um indicador crítico de competência na elaboração dos projetos."),

        ("📊 Distribuição Regional — Situação", "Proporção de planos por situação em cada região do Brasil. "
         "Revela disparidades regionais na aprovação dos planos — onde os projetos são mais bem elaborados "
         "e onde enfrentam mais barreiras técnicas."),

        ("🏆 Radar de Competência", "Perfil multidimensional dos 10 maiores deputados. Cinco métricas normalizadas: "
         "Valor Total, Municípios Atendidos, Diversidade de Objetos, Taxa de Sucesso e Valor por Município. "
         "Quanto mais larga a estrela, mais completo o perfil do parlamentar."),

        ("📦 Mapa de Áreas — Objetos por Região", "Visão hierárquica: Região → Objeto de Execução. O tamanho de cada "
         "retângulo reflete o valor investido; a cor, a taxa de sucesso. Uma radiografia completa de para onde "
         "o dinheiro das emendas está indo e com que eficiência."),
    ]

    for i, (chart_html, (titulo, descricao)) in enumerate(zip(charts, descricoes)):
        secoes.append(f"""
    <div class="section">
        <div class="section-header">
            <h2>Gráfico {i+1}: {titulo}</h2>
            <p class="section-desc">{descricao}</p>
        </div>
        <div class="chart-box">{chart_html}</div>
    </div>
        """)

    secoes_html = "\n".join(secoes)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TransfereGov — Dashboard de Competência Parlamentar 2026</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

        /* Header */
        .hero {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 32px;
            border: 1px solid #1e293b;
            position: relative;
            overflow: hidden;
        }}
        .hero::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -20%;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%);
            border-radius: 50%;
        }}
        .hero h1 {{
            font-size: 32px;
            font-weight: 700;
            color: #f8fafc;
            margin-bottom: 8px;
            position: relative;
        }}
        .hero .subtitle {{
            color: #64748b;
            font-size: 15px;
            position: relative;
        }}
        .hero .badge {{
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
        }}

        /* Cards de resumo */
        .cards-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid #1e293b;
            transition: border-color 0.2s;
        }}
        .card:hover {{ border-color: #3b82f6; }}
        .card .card-icon {{ font-size: 24px; margin-bottom: 8px; }}
        .card .card-num {{
            font-size: 22px;
            font-weight: 700;
            color: #f8fafc;
        }}
        .card .card-label {{
            font-size: 12px;
            color: #64748b;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Seções de gráfico */
        .section {{
            margin-bottom: 32px;
        }}
        .section-header {{
            margin-bottom: 12px;
        }}
        .section-header h2 {{
            font-size: 20px;
            color: #f8fafc;
            font-weight: 600;
        }}
        .section-desc {{
            color: #64748b;
            font-size: 13px;
            line-height: 1.5;
            margin-top: 4px;
            max-width: 900px;
        }}

        .chart-box {{
            background: #1e293b;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #1e293b;
        }}

        /* Navegação rápida */
        .nav-index {{
            background: #1e293b;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 32px;
            border: 1px solid #1e293b;
        }}
        .nav-index h3 {{
            font-size: 14px;
            color: #94a3b8;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .nav-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 8px;
        }}
        .nav-item {{
            color: #94a3b8;
            text-decoration: none;
            font-size: 13px;
            padding: 6px 10px;
            border-radius: 6px;
            transition: all 0.2s;
            cursor: pointer;
        }}
        .nav-item:hover {{
            background: #0f172a;
            color: #f8fafc;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            color: #475569;
            font-size: 12px;
            margin-top: 48px;
            padding: 24px;
            border-top: 1px solid #1e293b;
        }}

        /* Modo escuro para plotly */
        .js-plotly-plot .plotly .modebar {{ display: none !important; }}

        @media (max-width: 768px) {{
            .container {{ padding: 12px; }}
            .hero {{ padding: 24px; }}
            .hero h1 {{ font-size: 24px; }}
            .cards-row {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- Hero -->
    <div class="hero">
        <h1>🏛️ Competência e Eficiência dos Parlamentares</h1>
        <p class="subtitle">
            Transferências Especiais (Emendas Pix) — Programa 09032026 (programaId=25)
            — Dados extraídos da API pública em {data_str}
        </p>
        <span class="badge">📊 10 gráficos • {cards.split()[1] if len(cards.split()) > 1 else ''} planos • {cards.split()[3] if len(cards.split()) > 3 else ''} parlamentares</span>
    </div>

    <!-- Cards de resumo -->
    {cards}

    <!-- Índice de navegação -->
    <div class="nav-index">
        <h3>📋 Navegação Rápida</h3>
        <div class="nav-grid">
            <a class="nav-item" href="#g1">1. Eficiência vs Volume</a>
            <a class="nav-item" href="#g2">2. Top 30 por Valor</a>
            <a class="nav-item" href="#g3">3. Parlamentar vs Região</a>
            <a class="nav-item" href="#g4">4. Comparativo Partidário</a>
            <a class="nav-item" href="#g5">5. Concentração vs Capilaridade</a>
            <a class="nav-item" href="#g6">6. Matriz de Especialização</a>
            <a class="nav-item" href="#g7">7. Taxa de Impedimento</a>
            <a class="nav-item" href="#g8">8. Distribuição Regional</a>
            <a class="nav-item" href="#g9">9. Radar de Competência</a>
            <a class="nav-item" href="#g10">10. Mapa de Áreas</a>
        </div>
    </div>

    <!-- Gráficos -->
    {secoes_html}

    <!-- Footer -->
    <div class="footer">
        Gerado automaticamente por TransfereGov — Dashboard de Competência Parlamentar<br>
        Dados públicos do Governo Federal • {data_str}
    </div>

</div>

<script>
    // Smooth scroll para navegação
    document.querySelectorAll('.nav-item').forEach(item => {{
        item.addEventListener('click', function(e) {{
            e.preventDefault();
            const id = this.getAttribute('href').substring(1);
            const el = document.getElementById(id);
            if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }});
    }});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Dashboard de Competência e Eficiência dos Parlamentares"
    )
    parser.add_argument(
        "--output", default="output/dashboard_deputados.html",
        help="Caminho do arquivo HTML de saída"
    )
    args = parser.parse_args()

    print("🔌 Conectando ao banco...")
    conn = get_connection()

    print("📥 Carregando dados...")
    resumo = query_df(conn, SQL_RESUMO)
    df_eficiencia = query_df(conn, SQL_EFICIENCIA_PARLAMENTAR)
    df_par_regiao = query_df(conn, SQL_PARLAMENTAR_REGIAO)
    df_partidos = query_df(conn, SQL_PARTIDO_EFICIENCIA)
    df_par_objeto = query_df(conn, SQL_PARLAMENTAR_OBJETO)
    df_impedimento = query_df(conn, SQL_IMPEDIMENTO)
    df_regiao_sit = query_df(conn, SQL_REGIAO_SITUACAO)
    df_objeto_tree = query_df(conn, SQL_OBJETO_TREEMAP)
    conn.close()

    print(f"📊 Dados carregados: {len(df_eficiencia)} parlamentares, "
          f"{len(df_partidos)} partidos, {len(df_par_objeto)} vínculos parl-objeto")

    print("🎨 Gerando 10 gráficos...")
    import time
    data_str = time.strftime("%d/%m/%Y %H:%M")

    # Cards de resumo
    r = resumo.iloc[0]
    cards = f"""
    <div class="cards-row">
        <div class="card">
            <div class="card-icon">📋</div>
            <div class="card-num">{fmt_num(r['total_planos'])}</div>
            <div class="card-label">Planos de Ação</div>
        </div>
        <div class="card">
            <div class="card-icon">💰</div>
            <div class="card-num">{fmt_brl(r['valor_total'])}</div>
            <div class="card-label">Valor Total</div>
        </div>
        <div class="card">
            <div class="card-icon">👤</div>
            <div class="card-num">{fmt_num(r['total_parlamentares'])}</div>
            <div class="card-label">Parlamentares</div>
        </div>
        <div class="card">
            <div class="card-icon">🏘️</div>
            <div class="card-num">{fmt_num(r['total_municipios'])}</div>
            <div class="card-label">Municípios</div>
        </div>
        <div class="card">
            <div class="card-icon">🏗️</div>
            <div class="card-num">{fmt_num(r['total_objetos'])}</div>
            <div class="card-label">Objetos</div>
        </div>
    </div>
    """

    print("  [1/10] Eficiência vs Volume...")
    g1 = grafico_eficiencia_vs_volume(df_eficiencia)

    print("  [2/10] Top 30 Parlamentares...")
    g2 = grafico_top_parlamentares(df_eficiencia)

    print("  [3/10] Parlamentar vs Região...")
    g3 = grafico_parlamentar_regiao(df_par_regiao)

    print("  [4/10] Comparativo Partidário...")
    g4 = grafico_partidos(df_partidos)

    print("  [5/10] Concentração vs Capilaridade...")
    g5 = grafico_concentracao(df_eficiencia)

    print("  [6/10] Matriz Parlamentar × Objeto...")
    g6 = grafico_parlamentar_objeto(df_par_objeto)

    print("  [7/10] Taxa de Impedimento...")
    g7 = grafico_impedimento(df_impedimento)

    print("  [8/10] Distribuição Regional...")
    g8 = grafico_regiao_situacao(df_regiao_sit)

    print("  [9/10] Radar de Competência...")
    g9 = grafico_radar_competencia(df_eficiencia)

    print("  [10/10] Mapa de Áreas...")
    g10 = grafico_objeto_treemap(df_objeto_tree)

    print("📝 Montando HTML...")
    html = gerar_html(data_str, cards, g1, g2, g3, g4, g5, g6, g7, g8, g9, g10)

    # Injetar IDs de âncora nas seções
    for i in range(1, 11):
        html = html.replace(
            f'<div class="section">',
            f'<div class="section" id="g{i}">', 1
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Dashboard salvo: {output_path.resolve()}")
    print(f"📊 {fmt_num(r['total_planos'])} planos • "
          f"{fmt_num(r['total_parlamentares'])} parlamentares • "
          f"{fmt_brl(r['valor_total'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
