"""Charts 4, 5, 19 — Fiscal & Geographic analysis."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import query_df
from src.graphs.registry import ControlSpec, register_chart
from src.graphs.theme import TODAS_UFS, aplicar_tema


@register_chart(
    id="custeio_vs_investimento",
    title="4. Custeio vs. Investimento por Região Geográfica",
    description="Distribuição da natureza da despesa (Custeio/Operacional vs. Investimento/Obras) por região do Brasil com filtro de estado.",
    category="Fiscal & Geográfico",
    controls=[
        ControlSpec(
            id="uf_filter", label="Filtrar por Estado (UF)", options=TODAS_UFS, default="TODOS"
        )
    ],
)
def chart_custeio_vs_investimento(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            COALESCE(NULLIF(ibge_regiao, ''), 'Não Informado') as regiao,
            SUM(valor_custeio) as custeio,
            SUM(valor_investimento) as investimento
        FROM v_planos_enriquecidos
        WHERE (%s = 'TODOS' OR parlamentar_uf = %s)
        GROUP BY regiao
        HAVING (SUM(valor_custeio) + SUM(valor_investimento)) > 0
        ORDER BY (SUM(valor_custeio) + SUM(valor_investimento)) DESC;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Nenhum dado encontrado para o filtro selecionado",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "4. Custeio vs. Investimento por Região Geográfica")

    df_melted = df.melt(
        id_vars=["regiao"],
        value_vars=["custeio", "investimento"],
        var_name="Natureza",
        value_name="Valor (R$)",
    )
    df_melted["Natureza"] = df_melted["Natureza"].map(
        {"custeio": "Custeio (Operacional)", "investimento": "Investimento (Obras/Equip.)"}
    )

    fig = px.bar(
        df_melted,
        x="regiao",
        y="Valor (R$)",
        color="Natureza",
        barmode="group",
        color_discrete_map={
            "Custeio (Operacional)": "#38bdf8",
            "Investimento (Obras/Equip.)": "#f59e0b",
        },
        labels={"regiao": "Região Geográfica", "Valor (R$)": "Montante Total (R$)"},
    )
    return aplicar_tema(fig, "4. Custeio vs. Investimento por Região Geográfica")


@register_chart(
    id="taxa_impedimento_objeto",
    title="5. Taxa de Impedimento Técnico e Rejeição por Objeto",
    description="Identifica quais objetos de execução possuem maior índice de impedimento e rejeição.",
    category="Riscos & Impedimentos",
)
def chart_taxa_impedimento_objeto() -> go.Figure:
    query = """
        SELECT
            o.descricao as objeto, COUNT(*) as total_planos,
            SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) as impedidos,
            ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) / COUNT(*), 1) as taxa_impedimento_pct
        FROM planos_acao pa
        JOIN objetos o ON pa.objeto_id = o.objeto_id
        GROUP BY o.descricao
        HAVING COUNT(*) >= 5
        ORDER BY taxa_impedimento_pct DESC LIMIT 15;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Dados insuficientes para calcular taxa de impedimento",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "5. Taxa de Impedimento Técnico por Objeto")

    fig = px.bar(
        df,
        x="taxa_impedimento_pct",
        y="objeto",
        orientation="h",
        text_auto=".1f",
        color="taxa_impedimento_pct",
        color_continuous_scale="Reds",
        labels={"objeto": "Objeto de Execução", "taxa_impedimento_pct": "Impedimento (%)"},
        hover_data=["total_planos", "impedidos"],
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "5. Taxa de Impedimento Técnico e Rejeição por Objeto")


@register_chart(
    id="emendas_vs_compras",
    title="19. Emendas Parlamentares × Compras Públicas por Município",
    description="Cruzamento entre o volume de emendas recebidas e o valor total em licitações/contratos do município.",
    category="Fiscal & Geográfico",
    controls=[
        ControlSpec(
            id="uf_filter", label="Filtrar por Estado (UF)", options=TODAS_UFS, default="TODOS"
        )
    ],
)
def chart_emendas_vs_compras(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio, m.uf,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            COUNT(DISTINCT v.codigo_emenda) AS qtd_emendas,
            COALESCE(cm.valor_total_compras, 0) AS total_compras,
            COALESCE(cm.total_contratos, 0) AS qtd_contratos
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN (
            SELECT municipio_id,
                   SUM(COALESCE(valor_homologado, valor_estimado, 0)) AS valor_total_compras,
                   COUNT(*) FILTER (WHERE tipo_documento = 'CONTRATO') AS total_contratos
            FROM compras_municipios GROUP BY municipio_id
        ) cm ON m.municipio_id = cm.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.nome, m.uf, cm.valor_total_compras, cm.total_contratos
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC LIMIT 40;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de compras públicas disponíveis. Execute o enriquecedor de compras primeiro.",
            showarrow=False,
            font=dict(size=16, color="#64748b"),
        )
        return aplicar_tema(fig, "19. Emendas × Compras Públicas")

    df["ratio"] = df.apply(
        lambda r: (
            r["total_compras"] / r["total_emendas"]
            if r["total_emendas"] > 0 and r["total_compras"] > 0
            else 0
        ),
        axis=1,
    )
    df["status_execucao"] = df["ratio"].apply(
        lambda x: (
            "Alta Execução" if x > 0.5 else ("Execução Parcial" if x > 0.1 else "Baixa Execução")
        ),
    )

    fig = px.scatter(
        df,
        x="total_emendas",
        y="total_compras",
        size="qtd_emendas",
        color="status_execucao",
        hover_name="municipio",
        text="municipio",
        color_discrete_map={
            "Alta Execução": "#22c55e",
            "Execução Parcial": "#f59e0b",
            "Baixa Execução": "#ef4444",
        },
        labels={
            "total_emendas": "Total Emendas Parlamentares (R$)",
            "total_compras": "Total Compras/Contratos (R$)",
            "status_execucao": "Status de Execução",
        },
    )
    fig.update_traces(textposition="top center", textfont_size=9)
    fig.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=max(df["total_emendas"].max(), 1),
        y1=max(df["total_emendas"].max(), 1),
        line=dict(color="#475569", width=1, dash="dash"),
    )
    fig.add_annotation(
        text="Linha de referência: Emendas = Compras",
        x=max(df["total_emendas"].max(), 1) * 0.5,
        y=max(df["total_emendas"].max(), 1) * 0.55,
        showarrow=False,
        font=dict(size=10, color="#64748b"),
    )
    return aplicar_tema(fig, "19. Emendas Parlamentares × Compras Públicas por Município")
