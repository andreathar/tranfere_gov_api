"""
CLDF Bancada Distrital — Dash tab layout and callbacks.

Carrega dados ao vivo do PostgreSQL para os 24 deputados distritais eleitos
em 2022 (9ª Legislatura), emendas CLDF 2021–2025, verbas indenizatórias e
menções no Diário Oficial do DF (DODF).
"""

from __future__ import annotations

import logging

import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from src.db_utils import get_connection

log = logging.getLogger(__name__)

PARTY_COLORS = {
    "PL": "#003087", "PT": "#CC0000", "MDB": "#006699", "PSOL": "#E05A1C",
    "PSD": "#0099CC", "AGIR": "#2E7D32", "PP": "#1A237E",
    "Republicanos": "#E65100", "União": "#01579B", "PMN": "#7B1FA2",
    "Avante": "#F57F17", "Cidadania": "#558B2F", "PSB": "#F44336",
}

# Name mapping: DB nome_parlamentar → nome_candidato in df_deputados_distritais_cldf
# (verbas data has legacy/informal names that don't match TSE names exactly)
VERBAS_NAME_MAP = {
    "Bernardo Rogério Mata de Araújo Júnior": "ROGÉRIO MORRO DA CRUZ",
    "Chico Vigilante": "CHICO VIGILANTE",
    "CHICO VIGILANTE": "CHICO VIGILANTE",
    "Dayse Amarílio Donetts Diniz": "DAYSE AMARILIO",
    "Dep. PEPA": "PEPA",
    "Deputada Paula Belmonte": "PAULA BELMONTE",
    "Deputado Daniel Donizet": "DANIEL DONIZET",
    "Deputado Gabriel Magno": "GABRIEL MAGNO",
    "Deputado Hermeto": "HERMETO",
    "Deputado João Cardoso": "JOÃO CARDOSO PROFESSOR AUDITOR",
    "Deputado Joaquim Roriz Neto": "JOAQUIM RORIZ NETO",
    "Deputado Roosevelt Vilela": "ROOSEVELT VILELA",
    "Deputado Thiago De Araújo Macieira Manzoni": "THIAGO MANZONI",
    "FÁBIO FELIX SILVEIRA": "FÁBIO FELIX",
    "Fábio Silveira Felix": "FÁBIO FELIX",
    "Iolando Almeida": "IOLANDO",
    "Jane Klébia do Nascimento da Silva": "DOUTORA JANE",
    "JAQUELINE SILVA": "JAQUELINE SILVA",
    "Martins Machado": "MARTINS MACHADO",
    "Max Maciel Cavalcanti": "MAX MACIEL",
    "Ricardo Vale da Silva": "RICARDO VALE",
}

_S = {  # style tokens
    "card": {
        "backgroundColor": "#1e293b", "borderRadius": "8px",
        "padding": "1.2rem", "marginBottom": "1.2rem",
        "border": "1px solid #334155",
    },
    "h3": {"color": "#f8fafc", "fontSize": "1rem", "marginBottom": "0.6rem"},
    "label": {"color": "#94a3b8", "fontSize": "0.8rem", "marginBottom": "0.3rem"},
    "val": {"color": "#f8fafc", "fontWeight": "bold"},
    "accent": {"color": "#f59e0b"},
    "muted": {"color": "#94a3b8", "fontSize": "0.8rem"},
    "tab_base": {
        "backgroundColor": "#1e293b", "color": "#94a3b8",
        "border": "none", "borderBottom": "1px solid #334155",
    },
}

_TABLE_STYLE = {
    "style_table": {"overflowX": "auto"},
    "style_cell": {
        "backgroundColor": "#0f172a", "color": "#cbd5e1",
        "border": "1px solid #1e293b", "fontSize": "0.82rem",
        "padding": "6px 10px", "textAlign": "left",
    },
    "style_header": {
        "backgroundColor": "#1e293b", "color": "#f8fafc",
        "fontWeight": "bold", "border": "1px solid #334155",
        "fontSize": "0.78rem",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": "#0d1a2e"},
    ],
}


# ─────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────

