"""Charts 40-44 — Módulo de Inteligência Política e Cruzamentos Tríplices (Deputados x Prefeitos x Vereadores)."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, aplicar_tema


# ---------------------------------------------------------------------------
# Chart 40 — Dinastias Políticas: Emendas PIX para Prefeitos com Sobrenome Coincidente
# ---------------------------------------------------------------------------
@register_chart(
    id="dinastias_politicas_emendas",
    title="40. Dinastias Políticas: Repasses PIX para Prefeitos Parentes/Sobrenome",
    description="Ranking de repasses de emendas PIX em municípios onde o Deputado e o Prefeito eleito possuem o mesmo sobrenome.",
    category="Inteligência Política",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por UF",
            options=["TODAS"] + TODAS_UFS,
            default="TODAS",
        ),
    ],
)
def chart_dinastias_politicas_emendas(uf_filter: str = "TODAS") -> go.Figure:
    params = (uf_filter, uf_filter)
    query = """
        SELECT
            deputado_nome,
            partido_deputado,
            uf,
            municipio_nome,
            prefeito_nome,
            partido_prefeito,
            sobrenome_comum,
            total_emendas_brl
        FROM v_dinastias_politicas
        WHERE (%s = 'TODAS' OR uf = %s)
        ORDER BY total_emendas_brl DESC
        LIMIT 20;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhuma dinastia política encontrada para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "40. Dinastias Políticas: Repasses PIX para Prefeitos Parentes/Sobrenome",
            altura=550,
        )

    df["hover_info"] = (
        "<b>Deputado:</b> "
        + df["deputado_nome"]
        + " ("
        + df["partido_deputado"]
        + ")<br>"
        + "<b>Prefeito:</b> "
        + df["prefeito_nome"]
        + " ("
        + df["partido_prefeito"]
        + ")<br>"
        + "<b>Município:</b> "
        + df["municipio_nome"]
        + " - "
        + df["uf"]
        + "<br>"
        + "<b>Sobrenome:</b> "
        + df["sobrenome_comum"]
    )

    fig = px.bar(
        df,
        x="total_emendas_brl",
        y="deputado_nome",
        color="partido_deputado",
        orientation="h",
        custom_data=["hover_info"],
        labels={
            "total_emendas_brl": "Volume de Emendas PIX (R$)",
            "deputado_nome": "Deputado Federal",
        },
    )
    fig.update_traces(
        hovertemplate="%{custom_data[0]}<br><b>Total PIX:</b> R$ %{x:,.2f}<extra></extra>"
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})

    return aplicar_tema(
        fig, "40. Dinastias Políticas: Repasses PIX para Prefeitos Parentes/Sobrenome", altura=550
    )


