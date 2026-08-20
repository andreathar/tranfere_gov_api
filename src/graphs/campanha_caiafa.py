"""
Campanha Ricardo Caiafa 27027 — Democracia Cristã · CLDF 2026

Tab Dash com 5 sub-abas:
  1. Visão Geral   — KPIs + funil de votos + Gantt do sprint
  2. Mapa Eleitoral — scatter map das RAs do DF com peso de votos
  3. Bancada & Rivais — tabela interativa dos 24 incumbentes
  4. Roosevelt & DODF — atividade legislativa do aliado-chave
  5. Emendas CLDF — charts de emendas por ano e UO
"""

from __future__ import annotations

import logging
from datetime import date

import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from src.db_utils import get_connection

log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
ELECTION_DATE = date(2026, 10, 4)
DAYS_LEFT = (ELECTION_DATE - date.today()).days
VOTE_TARGET = 15_000
VOTE_MIN = 11_012

# Relationship mapping for incumbent analysis
RIVAL_MAP = {
    "ROOSEVELT VILELA": "aliado",
    "THIAGO MANZONI": "neutro",
    "DAYSE AMARILIO": "limiar",
    "CHICO VIGILANTE": "rival",
    "FÁBIO FELIX": "neutro",
}

# ── DF Regiões Administrativas — centroides aproximados ───────────────────────
RA_MAP = [
    {"ra": "Ceilândia",     "lat": -15.8141, "lon": -48.1097, "p": "primary",   "votos": 5500, "motivo": "Facilities workers · Maior RA do DF"},
    {"ra": "Taguatinga",    "lat": -15.8397, "lon": -48.0537, "p": "primary",   "votos": 2800, "motivo": "CAC + Terceirizados"},
    {"ra": "Samambaia",     "lat": -15.8750, "lon": -48.0950, "p": "primary",   "votos": 2200, "motivo": "Facilities + densidade residencial"},
    {"ra": "Plano Piloto",  "lat": -15.7941, "lon": -47.8825, "p": "secondary", "votos": 1800, "motivo": "Empresários + Tech · Polo de Dados"},
    {"ra": "Planaltina",    "lat": -15.6228, "lon": -47.6514, "p": "secondary", "votos": 1500, "motivo": "Expansão de base"},
    {"ra": "Gama",          "lat": -16.0142, "lon": -48.0650, "p": "secondary", "votos":  900, "motivo": "Vigilantes privados"},
    {"ra": "Brasília",      "lat": -15.7801, "lon": -47.9292, "p": "secondary", "votos": 1600, "motivo": "Tech + DCVerde + ONGs"},
    {"ra": "Sobradinho",    "lat": -15.6534, "lon": -47.7939, "p": "secondary", "votos":  700, "motivo": "Clubes CAC"},
    {"ra": "Vicente Pires", "lat": -15.8017, "lon": -48.0497, "p": "watch",     "votos":  400, "motivo": "Monitorar"},
    {"ra": "Recanto",       "lat": -15.9073, "lon": -48.0614, "p": "watch",     "votos":  350, "motivo": "Monitorar"},
    {"ra": "Santa Maria",   "lat": -16.0012, "lon": -48.0368, "p": "watch",     "votos":  250, "motivo": "Monitorar"},
    {"ra": "Guará",         "lat": -15.8302, "lon": -47.9765, "p": "watch",     "votos":  300, "motivo": "Monitorar"},
]

# Sprint weeks
SPRINT = [
    {"semana": "Sem 1–2 (18–31 ago)",  "tarefa": "Ativação TeamCaiafa",     "foco": "Digital + Voluntários",   "meta": "500 voluntários · 50k alcance/sem", "start": 0,  "dur": 14},
    {"semana": "Sem 3–4 (1–14 set)",   "tarefa": "Penetração Setorial",     "foco": "Facilities + CAC + Tech", "meta": "15 reuniões B2B · 3 clubes CAC",    "start": 14, "dur": 14},
    {"semana": "Sem 5–6 (15–28 set)",  "tarefa": "Mídia Paga + Debates",    "foco": "Meta Ads + TikTok",       "meta": "1M impressões · 2 carreatas",       "start": 28, "dur": 14},
    {"semana": "Sem 7 (29 set–3 out)", "tarefa": "Semana do Número",        "foco": "Broadcast 27027",         "meta": "100% dos cadastrados contactados",  "start": 42, "dur": 5},
    {"semana": "4 Out",                "tarefa": "Dia da Eleição",          "foco": "Fiscais + Transporte",    "meta": "80%+ de comparecimento",            "start": 47, "dur": 1},
]

