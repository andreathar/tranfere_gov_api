#!/usr/bin/env python3
"""
TransfereGov — Dashboard Interativo de Visualizações.

Gera um relatório HTML com gráficos Plotly interativos:
  - Visão geral do programa
  - Por Finalidade da Política Pública
  - Por Objeto de Execução
  - Por Estado (UF)
  - Por Parlamentar
  - Situação dos Planos

Uso: python3 src/dashboard.py [--output output/dashboard.html]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import psycopg2

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER

# ── Cores do tema ──────────────────────────────────────────────────────
CORES = {
    "CIENTE": "#3498db",
    "IMPEDIDO": "#e74c3c",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO": "#e67e22",
    "REPROVADO": "#9b59b6",
    "CANCELADO": "#95a5a6",
    "EM_EXECUCAO": "#2ecc71",
    "CONCLUIDO": "#1abc9c",
    "NAO_CUMPROU": "#34495e",
}

CORES_CATEGORIA = {
    "positiva": "#2ecc71",
    "negada": "#e74c3c",
    "neutra": "#3498db",
}


def get_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )


def query_df(conn, sql):
    return pd.read_sql(sql, conn)


def fmt_brl(valor):
    """Formata valor em R$ brasileiro."""
    if pd.isna(valor):
        return "R$ 0"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_num(valor):
    if pd.isna(valor):
        return "0"
    return f"{int(valor):,}".replace(",", ".")


# ── Queries ────────────────────────────────────────────────────────────

SQL_RESUMO = """
SELECT
    COUNT(*) AS total_planos,
    COUNT(DISTINCT parlamentar_nome) AS total_parlamentares,
    COUNT(DISTINCT beneficiario_id) AS total_municipios,
    COUNT(DISTINCT objeto_id) AS total_objetos,
    SUM(valor_total) AS valor_total
FROM planos_acao
"""

SQL_POR_SITUACAO = """
SELECT
    plano_acao_situacao,
    COUNT(*) AS qtd,
    SUM(valor_total) AS valor
FROM planos_acao
GROUP BY plano_acao_situacao
ORDER BY qtd DESC
"""

SQL_POR_ESTADO = """
SELECT
    b.uf,
    pa.plano_acao_situacao,
    COUNT(*) AS qtd,
    SUM(pa.valor_total) AS valor
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE b.uf IS NOT NULL
GROUP BY b.uf, pa.plano_acao_situacao
ORDER BY b.uf
"""

SQL_POR_POLITICA = """
SELECT
    politicas_publicas,
    COUNT(*) AS qtd,
    SUM(valor_total) AS valor,
    COUNT(DISTINCT parlamentar_nome) AS parlamentares,
    COUNT(DISTINCT beneficiario_id) AS municipios
FROM planos_acao
WHERE politicas_publicas IS NOT NULL AND politicas_publicas != ''
GROUP BY politicas_publicas
ORDER BY valor DESC
"""

SQL_POR_OBJETO = """
SELECT
    o.objeto_id,
    LEFT(o.descricao, 60) AS descricao_curta,
    pa.plano_acao_situacao,
    COUNT(*) AS qtd,
    SUM(pa.valor_total) AS valor,
    COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares
FROM planos_acao pa
JOIN objetos o ON pa.objeto_id = o.objeto_id
GROUP BY o.objeto_id, descricao_curta, pa.plano_acao_situacao
ORDER BY valor DESC
"""

SQL_POR_PARLAMENTAR = """
SELECT
    parlamentar_nome,
    plano_acao_situacao,
    COUNT(*) AS planos,
    SUM(valor_total) AS valor,
    COUNT(DISTINCT beneficiario_id) AS municipios
FROM planos_acao
WHERE parlamentar_nome IS NOT NULL AND parlamentar_nome != ''
GROUP BY parlamentar_nome, plano_acao_situacao
ORDER BY valor DESC
"""

SQL_POR_PARLAMENTAR_ESTADO = """
SELECT
    pa.parlamentar_nome,
    b.uf,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_nome IS NOT NULL AND pa.parlamentar_nome != '' AND b.uf IS NOT NULL
