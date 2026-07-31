"""Charts 31-35 — Governadores Estaduais: Emendas, Alinhamento, Triângulo Político, Financeiro e Partidos."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, aplicar_tema

# ---------------------------------------------------------------------------
# Chart 31 — Ranking de Estados por Captação de Emendas Pix
# ---------------------------------------------------------------------------


@register_chart(
    id="ranking_estados_emendas",
    title="31. Ranking de Estados por Captação de Emendas Pix",
    description=(
        "Volume total de emendas Pix recebidas em cada UF, com governador e partido. "
        "Cruza planos_acao com beneficiarios.uf e governadores_dados."
    ),
    category="Governadores",
    controls=[
        ControlSpec(
            id="limit",
            label="Nº de Estados",
            options=["10", "15", "20", "27"],
            default="27",
        ),
    ],
)
def chart_ranking_estados_emendas(limit: str = "27") -> go.Figure:
    n = int(limit)
    query = """
        SELECT
            g.uf,
            g.nome_governador,
            g.sigla_partido,
            COALESCE(e.total_emendas, 0)     AS total_emendas,
            COALESCE(e.valor_total, 0)       AS valor_total
        FROM governadores_dados g
        LEFT JOIN (
            SELECT b.uf,
                   COUNT(*)     AS total_emendas,
                   SUM(pa.valor_total) AS valor_total
            FROM planos_acao pa
            JOIN beneficiarios b ON b.beneficiario_id = pa.beneficiario_id
            GROUP BY b.uf
        ) e ON e.uf = g.uf
        ORDER BY valor_total DESC NULLS LAST
        LIMIT %s
    """
    df = query_df(query, (n,))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "31. Ranking de Estados por Captação de Emendas Pix")

    df["label"] = df["uf"] + " — " + df["nome_governador"] + " (" + df["sigla_partido"] + ")"
    chart_height = max(500, len(df) * 35)

    fig = px.bar(
        df,
        x="valor_total",
        y="label",
        orientation="h",
        color="valor_total",
        color_continuous_scale=["#1e293b", "#22d3ee", "#22c55e"],
        text_auto=".3s",
        labels={
            "valor_total": "Valor Total (R$)",
            "label": "UF — Governador (Partido)",
            "total_emendas": "Qtd. Emendas",
            "sigla_partido": "Partido",
        },
        hover_data=["total_emendas", "sigla_partido"],
        template="plotly_dark",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=chart_height)
    fig.update_traces(textposition="outside")

    return aplicar_tema(
        fig, "31. Ranking de Estados por Captação de Emendas Pix", altura=chart_height
    )


# ---------------------------------------------------------------------------
# Chart 32 — Alinhamento Governador × Bancada Federal
# ---------------------------------------------------------------------------


@register_chart(
    id="alinhamento_governador_bancada",
    title="32. Alinhamento Governador × Bancada Federal",
    description=(
        "Percentual de deputados federais da bancada da UF que são do mesmo partido "
        "do governador eleito. Indicador de força política e governabilidade."
    ),
    category="Governadores",
)
def chart_alinhamento_governador_bancada() -> go.Figure:
    query = """
        SELECT
            g.uf,
            g.nome_governador,
            g.sigla_partido,
            COUNT(pd.deputado_id) AS total_deputados,
            COUNT(pd.deputado_id) FILTER (WHERE pd.sigla_partido = g.sigla_partido) AS aliados,
            ROUND(
                100.0 * COUNT(pd.deputado_id) FILTER (WHERE pd.sigla_partido = g.sigla_partido)
                / NULLIF(COUNT(pd.deputado_id), 0), 1
            ) AS pct_aliados
        FROM governadores_dados g
        LEFT JOIN parlamentares_dados pd ON pd.uf = g.uf
        GROUP BY g.uf, g.nome_governador, g.sigla_partido
        ORDER BY pct_aliados DESC NULLS LAST
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado disponível",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "32. Alinhamento Governador × Bancada Federal")

    df["label"] = df["uf"] + " — " + df["nome_governador"] + " (" + df["sigla_partido"] + ")"
    chart_height = max(500, len(df) * 35)

    fig = px.bar(
        df,
        x="pct_aliados",
        y="label",
        orientation="h",
        color="pct_aliados",
        color_continuous_scale=["#ef4444", "#f97316", "#22c55e"],
        text_auto=".1f",
        labels={
            "pct_aliados": "% Aliados na Bancada",
            "label": "UF — Governador (Partido)",
            "aliados": "Dep. Aliados",
            "total_deputados": "Total Deputados",
        },
        hover_data=["aliados", "total_deputados", "sigla_partido"],
        template="plotly_dark",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=chart_height)
    fig.update_traces(
        texttemplate="%{x}%",
        textposition="outside",
    )

    return aplicar_tema(fig, "32. Alinhamento Governador × Bancada Federal", altura=chart_height)