# ── Design tokens ─────────────────────────────────────────────────────────────
_S = {
    "card": {"backgroundColor": "#1e293b", "borderRadius": "8px", "padding": "1.2rem",
             "marginBottom": "1rem", "border": "1px solid #334155"},
    "h3":    {"color": "#f8fafc", "fontSize": "1rem", "marginBottom": "0.5rem", "fontWeight": "700"},
    "label": {"color": "#94a3b8", "fontSize": "0.75rem", "marginBottom": "0.2rem"},
    "val":   {"color": "#f8fafc", "fontWeight": "bold", "fontSize": "1.4rem"},
    "muted": {"color": "#94a3b8", "fontSize": "0.78rem"},
    "tab_base": {"backgroundColor": "#1e293b", "color": "#94a3b8",
                 "border": "none", "borderBottom": "1px solid #334155"},
    "tab_sel": {"backgroundColor": "#dc2626", "color": "white",
                "border": "none", "fontWeight": "bold"},
}

_TABLE = {
    "style_table": {"overflowX": "auto"},
    "style_cell": {"backgroundColor": "#0f172a", "color": "#cbd5e1",
                   "border": "1px solid #1e293b", "fontSize": "0.8rem", "padding": "6px 10px"},
    "style_header": {"backgroundColor": "#1e293b", "color": "#f8fafc",
                     "fontWeight": "bold", "border": "1px solid #334155", "fontSize": "0.75rem"},
    "style_data_conditional": [{"if": {"row_index": "odd"}, "backgroundColor": "#0d1a2e"}],
}


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────