# ---------------------------------------------------------------------------
# Chart 41 — O Triângulo Político: Domínio Municipal (Deputado + Prefeito + Vereadores)
# ---------------------------------------------------------------------------
@register_chart(
    id="triangulo_politico_municipios",
    title="41. Triângulo Político: Domínio Municipal Deputado-Prefeito-Bancada",
    description="Identifica feudos políticos locais onde o Deputado, o Prefeito e a maioria dos Vereadores eleitos pertencem ao mesmo partido.",
    category="Inteligência Política",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por UF",
            options=["TODAS"] + TODAS_UFS,
            default="TODAS",
        ),
    ],
)
def chart_triangulo_politico_municipios(uf_filter: str = "TODAS") -> go.Figure:
    params = (uf_filter, uf_filter)
    query = """
        SELECT
            deputado_nome,
            partido_deputado,
            municipio_nome,
            uf,
            prefeito_nome,
            partido_prefeito,
            relacao_partidaria_prefeito,
            vereadores_eleitos_partido_dep,
            total_emendas_brl
        FROM v_triangulo_politico
        WHERE (%s = 'TODAS' OR uf = %s)
          AND relacao_partidaria_prefeito = 'MESMO PARTIDO'
        ORDER BY vereadores_eleitos_partido_dep DESC, total_emendas_brl DESC
        LIMIT 20;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum triângulo político encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "41. Triângulo Político: Domínio Municipal Deputado-Prefeito-Bancada", altura=550
        )

    fig = px.scatter(
        df,
        x="vereadores_eleitos_partido_dep",
        y="total_emendas_brl",
        size="total_emendas_brl",
        color="partido_deputado",
        hover_name="deputado_nome",
        hover_data={
            "municipio_nome": True,
            "prefeito_nome": True,
            "partido_deputado": True,
            "total_emendas_brl": ":,.2f",
        },
        labels={
            "vereadores_eleitos_partido_dep": "Vereadores Eleitos do Mesmo Partido",
            "total_emendas_brl": "Total de Emendas PIX Repassadas (R$)",
            "partido_deputado": "Partido",
        },
    )

    return aplicar_tema(
        fig, "41. Triângulo Político: Domínio Municipal Deputado-Prefeito-Bancada", altura=550
    )


# ---------------------------------------------------------------------------
# Chart 42 — Taxa de Endogamia Partidária (% Fisiologismo no Repasse)
# ---------------------------------------------------------------------------
@register_chart(
    id="endogamia_partidaria_deputados",
    title="42. Taxa de Endogamia Partidária: Verba PIX para Correligionários vs Oposição",
    description="Mede a porcentagem da verba PIX de cada deputado canalizada estritamente para prefeitos do seu próprio partido.",
    category="Inteligência Política",
    controls=[
        ControlSpec(
            id="partido_filter",
            label="Filtrar por Partido",
            options=["TODOS", "PL", "PT", "PP", "UNIÃO", "PSD", "MDB", "REPUBLICANOS", "PODE"],
            default="TODOS",
        ),
    ],
)
def chart_endogamia_partidaria_deputados(partido_filter: str = "TODOS") -> go.Figure:
    params = (partido_filter, partido_filter)
    query = """
        WITH resumo_partidario AS (
            SELECT
                deputado_nome,
                partido_deputado,
                SUM(CASE WHEN relacao_partidaria_prefeito = 'MESMO PARTIDO' THEN total_emendas_brl ELSE 0 END) AS verba_mesmo_partido,
                SUM(CASE WHEN relacao_partidaria_prefeito <> 'MESMO PARTIDO' THEN total_emendas_brl ELSE 0 END) AS verba_outros_partidos,
                SUM(total_emendas_brl) AS verba_total
            FROM v_triangulo_politico
            WHERE (%s = 'TODOS' OR partido_deputado = %s)
            GROUP BY deputado_nome, partido_deputado
            HAVING SUM(total_emendas_brl) > 2000000
        )
        SELECT
            deputado_nome,
            partido_deputado,
            verba_mesmo_partido,
            verba_outros_partidos,
            verba_total,
            ROUND((verba_mesmo_partido / verba_total * 100)::numeric, 1) AS pct_endogamia
        FROM resumo_partidario
        ORDER BY pct_endogamia DESC, verba_total DESC
        LIMIT 25;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "42. Taxa de Endogamia Partidária: Verba PIX para Correligionários vs Oposição",
            altura=550,
        )

    fig = px.bar(
        df,
        x="pct_endogamia",
        y="deputado_nome",
        color="partido_deputado",
        orientation="h",
        hover_data={"verba_mesmo_partido": ":,.2f", "verba_total": ":,.2f", "pct_endogamia": True},
        labels={
            "pct_endogamia": "% Verba PIX para Prefeitos do Mesmo Partido",
            "deputado_nome": "Deputado Federal",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})

    return aplicar_tema(
        fig,
        "42. Taxa de Endogamia Partidária: Verba PIX para Correligionários vs Oposição",
        altura=550,
    )