def _load_deputados() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT nome_candidato, nome_civil, sigla_partido, votos_total,
                   COALESCE(total_bens, 0) AS total_bens,
                   sexo, cor_raca, grau_instrucao, estado_civil,
                   data_nascimento, nr_candidato, sq_candidato,
                   COALESCE(gasto_campanha_r1, 0) AS gasto_campanha
            FROM df_deputados_distritais_cldf
            WHERE legislatura = 9
            ORDER BY votos_total DESC NULLS LAST
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_bens() -> dict[int, list[dict]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT sq_candidato, descricao, tipo_bem, COALESCE(valor, 0) AS valor
            FROM df_deputados_distritais_bens
            ORDER BY sq_candidato, ordem
        """)
        result: dict[int, list[dict]] = {}
        for sq, desc, tipo, val in cur.fetchall():
            result.setdefault(sq, []).append(
                {"Descrição": desc or "—", "Tipo": tipo or "Outros", "Valor (R$)": float(val)}
            )
        cur.close()
    return result


def _load_verbas_by_name() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT nome_parlamentar,
                   SUM(valor_despesa) AS total,
                   COUNT(*)           AS n,
                   MIN(data_comprovante) AS primeira,
                   MAX(data_comprovante) AS ultima
            FROM cldf_verbas_indenizatorias
            WHERE valor_despesa IS NOT NULL
            GROUP BY nome_parlamentar
            ORDER BY total DESC
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_verbas_detail(nome_parlamentar: str) -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT data_comprovante, classificacao, nome_prestador,
                   valor_despesa, observacoes
            FROM cldf_verbas_indenizatorias
            WHERE nome_parlamentar = %s
            ORDER BY data_comprovante DESC
        """, (nome_parlamentar,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_dodf_all() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT deputado_nome, date_pub::text, gazette_url,
                   LEFT(COALESCE(excerpt, ''), 200) AS excerpt
            FROM cldf_dodf_mentions
            WHERE query_type = 'deputado'
            ORDER BY date_pub DESC
        """)
        cols = ["Deputado", "Data", "URL Gazette", "Trecho"]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_emendas_anos() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ano_emenda,
                   COUNT(*)                AS n,
                   SUM(vl_emenda)          AS proposto,
                   SUM(vl_empenhado)       AS empenhado,
                   SUM(vl_liquidado)       AS liquidado,
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
            LIMIT 12
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


# ─────────────────────────────────────────────
# Layout helpers
# ─────────────────────────────────────────────

def _kv(label: str, value) -> html.Div:
    return html.Div(
        style={"marginBottom": "0.5rem"},
        children=[
            html.Span(label + ": ", style=_S["muted"]),
            html.Span(str(value) if value is not None else "—", style=_S["val"]),
        ],
    )


def _fmt_brl(v) -> str:
    if v is None:
        return "—"
    v = float(v)
    if v >= 1e9:
        return f"R$ {v/1e9:.2f}B"
    if v >= 1e6:
        return f"R$ {v/1e6:.2f}M"
    if v >= 1e3:
        return f"R$ {v/1e3:.0f}k"
    return f"R$ {v:,.0f}"


def _dark_fig(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
        font_color="#cbd5e1", margin=dict(t=30, b=20, l=10, r=10),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"),
    )
    fig.update_xaxes(gridcolor="#1e293b", zerolinecolor="#334155")
    fig.update_yaxes(gridcolor="#1e293b", zerolinecolor="#334155")
    return fig


# ─────────────────────────────────────────────
# Sub-tab: Bancada
# ─────────────────────────────────────────────

def _build_bancada_content() -> html.Div:
    try:
        deps = _load_deputados()
    except Exception as e:
        log.error("Error loading deputados: %s", e)
        return html.Div(f"Erro ao carregar dados: {e}", style=_S["muted"])

    rows = [
        {
            "#": i + 1,
            "Nome": d["nome_candidato"],
            "Partido": d["sigla_partido"],
            "Nº": d["nr_candidato"],
            "Votos": f"{(d['votos_total'] or 0):,}".replace(",", "."),
            "Patrimônio": _fmt_brl(d["total_bens"]),
            "Sexo": d["sexo"] or "—",
            "Raça/Cor": d["cor_raca"] or "—",
            "Instrução": d["grau_instrucao"] or "—",
        }
        for i, d in enumerate(deps)
    ]

    # Party seat distribution chart
    party_counts: dict[str, int] = {}
    for d in deps:
        p = d["sigla_partido"] or "Outros"
        party_counts[p] = party_counts.get(p, 0) + 1
    parties = list(party_counts.keys())
    colors = [PARTY_COLORS.get(p, "#64748b") for p in parties]
    pie = _dark_fig(go.Figure(go.Pie(
        labels=parties,
        values=[party_counts[p] for p in parties],
        marker_colors=colors,
        hole=0.4,
        textinfo="label+value",
    )))
    pie.update_layout(title_text="Cadeiras por Partido", title_font_color="#f8fafc")

    # Vote bar chart (top 12)
    top12 = deps[:12]
    bar = _dark_fig(px.bar(
        x=[d["nome_candidato"] for d in top12],
        y=[d["votos_total"] or 0 for d in top12],
        color=[d["sigla_partido"] for d in top12],
        color_discrete_map=PARTY_COLORS,
        labels={"x": "", "y": "Votos", "color": "Partido"},
    ))
    bar.update_layout(title_text="Top 12 Deputados por Votos", title_font_color="#f8fafc",
                      showlegend=False)
    bar.update_xaxes(tickangle=-35)

    return html.Div([
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "1rem",
                        "marginBottom": "1.2rem"}, children=[
            html.Div(style=_S["card"], children=[dcc.Graph(figure=pie, config={"displayModeBar": False})]),
            html.Div(style=_S["card"], children=[dcc.Graph(figure=bar, config={"displayModeBar": False})]),
        ]),
        html.Div(style=_S["card"], children=[
            html.H3("Bancada Eleita 2022 — 9ª Legislatura", style=_S["h3"]),
            dash_table.DataTable(
                data=rows,
                columns=[{"name": c, "id": c} for c in rows[0].keys()],
                sort_action="native",
                filter_action="native",
                page_size=24,
                **_TABLE_STYLE,
                style_cell_conditional=[
                    {"if": {"column_id": "Nome"}, "minWidth": "180px"},
                ],
            ),
        ]),
    ])


# ─────────────────────────────────────────────
# Sub-tab: Perfil Deputado
# ─────────────────────────────────────────────

def _build_perfil_content(deps: list[dict]) -> html.Div:
    options = [{"label": f"{d['nome_candidato']} ({d['sigla_partido']})",
                "value": str(d["sq_candidato"])} for d in deps]
    return html.Div([
        html.Div(style={"marginBottom": "1rem"}, children=[
            html.Label("Selecionar Deputado:", style=_S["label"]),
            dcc.Dropdown(
                id="cldf-dep-dropdown",
                options=options,
                placeholder="Escolha um deputado...",
                clearable=False,
                style={"width": "360px", "color": "#0f172a"},
            ),
        ]),
        dcc.Loading(
            type="circle",
            children=html.Div(id="cldf-dep-profile", children=[
                html.Div("← Selecione um deputado acima", style={**_S["muted"], "padding": "2rem"}),
            ]),
        ),
    ])


# ─────────────────────────────────────────────
# Sub-tab: Emendas CLDF
# ─────────────────────────────────────────────

def _build_emendas_content() -> html.Div:
    try:
        anos = _load_emendas_anos()
        uo_data = _load_emendas_uo()
    except Exception as e:
        log.error("Error loading emendas: %s", e)
        return html.Div(f"Erro ao carregar emendas: {e}", style=_S["muted"])

    # Stats cards
    total_n = sum(r["n"] or 0 for r in anos)
    total_prop = sum(float(r["proposto"] or 0) for r in anos)
    total_emp = sum(float(r["empenhado"] or 0) for r in anos)

    stats = html.Div(
        style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)", "gap": "0.8rem",
               "marginBottom": "1.2rem"},
        children=[
            html.Div(style=_S["card"], children=[
                html.Div(f"{total_n:,}", style={**_S["accent"], "fontSize": "1.8rem", "fontWeight": "bold"}),
                html.Div("Emendas 2021–2025", style=_S["muted"]),
            ]),
            html.Div(style=_S["card"], children=[
                html.Div(_fmt_brl(total_prop), style={**_S["accent"], "fontSize": "1.8rem", "fontWeight": "bold"}),
                html.Div("Total proposto", style=_S["muted"]),
            ]),
            html.Div(style=_S["card"], children=[
                html.Div(_fmt_brl(total_emp), style={**_S["accent"], "fontSize": "1.8rem", "fontWeight": "bold"}),
                html.Div("Total empenhado", style=_S["muted"]),
            ]),
            html.Div(style=_S["card"], children=[
                html.Div(f"{(total_emp/total_prop*100):.0f}%" if total_prop else "—",
                         style={**_S["accent"], "fontSize": "1.8rem", "fontWeight": "bold"}),
                html.Div("Taxa de execução", style=_S["muted"]),
            ]),
        ],
    )

    # Annual bar chart
    anos_labels = [str(r["ano_emenda"]) for r in anos]
    fig_anos = _dark_fig(go.Figure([
        go.Bar(name="Proposto", x=anos_labels, y=[float(r["proposto"] or 0)/1e6 for r in anos],
               marker_color="#3b82f6"),
        go.Bar(name="Empenhado", x=anos_labels, y=[float(r["empenhado"] or 0)/1e6 for r in anos],
               marker_color="#f59e0b"),
        go.Bar(name="Liquidado", x=anos_labels, y=[float(r["liquidado"] or 0)/1e6 for r in anos],
               marker_color="#10b981"),
    ]))
    fig_anos.update_layout(barmode="group", title_text="Emendas por Ano (R$ milhões)",
                           title_font_color="#f8fafc", legend_font_color="#f8fafc")

    # Top UO chart
    uo_names = [r["nome_uo"][:35] + "…" if r["nome_uo"] and len(r["nome_uo"]) > 35
                else (r["nome_uo"] or "—") for r in uo_data]
    uo_emp = [float(r["empenhado"] or 0)/1e6 for r in uo_data]
    fig_uo = _dark_fig(px.bar(
        x=uo_emp, y=uo_names, orientation="h",
        labels={"x": "Empenhado (R$ M)", "y": ""},
        color=uo_emp, color_continuous_scale="Blues",
    ))
    fig_uo.update_layout(title_text="Top 12 Secretarias / UOs por Empenhado",
                         title_font_color="#f8fafc", coloraxis_showscale=False,
                         height=400)
    fig_uo.update_yaxes(autorange="reversed")

    # Year-by-year table
    table_rows = [
        {
            "Ano": r["ano_emenda"],
            "Emendas": int(r["n"] or 0),
            "Canceladas": int(r["cancelados"] or 0),
            "Proposto": _fmt_brl(r["proposto"]),
            "Empenhado": _fmt_brl(r["empenhado"]),
            "Liquidado": _fmt_brl(r["liquidado"]),
            "Execução %": f"{float(r['empenhado'] or 0)/float(r['proposto'])*100:.0f}%"
            if r["proposto"] else "—",
        }
        for r in anos
    ]

    return html.Div([
        stats,
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "1rem",
                        "marginBottom": "1.2rem"}, children=[
            html.Div(style=_S["card"], children=[dcc.Graph(figure=fig_anos, config={"displayModeBar": False})]),
            html.Div(style=_S["card"], children=[dcc.Graph(figure=fig_uo, config={"displayModeBar": False})]),
        ]),
        html.Div(style=_S["card"], children=[
            html.H3("Resumo por Ano", style=_S["h3"]),
            dash_table.DataTable(
                data=table_rows,
                columns=[{"name": c, "id": c} for c in table_rows[0].keys()],
                sort_action="native",
                **_TABLE_STYLE,
            ),
        ]),
    ])


# ─────────────────────────────────────────────
# Sub-tab: Verbas Indenizatórias
# ─────────────────────────────────────────────

def _build_verbas_content() -> html.Div:
    try:
        verbas = _load_verbas_by_name()
    except Exception as e:
        log.error("Error loading verbas: %s", e)
        return html.Div(f"Erro: {e}", style=_S["muted"])

    # Map to canonical names where possible
    rows = [
        {
            "Parlamentar (DB)": v["nome_parlamentar"],
            "Deputado (mapeado)": VERBAS_NAME_MAP.get(v["nome_parlamentar"], "—"),
            "Total (R$)": _fmt_brl(v["total"]),
            "Comprovantes": int(v["n"] or 0),
            "Primeira": str(v["primeira"]) if v["primeira"] else "—",
            "Última": str(v["ultima"]) if v["ultima"] else "—",
        }
        for v in verbas
    ]

    names = [r["Parlamentar (DB)"] for r in rows]
    vals = [float(v["total"] or 0) / 1e3 for v in verbas]
    fig = _dark_fig(px.bar(
        x=vals, y=names, orientation="h",
        labels={"x": "Total verbas (R$ mil)", "y": ""},
        color=vals, color_continuous_scale="Oranges",
    ))
    fig.update_layout(title_text="Verbas Indenizatórias por Parlamentar (R$ mil)",
                      title_font_color="#f8fafc", coloraxis_showscale=False, height=500)
    fig.update_yaxes(autorange="reversed")

    return html.Div([
        html.Div(style=_S["card"], children=[
            html.P("Total: R$ 29,4M · 1.641 comprovantes · 2022–2024 · fonte: Portal Transparência CLDF",
                   style=_S["muted"]),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ]),
        html.Div(style=_S["card"], children=[
            html.H3("Detalhamento por Parlamentar", style=_S["h3"]),
            html.Div(style={"marginBottom": "1rem"}, children=[
                html.Label("Filtrar por parlamentar para ver detalhes:", style=_S["label"]),
                dcc.Dropdown(
                    id="cldf-verbas-dropdown",
                    options=[{"label": v["nome_parlamentar"], "value": v["nome_parlamentar"]}
                             for v in verbas],
                    placeholder="Selecione...",
                    clearable=True,
                    style={"width": "360px", "color": "#0f172a"},
                ),
            ]),
            dcc.Loading(type="circle", children=html.Div(id="cldf-verbas-detail")),
        ]),
        html.Div(style=_S["card"], children=[
            html.H3("Ranking geral", style=_S["h3"]),
            dash_table.DataTable(
                data=rows,
                columns=[{"name": c, "id": c} for c in rows[0].keys()],
                sort_action="native",
                **_TABLE_STYLE,
                style_cell_conditional=[
                    {"if": {"column_id": "Parlamentar (DB)"}, "minWidth": "250px"},
                ],
            ),
        ]),
    ])


# ─────────────────────────────────────────────
# Sub-tab: DODF
# ─────────────────────────────────────────────

def _build_dodf_content() -> html.Div:
    try:
        dodf = _load_dodf_all()
    except Exception as e:
        log.error("Error loading DODF: %s", e)
        return html.Div(f"Erro: {e}", style=_S["muted"])

    dep_names = sorted({r["Deputado"] for r in dodf if r["Deputado"]})

    stats_by_dep: dict[str, int] = {}
    for r in dodf:
        n = r["Deputado"] or "—"
        stats_by_dep[n] = stats_by_dep.get(n, 0) + 1

    top_dep = sorted(stats_by_dep.items(), key=lambda x: -x[1])
    fig = _dark_fig(px.bar(
        x=[t[1] for t in top_dep[:15]],
        y=[t[0].title() for t in top_dep[:15]],
        orientation="h",
        labels={"x": "Menções DODF", "y": ""},
        color=[t[1] for t in top_dep[:15]],
        color_continuous_scale="Blues",
    ))
    fig.update_layout(title_text="Top 15 Deputados por Menções no DODF",
                      title_font_color="#f8fafc", coloraxis_showscale=False, height=400)
    fig.update_yaxes(autorange="reversed")

    # Prepare table rows (without URL column for display — link it)
    table_rows = []
    for r in dodf:
        url = r["URL Gazette"]
        table_rows.append({
            "Deputado": (r["Deputado"] or "—").title(),
            "Data": r["Data"],
            "Trecho": (r["Trecho"] or "")[:120],
            "Link": url or "—",
        })

    return html.Div([
        html.Div(style={"display": "flex", "gap": "1rem", "marginBottom": "0.5rem",
                        "flexWrap": "wrap", "alignItems": "center"}, children=[
            html.Span(f"{len(dodf)} menções indexadas via Querido Diário API · território 5300108 (Brasília/DF)",
                      style=_S["muted"]),
        ]),
        html.Div(style=_S["card"], children=[dcc.Graph(figure=fig, config={"displayModeBar": False})]),
        html.Div(style=_S["card"], children=[
            html.H3("Feed de Menções — DODF", style=_S["h3"]),
            html.Div(style={"marginBottom": "1rem"}, children=[
                html.Label("Filtrar por deputado:", style=_S["label"]),
                dcc.Dropdown(
                    id="cldf-dodf-dep-filter",
                    options=[{"label": n.title(), "value": n} for n in dep_names],
                    placeholder="Todos os deputados",
                    clearable=True,
                    style={"width": "320px", "color": "#0f172a"},
                ),
            ]),
            dcc.Loading(type="circle", children=html.Div(id="cldf-dodf-table",
                children=[_render_dodf_table(table_rows)])),
        ]),
    ])


def _render_dodf_table(rows: list[dict]) -> html.Div:
    if not rows:
        return html.Div("Nenhuma menção encontrada.", style=_S["muted"])
    return dash_table.DataTable(
        data=rows[:200],
        columns=[{"name": c, "id": c} for c in rows[0].keys()],
        sort_action="native",
        filter_action="native",
        page_size=20,
        **_TABLE_STYLE,
        style_cell_conditional=[
            {"if": {"column_id": "Trecho"}, "minWidth": "300px", "whiteSpace": "normal"},
            {"if": {"column_id": "Link"}, "minWidth": "120px"},
        ],
    )


# ─────────────────────────────────────────────
# Full CLDF tab layout
# ─────────────────────────────────────────────

def build_cldf_tab() -> dcc.Tab:
    """Build and return the CLDF Bancada Distrital dcc.Tab."""
    try:
        deps = _load_deputados()
    except Exception as e:
        log.error("Failed to load deputados for CLDF tab: %s", e)
        deps = []

    inner_tabs = dcc.Tabs(
        style={"marginTop": "1.2rem"},
        children=[
            dcc.Tab(label="Bancada",
                    children=[html.Div(_build_bancada_content(), style={"paddingTop": "1rem"})],
                    style=_S["tab_base"],
                    selected_style={**_S["tab_base"], "backgroundColor": "#f59e0b",
                                    "color": "#0f172a", "fontWeight": "bold"}),
            dcc.Tab(label="Perfil Deputado",
                    children=[html.Div(_build_perfil_content(deps), style={"paddingTop": "1rem"})],
                    style=_S["tab_base"],
                    selected_style={**_S["tab_base"], "backgroundColor": "#f59e0b",
                                    "color": "#0f172a", "fontWeight": "bold"}),
            dcc.Tab(label="Emendas CLDF",
                    children=[html.Div(_build_emendas_content(), style={"paddingTop": "1rem"})],
                    style=_S["tab_base"],
                    selected_style={**_S["tab_base"], "backgroundColor": "#f59e0b",
                                    "color": "#0f172a", "fontWeight": "bold"}),
            dcc.Tab(label="Verbas Indenizatórias",
                    children=[html.Div(_build_verbas_content(), style={"paddingTop": "1rem"})],
                    style=_S["tab_base"],
                    selected_style={**_S["tab_base"], "backgroundColor": "#f59e0b",
                                    "color": "#0f172a", "fontWeight": "bold"}),
            dcc.Tab(label="Diário Oficial (DODF)",
                    children=[html.Div(_build_dodf_content(), style={"paddingTop": "1rem"})],
                    style=_S["tab_base"],
                    selected_style={**_S["tab_base"], "backgroundColor": "#f59e0b",
                                    "color": "#0f172a", "fontWeight": "bold"}),
        ],
    )

    content = html.Div(
        style={
            "backgroundColor": "#1e293b", "borderRadius": "12px",
            "padding": "1.5rem", "marginTop": "2rem",
            "border": "1px solid #334155",
        },
        children=[
            html.Div(style={"display": "flex", "alignItems": "flex-start",
                            "justifyContent": "space-between"}, children=[
                html.Div([
                    html.H2("Câmara Legislativa do DF — Bancada Distrital",
                            style={"color": "#f8fafc", "marginBottom": "0.3rem"}),
                    html.P("9ª Legislatura · 24 deputados eleitos em 2022 · Emendas R$2,9B · "
                           "701 menções DODF · Eleição seguinte: 5 out 2026",
                           style={**_S["muted"], "marginBottom": "0"}),
                ]),
                html.Span("🏛️ CLDF", style={
                    "padding": "0.3rem 0.8rem", "borderRadius": "20px",
                    "background": "#f59e0b", "color": "#0f172a",
                    "fontSize": "0.82rem", "fontWeight": "bold",
                }),
            ]),
            inner_tabs,
        ],
    )

    return dcc.Tab(
        label="🏛️ CLDF Bancada",
        children=[content],
        style={
            "backgroundColor": "#1e293b", "color": "#94a3b8",
            "border": "none", "borderBottom": "1px solid #334155",
        },
        selected_style={
            "backgroundColor": "#f59e0b", "color": "#0f172a",
            "border": "none", "fontWeight": "bold",
        },
    )


# ─────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────

def register_callbacks() -> None:
    """Register all CLDF-tab callbacks. Call once after app is created."""

    @callback(
        Output("cldf-dep-profile", "children"),
        Input("cldf-dep-dropdown", "value"),
        prevent_initial_call=True,
    )
    def update_dep_profile(sq_str):
        """Mostra o perfil completo, patrimônio e menções DODF do deputado selecionado."""
        if not sq_str:
            return html.Div("← Selecione um deputado", style=_S["muted"])
        sq = int(sq_str)
        try:
            deps = _load_deputados()
            dep = next((d for d in deps if d["sq_candidato"] == sq), None)
            if not dep:
                return html.Div("Deputado não encontrado.", style=_S["muted"])
            bens_map = _load_bens()
            bens = bens_map.get(sq, [])
            total_bens = sum(b["Valor (R$)"] for b in bens)

            # DODF for this deputy
            dodf_name = dep["nome_candidato"]
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT date_pub::text, LEFT(COALESCE(excerpt, ''), 200), gazette_url
                    FROM cldf_dodf_mentions
                    WHERE sq_candidato = %s AND query_type = 'deputado'
                    ORDER BY date_pub DESC
                """, (sq,))
                dodf_rows = [{"Data": r[0], "Trecho": r[1], "Link": r[2] or "—"}
                             for r in cur.fetchall()]
                cur.close()

            idade_str = ""
            if dep["data_nascimento"]:
                from datetime import date
                dn = dep["data_nascimento"]
                today = date(2026, 8, 18)
                idade = (today - dn).days // 365
                idade_str = f"{idade} anos"

            profile_card = html.Div(style=_S["card"], children=[
                html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "0.5rem"},
                         children=[
                    _kv("Nome civil", dep["nome_civil"]),
                    _kv("Partido", dep["sigla_partido"]),
                    _kv("Número de urna", dep["nr_candidato"]),
                    _kv("Votos (2022)", f"{dep['votos_total']:,}".replace(",", ".") if dep["votos_total"] else "—"),
                    _kv("Nascimento", f"{dep['data_nascimento']} ({idade_str})" if dep["data_nascimento"] else "—"),
                    _kv("Sexo / Raça", f"{dep['sexo'] or '—'} / {dep['cor_raca'] or '—'}"),
                    _kv("Estado Civil", dep["estado_civil"]),
                    _kv("Instrução", dep["grau_instrucao"]),
                    _kv("Patrimônio declarado (TSE)", _fmt_brl(dep["total_bens"])),
                    _kv("Gasto campanha 1ª volta", _fmt_brl(dep["gasto_campanha"])),
                    _kv("Mandato", "2023–2027 · 9ª Legislatura"),
                    _kv("Menções DODF", f"{len(dodf_rows)} edições"),
                ]),
            ])

            bens_card = html.Div(style=_S["card"], children=[
                html.H3(f"Patrimônio — {len(bens)} itens · {_fmt_brl(total_bens)} total", style=_S["h3"]),
                (dash_table.DataTable(
                    data=bens, columns=[{"name": c, "id": c} for c in bens[0].keys()],
                    sort_action="native", **_TABLE_STYLE,
                    style_cell_conditional=[
                        {"if": {"column_id": "Descrição"}, "minWidth": "250px"},
                    ],
                ) if bens else html.Div("Nenhum bem declarado.", style=_S["muted"])),
            ])

            dodf_card = html.Div(style=_S["card"], children=[
                html.H3(f"Menções no DODF — {len(dodf_rows)} edições", style=_S["h3"]),
                (dash_table.DataTable(
                    data=dodf_rows, columns=[{"name": c, "id": c} for c in dodf_rows[0].keys()],
                    sort_action="native", page_size=15, **_TABLE_STYLE,
                    style_cell_conditional=[
                        {"if": {"column_id": "Trecho"}, "minWidth": "300px", "whiteSpace": "normal"},
                    ],
                ) if dodf_rows else html.Div("Nenhuma menção DODF encontrada.", style=_S["muted"])),
            ])

            return html.Div([profile_card, bens_card, dodf_card])

        except Exception as e:
            log.error("Error rendering profile for sq=%s: %s", sq_str, e)
            return html.Div(f"Erro: {e}", style=_S["muted"])

    @callback(
        Output("cldf-verbas-detail", "children"),
        Input("cldf-verbas-dropdown", "value"),
        prevent_initial_call=True,
    )
    def update_verbas_detail(nome_parlamentar):
        """Mostra comprovantes detalhados de verbas para o parlamentar selecionado."""
        if not nome_parlamentar:
            return html.Div()
        try:
            rows = _load_verbas_detail(nome_parlamentar)
            if not rows:
                return html.Div("Nenhum comprovante encontrado.", style=_S["muted"])
            table_rows = [
                {
                    "Data": str(r["data_comprovante"]) if r["data_comprovante"] else "—",
                    "Classificação": r["classificacao"] or "—",
                    "Prestador": r["nome_prestador"] or "—",
                    "Valor (R$)": f"R$ {float(r['valor_despesa'] or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "Obs": (r["observacoes"] or "")[:60],
                }
                for r in rows
            ]
            total = sum(float(r["valor_despesa"] or 0) for r in rows)
            return html.Div([
                html.Div(style={"marginBottom": "0.6rem"}, children=[
                    html.Span(f"{len(rows)} comprovantes · Total: ", style=_S["muted"]),
                    html.Span(_fmt_brl(total), style=_S["accent"]),
                ]),
                dash_table.DataTable(
                    data=table_rows,
                    columns=[{"name": c, "id": c} for c in table_rows[0].keys()],
                    sort_action="native",
                    filter_action="native",
                    page_size=20,
                    **_TABLE_STYLE,
                ),
            ])
        except Exception as e:
            log.error("Error loading verbas detail: %s", e)
            return html.Div(f"Erro: {e}", style=_S["muted"])

    @callback(
        Output("cldf-dodf-table", "children"),
        Input("cldf-dodf-dep-filter", "value"),
        prevent_initial_call=False,
    )
    def update_dodf_table(dep_filter):
        """Filtra a tabela DODF pelo deputado selecionado."""
        try:
            dodf = _load_dodf_all()
            if dep_filter:
                dodf = [r for r in dodf if r["Deputado"] == dep_filter]
            rows = [{"Deputado": (r["Deputado"] or "—").title(), "Data": r["Data"],
                     "Trecho": (r["Trecho"] or "")[:120], "Link": r["URL Gazette"] or "—"}
                    for r in dodf]
            return _render_dodf_table(rows)
        except Exception as e:
            return html.Div(f"Erro: {e}", style=_S["muted"])
