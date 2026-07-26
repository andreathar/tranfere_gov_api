"""Charts 26-28 — Hierarchical visualizations: sunburst, treemap, sankey."""

from __future__ import annotations

import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import (
    CORES_SITUACAO,
    TODAS_UFS,
    THEME_CARD_BG,
    THEME_GRID,
    THEME_TEXT,
    aplicar_tema,
)


# ---------------------------------------------------------------------------
# Chart 26 — Hierarquia de Recursos: Região → UF → Parlamentar
# ---------------------------------------------------------------------------

@register_chart(
    id="sunburst_drilldown_recursos",
    title="26. Hierarquia de Recursos: Região → UF → Parlamentar",
    description=(
        "Visualização sunburst com drill-down hierárquico: Região → UF → "
        "Parlamentar, mostrando a distribuição do volume de emendas."
    ),
    category="Hierárquico",
    controls=[
        ControlSpec(
            id="ano_filter",
            label="Filtrar por Ano",
            options=["TODOS", "2024", "2025", "2026"],
            default="TODOS",
        ),
    ],
)
def chart_sunburst_drilldown_recursos(ano_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...]
    if ano_filter != "TODOS":
        params = (ano_filter, ano_filter)
    else:
        params = (ano_filter, "9999")

    query = """
        SELECT
            COALESCE(mibge.regiao, 'Sem Região')          AS regiao,
            COALESCE(b.uf, 'XX')                            AS uf,
            COALESCE(pd.sigla_partido, 'IND')               AS sigla_partido,
            v.parlamentar_nome,
            SUM(v.valor_total)                              AS total_emendas
        FROM v_emendas_unificadas v
        LEFT JOIN beneficiarios b
            ON v.beneficiario_nome = b.nome
        LEFT JOIN beneficiario_ibge_map bibge
            ON b.beneficiario_id = bibge.beneficiario_id
        LEFT JOIN municipios_ibge mibge
            ON bibge.municipio_id = mibge.municipio_id
        LEFT JOIN parlamentares_dados pd
            ON v.parlamentar_nome ILIKE CONCAT('%%', pd.nome_urna, '%%')
        WHERE v.parlamentar_nome IS NOT NULL
          AND (%s = 'TODOS' OR v.ano = %s::INTEGER)
        GROUP BY
            COALESCE(mibge.regiao, 'Sem Região'),
            COALESCE(b.uf, 'XX'),
            COALESCE(pd.sigla_partido, 'IND'),
            v.parlamentar_nome
        HAVING SUM(v.valor_total) > 0
        ORDER BY total_emendas DESC;
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
            fig, "26. Hierarquia de Recursos: Região → UF → Parlamentar",
            altura=550,
        )

    fig = go.Figure(
        go.Sunburst(
            ids=df.apply(
                lambda r: f"{r['regiao']}/{r['uf']}/{r['parlamentar_nome']}",
                axis=1,
            ).tolist(),
            labels=df.apply(
                lambda r: (
                    r["parlamentar_nome"]
                    if r["regiao"] != "Sem Região"
                    else r["regiao"]
                ),
                axis=1,
            ).tolist(),
            parents=df.apply(
                lambda r: (
                    f"{r['regiao']}/{r['uf']}"
                    if r["regiao"] != "Sem Região" and r["uf"] != "XX"
                    else r["regiao"]
                    if r["regiao"] != "Sem Região"
                    else ""
                ),
                axis=1,
            ).tolist(),
            values=df["total_emendas"].tolist(),
            branchvalues="remainder",
            maxdepth=3,
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Valor: R$ %{value:,.2f}<br>"
                "<extra></extra>"
            ),
            marker=dict(
                colorscale="Viridis",
                line=dict(width=1, color=THEME_CARD_BG),
            ),
            textfont=dict(size=11, color=THEME_TEXT),
            insidetextorientation="radial",
        )
    )

    return aplicar_tema(
        fig, "26. Hierarquia de Recursos: Região → UF → Parlamentar",
        altura=550,
    )


# ---------------------------------------------------------------------------
# Chart 27 — Composição de Investimentos por Objeto
# ---------------------------------------------------------------------------

@register_chart(
    id="treemap_investimentos_objetos",
    title="27. Composição de Investimentos por Objeto",
    description=(
        "Treemap mostrando a composição do volume de investimentos agrupados "
        "por Região → UF → Objeto de execução."
    ),
    category="Hierárquico",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_treemap_investimentos_objetos(
    uf_filter: str = "TODOS",
) -> go.Figure:
    params: tuple[str, ...]
    if uf_filter != "TODOS":
        params = (uf_filter, uf_filter)
    else:
        params = (uf_filter, "XX")

    query = """
        SELECT
            COALESCE(mibge.regiao, 'Sem Região')   AS regiao,
            COALESCE(b.uf, 'XX')                     AS uf,
            COALESCE(o.descricao, 'Objeto Desconhecido') AS objeto_nome,
            SUM(v.valor_total)                       AS total_emendas
        FROM v_emendas_unificadas v
        LEFT JOIN beneficiarios b
            ON v.beneficiario_nome = b.nome
        LEFT JOIN beneficiario_ibge_map bibge
            ON b.beneficiario_id = bibge.beneficiario_id
        LEFT JOIN municipios_ibge mibge
            ON bibge.municipio_id = mibge.municipio_id
        LEFT JOIN objetos o
            ON v.objeto = o.objeto_id::TEXT
        WHERE (%s = 'TODOS' OR b.uf = %s)
        GROUP BY
            COALESCE(mibge.regiao, 'Sem Região'),
            COALESCE(b.uf, 'XX'),
            COALESCE(o.descricao, 'Objeto Desconhecido')
        HAVING SUM(v.valor_total) > 0
        ORDER BY total_emendas DESC;
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
            fig, "27. Composição de Investimentos por Objeto",
            altura=550,
        )

    # Build proper hierarchical treemap with region/UF parent nodes
    REGIAO_CORES = {
        "Norte": "#0ea5e9",
        "Nordeste": "#f59e0b",
        "Sudeste": "#22c55e",
        "Sul": "#a855f7",
        "Centro-Oeste": "#ef4444",
        "Sem Região": "#64748b",
    }

    ids: list[str] = []
    labels: list[str] = []
    parents: list[str] = []
    values: list[float] = []
    colors: list[str] = []

    # Add root-level region nodes
    for regiao in df["regiao"].unique():
        cor = REGIAO_CORES.get(regiao, "#475569")
        ids.append(regiao)
        labels.append(regiao)
        parents.append("")
        values.append(0)
        colors.append(cor)

        # Add UF nodes under each region
        ufs_regiao = df[df["regiao"] == regiao]["uf"].unique()
        for uf in ufs_regiao:
            uf_id = f"{regiao}/{uf}"
            ids.append(uf_id)
            labels.append(uf)
            parents.append(regiao)
            values.append(0)
            colors.append(cor)

    # Add leaf object nodes
    for _, row in df.iterrows():
        cor = REGIAO_CORES.get(row["regiao"], "#475569")
        obj_id = f"{row['regiao']}/{row['uf']}/{row['objeto_nome']}"
        ids.append(obj_id)
        labels.append(row["objeto_nome"])
        parents.append(f"{row['regiao']}/{row['uf']}")
        values.append(float(row["total_emendas"]))
        colors.append(cor)

    fig = go.Figure(
        go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="remainder",
            textinfo="label+value+percent parent",
            texttemplate="<b>%{label}</b><br>R$ %{value:,.0f}<br>%{percentParent:.1%}",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Valor: R$ %{value:,.2f}<br>"
                "Proporção: %{percentParent:.1%}<br>"
                "<extra></extra>"
            ),
            marker=dict(
                colors=colors,
                line=dict(width=1.5, color=THEME_CARD_BG),
            ),
            textfont=dict(size=12, color=THEME_TEXT),
        )
    )

    return aplicar_tema(
        fig, "27. Composição de Investimentos por Objeto",
        altura=600,
    )


