"""Geospatial charts — choropleth maps and geographic visualizations."""

from __future__ import annotations

import json
import os

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, THEME_CARD_BG, THEME_GRID, aplicar_tema

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

GEOJSON_BR_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "brazil_states.json",
)


def _load_brazil_geojson() -> dict:
    """Load Brazil states GeoJSON from data/brazil_states.json."""
    if os.path.exists(GEOJSON_BR_PATH):
        try:
            with open(GEOJSON_BR_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Chart 18a — Emendas Parlamentares por Município (scatter_geo)
# ---------------------------------------------------------------------------

@register_chart(
    id="choropleth_emendas",
    title="18. Mapa Coroplético: Emendas Parlamentares por Município",
    description="Mapa interativo do Brasil com cores representando o volume total de emendas recebidas por município. Pontos maiores = maior valor.",
    category="Geoespacial",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_choropleth_emendas(uf_filter: str = "TODOS") -> go.Figure:
    # Aggregate to UF level for choropleth (municipality lat/lon not in DB)
    query = """
        SELECT
            m.uf,
            COALESCE(SUM(v.valor_total), 0) AS valor_total,
            COUNT(v.codigo_emenda)           AS qtd_emendas,
            COUNT(DISTINCT m.municipio_id)   AS qtd_municipios
        FROM v_emendas_unificadas v
        JOIN municipios_ibge m ON v.beneficiario_ibge = m.municipio_id
        WHERE v.beneficiario_ibge IS NOT NULL
          AND (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.uf
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY valor_total DESC;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados geoespaciais disponíveis para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "18. Mapa Coroplético: Emendas Parlamentares por Município",
        )

    df["uf"] = df["uf"].str.strip().str.upper()
    df["valor_fmt"] = df["valor_total"].apply(lambda x: f"R$ {x:,.0f}".replace(",", "."))

    geojson = _load_brazil_geojson()
    if geojson:
        fig = px.choropleth(
            df,
            geojson=geojson,
            locations="uf",
            featureidkey="properties.sigla",
            color="valor_total",
            color_continuous_scale="Blues",
            hover_name="uf",
            hover_data={
                "valor_total": ":,.0f",
                "qtd_emendas": ":,",
                "qtd_municipios": ":,",
            },
            labels={
                "valor_total": "Valor Total (R$)",
                "qtd_emendas": "Qtd. Emendas",
                "qtd_municipios": "Municípios Beneficiados",
            },
        )
        fig.update_geos(fitbounds="locations", visible=False)
    else:
        # Fallback: bar chart by UF if GeoJSON not available
        fig = px.bar(
            df.sort_values("valor_total", ascending=True),
            x="valor_total", y="uf",
            orientation="h",
            color="valor_total",
            color_continuous_scale="Blues",
            labels={"valor_total": "Valor Total (R$)", "uf": "Estado"},
        )

    fig.update_layout(
        paper_bgcolor=THEME_CARD_BG,
        geo=dict(bgcolor=THEME_CARD_BG),
        coloraxis_colorbar=dict(
            title="Valor (R$)",
            tickfont=dict(color="#f8fafc"),
            title_font=dict(color="#f8fafc"),
        ),
    )

    return aplicar_tema(
        fig, "18. Mapa Coroplético: Emendas Parlamentares por Estado (UF)",
    )




# ---------------------------------------------------------------------------
# Chart 18b — Distribuição de Recursos por Estado (UF)
# ---------------------------------------------------------------------------

@register_chart(
    id="choropleth_valor_total_uf",
    title="18. Mapa Coroplético: Distribuição de Recursos por Estado (UF)",
    description="Mapeamento geográfico coroplético do volume total de investimentos (R$) repassados por estado.",
    category="Geográfico & Mapas",
    controls=[
        ControlSpec(
            id="categoria_gasto",
            label="Categoria de Gasto:",
            options=["TODOS", "CUSTEIO", "INVESTIMENTO"],
            default="TODOS",
        ),
    ],
)
def chart_choropleth_valor_total_uf(
    categoria_gasto: str = "TODOS",
) -> go.Figure:
    geojson_br = _load_brazil_geojson()

    where_clause = "WHERE b.uf IS NOT NULL AND b.uf != ''"
    if categoria_gasto == "CUSTEIO":
        where_clause += " AND p.valor_custeio > 0"
    elif categoria_gasto == "INVESTIMENTO":
        where_clause += " AND p.valor_investimento > 0"

    query = f"""
        SELECT
            b.uf,
            SUM(p.valor_total) AS valor_total,
            COUNT(*) AS total_planos
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        {where_clause}
        GROUP BY b.uf;
    """
    df = query_df(query)

    if df.empty or not geojson_br:
        fig = go.Figure()
        fig.add_annotation(
            text="Mapa GeoJSON ou dados indisponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "18. Mapa Coroplético: Distribuição de Recursos por Estado (UF)",
        )

    fig = px.choropleth(
        df,
        geojson=geojson_br,
        locations="uf",
        featureidkey="properties.sigla",
        color="valor_total",
        color_continuous_scale="Viridis",
        hover_name="uf",
        hover_data={"valor_total": ":,.2f", "total_planos": True},
        labels={
            "valor_total": "Valor Total (R$)",
            "total_planos": "Nº de Planos",
            "uf": "Estado",
        },
    )
    fig.update_geos(fitbounds="locations", visible=False)
    return aplicar_tema(
        fig, "18. Mapa Coroplético: Distribuição de Recursos por Estado (UF)",
    )


# ---------------------------------------------------------------------------
# Chart 19 — Taxa de Impedimento Técnico por Estado
# ---------------------------------------------------------------------------

@register_chart(
    id="choropleth_taxa_impedimento_uf",
    title="19. Mapa Coroplético: Taxa de Impedimento Técnico por Estado",
    description="Mapeamento espacial da porcentagem de recursos impedidos ou rejeitados por UF.",
    category="Geográfico & Mapas",
)
def chart_choropleth_taxa_impedimento_uf() -> go.Figure:
    geojson_br = _load_brazil_geojson()

    query = """
        SELECT
            b.uf,
            COUNT(*) AS total_planos,
            SUM(CASE WHEN p.plano_acao_situacao IN (
                'IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO',
                'REPROVADO', 'CANCELADO'
            ) THEN 1 ELSE 0 END) AS impedidos,
            ROUND(
                100.0 * SUM(CASE WHEN p.plano_acao_situacao IN (
                    'IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO',
                    'REPROVADO', 'CANCELADO'
                ) THEN 1 ELSE 0 END) / COUNT(*),
                2
            ) AS taxa_impedimento
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        WHERE b.uf IS NOT NULL AND b.uf != ''
        GROUP BY b.uf;
    """
    df = query_df(query)

    if df.empty or not geojson_br:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de impedimento não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "19. Mapa Coroplético: Taxa de Impedimento Técnico por Estado",
        )

    fig = px.choropleth(
        df,
        geojson=geojson_br,
        locations="uf",
        featureidkey="properties.sigla",
        color="taxa_impedimento",
        color_continuous_scale="Reds",
        hover_name="uf",
        hover_data={
            "taxa_impedimento": ":.2f",
            "impedidos": True,
            "total_planos": True,
        },
        labels={
            "taxa_impedimento": "Taxa de Impedimento (%)",
            "impedidos": "Planos Impedidos",
            "uf": "Estado",
        },
    )
    fig.update_geos(fitbounds="locations", visible=False)
    return aplicar_tema(
        fig, "19. Mapa Coroplético: Taxa de Impedimento Técnico por Estado",
    )
