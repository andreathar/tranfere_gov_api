#!/usr/bin/env python3
"""
TransfereGov — Graph Factory & Chart Registry.

Estrutura ultra-intuitiva para criação e registro de novos gráficos Plotly.
Qualquer novo gráfico registrado via @register_chart() é automaticamente:
 1. Adicionado à interface web interativa do Dash.
 2. Exposto como ferramenta MCP no endpoint /_mcp para IAs.
 3. Estilizado com o tema Dark Slate padrão do sistema.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.db_utils import get_connection

# ---------------------------------------------------------------------------
# DESIGN TOKENS
# ---------------------------------------------------------------------------
THEME_CARD_BG = "#1e293b"
THEME_TEXT = "#f8fafc"
THEME_GRID = "#334155"

# Lista completa de UFs brasileiras (27 estados + TODOS)
TODAS_UFS = ["TODOS", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
             "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ",
             "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]

CORES_SITUACAO = {
    "CIENTE": "#3b82f6",
    "IMPEDIDO": "#ef4444",
    "IMPEDIDO_REJEICAO_PLANO_TRABALHO": "#f97316",
    "REPROVADO": "#a855f7",
    "CANCELADO": "#64748b",
    "EM_EXECUCAO": "#22c55e",
    "CONCLUIDO": "#10b981",
    "NAO_CUMPROU": "#475569",
}

def aplicar_tema(fig: go.Figure, titulo: str, altura: int = 450) -> go.Figure:
    """Aplica o tema Dark Slate padrão do sistema."""
    fig.update_layout(
        title={"text": f"<b>{titulo}</b>", "y": 0.95, "x": 0.02, "xanchor": "left", "font": {"size": 16, "color": THEME_TEXT}},
        paper_bgcolor=THEME_CARD_BG,
        plot_bgcolor=THEME_CARD_BG,
        font={"family": "Inter, sans-serif", "color": THEME_TEXT},
        height=altura,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(bgcolor="rgba(15, 23, 42, 0.7)", bordercolor="#475569", borderwidth=1, font=dict(color=THEME_TEXT, size=11))
    )
    fig.update_xaxes(gridcolor=THEME_GRID, zerolinecolor=THEME_GRID, tickfont=dict(color=THEME_TEXT))
    fig.update_yaxes(gridcolor=THEME_GRID, zerolinecolor=THEME_GRID, tickfont=dict(color=THEME_TEXT))
    return fig



def query_df(sql: str, params: Any | None = None) -> pd.DataFrame:
    """Executa consulta SQL via psycopg2 e retorna um DataFrame do pandas com tipos numéricos convertidos."""
    with get_connection() as conn, conn.cursor() as cur:
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        if cur.description:
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=cols)
            for col in df.columns:
                if df[col].dtype == "object":
                    converted = pd.to_numeric(df[col], errors="coerce")
                    if not converted.isna().all():
                        df[col] = converted
            return df
        return pd.DataFrame()





# ---------------------------------------------------------------------------
# ESTRUTURA DO REGISTRY DE GRÁFICOS
# ---------------------------------------------------------------------------
@dataclass
class ControlSpec:
    id: str
    label: str
    options: list[str]
    default: str

@dataclass
class ChartSpec:
    id: str
    title: str
    description: str
    category: str
    builder: Callable[..., go.Figure]
    controls: list[ControlSpec] = field(default_factory=list)

# Registro global de gráficos
CHART_REGISTRY: dict[str, ChartSpec] = {}

def register_chart(
    id: str,
    title: str,
    description: str,
    category: str = "Geral",
    controls: list[ControlSpec] | None = None
):
    """
    Decorador intuitivo para registrar um novo gráfico Plotly.
    
    Exemplo de uso:
    
    @register_chart(
        id="meu_novo_grafico",
        title="Meu Novo Gráfico",
        description="Descrição explicativa para a IA e para o usuário.",
        category="Finanças",
        controls=[ControlSpec(id="uf", label="Filtrar por UF", options=["TODOS", "SP", "RJ"], default="TODOS")]
    )
    def build_chart(uf="TODOS"):
        ...
        return fig
    """
    def decorator(fn: Callable[..., go.Figure]):
        spec = ChartSpec(
            id=id,
            title=title,
            description=description,
            category=category,
            builder=fn,
            controls=controls or []
        )
        CHART_REGISTRY[id] = spec
        return fn
    return decorator


# ---------------------------------------------------------------------------
# DEFINIÇÃO DOS GRÁFICOS DO SISTEMA (FÁCIL DE EXPANDIR!)
# ---------------------------------------------------------------------------

@register_chart(
    id="eficiencia_partidos",
    title="1. Eficiência na Execução de Emendas por Partido",
    description="Proporção do volume de emendas aprovadas/concluídas vs impedidas por partido político.",
    category="Parlamentar",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS"
        )
    ]
)
def chart_eficiencia_partidos(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT 
            p.sigla_partido,
            v.status_execucao,
            COUNT(*) as total_planos,
            SUM(v.valor_total) as valor_total
        FROM v_emendas_unificadas v
        JOIN parlamentares_dados p ON v.parlamentar_nome ILIKE CONCAT('%%', p.nome_urna, '%%')
        WHERE (%s = 'TODOS' OR p.uf = %s)
        GROUP BY p.sigla_partido, v.status_execucao
        ORDER BY valor_total DESC
        LIMIT 50;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Nenhum dado encontrado para o filtro selecionado", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "1. Eficiência na Execução de Emendas por Partido")

    fig = px.bar(
        df,
        x="sigla_partido",
        y="valor_total",
        color="status_execucao",
        title="1. Eficiência na Execução de Emendas por Partido",
        color_discrete_map=CORES_SITUACAO,
        labels={"sigla_partido": "Partido", "valor_total": "Valor Total (R$)", "status_execucao": "Situação"}
    )
    return aplicar_tema(fig, "1. Eficiência na Execução de Emendas por Partido")


@register_chart(
    id="top_parlamentares_valores",
    title="2. Top 15 Deputados por Volume de Emendas",
    description="Ranking dos deputados com maior montante em emendas parlamentares aprovadas.",
    category="Parlamentar"
)
def chart_top_parlamentares() -> go.Figure:
    query = """
        SELECT 
            parlamentar_nome,
            SUM(valor_total) as valor_total,
            COUNT(*) as qtd_emendas
        FROM v_emendas_unificadas
        WHERE parlamentar_nome IS NOT NULL
        GROUP BY parlamentar_nome
        ORDER BY valor_total DESC
        LIMIT 15;
    """
    df = query_df(query)
    df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0.0)

    fig = px.bar(
        df,
        x="valor_total",
        y="parlamentar_nome",
        orientation="h",
        text_auto=".2s",
        color="valor_total",
        color_continuous_scale="Viridis",
        labels={"parlamentar_nome": "Deputado", "valor_total": "Valor Total (R$)"}
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "2. Top 15 Deputados por Volume de Emendas")


@register_chart(
    id="socioeconomico_idhm",
    title="3. Relação IDHM Municipal vs. Volume de Emendas",
    description="Mapeamento de investimentos: verifica se os repasses beneficiam municípios com menor IDHM.",
    category="Socioeconômico"
)
def chart_socioeconomico_idhm() -> go.Figure:
    query = """
        SELECT 
            m.nome AS municipio,
            m.uf,
            bm.municipio_id,
            SUM(v.valor_total) AS valor_total,
            COUNT(v.codigo_emenda) AS total_emendas
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        GROUP BY m.nome, m.uf, bm.municipio_id
        ORDER BY valor_total DESC
        LIMIT 30;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados de IDHM / IBGE em processamento", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "3. Relação IDHM Municipal vs. Volume de Emendas")

    fig = px.scatter(
        df,
        x="total_emendas",
        y="valor_total",
        size="valor_total",
        color="uf",
        hover_name="municipio",
        labels={"total_emendas": "Quantidade de Emendas", "valor_total": "Valor Total (R$)", "uf": "Estado"}
    )
    return aplicar_tema(fig, "3. Relação IDHM Municipal vs. Volume de Emendas")


