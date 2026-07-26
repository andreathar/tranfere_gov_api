"""Charts 8-17 — SICONFI Fiscal (municipal financeiro data)."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, aplicar_tema

# ---------------------------------------------------------------------------
# Chart 8 — Dependência de Emendas Pix vs. Receitas Correntes (%)
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_dependencia_emendas",
    title="8. Dependência de Emendas Pix vs. Receitas Correntes (%)",
    description="Mede o percentual das receitas correntes municipais do SICONFI oriundo de Emendas Pix do TransfereGov.",
    category="SICONFI Fiscal",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        )
    ],
)
def chart_siconfi_dependencia_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            mf.receitas_correntes,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            ROUND(100.0 * COALESCE(SUM(v.valor_total), 0) / NULLIF(mf.receitas_correntes, 0), 2) AS razao_emendas_pct
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        LEFT JOIN beneficiario_ibge_map bm ON m.municipio_id = bm.municipio_id
        LEFT JOIN beneficiarios b ON bm.beneficiario_id = b.beneficiario_id
        LEFT JOIN v_emendas_unificadas v ON b.nome = v.beneficiario_nome
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND mf.receitas_correntes > 0
        GROUP BY m.nome, m.uf, mf.receitas_correntes
        HAVING SUM(v.valor_total) > 0
        ORDER BY razao_emendas_pct DESC
        LIMIT 30;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados suficientes para o estado selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "8. Dependência de Emendas Pix vs. Receitas Correntes (%)")

    fig = px.bar(
        df,
        x="razao_emendas_pct",
        y="municipio",
        orientation="h",
        color="razao_emendas_pct",
        color_continuous_scale="Reds",
        labels={
            "razao_emendas_pct": "Emendas / Receita Corrente (%)",
            "municipio": "Município",
        },
        hover_data=["receitas_correntes", "total_emendas"],
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "8. Dependência de Emendas Pix vs. Receitas Correntes (%)")


# ---------------------------------------------------------------------------
# Chart 9 — Saldo Fiscal Estimado vs. Volume de Emendas
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_resultado_primario_emendas",
    title="9. Saldo Fiscal Estimado (Receita - Despesa) vs. Volume de Emendas",
    description="Compara o saldo fiscal dos municípios SICONFI (Receitas Totais minus Despesas Totais) com o volume de repasses do TransfereGov.",
    category="SICONFI Fiscal",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        )
    ],
)
def chart_siconfi_resultado_primario(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            ((mf.receitas_correntes + mf.receitas_capital) - (mf.despesas_correntes + mf.despesas_capital)) AS saldo_fiscal,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        LEFT JOIN beneficiario_ibge_map bm ON m.municipio_id = bm.municipio_id
        LEFT JOIN beneficiarios b ON bm.beneficiario_id = b.beneficiario_id
        LEFT JOIN v_emendas_unificadas v ON b.nome = v.beneficiario_nome
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND (mf.receitas_correntes + mf.receitas_capital) > 0
        GROUP BY m.nome, m.uf, mf.receitas_correntes, mf.receitas_capital,
                 mf.despesas_correntes, mf.despesas_capital
        HAVING SUM(v.valor_total) > 0
        ORDER BY total_emendas DESC
        LIMIT 40;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados fiscais para o estado selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "9. Saldo Fiscal Estimado (Receita - Despesa) vs. Volume de Emendas"
        )

    df["status_saldo"] = df["saldo_fiscal"].apply(
        lambda x: "Superávit Fiscal" if x >= 0 else "Déficit Fiscal",
    )

    fig = px.scatter(
        df,
        x="saldo_fiscal",
        y="total_emendas",
        size="total_emendas",
        color="status_saldo",
        hover_name="municipio",
        color_discrete_map={"Superávit Fiscal": "#22c55e", "Déficit Fiscal": "#ef4444"},
        labels={
            "saldo_fiscal": "Saldo Fiscal Estimado (R$)",
            "total_emendas": "Total em Emendas (R$)",
        },
    )
    return aplicar_tema(fig, "9. Saldo Fiscal Estimado (Receita - Despesa) vs. Volume de Emendas")


# ---------------------------------------------------------------------------
# Chart 10 — Capacidade de Investimento Próprio vs. Emendas TransfereGov
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_autonomia_fiscal",
    title="10. Capacidade de Investimento Próprio vs. Emendas TransfereGov",
    description="Mapeia quanto o município investe com recursos próprios (Despesas de Capital SICONFI) versus o montante recebido via Emendas.",
    category="SICONFI Fiscal",
)
def chart_siconfi_autonomia_fiscal() -> go.Figure:
    query = """
        SELECT
            m.regiao,
            m.uf,
            m.nome AS municipio,
            mf.despesas_capital AS investimento_siconfi,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        LEFT JOIN beneficiario_ibge_map bm ON m.municipio_id = bm.municipio_id
        LEFT JOIN beneficiarios b ON bm.beneficiario_id = b.beneficiario_id
        LEFT JOIN v_emendas_unificadas v ON b.nome = v.beneficiario_nome
        WHERE mf.despesas_capital > 0
        GROUP BY m.regiao, m.uf, m.nome, mf.despesas_capital
        HAVING SUM(v.valor_total) > 0
        ORDER BY investimento_siconfi DESC
        LIMIT 50;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de investimento não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "10. Capacidade de Investimento Próprio vs. Emendas TransfereGov")

    fig = px.scatter(
        df,
        x="investimento_siconfi",
        y="total_emendas",
        size="total_emendas",
        color="regiao",
        hover_name="municipio",
        labels={
            "investimento_siconfi": "Investimentos SICONFI (Despesas de Capital R$)",
            "total_emendas": "Total em Emendas TransfereGov (R$)",
        },
    )
    return aplicar_tema(fig, "10. Capacidade de Investimento Próprio vs. Emendas TransfereGov")