def _load_incumbentes() -> list[dict]:
    """24 deputados com contagem de menções no DODF."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                d.nome_candidato,
                d.sigla_partido,
                d.votos_total,
                COALESCE(d.total_bens, 0)           AS total_bens,
                COALESCE(d.gasto_campanha_r1, 0)    AS gasto_campanha,
                d.nr_candidato,
                COALESCE(m.dodf_count, 0)           AS dodf_count
            FROM df_deputados_distritais_cldf d
            LEFT JOIN (
                SELECT deputado_nome, COUNT(*) AS dodf_count
                FROM cldf_dodf_mentions
                WHERE query_type = 'deputado'
                GROUP BY deputado_nome
            ) m ON UPPER(TRIM(m.deputado_nome)) = UPPER(TRIM(d.nome_candidato))
            WHERE d.legislatura = 9
            ORDER BY d.votos_total DESC NULLS LAST
        """)
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_dodf_roosevelt() -> list[dict]:
    """Menções no DODF relacionadas a Roosevelt Vilela (aliado CAC)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                date_pub::text              AS data,
                gazette_url                 AS url,
                LEFT(COALESCE(excerpt, ''), 300) AS trecho
            FROM cldf_dodf_mentions
            WHERE query_type = 'deputado'
              AND UPPER(deputado_nome) LIKE '%%ROOSEVELT%%'
            ORDER BY date_pub DESC
        """)
        cols = ["Data", "URL", "Trecho"]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_dodf_by_month_aliado() -> list[dict]:
    """Menções mensais de Roosevelt Vilela — para timeline."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                TO_CHAR(date_pub, 'YYYY-MM')    AS mes,
                COUNT(*)                         AS mencoes
            FROM cldf_dodf_mentions
            WHERE query_type = 'deputado'
              AND UPPER(deputado_nome) LIKE '%%ROOSEVELT%%'
            GROUP BY mes
            ORDER BY mes
        """)
        cols = ["mes", "mencoes"]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_emendas_anos() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ano_emenda,
                   COUNT(*)          AS n,
                   SUM(vl_emenda)    AS proposto,
                   SUM(vl_empenhado) AS empenhado,
                   SUM(vl_liquidado) AS liquidado,
                   COUNT(*) FILTER (WHERE status_emenda = 'CANCELADO') AS cancelados
            FROM cldf_emendas
            GROUP BY ano_emenda
            ORDER BY ano_emenda
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_emendas_uo() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT nome_uo,
                   SUM(vl_empenhado) AS empenhado,
                   SUM(vl_emenda)    AS proposto,
                   COUNT(*)          AS n
            FROM cldf_emendas
            WHERE status_emenda = 'ATIVO' AND nome_uo IS NOT NULL
            GROUP BY nome_uo
            ORDER BY empenhado DESC NULLS LAST
            LIMIT 10
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_verbas_summary() -> list[dict]:
    """Verbas indenizatórias totais por parlamentar — para contexto comparativo."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT nome_parlamentar, SUM(valor_despesa) AS total, COUNT(*) AS n
            FROM cldf_verbas_indenizatorias
            WHERE valor_despesa IS NOT NULL
            GROUP BY nome_parlamentar
            ORDER BY total DESC
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders (stateless — called at layout build or from callbacks)
# ─────────────────────────────────────────────────────────────────────────────

_DARK = {"paper_bgcolor": "#0f172a", "plot_bgcolor": "#0f172a",
         "font": {"color": "#cbd5e1", "size": 11}}


def _chart_voto_potencial() -> go.Figure:
    """Barra horizontal: potencial de votos por eleitorado (min–max)."""
    nomes = ["Terceirizados GDF", "CAC Community", "Empresários Serviços",
             "Tech & Data", "Vigilantes & +50"]
    mids = [5250, 3000, 2250, 1500, 1500]
    errs = [750, 1000, 750, 500, 500]
    colors = ["#3b82f6", "#f59e0b", "#10b981", "#8b5cf6", "#f43f5e"]

    fig = go.Figure()
    for i, (n, m, e, c) in enumerate(zip(nomes, mids, errs, colors)):
        fig.add_trace(go.Bar(
            y=[n], x=[m],
            orientation="h",
            marker_color=c,
            error_x={"type": "data", "array": [e], "color": "#475569"},
            name=n,
            hovertemplate=f"<b>{n}</b><br>Potencial: {m-e:,.0f}–{m+e:,.0f} votos<extra></extra>",
        ))

    fig.add_vline(x=VOTE_MIN, line_dash="dot", line_color="#f87171",
                  annotation_text=f"Limiar ({VOTE_MIN:,})", annotation_font_color="#f87171")
    fig.add_vline(x=VOTE_TARGET, line_dash="dot", line_color="#4ade80",
                  annotation_text=f"Meta ({VOTE_TARGET:,})", annotation_font_color="#4ade80")

    fig.update_layout(
        **_DARK,
        title={"text": "Potencial de Votos por Eleitorado-Alvo", "font": {"color": "#f8fafc"}},
        showlegend=False, height=300,
        xaxis={"gridcolor": "#1e293b", "title": "Votos estimados"},
        yaxis={"gridcolor": "#1e293b"},
        margin={"l": 160, "r": 60, "t": 50, "b": 40},
    )
    return fig


def _chart_gantt() -> go.Figure:
    """Gantt horizontal do sprint de 47 dias."""
    colors_gantt = {
        "Ativação TeamCaiafa":  "#f59e0b",
        "Penetração Setorial":  "#3b82f6",
        "Mídia Paga + Debates": "#10b981",
        "Semana do Número":     "#8b5cf6",
        "Dia da Eleição":       "#dc2626",
    }
    fig = go.Figure()
    for s in SPRINT:
        c = colors_gantt.get(s["tarefa"], "#64748b")
        fig.add_trace(go.Bar(
            y=[s["tarefa"]], x=[s["dur"]], base=[s["start"]],
            orientation="h",
            marker_color=c,
            hovertemplate=(
                f"<b>{s['tarefa']}</b><br>"
                f"{s['semana']}<br>"
                f"Foco: {s['foco']}<br>"
                f"Meta: {s['meta']}<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.update_layout(
        **_DARK,
        title={"text": "Sprint Final — 47 Dias", "font": {"color": "#f8fafc"}},
        height=280,
        xaxis={"title": "Dias a partir de 19/ago", "gridcolor": "#1e293b",
               "tickvals": [0, 7, 14, 21, 28, 35, 42, 47],
               "ticktext": ["19/ago", "26/ago", "2/set", "9/set", "16/set", "23/set", "30/set", "4/out"]},
        yaxis={"gridcolor": "#1e293b"},
        margin={"l": 170, "r": 40, "t": 50, "b": 50},
        barmode="overlay",
    )
    return fig


def _chart_mapa_ra() -> go.Figure:
    """Scatter map das Regiões Administrativas — tamanho = votos potenciais."""
    priority_colors = {"primary": "#3b82f6", "secondary": "#64748b", "watch": "#334155"}
    priority_labels = {"primary": "Prioritária", "secondary": "Secundária", "watch": "Monitorar"}

    fig = go.Figure()
    for prio in ["primary", "secondary", "watch"]:
        pts = [r for r in RA_MAP if r["p"] == prio]
        if not pts:
            continue
        fig.add_trace(go.Scattermapbox(
            lat=[p["lat"] for p in pts],
            lon=[p["lon"] for p in pts],
            mode="markers+text",
            marker={
                "size": [max(8, p["votos"] // 150) for p in pts],
                "color": priority_colors[prio],
                "opacity": 0.85 if prio == "primary" else 0.6,
            },
            text=[p["ra"] for p in pts],
            textposition="top right",
            textfont={"color": "#e2e8f0", "size": 10},
            hovertemplate="<b>%{text}</b><br>Votos potenciais: %{customdata[0]:,}<br>%{customdata[1]}<extra></extra>",
            customdata=[[p["votos"], p["motivo"]] for p in pts],
            name=priority_labels[prio],
        ))

    # Marker: target vote total
    fig.add_trace(go.Scattermapbox(
        lat=[-15.7941], lon=[-47.8825],
        mode="markers",
        marker={"size": 18, "color": "#dc2626", "symbol": "star"},
        hovertemplate="<b>Meta: 15.000 votos</b><br>Distribuídos nas RAs prioritárias<extra></extra>",
        name="Meta 15k votos",
        showlegend=True,
    ))

    fig.update_layout(
        **_DARK,
        mapbox={
            "style": "open-street-map",
            "center": {"lat": -15.82, "lon": -48.00},
            "zoom": 9.5,
        },
        legend={"font": {"color": "#cbd5e1"}, "bgcolor": "#1e293b",
                "bordercolor": "#334155", "borderwidth": 1},
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=500,
    )
    return fig


def _chart_ra_bars() -> go.Figure:
    """Barra: votos potenciais por RA ordenados."""
    pts = sorted(RA_MAP, key=lambda x: x["votos"], reverse=True)
    colors = ["#3b82f6" if p["p"] == "primary" else "#64748b" if p["p"] == "secondary" else "#334155"
              for p in pts]
    fig = go.Figure(go.Bar(
        x=[p["ra"] for p in pts],
        y=[p["votos"] for p in pts],
        marker_color=colors,
        hovertemplate="<b>%{x}</b><br>Potencial: %{y:,} votos<extra></extra>",
    ))
    fig.update_layout(
        **_DARK,
        title={"text": "Votos Potenciais por RA", "font": {"color": "#f8fafc"}},
        xaxis={"gridcolor": "#1e293b", "tickangle": -30},
        yaxis={"gridcolor": "#1e293b"},
        height=300,
        margin={"l": 50, "r": 30, "t": 50, "b": 90},
        showlegend=False,
    )
    return fig


def _chart_incumbentes_scatter(rows: list[dict]) -> go.Figure:
    """Scatter: votos 2022 × menções DODF, colorido por relação."""
    rel_colors = {"aliado": "#4ade80", "neutro": "#94a3b8",
                  "limiar": "#f59e0b", "rival": "#f87171", "outro": "#64748b"}

    def _rel(nome: str) -> str:
        key = nome.upper().strip()
        for k, v in RIVAL_MAP.items():
            if k in key:
                return v
        return "outro"

    fig = go.Figure()
    for rel, color in rel_colors.items():
        pts = [r for r in rows if _rel(r.get("nome_candidato", "")) == rel]
        if not pts:
            continue
        fig.add_trace(go.Scatter(
            x=[p["votos_total"] for p in pts],
            y=[p["dodf_count"] for p in pts],
            mode="markers+text",
            marker={"size": 12, "color": color, "line": {"color": "#0f172a", "width": 1}},
            text=[p["nome_candidato"].split()[0].title() for p in pts],
            textposition="top center",
            textfont={"size": 9, "color": color},
            name=rel.title(),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Votos 2022: %{x:,}<br>"
                "Menções DODF: %{y}<extra></extra>"
            ),
        ))

    fig.add_vline(x=VOTE_MIN, line_dash="dot", line_color="#f87171",
                  annotation_text="Limiar 11k", annotation_font_color="#f87171")
    fig.add_vline(x=VOTE_TARGET, line_dash="dot", line_color="#4ade80",
                  annotation_text="Meta 15k", annotation_font_color="#4ade80")

    fig.update_layout(
        **_DARK,
        title={"text": "Votos 2022 × Atividade DODF — Incumbentes", "font": {"color": "#f8fafc"}},
        xaxis={"title": "Votos 2022", "gridcolor": "#1e293b"},
        yaxis={"title": "Menções no DODF", "gridcolor": "#1e293b"},
        height=420,
        legend={"font": {"color": "#cbd5e1"}, "bgcolor": "#1e293b"},
        margin={"l": 60, "r": 40, "t": 50, "b": 50},
    )
    return fig


def _chart_dodf_timeline(rows: list[dict]) -> go.Figure:
    """Timeline mensal de menções Roosevelt Vilela."""
    if not rows:
        return go.Figure().update_layout(**_DARK, height=250)
    meses = [r["mes"] for r in rows]
    counts = [r["mencoes"] for r in rows]
    fig = go.Figure(go.Bar(
        x=meses, y=counts,
        marker_color="#3b82f6",
        hovertemplate="<b>%{x}</b><br>Menções: %{y}<extra></extra>",
    ))
    fig.update_layout(
        **_DARK,
        title={"text": "Roosevelt Vilela — Menções DODF por Mês", "font": {"color": "#f8fafc"}},
        xaxis={"gridcolor": "#1e293b"},
        yaxis={"gridcolor": "#1e293b", "title": "Menções"},
        height=250,
        margin={"l": 50, "r": 30, "t": 50, "b": 50},
    )
    return fig


def _chart_emendas_anos(rows: list[dict]) -> go.Figure:
    anos = [str(r["ano_emenda"]) for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=anos, y=[float(r.get("proposto") or 0) / 1e6 for r in rows],
                         name="Proposto (R$M)", marker_color="#334155"))
    fig.add_trace(go.Bar(x=anos, y=[float(r.get("empenhado") or 0) / 1e6 for r in rows],
                         name="Empenhado (R$M)", marker_color="#3b82f6"))
    fig.add_trace(go.Bar(x=anos, y=[float(r.get("liquidado") or 0) / 1e6 for r in rows],
                         name="Liquidado (R$M)", marker_color="#10b981"))
    fig.update_layout(
        **_DARK,
        title={"text": "Emendas CLDF — Proposto vs Empenhado vs Liquidado (R$M)", "font": {"color": "#f8fafc"}},
        barmode="group", height=300,
        xaxis={"gridcolor": "#1e293b"},
        yaxis={"gridcolor": "#1e293b", "title": "R$ Milhões"},
        legend={"font": {"color": "#cbd5e1"}, "bgcolor": "#1e293b"},
        margin={"l": 60, "r": 30, "t": 50, "b": 40},
    )
    return fig


def _chart_emendas_uo(rows: list[dict]) -> go.Figure:
    nomes = [r.get("nome_uo", "—")[:35] for r in rows]
    vals = [float(r.get("empenhado") or 0) / 1e6 for r in rows]
    fig = go.Figure(go.Bar(
        y=nomes, x=vals, orientation="h",
        marker_color="#3b82f6",
        hovertemplate="<b>%{y}</b><br>Empenhado: R$ %{x:.2f}M<extra></extra>",
    ))
    fig.update_layout(
        **_DARK,
        title={"text": "Top UOs por Emendas Empenhadas (R$M)", "font": {"color": "#f8fafc"}},
        xaxis={"gridcolor": "#1e293b", "title": "R$ Milhões"},
        yaxis={"gridcolor": "#1e293b"},
        height=380,
        margin={"l": 280, "r": 40, "t": 50, "b": 40},
    )
    return fig


def _chart_funil() -> go.Figure:
    """Funil de conversão: seguidores → voluntários → votos comprometidos → votos."""
    fig = go.Figure(go.Funnel(
        y=["Seguidores Instagram", "Alcance Orgânico Est.", "Voluntários Ativos",
           "Contatos Comprometidos", "META: Votos"],
        x=[30_000, 90_000, 500, 12_000, 15_000],
        marker_color=["#334155", "#475569", "#3b82f6", "#10b981", "#dc2626"],
        textinfo="value+percent initial",
        textfont={"color": "#f8fafc"},
        connector={"line": {"color": "#334155", "width": 1}},
    ))
    fig.update_layout(
        **_DARK,
        title={"text": "Funil de Conversão — Base Digital → Votos", "font": {"color": "#f8fafc"}},
        height=380,
        margin={"l": 40, "r": 40, "t": 50, "b": 40},
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# KPI row helper
# ─────────────────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, sub: str = "", color: str = "#f8fafc") -> html.Div:
    return html.Div(style={**_S["card"], "flex": "1", "minWidth": "130px", "textAlign": "center"}, children=[
        html.Div(label, style=_S["label"]),
        html.Div(value, style={**_S["val"], "color": color}),
        html.Div(sub, style=_S["muted"]) if sub else None,
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Layout builder
# ─────────────────────────────────────────────────────────────────────────────

def build_campanha_tab() -> dcc.Tab:
    try:
        incumbentes = _load_incumbentes()
    except Exception as e:
        log.error("Erro incumbentes: %s", e)
        incumbentes = []

    try:
        dodf_timeline = _load_dodf_by_month_aliado()
    except Exception as e:
        log.error("Erro dodf timeline: %s", e)
        dodf_timeline = []

    try:
        emendas_anos = _load_emendas_anos()
    except Exception as e:
        log.error("Erro emendas anos: %s", e)
        emendas_anos = []

    try:
        emendas_uo = _load_emendas_uo()
    except Exception as e:
        log.error("Erro emendas uo: %s", e)
        emendas_uo = []

    # ── incumbentes table rows ────────────────────────────────────────────────
    def _relacao(nome: str) -> str:
        key = nome.upper()
        for k, v in RIVAL_MAP.items():
            if k in key:
                labels = {"aliado": "✓ Aliado", "neutro": "~ Neutro",
                          "limiar": "⚠ Limiar", "rival": "✗ Rival"}
                return labels.get(v, "—")
        return "—"

    table_rows = [
        {
            "Deputado": r.get("nome_candidato", "—").title(),
            "Partido":  r.get("sigla_partido", "—"),
            "Votos 2022": f"{int(r.get('votos_total') or 0):,}".replace(",", "."),
            "Bens (R$)": f"R$ {float(r.get('total_bens') or 0)/1e3:,.0f}k".replace(",", "."),
            "Gasto Camp.": f"R$ {float(r.get('gasto_campanha') or 0)/1e3:,.0f}k".replace(",", "."),
            "DODF": int(r.get("dodf_count") or 0),
            "Relação": _relacao(r.get("nome_candidato", "")),
        }
        for r in incumbentes
    ]

    # ── DODF Roosevelt rows ──────────────────────────────────────────────────
    try:
        dodf_rows = _load_dodf_roosevelt()
    except Exception:
        dodf_rows = []

    # ─── Build layout ─────────────────────────────────────────────────────────
    header = html.Div(style={
        "background": "linear-gradient(135deg, #0f172a 60%, #1a2744)",
        "borderRadius": "8px", "padding": "1.4rem 1.6rem", "marginBottom": "1.2rem",
        "borderLeft": "4px solid #dc2626",
        "display": "grid", "gridTemplateColumns": "1fr auto", "gap": "1rem", "alignItems": "center",
    }, children=[
        html.Div([
            html.Div("CAMPANHA ELEITORAL — CLDF 2026", style={
                "fontSize": ".6rem", "letterSpacing": ".16em", "color": "#dc2626",
                "fontWeight": "700", "marginBottom": ".3rem", "textTransform": "uppercase",
            }),
            html.Div("Ricardo Caiafa", style={
                "fontFamily": "Georgia,serif", "fontSize": "1.8rem",
                "fontWeight": "700", "color": "#E4EEF8", "lineHeight": "1.1",
            }),
            html.Div("CEO · Democracia Cristã · trajetória camareiro → empresário",
                     style={"fontSize": ".8rem", "color": "#8DAAC4", "marginTop": ".2rem"}),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": ".35rem", "marginTop": ".7rem"}, children=[
                html.Span("Democracia Cristã · 27", style={"background": "#1a3a5c", "color": "#60a5fa", "padding": ".12rem .45rem", "borderRadius": "2px", "fontSize": ".62rem", "fontWeight": "700"}),
                html.Span("Nº 27027", style={"background": "#1a3a1a", "color": "#4ade80", "padding": ".12rem .45rem", "borderRadius": "2px", "fontSize": ".62rem", "fontWeight": "700"}),
                html.Span(f"⏱ {DAYS_LEFT} dias", style={"background": "#3a1a1a", "color": "#f87171", "padding": ".12rem .45rem", "borderRadius": "2px", "fontSize": ".62rem", "fontWeight": "700"}),
                html.Span("30k+ IG · valdirene.app", style={"background": "#2a1a3a", "color": "#c084fc", "padding": ".12rem .45rem", "borderRadius": "2px", "fontSize": ".62rem", "fontWeight": "700"}),
            ]),
        ]),
        html.Div(style={"textAlign": "right"}, children=[
            html.Div("27027", style={"fontFamily": "'Courier New',monospace", "fontSize": "2.8rem", "fontWeight": "700", "color": "#dc2626", "lineHeight": "1"}),
            html.Div("NÚMERO DE URNA", style={"fontSize": ".6rem", "color": "#8DAAC4", "letterSpacing": ".1em"}),
            html.Div(f"META {VOTE_TARGET:,} VOTOS".replace(",", "."), style={"fontFamily": "'Courier New',monospace", "fontSize": "1rem", "color": "#4ade80", "fontWeight": "700", "marginTop": ".5rem"}),
            html.Div(f"mínimo histórico: {VOTE_MIN:,}".replace(",", "."), style={"fontSize": ".62rem", "color": "#8DAAC4"}),
        ]),
    ])

    kpi_row = html.Div(style={"display": "flex", "gap": ".75rem", "flexWrap": "wrap", "marginBottom": "1rem"}, children=[
        _kpi("Dias Restantes", str(DAYS_LEFT), "4 out 2026", "#f87171"),
        _kpi("Meta de Votos",  f"{VOTE_TARGET:,}".replace(",", "."), "conservador", "#4ade80"),
        _kpi("Limiar Histórico", f"{VOTE_MIN:,}".replace(",", "."), "Dayse Amarilio 2022", "#f59e0b"),
        _kpi("Seguidores IG",  "30k+", "já ativo", "#3b82f6"),
        _kpi("Eleitorados Alvo", "5", "constituencies", "#8b5cf6"),
        _kpi("Aliado CLDF",    "Roosevelt", "Vilela · PL", "#4ade80"),
        _kpi("Partido",        "DC · 27", "limpa — zero cand. 2022", "#94a3b8"),
    ])

    # ── Sub-tabs ──────────────────────────────────────────────────────────────
    subtab_style = {"backgroundColor": "#0f172a", "color": "#64748b", "border": "none", "borderBottom": "1px solid #1e293b", "fontSize": ".8rem"}
    subtab_sel   = {"backgroundColor": "#1e293b", "color": "#f8fafc", "border": "none", "borderBottom": "2px solid #dc2626", "fontWeight": "700", "fontSize": ".8rem"}

    # 1. VISÃO GERAL
    tab_visao = dcc.Tab(label="Visão Geral", style=subtab_style, selected_style=subtab_sel, children=[
        html.Div(style={"padding": "1rem 0"}, children=[
            kpi_row,
            html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "1rem"}, children=[
                html.Div(style=_S["card"], children=[
                    dcc.Graph(figure=_chart_voto_potencial(), config={"displayModeBar": False}),
                ]),
                html.Div(style=_S["card"], children=[
                    dcc.Graph(figure=_chart_funil(), config={"displayModeBar": False}),
                ]),
            ]),
            html.Div(style=_S["card"], children=[
                dcc.Graph(figure=_chart_gantt(), config={"displayModeBar": False}),
            ]),
        ]),
    ])

    # 2. MAPA ELEITORAL
    tab_mapa = dcc.Tab(label="🗺 Mapa Eleitoral DF", style=subtab_style, selected_style=subtab_sel, children=[
        html.Div(style={"padding": "1rem 0"}, children=[
            html.Div(style=_S["card"], children=[
                html.P("Tamanho dos círculos proporcional ao potencial de votos estimado por RA. Azul = prioritária · Cinza = secundária.",
                       style=_S["muted"]),
                dcc.Graph(figure=_chart_mapa_ra(), config={"displayModeBar": True}),
            ]),
            html.Div(style=_S["card"], children=[
                dcc.Graph(figure=_chart_ra_bars(), config={"displayModeBar": False}),
            ]),
        ]),
    ])

    # 3. BANCADA & RIVAIS
    tab_bancada = dcc.Tab(label="Bancada & Rivais", style=subtab_style, selected_style=subtab_sel, children=[
        html.Div(style={"padding": "1rem 0"}, children=[
            html.Div(style=_S["card"], children=[
                html.H3("24 Incumbentes — Votos 2022 × Atividade DODF", style=_S["h3"]),
                html.P("Verde = aliado | Amarelo = limiar referência | Vermelho = rival direto | Cinza = neutro",
                       style=_S["muted"]),
                dcc.Graph(id="campanha-scatter-incumbentes",
                          figure=_chart_incumbentes_scatter(incumbentes),
                          config={"displayModeBar": False}),
            ]),
            html.Div(style=_S["card"], children=[
                html.H3("Tabela Completa — Incumbentes CLDF 9ª Legislatura", style=_S["h3"]),
                dash_table.DataTable(
                    id="campanha-table-incumbentes",
                    data=table_rows,
                    columns=[{"name": c, "id": c} for c in (table_rows[0].keys() if table_rows else [])],
                    sort_action="native",
                    filter_action="native",
                    page_size=12,
                    **{**_TABLE, "style_data_conditional": [
                        {"if": {"row_index": "odd"}, "backgroundColor": "#0d1a2e"},
                        {"if": {"filter_query": '{Relação} contains "Aliado"'}, "color": "#4ade80"},
                        {"if": {"filter_query": '{Relação} contains "Rival"'},  "color": "#f87171"},
                        {"if": {"filter_query": '{Relação} contains "Limiar"'}, "color": "#f59e0b"},
                    ]},
                ),
            ]),
        ]),
    ])

    # 4. ROOSEVELT & DODF
    tab_roosevelt = dcc.Tab(label="Roosevelt & DODF", style=subtab_style, selected_style=subtab_sel, children=[
        html.Div(style={"padding": "1rem 0"}, children=[
            html.Div(style={**_S["card"], "borderLeft": "3px solid #4ade80"}, children=[
                html.H3("Roosevelt Vilela — Aliado Estratégico", style={**_S["h3"], "color": "#4ade80"}),
                html.P("Deputado Distrital · PL · 20.223 votos em 2022 · Presidente da Frente Parlamentar de Defesa dos CACs. "
                       "Ricardo Caiafa é Secretário-Geral da mesma frente. Um endosso público vale ~2.000 votos no bloco CAC.",
                       style=_S["muted"]),
            ]),
            html.Div(style=_S["card"], children=[
                dcc.Graph(figure=_chart_dodf_timeline(dodf_timeline), config={"displayModeBar": False}),
            ]),
            html.Div(style=_S["card"], children=[
                html.H3(f"Menções no DODF — Roosevelt Vilela ({len(dodf_rows)} registros)", style=_S["h3"]),
                dcc.Loading(children=html.Div(id="campanha-dodf-roosevelt-table", children=[
                    dash_table.DataTable(
                        data=dodf_rows[:50],
                        columns=[{"name": c, "id": c} for c in (dodf_rows[0].keys() if dodf_rows else [])],
                        sort_action="native",
                        page_size=10,
                        **_TABLE,
                        style_cell_conditional=[
                            {"if": {"column_id": "Trecho"}, "maxWidth": "500px",
                             "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "normal"},
                        ],
                    ) if dodf_rows else html.P("Nenhum registro encontrado.", style=_S["muted"]),
                ])),
            ]),
        ]),
    ])

    # 5. EMENDAS CLDF
    tab_emendas = dcc.Tab(label="Emendas CLDF", style=subtab_style, selected_style=subtab_sel, children=[
        html.Div(style={"padding": "1rem 0"}, children=[
            html.Div(style=_S["card"], children=[
                dcc.Graph(figure=_chart_emendas_anos(emendas_anos), config={"displayModeBar": False}),
            ]),
            html.Div(style=_S["card"], children=[
                dcc.Graph(figure=_chart_emendas_uo(emendas_uo), config={"displayModeBar": False}),
            ]),
            html.Div(style=_S["card"], children=[
                html.H3("Top UOs — Tabela Detalhada", style=_S["h3"]),
                dash_table.DataTable(
                    data=[{
                        "Unidade Orçamentária": r.get("nome_uo", "—"),
                        "Proposto (R$)": f"R$ {float(r.get('proposto') or 0):,.0f}".replace(",", "."),
                        "Empenhado (R$)": f"R$ {float(r.get('empenhado') or 0):,.0f}".replace(",", "."),
                        "Emendas": int(r.get("n") or 0),
                    } for r in emendas_uo],
                    columns=[
                        {"name": "Unidade Orçamentária", "id": "Unidade Orçamentária"},
                        {"name": "Proposto (R$)", "id": "Proposto (R$)"},
                        {"name": "Empenhado (R$)", "id": "Empenhado (R$)"},
                        {"name": "Emendas", "id": "Emendas"},
                    ],
                    sort_action="native",
                    page_size=10,
                    **_TABLE,
                ) if emendas_uo else html.P("Sem dados de emendas.", style=_S["muted"]),
            ]),
        ]),
    ])

    inner_tabs = dcc.Tabs(
        [tab_visao, tab_mapa, tab_bancada, tab_roosevelt, tab_emendas],
        style={"marginBottom": "1rem"},
    )

    content = html.Div(style={"padding": "1.5rem 2rem 2rem"}, children=[header, inner_tabs])

    return dcc.Tab(
        label="🗳️ Campanha Caiafa",
        children=[content],
        style={"backgroundColor": "#1e293b", "color": "#94a3b8",
               "border": "none", "borderBottom": "1px solid #334155"},
        selected_style={"backgroundColor": "#dc2626", "color": "white",
                        "border": "none", "fontWeight": "bold"},
    )


def register_callbacks() -> None:
    # No interactive server-side callbacks needed for this tab yet;
    # all charts are pre-rendered at layout build time.
    pass