@register_chart(
    id="custeio_vs_investimento",
    title="4. Custeio vs. Investimento por Região Geográfica",
    description="Distribuição da natureza da despesa (Custeio/Operacional vs. Investimento/Obras) por região do Brasil com filtro de estado.",
    category="Fiscal & Geográfico",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS"
        )
    ]
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
        fig.add_annotation(text="Nenhum dado encontrado para o filtro selecionado", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "4. Custeio vs. Investimento por Região Geográfica")

    df_melted = df.melt(id_vars=["regiao"], value_vars=["custeio", "investimento"], var_name="Natureza", value_name="Valor (R$)")
    df_melted["Natureza"] = df_melted["Natureza"].map({"custeio": "Custeio (Operacional)", "investimento": "Investimento (Obras/Equip.)"})

    fig = px.bar(
        df_melted,
        x="regiao",
        y="Valor (R$)",
        color="Natureza",
        barmode="group",
        color_discrete_map={
            "Custeio (Operacional)": "#38bdf8",
            "Investimento (Obras/Equip.)": "#f59e0b"
        },
        labels={"regiao": "Região Geográfica", "Valor (R$)": "Montante Total (R$)"}
    )
    return aplicar_tema(fig, "4. Custeio vs. Investimento por Região Geográfica")


@register_chart(
    id="taxa_impedimento_objeto",
    title="5. Taxa de Impedimento Técnico e Rejeição por Objeto",
    description="Identifica quais objetos de execução (Saúde, Turismo, Infraestrutura) possuem maior índice de impedimento e rejeição.",
    category="Riscos & Impedimentos"
)
def chart_taxa_impedimento_objeto() -> go.Figure:
    query = """
        SELECT 
            o.descricao as objeto,
            COUNT(*) as total_planos,
            SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) as impedidos,
            ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) / COUNT(*), 1) as taxa_impedimento_pct
        FROM planos_acao pa
        JOIN objetos o ON pa.objeto_id = o.objeto_id
        GROUP BY o.descricao
        HAVING COUNT(*) >= 5
        ORDER BY taxa_impedimento_pct DESC
        LIMIT 15;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados insuficientes para calcular taxa de impedimento", showarrow=False, font=dict(size=16, color="#64748b"))
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
        hover_data=["total_planos", "impedidos"]
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "5. Taxa de Impedimento Técnico e Rejeição por Objeto")


@register_chart(
    id="investimento_per_capita_idhm",
    title="6. Repasse Per Capita (R$/hab) vs. IDHM Municipal",
    description="Análise demográfica de equidade fiscal: mede a proporção do investimento por habitante em relação ao IDHM do município.",
    category="Socioeconômico",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS"
        )
    ]
)
def chart_investimento_per_capita(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT 
            municipio_nome,
            COALESCE(NULLIF(ibge_regiao, ''), 'Outros') as regiao,
            ibge_populacao,
            ibge_idhm,
            SUM(valor_total) as valor_total,
            ROUND(SUM(valor_total) / NULLIF(ibge_populacao, 0), 2) as valor_per_capita
        FROM v_planos_enriquecidos
        WHERE ibge_populacao IS NOT NULL AND ibge_populacao > 0
          AND (%s = 'TODOS' OR ibge_regiao = %s)
        GROUP BY municipio_nome, regiao, ibge_populacao, ibge_idhm
        HAVING SUM(valor_total) > 0
        ORDER BY valor_per_capita DESC
        LIMIT 40;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados demográficos suficientes para esta região", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "6. Repasse Per Capita (R$/hab) vs. IDHM Municipal")

    df["regiao"] = df["regiao"].astype(str).fillna("Não Informado")
    fig = px.scatter(
        df,
        x="ibge_idhm",
        y="valor_per_capita",
        size="valor_total",
        hover_name="municipio_nome",
        hover_data=["ibge_populacao", "valor_total"],
        labels={"ibge_idhm": "IDHM (Índice de Desenv. Humano)", "valor_per_capita": "Valor Per Capita (R$/hab)", "regiao": "Região"}
    )
    return aplicar_tema(fig, "6. Repasse Per Capita (R$/hab) vs. IDHM Municipal")


@register_chart(
    id="impedimentos_por_partido",
    title="7. Matriz de Risco: Volume Total vs. Taxa de Rejeição por Partido",
    description="Cruzamento entre a quantidade total alocada por partido e sua respectiva taxa de impedimento técnico/rejeição.",
    category="Análise Parlamentar"
)
def chart_impedimentos_por_partido() -> go.Figure:
    query = """
        SELECT 
            COALESCE(pd.sigla_partido, 'OUTROS') as partido,
            COUNT(*) as total_planos,
            SUM(pa.valor_total) as valor_total,
            SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) as impedidos,
            ROUND(100.0 * SUM(CASE WHEN pa.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO') THEN 1 ELSE 0 END) / COUNT(*), 1) as taxa_impedimento_pct
        FROM planos_acao pa
        JOIN parlamentares_dados pd ON pa.parlamentar_nome ILIKE CONCAT('%%', pd.nome_urna, '%%')
        GROUP BY pd.sigla_partido
        HAVING COUNT(*) >= 10
        ORDER BY valor_total DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados de partidos não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "7. Matriz de Risco: Volume Total vs. Taxa de Rejeição por Partido")

    fig = px.scatter(
        df,
        x="valor_total",
        y="taxa_impedimento_pct",
        size="total_planos",
        color="taxa_impedimento_pct",
        text="partido",
        color_continuous_scale="OrRd",
        labels={"valor_total": "Volume Total Alocado (R$)", "taxa_impedimento_pct": "Taxa de Impedimento (%)", "partido": "Partido"},
        hover_data=["total_planos", "impedidos"]
    )
    fig.update_traces(textposition="top center", marker=dict(sizeref=2.0 * max(df["total_planos"]) / (40**2), sizemin=8))
    return aplicar_tema(fig, "7. Matriz de Risco: Volume Total vs. Taxa de Rejeição por Partido")


# ---------------------------------------------------------------------------
# NOVOS GRÁFICOS SICONFI (DADOS FINANCEIROS MUNICIPAIS DE 5.561 CIDADES)
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
            default="TODOS"
        )
    ]
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
        fig.add_annotation(text="Sem dados suficientes para o estado selecionado", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "8. Dependência de Emendas Pix vs. Receitas Correntes (%)")

    fig = px.bar(
        df,
        x="razao_emendas_pct",
        y="municipio",
        orientation="h",
        color="razao_emendas_pct",
        color_continuous_scale="Reds",
        labels={"razao_emendas_pct": "Emendas / Receita Corrente (%)", "municipio": "Município"},
        hover_data=["receitas_correntes", "total_emendas"]
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "8. Dependência de Emendas Pix vs. Receitas Correntes (%)")


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
            default="TODOS"
        )
    ]
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
        GROUP BY m.nome, m.uf, mf.receitas_correntes, mf.receitas_capital, mf.despesas_correntes, mf.despesas_capital
        HAVING SUM(v.valor_total) > 0
        ORDER BY total_emendas DESC
        LIMIT 40;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem dados fiscais para o estado selecionado", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "9. Saldo Fiscal Estimado (Receita - Despesa) vs. Volume de Emendas")

    df["status_saldo"] = df["saldo_fiscal"].apply(lambda x: "Superávit Fiscal" if x >= 0 else "Déficit Fiscal")

    fig = px.scatter(
        df,
        x="saldo_fiscal",
        y="total_emendas",
        size="total_emendas",
        color="status_saldo",
        hover_name="municipio",
        color_discrete_map={"Superávit Fiscal": "#22c55e", "Déficit Fiscal": "#ef4444"},
        labels={"saldo_fiscal": "Saldo Fiscal Estimado (R$)", "total_emendas": "Total em Emendas (R$)"}
    )
    return aplicar_tema(fig, "9. Saldo Fiscal Estimado (Receita - Despesa) vs. Volume de Emendas")