# ---------------------------------------------------------------------------
# Chart 11 — Perfil de Gasto Municipal: Custeio vs. Investimento
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_custeio_vs_investimento",
    title="11. Perfil de Gasto Municipal: Custeio vs. Investimento (SICONFI)",
    description="Comparativo entre Despesas Correntes (manutenção/pessoal) e Despesas de Capital (obras/investimentos).",
    category="SICONFI Fiscal",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        )
    ],
)
def chart_siconfi_custeio_vs_investimento(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            mf.despesas_correntes,
            mf.despesas_capital
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND mf.despesas_correntes > 0
        ORDER BY (mf.despesas_correntes + mf.despesas_capital) DESC
        LIMIT 25;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de despesas não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "11. Perfil de Gasto Municipal: Custeio vs. Investimento (SICONFI)"
        )

    df_melt = df.melt(
        id_vars=["municipio"],
        value_vars=["despesas_correntes", "despesas_capital"],
        var_name="Tipo",
        value_name="Valor",
    )
    df_melt["Tipo"] = df_melt["Tipo"].map(
        {
            "despesas_correntes": "Despesas Correntes (Custeio)",
            "despesas_capital": "Despesas de Capital (Investimento)",
        }
    )

    fig = px.bar(
        df_melt,
        x="Valor",
        y="municipio",
        color="Tipo",
        orientation="h",
        color_discrete_map={
            "Despesas Correntes (Custeio)": "#3b82f6",
            "Despesas de Capital (Investimento)": "#10b981",
        },
        labels={"Valor": "Despesas (R$)", "municipio": "Município"},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "11. Perfil de Gasto Municipal: Custeio vs. Investimento (SICONFI)")


# ---------------------------------------------------------------------------
# Chart 12 — Despesa Corrente Municipal (Custeio) por Região
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_divida_per_capita",
    title="12. Despesa Corrente Municipal (Custeio) por Região",
    description="Compara o volume total de despesas correntes executadas por município agrupado por região.",
    category="SICONFI Fiscal",
)
def chart_siconfi_divida_per_capita() -> go.Figure:
    query = """
        SELECT
            m.regiao,
            m.nome AS municipio,
            m.uf,
            mf.despesas_correntes
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.despesas_correntes > 0
        ORDER BY mf.despesas_correntes DESC
        LIMIT 50;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de despesa não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "12. Despesa Corrente Municipal (Custeio) por Região")

    fig = px.box(
        df,
        x="regiao",
        y="despesas_correntes",
        color="regiao",
        points="all",
        hover_name="municipio",
        labels={
            "despesas_correntes": "Despesas Correntes (R$)",
            "regiao": "Região Geográfica",
        },
    )
    return aplicar_tema(fig, "12. Despesa Corrente Municipal (Custeio) por Região")


# ---------------------------------------------------------------------------
# Chart 13 — Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_patrimonio_vs_passivo",
    title="13. Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente",
    description="Avalia a folga orçamentária (Receita Corrente minus Despesa Corrente) das principais prefeituras.",
    category="SICONFI Fiscal",
)
def chart_siconfi_patrimonio_vs_passivo() -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            m.regiao,
            mf.receitas_correntes,
            mf.despesas_correntes,
            (mf.receitas_correntes - mf.despesas_correntes) AS superavit_corrente
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes > 0 AND mf.despesas_correntes > 0
        ORDER BY mf.receitas_correntes DESC
        LIMIT 40;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados orçamentários não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(
            fig, "13. Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente"
        )

    fig = px.scatter(
        df,
        x="receitas_correntes",
        y="despesas_correntes",
        size="receitas_correntes",
        color="regiao",
        hover_name="municipio",
        labels={
            "receitas_correntes": "Receitas Correntes (R$)",
            "despesas_correntes": "Despesas Correntes (R$)",
        },
    )
    return aplicar_tema(fig, "13. Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente")


# ---------------------------------------------------------------------------
# Chart 14 — Top 20 Maiores Arrecadações Correntes Municipais
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_top20_receita",
    title="14. Top 20 Maiores Arrecadações Correntes Municipais",
    description="Ranking das 20 maiores receitas correntes municipais consolidadas no SICONFI.",
    category="SICONFI Fiscal",
)
def chart_siconfi_top20_receita() -> go.Figure:
    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            mf.receitas_correntes,
            mf.despesas_correntes
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes > 0
        ORDER BY mf.receitas_correntes DESC
        LIMIT 20;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de receita",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "14. Top 20 Maiores Arrecadações Correntes Municipais")

    fig = px.bar(
        df,
        x="receitas_correntes",
        y="municipio_uf",
        orientation="h",
        text_auto=".2s",
        color="receitas_correntes",
        color_continuous_scale="Blues",
        labels={
            "receitas_correntes": "Receita Corrente Total (R$)",
            "municipio_uf": "Município",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "14. Top 20 Maiores Arrecadações Correntes Municipais")


# ---------------------------------------------------------------------------
# Chart 15 — Saldo Fiscal Estimado por Região
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_resultado_por_regiao",
    title="15. Saldo Fiscal Estimado (Receita - Despesa) por Região",
    description="Distribuição do saldo fiscal municipal (Receitas Totais minus Despesas Totais) por região geográfica.",
    category="SICONFI Fiscal",
)
def chart_siconfi_resultado_por_regiao() -> go.Figure:
    query = """
        SELECT
            m.regiao,
            ((mf.receitas_correntes + mf.receitas_capital) - (mf.despesas_correntes + mf.despesas_capital)) AS saldo_fiscal
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE (mf.receitas_correntes + mf.receitas_capital) > 0;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de saldo fiscal não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "15. Saldo Fiscal Estimado (Receita - Despesa) por Região")

    fig = px.violin(
        df,
        x="regiao",
        y="saldo_fiscal",
        color="regiao",
        box=True,
        points=False,
        labels={
            "saldo_fiscal": "Saldo Fiscal Estimado (R$)",
            "regiao": "Região Geográfica",
        },
    )
    return aplicar_tema(fig, "15. Saldo Fiscal Estimado (Receita - Despesa) por Região")