# ---------------------------------------------------------------------------
# Chart 33 — Triângulo Político (Deputado × Prefeito × Governador)
# ---------------------------------------------------------------------------


@register_chart(
    id="triangulo_politico_uf",
    title="33. Triângulo Político por UF",
    description=(
        "Cruzamento entre deputados federais, prefeitos e governador por UF. "
        "Mostra deputados com mesmo partido do prefeito e/ou governador, "
        "revelando redes de alinhamento político-fisiológico."
    ),
    category="Governadores",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_triangulo_politico_uf(uf_filter: str = "TODOS") -> go.Figure:
    where = "WHERE vtp.uf = %s" if uf_filter != "TODOS" else ""
    params = (uf_filter,) if uf_filter != "TODOS" else ()

    query = f"""
        SELECT
            vtp.deputado_nome,
            vtp.partido_deputado,
            vtp.uf,
            vtp.municipio_nome,
            vtp.prefeito_nome,
            vtp.partido_prefeito,
            vtp.relacao_partidaria_prefeito,
            vtp.total_emendas_brl,
            g.nome_governador,
            g.sigla_partido AS partido_governador,
            (vtp.partido_deputado = g.sigla_partido) AS aliado_governador,
            CASE
                WHEN vtp.relacao_partidaria_prefeito = 'MESMO_PARTIDO'
                     AND vtp.partido_deputado = g.sigla_partido THEN 'Aliado Total'
                WHEN vtp.relacao_partidaria_prefeito = 'MESMO_PARTIDO' THEN 'Aliado Prefeito'
                WHEN vtp.partido_deputado = g.sigla_partido THEN 'Aliado Governador'
                ELSE 'Independente'
            END AS alinhamento
        FROM v_triangulo_politico vtp
        LEFT JOIN governadores_dados g ON g.uf = vtp.uf
        {where}
        ORDER BY vtp.total_emendas_brl DESC NULLS LAST
        LIMIT 50
    """
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "33. Triângulo Político por UF")

    color_map = {
        "Aliado Total": "#22c55e",
        "Aliado Governador": "#3b82f6",
        "Aliado Prefeito": "#f97316",
        "Independente": "#64748b",
    }

    df["label"] = df["deputado_nome"] + " (" + df["partido_deputado"] + ")"
    chart_height = max(500, len(df) * 30)

    fig = px.bar(
        df,
        x="total_emendas_brl",
        y="label",
        color="alinhamento",
        orientation="h",
        color_discrete_map=color_map,
        text_auto=".3s",
        labels={
            "total_emendas_brl": "Total Emendas (R$)",
            "label": "Deputado (Partido)",
            "alinhamento": "Alinhamento",
            "municipio_nome": "Município",
            "prefeito_nome": "Prefeito",
            "partido_prefeito": "Partido Prefeito",
        },
        hover_data=[
            "uf",
            "municipio_nome",
            "prefeito_nome",
            "partido_prefeito",
            "partido_governador",
        ],
        template="plotly_dark",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=chart_height)
    fig.update_traces(textposition="outside")

    return aplicar_tema(fig, "33. Triângulo Político por UF", altura=chart_height)


# ---------------------------------------------------------------------------
# Chart 34 — Financeiro SICONFI dos Estados (Receitas × Despesas)
# ---------------------------------------------------------------------------