@register_chart(
    id="siconfi_autonomia_fiscal",
    title="10. Capacidade de Investimento Próprio vs. Emendas TransfereGov",
    description="Mapeia quanto o município investe com recursos próprios (Despesas de Capital SICONFI) versus o montante recebido via Emendas.",
    category="SICONFI Fiscal"
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
        fig.add_annotation(text="Dados de investimento não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "10. Capacidade de Investimento Próprio vs. Emendas TransfereGov")

    fig = px.scatter(
        df,
        x="investimento_siconfi",
        y="total_emendas",
        size="total_emendas",
        color="regiao",
        hover_name="municipio",
        labels={"investimento_siconfi": "Investimentos SICONFI (Despesas de Capital R$)", "total_emendas": "Total em Emendas TransfereGov (R$)"}
    )
    return aplicar_tema(fig, "10. Capacidade de Investimento Próprio vs. Emendas TransfereGov")



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
            default="TODOS"
        )
    ]
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
        fig.add_annotation(text="Dados de despesas não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "11. Perfil de Gasto Municipal: Custeio vs. Investimento (SICONFI)")

    df_melt = df.melt(id_vars=["municipio"], value_vars=["despesas_correntes", "despesas_capital"],
                      var_name="Tipo", value_name="Valor")
    df_melt["Tipo"] = df_melt["Tipo"].map({"despesas_correntes": "Despesas Correntes (Custeio)", "despesas_capital": "Despesas de Capital (Investimento)"})

    fig = px.bar(
        df_melt,
        x="Valor",
        y="municipio",
        color="Tipo",
        orientation="h",
        color_discrete_map={"Despesas Correntes (Custeio)": "#3b82f6", "Despesas de Capital (Investimento)": "#10b981"},
        labels={"Valor": "Despesas (R$)", "municipio": "Município"}
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "11. Perfil de Gasto Municipal: Custeio vs. Investimento (SICONFI)")


@register_chart(
    id="siconfi_divida_per_capita",
    title="12. Despesa Corrente Municipal (Custeio) por Região",
    description="Compara o volume total de despesas correntes executadas por município agrupado por região.",
    category="SICONFI Fiscal"
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
        fig.add_annotation(text="Dados de despesa não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "12. Despesa Corrente Municipal (Custeio) por Região")

    fig = px.box(
        df,
        x="regiao",
        y="despesas_correntes",
        color="regiao",
        points="all",
        hover_name="municipio",
        labels={"despesas_correntes": "Despesas Correntes (R$)", "regiao": "Região Geográfica"}
    )
    return aplicar_tema(fig, "12. Despesa Corrente Municipal (Custeio) por Região")


@register_chart(
    id="siconfi_patrimonio_vs_passivo",
    title="13. Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente",
    description="Avalia a folga orçamentária (Receita Corrente minus Despesa Corrente) das principais prefeituras.",
    category="SICONFI Fiscal"
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
        fig.add_annotation(text="Dados orçamentários não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "13. Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente")

    fig = px.scatter(
        df,
        x="receitas_correntes",
        y="despesas_correntes",
        size="receitas_correntes",
        color="regiao",
        hover_name="municipio",
        labels={"receitas_correntes": "Receitas Correntes (R$)", "despesas_correntes": "Despesas Correntes (R$)"}
    )
    return aplicar_tema(fig, "13. Equilíbrio Orçamentário: Receita Corrente vs. Despesa Corrente")


@register_chart(
    id="siconfi_top20_receita",
    title="14. Top 20 Maiores Arrecadações Correntes Municipais",
    description="Ranking das 20 maiores receitas correntes municipais consolidadas no SICONFI.",
    category="SICONFI Fiscal"
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
        fig.add_annotation(text="Sem dados de receita", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "14. Top 20 Maiores Arrecadações Correntes Municipais")

    fig = px.bar(
        df,
        x="receitas_correntes",
        y="municipio_uf",
        orientation="h",
        text_auto=".2s",
        color="receitas_correntes",
        color_continuous_scale="Blues",
        labels={"receitas_correntes": "Receita Corrente Total (R$)", "municipio_uf": "Município"}
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "14. Top 20 Maiores Arrecadações Correntes Municipais")


@register_chart(
    id="siconfi_resultado_por_regiao",
    title="15. Saldo Fiscal Estimado (Receita - Despesa) por Região",
    description="Distribuição do saldo fiscal municipal (Receitas Totais minus Despesas Totais) por região geográfica.",
    category="SICONFI Fiscal"
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
        fig.add_annotation(text="Dados de saldo fiscal não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "15. Saldo Fiscal Estimado (Receita - Despesa) por Região")

    fig = px.violin(
        df,
        x="regiao",
        y="saldo_fiscal",
        color="regiao",
        box=True,
        points=False,
        labels={"saldo_fiscal": "Saldo Fiscal Estimado (R$)", "regiao": "Região Geográfica"}
    )
    return aplicar_tema(fig, "15. Saldo Fiscal Estimado (Receita - Despesa) por Região")



@register_chart(
    id="siconfi_ranking_vulnerabilidade",
    title="16. Vulnerabilidade Fiscal: Alta Dependência de Repasses",
    description="Municípios com maior razão entre receitas de transferências externas e arrecadação própria.",
    category="SICONFI Fiscal"
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

    fig = px.bar(
        df,
        x="dependencia_transferencias_pct",
        y="municipio_uf",
        orientation="h",
        color="dependencia_transferencias_pct",
        color_continuous_scale="Purples",
        labels={"dependencia_transferencias_pct": "Dependência de Transferências (%)", "municipio_uf": "Município"}
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return aplicar_tema(fig, "16. Vulnerabilidade Fiscal: Alta Dependência de Repasses")


@register_chart(
    id="siconfi_despesas_faixa_populacional",
    title="17. Perfil Médio de Despesas Orçamentárias por UF",
    description="Volume médio de despesas correntes executadas pelos municípios agregados por estado.",
    category="SICONFI Fiscal"
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

    df_melt = df.melt(id_vars=["uf"], value_vars=["media_despesas_correntes", "media_despesas_capital"],
                      var_name="Tipo", value_name="Valor")
    df_melt["Tipo"] = df_melt["Tipo"].map({"media_despesas_correntes": "Média Despesas Correntes", "media_despesas_capital": "Média Despesas de Capital"})

    fig = px.bar(
        df_melt,
        x="uf",
        y="Valor",
        color="Tipo",
        barmode="group",
        labels={"Valor": "Média de Despesa (R$)", "uf": "Estado (UF)"}
    )
    return aplicar_tema(fig, "17. Perfil Médio de Despesas Orçamentárias por UF")


# ---------------------------------------------------------------------------
# GRÁFICOS CRIATIVOS — CRUZAMENTO MULTIDIMENSIONAL (18-24)
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
            default="TODOS"
        )
    ]
)
def chart_choropleth_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.municipio_id,
            m.nome AS municipio,
            m.uf,
            COALESCE(SUM(v.valor_total), 0) AS valor_total,
            COUNT(v.codigo_emenda) AS qtd_emendas
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.municipio_id, m.nome, m.uf
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY valor_total DESC
        LIMIT 200;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados geoespaciais disponíveis para o filtro selecionado",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "18. Mapa Coroplético: Emendas por Município")

    df["municipio_label"] = df["municipio"] + " (" + df["uf"] + ")"
    df["valor_fmt"] = df["valor_total"].apply(
        lambda x: f"R$ {x:,.0f}".replace(",", ".")
    )

    fig = px.scatter_geo(
        df,
        lat=[0] * len(df),
        lon=[0] * len(df),
        hover_name="municipio_label",
        size="valor_total",
        color="valor_total",
        color_continuous_scale="YlOrRd",
        size_max=40,
        labels={
            "valor_total": "Valor Total (R$)",
            "qtd_emendas": "Qtd. Emendas"
        },
    )

    fig.update_geos(
        scope="south america",
        center=dict(lat=-14.2, lon=-51.9),
        projection_scale=3.5,
        showlakes=True,
        lakecolor="rgb(30, 41, 59)",
        bgcolor=THEME_CARD_BG,
        landcolor=THEME_GRID,
        countrycolor="#475569",
    )

    fig.update_traces(
        hovertemplate="<b>%{hovertext}</b><br>"
                      "Valor: R$ %{customdata[0]:,.0f}<br>"
                      "Emendas: %{customdata[1]}<extra></extra>",
        customdata=df[["valor_total", "qtd_emendas"]].values
    )

    return aplicar_tema(fig, "18. Mapa Coroplético: Emendas Parlamentares por Município", 600)


@register_chart(
    id="emendas_vs_compras",
    title="19. Emendas Parlamentares × Compras Públicas por Município",
    description="Cruzamento entre o volume de emendas recebidas e o valor total em licitações/contratos do município. Identifica municípios com alta captação mas baixa execução de compras.",
    category="Fiscal & Geográfico",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS"
        )
    ]
)
def chart_emendas_vs_compras(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio,
            m.uf,
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
            FROM compras_municipios
            GROUP BY municipio_id
        ) cm ON m.municipio_id = cm.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
        GROUP BY m.nome, m.uf, cm.valor_total_compras, cm.total_contratos
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 40;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de compras públicas disponíveis. Execute o enriquecedor de compras primeiro.",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "19. Emendas × Compras Públicas")

    df["ratio"] = df.apply(
        lambda r: r["total_compras"] / r["total_emendas"]
        if r["total_emendas"] > 0 and r["total_compras"] > 0 else 0,
        axis=1
    )
    df["status_execucao"] = df["ratio"].apply(
        lambda x: "Alta Execução" if x > 0.5
        else ("Execução Parcial" if x > 0.1 else "Baixa Execução")
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
            "Baixa Execução": "#ef4444"
        },
        labels={
            "total_emendas": "Total Emendas Parlamentares (R$)",
            "total_compras": "Total Compras/Contratos (R$)",
            "status_execucao": "Status de Execução"
        }
    )
    fig.update_traces(textposition="top center", textfont_size=9)
    fig.add_shape(
        type="line", x0=0, y0=0, x1=max(df["total_emendas"].max(), 1),
        y1=max(df["total_emendas"].max(), 1),
        line=dict(color="#475569", width=1, dash="dash")
    )
    fig.add_annotation(
        text="Linha de referência: Emendas = Compras",
        x=max(df["total_emendas"].max(), 1) * 0.5,
        y=max(df["total_emendas"].max(), 1) * 0.55,
        showarrow=False, font=dict(size=10, color="#64748b")
    )
    return aplicar_tema(fig, "19. Emendas Parlamentares × Compras Públicas por Município")


@register_chart(
    id="impacto_saude",
    title="20. Impacto na Saúde: Leitos por R$ Repassado via Emendas",
    description="Cruzamento entre o investimento via emendas e a infraestrutura de saúde municipal (leitos, hospitais, UBS). Identifica municípios com alto investimento mas baixa capacidade de saúde.",
    category="Impacto Social",
    controls=[
        ControlSpec(
            id="regiao_filter",
            label="Filtrar por Região",
            options=["TODOS", "Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"],
            default="TODOS"
        )
    ]
)
def chart_impacto_saude(regiao_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            COALESCE(NULLIF(m.regiao, ''), 'Outros') AS regiao,
            m.populacao,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            sm.total_leitos,
            sm.hospitais,
            sm.ubs,
            sm.total_estabelecimentos,
            CASE WHEN m.populacao > 0
                 THEN ROUND(sm.total_leitos::NUMERIC / m.populacao * 10000, 2)
                 ELSE 0 END AS leitos_por_10k,
            CASE WHEN m.populacao > 0
                 THEN ROUND(SUM(v.valor_total)::NUMERIC / m.populacao, 2)
                 ELSE 0 END AS emendas_per_capita
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN saude_municipios sm ON m.municipio_id = sm.municipio_id
        WHERE m.populacao IS NOT NULL AND m.populacao > 0
          AND (%s = 'TODOS' OR m.regiao = %s)
        GROUP BY m.nome, m.uf, m.regiao, m.populacao, sm.total_leitos,
                 sm.hospitais, sm.ubs, sm.total_estabelecimentos
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 50;
    """
    df = query_df(query, (regiao_filter, regiao_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de saúde disponíveis. Execute o enriquecedor saúde/educação primeiro.",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "20. Impacto na Saúde: Leitos por R$ Repassado")

    df["regiao"] = df["regiao"].astype(str).fillna("Não Informado")
    df["label"] = df["municipio"] + " (" + df["uf"] + ")"

    fig = px.scatter(
        df,
        x="emendas_per_capita",
        y="leitos_por_10k",
        size="total_emendas",
        color="regiao",
        hover_name="label",
        hover_data=["total_leitos", "hospitais", "ubs", "populacao"],
        labels={
            "emendas_per_capita": "Emendas Per Capita (R$/hab)",
            "leitos_por_10k": "Leitos por 10.000 habitantes",
            "regiao": "Região"
        }
    )

    brasil_media_leitos = 2.1
    fig.add_hline(
        y=brasil_media_leitos, line_dash="dash",
        line_color="#f59e0b", line_width=1,
        annotation_text=f"Média Brasil: {brasil_media_leitos} leitos/10k",
        annotation_position="top right",
        annotation_font=dict(color="#f59e0b", size=10)
    )

    return aplicar_tema(fig, "20. Impacto na Saúde: Leitos por R$ Repassado via Emendas")


@register_chart(
    id="ideb_vs_emendas",
    title="21. IDEB × Investimento em Educação via Emendas",
    description="Correlação entre o IDEB (ano iniciais e finais) e o volume de emendas parlamentares destinadas ao município. Avalia se investimentos se traduzem em melhor educação.",
    category="Impacto Social",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS"
        )
    ]
)
def chart_ideb_vs_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome || ' (' || m.uf || ')' AS municipio,
            m.uf,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            em.ideb_initial_years,
            em.ideb_final_years,
            em.matriculas_totais,
            m.populacao
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN educacao_municipios em ON m.municipio_id = em.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND em.ideb_initial_years IS NOT NULL
        GROUP BY m.nome, m.uf, em.ideb_initial_years, em.ideb_final_years,
                 em.matriculas_totais, m.populacao
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 50;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados de IDEB disponíveis. Execute o enriquecedor saúde/educação primeiro.",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "21. IDEB × Investimento em Educação")

    df["ideb_medio"] = (df["ideb_initial_years"] + df["ideb_final_years"]) / 2

    fig = px.scatter(
        df,
        x="total_emendas",
        y="ideb_medio",
        size="matriculas_totais",
        color="uf",
        hover_name="municipio",
        hover_data=["ideb_initial_years", "ideb_final_years", "matriculas_totais"],
        labels={
            "total_emendas": "Total Emendas Educacionais (R$)",
            "ideb_medio": "IDEB Médio (Anos Iniciais + Finais / 2)",
            "uf": "UF"
        }
    )

    fig.add_hline(
        y=5.0, line_dash="dash", line_color="#22c55e", line_width=1,
        annotation_text="Meta IDEB nacional: 5.0",
        annotation_position="top right",
        annotation_font=dict(color="#22c55e", size=10)
    )

    return aplicar_tema(fig, "21. IDEB × Investimento em Educação via Emendas")


@register_chart(
    id="tendencia_temporal",
    title="22. Tendência Temporal: Volume de Repasses e Indicadores Econômicos",
    description="Série temporal do volume mensal de emendas parlamentares sobreposta a indicadores macroeconômicos (IPCA, Selic). Permite analisar timing dos repasses vs contexto econômico.",
    category="Temporal",
    controls=[
        ControlSpec(
            id="ano_filter",
            label="Filtrar por Ano",
            options=["TODOS", "2024", "2025", "2026"],
            default="TODOS"
        )
    ]
)
def chart_tendencia_temporal(ano_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            TO_CHAR(DATE_TRUNC('month', pa.extracted_at), 'YYYY-MM') AS mes,
            COUNT(*) AS total_planos,
            SUM(pa.valor_total) AS valor_total,
            COUNT(DISTINCT pa.parlamentar_nome) AS parlamentares
        FROM planos_acao pa
        WHERE pa.extracted_at IS NOT NULL
          AND (%s = 'TODOS' OR EXTRACT(YEAR FROM pa.extracted_at) = %s::INTEGER)
        GROUP BY DATE_TRUNC('month', pa.extracted_at)
        ORDER BY mes;
    """
    params = (ano_filter, ano_filter) if ano_filter != "TODOS" else (ano_filter, "9999")
    df = query_df(query, params)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados temporais disponíveis",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "22. Tendência Temporal de Repasses")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df["mes"],
        y=df["valor_total"],
        name="Valor Total Emendas (R$)",
        marker_color="#3b82f6",
        opacity=0.7,
        yaxis="y"
    ))

    fig.add_trace(go.Scatter(
        x=df["mes"],
        y=df["parlamentares"],
        name="Parlamentares Únicos",
        mode="lines+markers",
        line=dict(color="#f59e0b", width=2),
        marker=dict(size=6),
        yaxis="y2"
    ))

    fig.update_layout(
        yaxis=dict(
            title="Valor Total (R$)",
            title_font=dict(color="#3b82f6"),
            tickfont=dict(color="#3b82f6"),
            gridcolor=THEME_GRID,
        ),
        yaxis2=dict(
            title="Nº Parlamentares",
            title_font=dict(color="#f59e0b"),
            tickfont=dict(color="#f59e0b"),
            overlaying="y",
            side="right",
        ),
        legend=dict(
            x=0.01, y=0.99,
            bgcolor="rgba(15, 23, 42, 0.7)",
            bordercolor="#475569",
            borderwidth=1,
            font=dict(color=THEME_TEXT, size=11)
        ),
    )

    return aplicar_tema(fig, "22. Tendência Temporal: Volume de Repasses", 500)


@register_chart(
    id="eleicao_emendas",
    title="23. Resultado Eleitoral × Distribuição de Emendas",
    description="Cruzamento entre o resultado das eleições municipais 2024 e o volume de emendas parlamentares recebidas por cada município. Analisa correlação política-financeira.",
    category="Análise Parlamentar",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS"
        )
    ]
)
def chart_eleicao_emendas(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            m.populacao,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            COUNT(DISTINCT v.codigo_emenda) AS qtd_emendas,
            pd.sigla_partido AS partido_parlamentar,
            COALESCE(NULLIF(pd.situacao, ''), 'Não Informado') AS situacao_parlamentar
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN parlamentares_dados pd ON v.parlamentar_nome = pd.nome
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND v.parlamentar_nome IS NOT NULL
        GROUP BY m.nome, m.uf, m.populacao, pd.sigla_partido, pd.situacao
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 60;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados disponíveis para o filtro selecionado",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "23. Resultado Eleitoral × Emendas")

    df["partido_parlamentar"] = df["partido_parlamentar"].fillna("OUTROS")
    top_partidos = df["partido_parlamentar"].value_counts().head(10).index.tolist()
    df["partido_grupo"] = df["partido_parlamentar"].apply(
        lambda x: x if x in top_partidos else "OUTROS"
    )
    df["label"] = df["municipio"] + " (" + df["uf"] + ")"

    fig = px.scatter(
        df,
        x="qtd_emendas",
        y="total_emendas",
        size="populacao",
        color="partido_grupo",
        hover_name="label",
        hover_data=["partido_parlamentar", "situacao_parlamentar"],
        labels={
            "qtd_emendas": "Quantidade de Emendas",
            "total_emendas": "Valor Total (R$)",
            "partido_grupo": "Partido Autor"
        },
        size_max=50,
    )

    return aplicar_tema(fig, "23. Resultado Eleitoral × Distribuição de Emendas")


@register_chart(
    id="vulnerabilidade_social",
    title="24. Vulnerabilidade Fiscal × Indicadores Sociais (Radar Multi-Indicador)",
    description="Gráfico radar/spider que compara municípios em múltiplas dimensões: dependência fiscal, investimento em saúde, educação e emendas parlamentares. Perfil multidimensional de vulnerabilidade.",
    category="Socioeconômico",
    controls=[
        ControlSpec(
            id="uf_filter",
            label="Filtrar por Estado (UF)",
            options=TODAS_UFS,
            default="TODOS"
        )
    ]
)
def chart_vulnerabilidade_social(uf_filter: str = "TODOS") -> go.Figure:
    query = """
        SELECT
            m.nome AS municipio,
            m.uf,
            m.populacao,
            COALESCE(SUM(v.valor_total), 0) AS total_emendas,
            mf.receitas_correntes,
            mf.receitas_transferencias,
            sm.total_leitos,
            em.ideb_initial_years
        FROM v_emendas_unificadas v
        JOIN beneficiarios b ON v.beneficiario_nome = b.nome
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        LEFT JOIN saude_municipios sm ON m.municipio_id = sm.municipio_id
        LEFT JOIN educacao_municipios em ON m.municipio_id = em.municipio_id
        WHERE (%s = 'TODOS' OR m.uf = %s)
          AND mf.receitas_correntes > 0
        GROUP BY m.nome, m.uf, m.populacao, mf.receitas_correntes,
                 mf.receitas_transferencias, sm.total_leitos, em.ideb_initial_years
        HAVING COALESCE(SUM(v.valor_total), 0) > 0
        ORDER BY total_emendas DESC
        LIMIT 10;
    """
    df = query_df(query, (uf_filter, uf_filter))

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Sem dados suficientes para gerar radar. Execute os enriquecedores primeiro.",
            showarrow=False, font=dict(size=16, color="#64748b")
        )
        return aplicar_tema(fig, "24. Vulnerabilidade Fiscal × Indicadores Sociais")

    categories = [
        "Dependência de\nTransferências",
        "Investimento\nPer Capita",
        "Infraestrutura\nSaúde",
        "IDEB\nMunicipal",
        "Captação\nEmendas"
    ]

    fig = go.Figure()

    colors = px.colors.qualitative.Set2

    for idx, (_, row) in enumerate(df.iterrows()):
        dep_transf = (
            100 * row["receitas_transferencias"] / row["receitas_correntes"]
            if row["receitas_correntes"] > 0 and pd.notna(row["receitas_transferencias"])
            else 0
        )
        invest_pc = (
            row["total_emendas"] / row["populacao"] * 1000
            if row["populacao"] > 0 else 0
        )
        saude = row["total_leitos"] if pd.notna(row["total_leitos"]) else 0
        ideb = row["ideb_initial_years"] if pd.notna(row["ideb_initial_years"]) else 0
        emendas_norm = min(row["total_emendas"] / 1e6, 100)

        max_dep = max(100, dep_transf)
        max_invest = max(10, invest_pc)
        max_saude = max(100, saude)
        max_ideb = max(10, ideb)
        max_emendas = max(100, emendas_norm)

        values = [
            dep_transf / max_dep * 100,
            invest_pc / max_invest * 100,
            saude / max_saude * 100,
            ideb / max_ideb * 100,
            emendas_norm / max_emendas * 100,
        ]
        values.append(values[0])

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill="toself",
            name=f"{row['municipio']} ({row['uf']})",
            line=dict(color=colors[idx % len(colors)]),
            opacity=0.6,
        ))

    fig.update_layout(
        polar=dict(
            bgcolor=THEME_CARD_BG,
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor=THEME_GRID,
                tickfont=dict(color=THEME_TEXT, size=9),
            ),
            angularaxis=dict(
                gridcolor=THEME_GRID,
                tickfont=dict(color=THEME_TEXT, size=10),
            ),
        ),
        showlegend=True,
        legend=dict(
            bgcolor="rgba(15, 23, 42, 0.7)",
            bordercolor="#475569",
            borderwidth=1,
            font=dict(color=THEME_TEXT, size=10)
        ),
    )

    return aplicar_tema(fig, "24. Vulnerabilidade Fiscal × Indicadores Sociais (Radar)", 550)