# ---------------------------------------------------------------------------
# Chart 28 — Fluxo Financeiro: Parlamentar → Beneficiário → Status
# ---------------------------------------------------------------------------

@register_chart(
    id="sankey_fluxo_financeiro",
    title="28. Fluxo Financeiro: Parlamentar → Beneficiário → Status",
    description=(
        "Diagrama Sankey mostrando o fluxo de recursos dos parlamentares "
        "para os beneficiários e o status final de cada plano de ação."
    ),
    category="Hierárquico",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS",
        ),
    ],
)
def chart_sankey_fluxo_financeiro(uf_filter: str = "TODOS") -> go.Figure:
    params: tuple[str, ...]
    if uf_filter != "TODOS":
        params = (uf_filter, uf_filter)
    else:
        params = (uf_filter, "XX")

    query = """
        SELECT
            v.parlamentar_nome,
            v.beneficiario_nome,
            v.status_execucao,
            SUM(v.valor_total) AS total_emendas
        FROM v_emendas_unificadas v
        LEFT JOIN beneficiarios b
            ON v.beneficiario_nome = b.nome
        WHERE v.parlamentar_nome IS NOT NULL
          AND v.beneficiario_nome IS NOT NULL
          AND v.status_execucao IS NOT NULL
          AND (%s = 'TODOS' OR b.uf = %s)
        GROUP BY v.parlamentar_nome, v.beneficiario_nome, v.status_execucao
        HAVING SUM(v.valor_total) > 0
        ORDER BY total_emendas DESC
        LIMIT 200;
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
            "28. Fluxo Financeiro: Parlamentar → Beneficiário → Status",
            altura=600,
        )

    # --- Build unique node labels and indices ---
    parlamentares = df["parlamentar_nome"].unique().tolist()
    beneficiarios = df["beneficiario_nome"].unique().tolist()
    situacoes = df["status_execucao"].unique().tolist()

    # Node list: parliamentarians first, then beneficiaries, then situations
    nodes = parlamentares + beneficiarios + situacoes
    node_index = {label: i for i, label in enumerate(nodes)}

    # Node colors
    node_colors = (
        ["#22c55e"] * len(parlamentares)     # green for parliamentarians
        + ["#3b82f6"] * len(beneficiarios)   # blue for beneficiaries
        + [CORES_SITUACAO.get(s, "#64748b") for s in situacoes]
    )

    # --- Build links ---
    sources: list[int] = []
    targets: list[int] = []
    values: list[float] = []
    link_colors: list[str] = []

    for _, row in df.iterrows():
        p_idx = node_index[row["parlamentar_nome"]]
        b_idx = node_index[row["beneficiario_nome"]]
        s_idx = node_index[row["status_execucao"]]
        valor = float(row["total_emendas"])

        # Link: Parlamentar → Beneficiário
        sources.append(p_idx)
        targets.append(b_idx)
        values.append(valor)
        link_colors.append("rgba(34, 197, 94, 0.35)")

        # Link: Beneficiário → Situação
        sources.append(b_idx)
        targets.append(s_idx)
        values.append(valor)
        situacao_color = CORES_SITUACAO.get(row["status_execucao"], "#64748b")
        # Convert hex to rgba
        hex_c = situacao_color.lstrip("#")
        r, g, b_c = int(hex_c[:2], 16), int(hex_c[2:4], 16), int(hex_c[4:], 16)
        link_colors.append(f"rgba({r}, {g}, {b_c}, 0.35)")

    fig = go.Figure(
        go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color=THEME_CARD_BG, width=0.5),
                label=[n[:30] + "…" if len(n) > 30 else n for n in nodes],
                color=node_colors,
                hovertemplate="<b>%{label}</b><br>Total: R$ %{value:,.2f}<extra></extra>",
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=link_colors,
                hovertemplate=(
                    "%{source.label} → %{target.label}<br>"
                    "Valor: R$ %{value:,.2f}<extra></extra>"
                ),
            ),
        )
    )

    return aplicar_tema(
        fig,
        "28. Fluxo Financeiro: Parlamentar → Beneficiário → Status",
        altura=600,
    )