@register_chart(
    id="financeiro_estados_siconfi",
    title="34. Financeiro SICONFI dos Estados",
    description=(
        "Comparação de receitas correntes, despesas totais e resultado primário "
        "dos estados (agregado via SICONFI/municipios_financeiro). "
        "Indicadores fiscais agregados por UF."
    ),
    category="Governadores",
)
def chart_financeiro_estados_siconfi() -> go.Figure:
    query = """
        SELECT
            mi.uf,
            SUM(mf.receitas_correntes) AS receitas_correntes,
            SUM(mf.despesas_totais) AS despesas_totais,
            SUM(mf.resultado_primario) AS resultado_primario,
            SUM(mf.arrec_cota_icms) AS icms_arrecadado,
            SUM(mf.arrec_cota_fpm) AS fpm_recebido,
            SUM(mf.arrec_impostos_geral) AS arrecadacao_total,
            MAX(mf.exercicio) AS ultimo_exercicio
        FROM municipios_financeiro mf
        JOIN municipios_ibge mi ON mi.municipio_id = mf.municipio_id
        GROUP BY mi.uf
        ORDER BY receitas_correntes DESC
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado financeiro disponível",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "34. Financeiro SICONFI dos Estados")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Receitas Correntes",
            x=df["uf"],
            y=df["receitas_correntes"],
            marker_color="#22c55e",
            hovertemplate="UF: %{x}<br>Receitas: R$ %{y:,.0f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            name="Despesas Totais",
            x=df["uf"],
            y=df["despesas_totais"],
            marker_color="#ef4444",
            hovertemplate="UF: %{x}<br>Despesas: R$ %{y:,.0f}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Resultado Primário",
            x=df["uf"],
            y=df["resultado_primario"],
            mode="lines+markers",
            line=dict(color="#fbbf24", width=3),
            marker=dict(size=8),
            yaxis="y2",
            hovertemplate="UF: %{x}<br>Resultado: R$ %{y:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="group",
        xaxis=dict(title="UF", tickangle=-45),
        yaxis=dict(title="R$ (Receitas/Despesas)", tickformat=",.0f"),
        yaxis2=dict(
            title="R$ (Resultado Primário)",
            overlaying="y",
            side="right",
            tickformat=",.0f",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
        template="plotly_dark",
    )

    chart_height = 500
    return aplicar_tema(fig, "34. Financeiro SICONFI dos Estados", altura=chart_height)


# ---------------------------------------------------------------------------
# Chart 35 — Distribuição Partidária dos Governadores
# ---------------------------------------------------------------------------


@register_chart(
    id="distribuicao_partidaria_governadores",
    title="35. Distribuição Partidária dos Governadores",
    description=(
        "Gráfico de pizza/rosquinha mostrando a distribuição dos 27 governadores "
        "por partido político. Quantos estados cada partido governa."
    ),
    category="Governadores",
)
def chart_distribuicao_partidaria_governadores() -> go.Figure:
    query = """
        SELECT sigla_partido, COUNT(*) AS total
        FROM governadores_dados
        GROUP BY sigla_partido
        ORDER BY total DESC
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado disponível",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "35. Distribuição Partidária dos Governadores")

    fig = go.Figure(
        data=[
            go.Pie(
                labels=df["sigla_partido"],
                values=df["total"],
                hole=0.4,
                textinfo="label+percent",
                textposition="outside",
                marker=dict(
                    colors=px.colors.qualitative.D3,
                    line=dict(color="#1e293b", width=2),
                ),
                hovertemplate="<b>%{label}</b><br>%{value} governadores (%{percent})<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        uniformtext_minsize=10,
        uniformtext_mode="hide",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
        ),
        template="plotly_dark",
    )

    chart_height = 500
    return aplicar_tema(fig, "35. Distribuição Partidária dos Governadores", altura=chart_height)


# ---------------------------------------------------------------------------
# Chart 36 — Governadores: Emendas por Partido
# ---------------------------------------------------------------------------


@register_chart(
    id="governadores_emendas_por_partido",
    title="36. Volume de Emendas por Partido do Governador",
    description=(
        "Volume total de emendas Pix recebidas nas UFs, agrupado pelo partido "
        "do governador. Mostra quais legendas têm maior poder de captação de "
        "recursos."
    ),
    category="Governadores",
)
def chart_governadores_emendas_por_partido() -> go.Figure:
    query = """
        SELECT
            g.sigla_partido,
            COUNT(DISTINCT g.uf) AS total_estados,
            COUNT(e.id) AS total_emendas,
            COALESCE(SUM(e.valor_total), 0) AS valor_total
        FROM governadores_dados g
        LEFT JOIN beneficiarios b ON b.uf = g.uf
        LEFT JOIN planos_acao e ON e.beneficiario_id = b.beneficiario_id
        GROUP BY g.sigla_partido
        HAVING COALESCE(SUM(e.valor_total), 0) > 0
        ORDER BY valor_total DESC
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado disponível",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "36. Volume de Emendas por Partido do Governador")

    fig = px.bar(
        df,
        x="sigla_partido",
        y="valor_total",
        color="sigla_partido",
        color_discrete_sequence=px.colors.qualitative.D3,
        text_auto=".3s",
        labels={
            "sigla_partido": "Partido do Governador",
            "valor_total": "Total Emendas (R$)",
            "total_estados": "Estados",
            "total_emendas": "Qtd. Emendas",
        },
        hover_data=["total_estados", "total_emendas"],
        template="plotly_dark",
    )
    fig.update_traces(textposition="outside")

    chart_height = 450
    return aplicar_tema(
        fig, "36. Volume de Emendas por Partido do Governador", altura=chart_height
    )