# ============================================================
# MAPAS COROPLÉTICOS (CHOROPLETH MAPS)
# ============================================================

GEOJSON_BR_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "brazil_states.json")

def _load_brazil_geojson() -> dict:
    if os.path.exists(GEOJSON_BR_PATH):
        try:
            with open(GEOJSON_BR_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


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
            default="TODOS"
        )
    ]
)
def chart_choropleth_valor_total_uf(categoria_gasto: str = "TODOS") -> go.Figure:
    geojson_br = _load_brazil_geojson()

    where_clause = "WHERE b.uf IS NOT NULL AND b.uf != ''"
    if categoria_gasto == "CUSTEIO":
        where_clause += " AND p.valor_custeio > 0"
    elif categoria_gasto == "INVESTIMENTO":
        where_clause += " AND p.valor_investimento > 0"

    query = f"""
        SELECT 
            b.uf, 
            SUM(p.valor_total) as valor_total, 
            COUNT(*) as total_planos
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        {where_clause}
        GROUP BY b.uf
    """
    df = query_df(query)

    if df.empty or not geojson_br:
        fig = go.Figure()
        fig.add_annotation(text="Mapa GeoJSON ou dados indisponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "18. Mapa Coroplético: Distribuição de Recursos por Estado (UF)")

    fig = px.choropleth(
        df,
        geojson=geojson_br,
        locations="uf",
        featureidkey="properties.sigla",
        color="valor_total",
        color_continuous_scale="Viridis",
        hover_name="uf",
        hover_data={"valor_total": ":,.2f", "total_planos": True},
        labels={"valor_total": "Valor Total (R$)", "total_planos": "Nº de Emendas", "uf": "Estado"}
    )
    fig.update_geos(fitbounds="locations", visible=False)
    return aplicar_tema(fig, "18. Mapa Coroplético: Distribuição de Recursos por Estado (UF)")


@register_chart(
    id="choropleth_taxa_impedimento_uf",
    title="19. Mapa Coroplético: Taxa de Impedimento Técnico por Estado",
    description="Mapeamento espacial da porcentagem de recursos impedidos ou rejeitados por UF.",
    category="Geográfico & Mapas"
)
def chart_choropleth_taxa_impedimento_uf() -> go.Figure:
    geojson_br = _load_brazil_geojson()
    query = """
        SELECT 
            b.uf,
            COUNT(*) as total_planos,
            SUM(CASE WHEN p.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO', 'CANCELADO') THEN 1 ELSE 0 END) as impedidos,
            ROUND(100.0 * SUM(CASE WHEN p.plano_acao_situacao IN ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO', 'CANCELADO') THEN 1 ELSE 0 END) / COUNT(*), 2) as taxa_impedimento
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        WHERE b.uf IS NOT NULL AND b.uf != ''
        GROUP BY b.uf
    """
    df = query_df(query)

    if df.empty or not geojson_br:
        fig = go.Figure()
        fig.add_annotation(text="Dados de impedimento não disponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "19. Mapa Coroplético: Taxa de Impedimento Técnico por Estado")

    fig = px.choropleth(
        df,
        geojson=geojson_br,
        locations="uf",
        featureidkey="properties.sigla",
        color="taxa_impedimento",
        color_continuous_scale="Reds",
        hover_name="uf",
        hover_data={"taxa_impedimento": ":.2f", "impedidos": True, "total_planos": True},
        labels={"taxa_impedimento": "Taxa de Impedimento (%)", "impedidos": "Planos Impedidos", "uf": "Estado"}
    )
    fig.update_geos(fitbounds="locations", visible=False)
    return aplicar_tema(fig, "19. Mapa Coroplético: Taxa de Impedimento Técnico por Estado")


# ============================================================
# AVANÇADOS: ANIMAÇÕES, 3D E FLUXOS (PLOTLY AVANÇADO)
# ============================================================

@register_chart(
    id="scatter_3d_socioeconomico",
    title="25. Análise Tridimensional (3D): Repasses × Arrecadação × Despesas",
    description="Espaço tridimensional interativo rotacionável comparando Receita Corrente (X), Despesa Corrente (Y) e Valor de Emendas (Z) por município.",
    category="Animações & 3D"
)
def chart_scatter_3d_socioeconomico() -> go.Figure:
    query = """
        SELECT 
            m.nome || ' (' || m.uf || ')' AS municipio_uf,
            COALESCE(NULLIF(m.regiao, ''), 'Outros') AS regiao,
            mf.receitas_correntes,
            mf.despesas_correntes,
            SUM(p.valor_total) AS valor_total,
            COUNT(p.id) AS total_emendas
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        JOIN municipios_financeiro mf ON m.municipio_id = mf.municipio_id
        WHERE mf.receitas_correntes > 0 AND mf.despesas_correntes > 0
        GROUP BY m.nome, m.uf, m.regiao, mf.receitas_correntes, mf.despesas_correntes
        ORDER BY valor_total DESC
        LIMIT 60;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados 3D indisponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "25. Análise Tridimensional (3D)")

    fig = px.scatter_3d(
        df,
        x="receitas_correntes",
        y="despesas_correntes",
        z="valor_total",
        color="regiao",
        size="total_emendas",
        hover_name="municipio_uf",
        labels={
            "receitas_correntes": "Receita Corrente (R$)",
            "despesas_correntes": "Despesa Corrente (R$)",
            "valor_total": "Valor de Emendas (R$)",
            "regiao": "Região Geográfica"
        }
    )
    return aplicar_tema(fig, "25. Análise Tridimensional (3D): Repasses × Arrecadação × Despesas", altura=600)


@register_chart(
    id="sunburst_drilldown_recursos",
    title="26. Drilldown Hierárquico Interativo (Sunburst): Região ➔ Estado ➔ Partido",
    description="Visualização circular hierárquica por níveis. Clique em qualquer setor para expandir e navegar em tempo real.",
    category="Hierárquico & Fluxos"
)
def chart_sunburst_drilldown_recursos() -> go.Figure:
    query = """
        SELECT 
            COALESCE(NULLIF(m.regiao, ''), 'Outros') AS regiao,
            m.uf,
            COALESCE(pd.sigla_partido, 'OUTROS') AS sigla_partido,
            SUM(p.valor_total) AS valor_total
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN parlamentares_dados pd ON p.parlamentar_nome = pd.nome
        GROUP BY m.regiao, m.uf, pd.sigla_partido
        HAVING SUM(p.valor_total) > 1000000;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados Sunburst indisponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "26. Drilldown Hierárquico Interativo (Sunburst)")

    fig = px.sunburst(
        df,
        path=["regiao", "uf", "sigla_partido"],
        values="valor_total",
        color="regiao",
        color_discrete_sequence=px.colors.qualitative.Dark24
    )
    return aplicar_tema(fig, "26. Drilldown Hierárquico Interativo (Sunburst)", altura=550)


@register_chart(
    id="treemap_investimentos_objetos",
    title="27. Treemap Proporcional: Distribuição por Objeto de Execução",
    description="Mapeamento em blocos proporcionais retangulares dos investimentos alocados por tipo de objeto.",
    category="Hierárquico & Fluxos"
)
def chart_treemap_investimentos_objetos() -> go.Figure:
    query = """
        SELECT 
            COALESCE(o.descricao, 'Outros Objetos') AS objeto_nome,
            b.uf,
            SUM(p.valor_total) AS valor_total,
            COUNT(p.id) AS total_emendas
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        LEFT JOIN objetos o ON p.objeto_id = o.objeto_id
        GROUP BY o.descricao, b.uf
        HAVING SUM(p.valor_total) > 500000;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados Treemap indisponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "27. Treemap Proporcional por Objeto")

    fig = px.treemap(
        df,
        path=["objeto_nome", "uf"],
        values="valor_total",
        color="valor_total",
        color_continuous_scale="Plasma",
        hover_data={"total_emendas": True}
    )
    return aplicar_tema(fig, "27. Treemap Proporcional: Distribuição por Objeto de Execução", altura=550)


@register_chart(
    id="sankey_fluxo_financeiro",
    title="28. Diagrama de Fluxo Sankey: Região ➔ Situação de Aprovação",
    description="Diagrama de fluxo interativo com nós arrastáveis conectando a origem regional do investimento ao status de aprovação ou impedimento.",
    category="Hierárquico & Fluxos"
)
def chart_sankey_fluxo_financeiro() -> go.Figure:
    query = """
        SELECT 
            COALESCE(NULLIF(m.regiao, ''), 'Outros') AS origem,
            COALESCE(s.display_site, p.plano_acao_situacao) AS destino,
            SUM(p.valor_total) AS valor
        FROM planos_acao p
        JOIN beneficiarios b ON p.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge m ON bm.municipio_id = m.municipio_id
        LEFT JOIN situacoes_map s ON p.plano_acao_situacao = s.valor_api
        GROUP BY m.regiao, s.display_site, p.plano_acao_situacao
        ORDER BY valor DESC;
    """
    df = query_df(query)

    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Dados de fluxo Sankey indisponíveis", showarrow=False, font=dict(size=16, color="#64748b"))
        return aplicar_tema(fig, "28. Diagrama de Fluxo Sankey")

    all_nodes = list(dict.fromkeys(df["origem"].tolist() + df["destino"].tolist()))
    node_dict = {name: i for i, name in enumerate(all_nodes)}

    sources = [node_dict[o] for o in df["origem"]]
    targets = [node_dict[d] for d in df["destino"]]
    values = df["valor"].tolist()

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="#475569", width=0.5),
            label=all_nodes,
            color="#3b82f6"
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color="rgba(59, 130, 246, 0.3)"
        )
    )])
    return aplicar_tema(fig, "28. Diagrama de Fluxo Sankey: Região ➔ Situação de Aprovação", altura=500)