GROUP BY pa.parlamentar_nome, b.uf
ORDER BY valor DESC
"""


# ── Gráficos ───────────────────────────────────────────────────────────

def grafico_resumo(resumo):
    """Cards de resumo no topo."""
    r = resumo.iloc[0]
    cards = f"""
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin:20px 0">
      <div class="card"><div class="card-num">{fmt_num(r['total_planos'])}</div><div class="card-label">Planos de Ação</div></div>
      <div class="card"><div class="card-num">{fmt_brl(r['valor_total'])}</div><div class="card-label">Valor Total</div></div>
      <div class="card"><div class="card-num">{fmt_num(r['total_parlamentares'])}</div><div class="card-label">Parlamentares</div></div>
      <div class="card"><div class="card-num">{fmt_num(r['total_municipios'])}</div><div class="card-label">Municípios</div></div>
      <div class="card"><div class="card-num">{fmt_num(r['total_objetos'])}</div><div class="card-label">Objetos</div></div>
    </div>
    """
    return cards


def grafico_situacao(df):
    """Pizza de situações."""
    fig = px.pie(
        df, values="qtd", names="plano_acao_situacao",
        title="Distribuição por Situação",
        color="plano_acao_situacao",
        color_discrete_map=CORES,
        hole=0.4,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label+value",
                       texttemplate="%{label}<br>%{percent}<br>%{value:,.0f}")
    fig.update_layout(height=400, showlegend=False)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_politica(df):
    """Barras horizontais por finalidade da política pública."""
    df_top = df.head(15).copy()
    df_top["label"] = df_top["politicas_publicas"].str[:50]
    df_top["valor_milhao"] = df_top["valor"] / 1_000_000

    fig = px.bar(
        df_top.sort_values("valor_milhao", ascending=True),
        x="valor_milhao", y="label",
        orientation="h",
        title="Top 15 Finalidades da Política Pública (R$ milhões)",
        text="qtd",
        hover_data={"qtd": ":,", "municipios": True, "parlamentares": True},
        labels={"valor_milhao": "Valor (R$ milhões)", "qtd": "Planos", "municipios": "Municípios", "parlamentares": "Parlamentares"},
    )
    fig.update_traces(texttemplate="%{text} planos", textposition="outside")
    fig.update_layout(height=550, margin=dict(l=300))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_politica_treemap(df):
    """Treemap por política pública."""
    df_top = df.head(20).copy()
    fig = px.treemap(
        df_top,
        path=["politicas_publicas"],
        values="valor",
        color="qtd",
        hover_data={"qtd": ":,", "valor": ":.2f"},
        title="Mapa de Áreas — Finalidade da Política Pública",
        color_continuous_scale="Blues",
    )
    fig.update_layout(height=500)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_objeto(df):
    """Barras por objeto de execução."""
    # Agregar por objeto (soma de todas as situações)
    df_agg = df.groupby("objeto_id").agg(
        descricao=("descricao_curta", "first"),
        qtd=("qtd", "sum"),
        valor=("valor", "sum"),
        parlamentares=("parlamentares", "max"),
    ).reset_index().sort_values("valor", ascending=False).head(20)

    df_agg["valor_milhao"] = df_agg["valor"] / 1_000_000

    fig = px.bar(
        df_agg.sort_values("valor_milhao", ascending=True),
        x="valor_milhao", y="descricao",
        orientation="h",
        title="Top 20 Objetos de Execução (R$ milhões)",
        text="qtd",
        hover_data={"qtd": ":,", "parlamentares": True},
        labels={"valor_milhao": "Valor (R$ milhões)", "qtd": "Planos", "parlamentares": "Parlamentares"},
    )
    fig.update_traces(texttemplate="%{text} planos", textposition="outside")
    fig.update_layout(height=600, margin=dict(l=350))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_objeto_situacao(df):
    """Stacked bar por objeto + situação."""
    df_top_objs = df.groupby("objeto_id")["valor"].sum().nlargest(10).index
    df_filtered = df[df["objeto_id"].isin(df_top_objs)].copy()

    fig = px.bar(
        df_filtered,
        x="descricao_curta", y="valor",
        color="plano_acao_situacao",
        title="Top 10 Objetos por Situação (R$)",
        color_discrete_map=CORES,
        hover_data={"qtd": ":,"},
        labels={"valor": "Valor Total", "qtd": "Planos"},
    )
    fig.update_layout(height=500, xaxis_tickangle=45, margin=dict(b=150))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_estado(df):
    """Barras empilhadas por estado + situação."""
    df_agg = df.groupby(["uf", "plano_acao_situacao"]).agg(qtd=("qtd", "sum"), valor=("valor", "sum")).reset_index()

    fig = px.bar(
        df_agg,
        x="uf", y="qtd",
        color="plano_acao_situacao",
        title="Planos por Estado e Situação",
        color_discrete_map=CORES,
        hover_data={"valor": ":.2f", "qtd": ":,"},
        labels={"qtd": "Quantidade", "valor": "Valor Total", "uf": "UF"},
    )
    fig.update_layout(height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_estado_valor(df):
    """Barras de valor por estado."""
    df_agg = df.groupby("uf").agg(valor=("valor", "sum"), qtd=("qtd", "sum")).reset_index()
    df_agg = df_agg.sort_values("valor", ascending=False)
    df_agg["valor_milhao"] = df_agg["valor"] / 1_000_000

    fig = px.bar(
        df_agg, x="uf", y="valor_milhao",
        title="Valor Total por Estado (R$ milhões)",
        text="qtd",
        hover_data={"qtd": ":,", "valor": ":.2f"},
        labels={"valor_milhao": "Valor (R$ milhões)", "qtd": "Planos"},
        color_discrete_sequence=["#3498db"],
    )
    fig.update_traces(texttemplate="%{text} planos", textposition="outside")
    fig.update_layout(height=450)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_parlamentar(df, top_n=20):
    """Top parlamentares por valor (agregado)."""
    df_agg = df.groupby("parlamentar_nome").agg(
        planos=("planos", "sum"), valor=("valor", "sum"), municipios=("municipios", "sum")
    ).reset_index().nlargest(top_n, "valor")

    df_agg["valor_milhao"] = df_agg["valor"] / 1_000_000

    fig = px.bar(
        df_agg.sort_values("valor_milhao", ascending=True),
        x="valor_milhao", y="parlamentar_nome",
        orientation="h",
        title=f"Top {top_n} Parlamentares por Valor (R$ milhões)",
        text="planos",
        hover_data={"planos": ":,", "municipios": True},
        labels={"valor_milhao": "Valor (R$ milhões)", "planos": "Planos", "municipios": "Municípios"},
        color_discrete_sequence=["#e74c3c"],
    )
    fig.update_traces(texttemplate="%{text} planos", textposition="outside")
    fig.update_layout(height=max(400, top_n * 28), margin=dict(l=200))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def grafico_parlamentar_heatmap(df_estados, top_n=20):
    """Heatmap parlamentares × estados."""
    top_p = df_estados.groupby("parlamentar_nome")["valor"].sum().nlargest(top_n).index
    df_filtered = df_estados[df_estados["parlamentar_nome"].isin(top_p)]

    pivot = df_filtered.pivot_table(index="parlamentar_nome", columns="uf", values="valor", fill_value=0)

    fig = px.imshow(
        pivot,
        title=f"Top {top_n} Parlamentares × Estados (valor)",
        color_continuous_scale="YlOrRd",
        labels=dict(x="UF", y="Parlamentar", color="Valor"),
        aspect="auto",
    )
    fig.update_layout(height=max(500, top_n * 28))
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ── HTML Template ──────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TransfereGov — Dashboard 2026</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
        h1 { font-size: 28px; margin-bottom: 8px; color: #f8fafc; }
        h2 { font-size: 20px; margin: 32px 0 12px; color: #94a3b8; border-bottom: 1px solid #1e293b; padding-bottom: 8px; }
        .subtitle { color: #64748b; font-size: 14px; margin-bottom: 24px; }
        .card { background: #1e293b; border-radius: 12px; padding: 20px; min-width: 180px; flex: 1; }
        .card-num { font-size: 24px; font-weight: 700; color: #f8fafc; }
        .card-label { font-size: 13px; color: #64748b; margin-top: 4px; }
        .chart-box { background: #1e293b; border-radius: 12px; padding: 16px; margin: 16px 0; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
        .generated { text-align: center; color: #475569; font-size: 12px; margin-top: 40px; padding: 20px; }
        .js-plotly-plot .plotly .modebar { display: none !important; }
    </style>
</head>
<body>
<div class="container">
    <h1>🏛️ TransfereGov — Dashboard Transferências Especiais 2026</h1>
    <p class="subtitle">Programa 09032026 (programaId=25) — Dados extraídos da API pública em {data}</p>

    {cards}

    <h2>📊 Situação dos Planos</h2>
    <div class="chart-box">{chart_situacao}</div>

    <h2>📋 Finalidade da Política Pública</h2>
    <div class="chart-box">{chart_politica}</div>
    <div class="chart-box">{chart_politica_treemap}</div>

    <h2>🏗️ Objeto de Execução</h2>
    <div class="chart-box">{chart_objeto}</div>
    <div class="chart-box">{chart_objeto_situacao}</div>

    <h2>🗺️ Por Estado (UF)</h2>
    <div class="grid-2">
        <div class="chart-box">{chart_estado}</div>
        <div class="chart-box">{chart_estado_valor}</div>
    </div>

    <h2>👔 Por Parlamentar</h2>
    <div class="chart-box">{chart_parlamentar}</div>
    <div class="chart-box">{chart_parlamentar_heatmap}</div>

    <div class="generated">Gerado automaticamente por TransfereGov Dashboard — {data}</div>
</div>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dashboard TransfereGov")
    parser.add_argument("--output", default="output/dashboard.html", help="Caminho do HTML")
    args = parser.parse_args()

    print("Conectando ao banco...")
    conn = get_connection()

    print("Carregando dados...")
    resumo = query_df(conn, SQL_RESUMO)
    df_sit = query_df(conn, SQL_POR_SITUACAO)
    df_pol = query_df(conn, SQL_POR_POLITICA)
    df_obj = query_df(conn, SQL_POR_OBJETO)
    df_est = query_df(conn, SQL_POR_ESTADO)
    df_par = query_df(conn, SQL_POR_PARLAMENTAR)
    df_par_est = query_df(conn, SQL_POR_PARLAMENTAR_ESTADO)
    conn.close()

    print("Gerando gráficos...")
    import time
    data_str = time.strftime("%d/%m/%Y %H:%M")

    html = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>TransfereGov — Dashboard 2026</title>'
        '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'
        '<style>'
        '*{margin:0;padding:0;box-sizing:border-box}'
        'body{font-family:"Segoe UI",system-ui,sans-serif;background:#0f172a;color:#e2e8f0}'
        '.container{max-width:1400px;margin:0 auto;padding:24px}'
        'h1{font-size:28px;margin-bottom:8px;color:#f8fafc}'
        'h2{font-size:20px;margin:32px 0 12px;color:#94a3b8;border-bottom:1px solid #1e293b;padding-bottom:8px}'
        '.subtitle{color:#64748b;font-size:14px;margin-bottom:24px}'
        '.card{background:#1e293b;border-radius:12px;padding:20px;min-width:180px;flex:1}'
        '.card-num{font-size:24px;font-weight:700;color:#f8fafc}'
        '.card-label{font-size:13px;color:#64748b;margin-top:4px}'
        '.chart-box{background:#1e293b;border-radius:12px;padding:16px;margin:16px 0}'
        '.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}'
        '@media(max-width:900px){.grid-2{grid-template-columns:1fr}}'
        '.generated{text-align:center;color:#475569;font-size:12px;margin-top:40px;padding:20px}'
        '</style></head><body><div class="container">'
        '<h1>TransfereGov — Dashboard Transferências Especiais 2026</h1>'
        f'<p class="subtitle">Programa 09032026 (programaId=25) — Dados extraídos da API pública em {data_str}</p>'
        + grafico_resumo(resumo)
        + '<h2>Situação dos Planos</h2><div class="chart-box">'
        + grafico_situacao(df_sit) + '</div>'
        + '<h2>Finalidade da Política Pública</h2><div class="chart-box">'
        + grafico_politica(df_pol) + '</div><div class="chart-box">'
        + grafico_politica_treemap(df_pol) + '</div>'
        + '<h2>Objeto de Execução</h2><div class="chart-box">'
        + grafico_objeto(df_obj) + '</div><div class="chart-box">'
        + grafico_objeto_situacao(df_obj) + '</div>'
        + '<h2>Por Estado (UF)</h2><div class="grid-2"><div class="chart-box">'
        + grafico_estado(df_est) + '</div><div class="chart-box">'
        + grafico_estado_valor(df_est) + '</div></div>'
        + '<h2>Por Parlamentar</h2><div class="chart-box">'
        + grafico_parlamentar(df_par) + '</div><div class="chart-box">'
        + grafico_parlamentar_heatmap(df_par_est) + '</div>'
        + f'<div class="generated">Gerado automaticamente por TransfereGov Dashboard — {data_str}</div>'
        + '</div></body></html>'
    )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard salvo: {args.output}")
    print(f"Total: {resumo.iloc[0]['total_planos']:.0f} planos | {fmt_brl(resumo.iloc[0]['valor_total'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