# ---------------------------------------------------------------------------
# Chart 43 — Eficiência Social do Repasse (Emendas PIX vs Leitos SUS / Finanças)
# ---------------------------------------------------------------------------
@register_chart(
    id="emendas_vs_desempenho_municipal",
    title="43. Eficiência do Repasse: Emendas PIX vs Leitos SUS & Indicadores Locais",
    description="Cruza a destinação de emendas PIX com a capacidade de infraestrutura de saúde (Leitos SUS por mil hab.) do município receptor.",
    category="Inteligência Política",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por UF",
            options=["TODAS"] + TODAS_UFS,
            default="TODAS",
        ),
    ],
)
def chart_emendas_vs_desempenho_municipal(uf_filter: str = "TODAS") -> go.Figure:
    params = (uf_filter, uf_filter)
    query = """
        SELECT
            b.nome AS municipio,
            b.uf,
            pr.prefeito_nome,
            pr.sigla_partido AS partido_prefeito,
            COALESCE(s.leitos_sus, 0) AS leitos_sus,
            COALESCE(m.populacao, 1) AS populacao,
            ROUND((COALESCE(s.leitos_sus, 0)::numeric / NULLIF(m.populacao, 0) * 1000), 2) AS leitos_por_mil,
            SUM(pa.valor_total) AS total_emendas_brl
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN prefeitos_dados pr ON bm.municipio_id = pr.municipio_id
        LEFT JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN saude_municipios s ON bm.municipio_id = s.municipio_id
        WHERE (%s = 'TODAS' OR b.uf = %s)
        GROUP BY b.nome, b.uf, pr.prefeito_nome, pr.sigla_partido, s.leitos_sus, m.populacao
        HAVING SUM(pa.valor_total) > 1000000
        ORDER BY total_emendas_brl DESC
        LIMIT 50;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "43. Eficiência do Repasse: Emendas PIX vs Leitos SUS & Indicadores Locais",
            altura=550,
        )

    fig = px.scatter(
        df,
        x="leitos_por_mil",
        y="total_emendas_brl",
        size="populacao",
        color="partido_prefeito",
        hover_name="municipio",
        hover_data={
            "prefeito_nome": True,
            "leitos_sus": True,
            "populacao": ":,",
            "total_emendas_brl": ":,.2f",
        },
        labels={
            "leitos_por_mil": "Leitos SUS por 1.000 Habitantes",
            "total_emendas_brl": "Total de Emendas PIX Recebidas (R$)",
            "partido_prefeito": "Partido do Prefeito",
        },
    )

    return aplicar_tema(
        fig,
        "43. Eficiência do Repasse: Emendas PIX vs Leitos SUS & Indicadores Locais",
        altura=550,
    )


# ---------------------------------------------------------------------------
# Chart 44 — Transferência de Capital Eleitoral (Deputado x Bancada de Vereadores)
# ---------------------------------------------------------------------------
@register_chart(
    id="reciprocidade_eleitoral_bancada",
    title="44. Transferência de Capital Eleitoral: Emendas PIX vs Bancada de Vereadores",
    description="Visualiza o volume de recursos alocados pelo deputado em relação à força numérica da sua bancada de vereadores aliados no município.",
    category="Inteligência Política",
    controls=[
        ControlSpec(
            id="partido_filter",
            label="Filtrar por Partido",
            options=["TODOS", "PL", "PT", "PP", "UNIÃO", "PSD", "MDB", "REPUBLICANOS", "PODE"],
            default="TODOS",
        ),
    ],
)
def chart_reciprocidade_eleitoral_bancada(partido_filter: str = "TODOS") -> go.Figure:
    params = (partido_filter, partido_filter)
    query = """
        SELECT
            deputado_nome,
            partido_deputado,
            municipio_nome,
            uf,
            vereadores_eleitos_partido_dep,
            total_emendas_brl
        FROM v_triangulo_politico
        WHERE (%s = 'TODOS' OR partido_deputado = %s)
          AND vereadores_eleitos_partido_dep > 0
        ORDER BY total_emendas_brl DESC
        LIMIT 35;
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig,
            "44. Transferência de Capital Eleitoral: Emendas PIX vs Bancada de Vereadores",
            altura=550,
        )

    fig = px.bar(
        df,
        x="municipio_nome",
        y="total_emendas_brl",
        color="vereadores_eleitos_partido_dep",
        hover_name="deputado_nome",
        hover_data={"partido_deputado": True, "uf": True, "vereadores_eleitos_partido_dep": True},
        labels={
            "municipio_nome": "Município Receptor",
            "total_emendas_brl": "Total PIX (R$)",
            "vereadores_eleitos_partido_dep": "Nº Vereadores Eleitos do Partido",
        },
    )
    fig.update_layout(xaxis={"categoryorder": "total descending"})

    return aplicar_tema(
        fig,
        "44. Transferência de Capital Eleitoral: Emendas PIX vs Bancada de Vereadores",
        altura=550,
    )