# ---------------------------------------------------------------------------
# Chart 16 — Vulnerabilidade Fiscal: Alta Dependência de Repasses
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_ranking_vulnerabilidade",
    title="16. Vulnerabilidade Fiscal: Alta Dependência de Repasses",
    description="Municípios com maior razão entre receitas de transferências externas e arrecadação própria.",
    category="SICONFI Fiscal",
)
def chart_siconfi_ranking_vulnerabilidade() -> go.Figure:
    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            mf.receitas_correntes,
            mf.receitas_transferencias,
            ROUND(100.0 * mf.receitas_transferencias / NULLIF(mf.receitas_correntes, 0), 1) AS dependencia_transferencias_pct
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.receitas_correntes > 1000000
        ORDER BY dependencia_transferencias_pct DESC
        LIMIT 25;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de transferências não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "16. Vulnerabilidade Fiscal: Alta Dependência de Repasses")

    fig = px.bar(
        df,
        x="dependencia_transferencias_pct",
        y="municipio_uf",
        orientation="h",
        color="dependencia_transferencias_pct",
        color_continuous_scale="Purples",
        labels={
            "dependencia_transferencias_pct": "Dependência de Transferências (%)",
            "municipio_uf": "Município",
        },
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "16. Vulnerabilidade Fiscal: Alta Dependência de Repasses")


# ---------------------------------------------------------------------------
# Chart 17 — Perfil Médio de Despesas Orçamentárias por UF
# ---------------------------------------------------------------------------


@register_chart(
    id="siconfi_despesas_faixa_populacional",
    title="17. Perfil Médio de Despesas Orçamentárias por UF",
    description="Volume médio de despesas correntes executadas pelos municípios agregados por estado.",
    category="SICONFI Fiscal",
)
def chart_siconfi_despesas_uf() -> go.Figure:
    query = """
        SELECT
            m.uf,
            AVG(mf.despesas_correntes) AS media_despesas_correntes,
            AVG(mf.despesas_capital) AS media_despesas_capital
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        GROUP BY m.uf
        ORDER BY media_despesas_correntes DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados de despesas não disponíveis",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "17. Perfil Médio de Despesas Orçamentárias por UF")

    df_melt = df.melt(
        id_vars=["uf"],
        value_vars=["media_despesas_correntes", "media_despesas_capital"],
        var_name="Tipo",
        value_name="Valor",
    )
    df_melt["Tipo"] = df_melt["Tipo"].map(
        {
            "media_despesas_correntes": "Média Despesas Correntes",
            "media_despesas_capital": "Média Despesas de Capital",
        }
    )

    fig = px.bar(
        df_melt,
        x="uf",
        y="Valor",
        color="Tipo",
        barmode="group",
        labels={"Valor": "Média de Despesa (R$)", "uf": "Estado (UF)"},
    )
    return aplicar_tema(fig, "17. Perfil Médio de Despesas Orçamentárias por UF")
