"""Canned SQL query tools for the anp_precos dataset feature."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from mcp_brasil._shared.datasets import executar_query, get_status, refresh_dataset
from mcp_brasil._shared.formatting import format_number_br, markdown_table

from . import DATASET_SPEC, DATASET_TABLE
from .constants import COLUNAS_DISTINCT_PERMITIDAS


def _fmt_brl(v: Any) -> str:
    try:
        n = float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return "—"
    return f"R$ {n:.3f}".replace(".", ",") if n else "—"


async def info_anp_precos(ctx: Context) -> str:
    """Estado do cache local do dataset ANP de preços de combustíveis."""
    await ctx.info("Consultando estado do cache ANP...")
    st = await get_status(DATASET_SPEC)
    lines = [
        "**ANP preços — estado do cache**",
        "",
        f"- **Cached localmente:** {'sim' if st['cached'] else 'não'}",
        f"- **Linhas:** {format_number_br(st['row_count'], 0) if st['cached'] else '—'}",
        f"- **Tamanho:** {st['size_bytes'] / 1024 / 1024:.1f} MB",
        "- **Idade:** "
        + (f"{st['age_days']:.2f} dias" if st.get("age_days") is not None else "—"),
        f"- **Fresh (TTL={st['ttl_days']}d):** {'sim' if st['fresh'] else 'não'}",
        f"- **Fonte:** {st['source']}",
    ]
    return "\n".join(lines)


async def refrescar_anp_precos(ctx: Context) -> str:
    """Força re-download do dataset ANP (ignora TTL)."""
    await ctx.info("Re-baixando ANP... isso pode levar 2-5 minutos (36 arquivos).")
    m = await refresh_dataset(DATASET_SPEC)
    return (
        f"**ANP atualizado**\n\n"
        f"- Linhas: {format_number_br(m.row_count, 0)}\n"
        f"- Tamanho: {m.size_bytes / 1024 / 1024:.1f} MB\n"
        f"- Schema hash: `{m.schema_hash}`\n"
    )


async def valores_distintos_anp(coluna: str, limite: int = 100) -> str:
    """Lista os valores distintos de uma coluna categórica da base ANP.

    Args:
        coluna: Nome da coluna (produto, bandeira, estado, regiao, unidade).
        limite: Número máximo de valores (padrão 100).
    """
    if coluna not in COLUNAS_DISTINCT_PERMITIDAS:
        return f"Coluna '{coluna}' não permitida. Permitidas: " + ", ".join(
            sorted(COLUNAS_DISTINCT_PERMITIDAS)
        )
    limite = max(1, min(limite, 500))
    sql = (
        f'SELECT "{coluna}" AS valor, COUNT(*) AS total '
        f'FROM "{DATASET_TABLE}" WHERE "{coluna}" IS NOT NULL '
        f'GROUP BY "{coluna}" ORDER BY total DESC LIMIT {limite}'
    )
    rows = await executar_query(DATASET_SPEC, sql)
    if not rows:
        return "Nenhum valor encontrado."
    table_rows = [(r["valor"], format_number_br(int(r["total"]), 0)) for r in rows]
    return markdown_table([coluna, "ocorrencias"], table_rows)


async def precos_por_municipio(
    ctx: Context,
    municipio: str,
    uf: str,
    produto: str | None = None,
    limite: int = 50,
) -> str:
    """Preços observados em um município para um produto específico.

    Args:
        municipio: Nome do município (substring, accent-insensitive).
        uf: UF (sigla). Ex: "SP", "RJ".
        produto: Filtra produto (ex: "GASOLINA ADITIVADA"). Opcional.
        limite: Linhas (padrão 50, máx 200).
    """
    limite = max(1, min(limite, 200))
    where: list[str] = ["UPPER(TRIM(estado)) = ?"]
    params: list[Any] = [uf.strip().upper()]
    where.append("strip_accents(municipio) ILIKE strip_accents(?)")
    params.append(f"%{municipio}%")
    if produto:
        where.append("strip_accents(produto) ILIKE strip_accents(?)")
        params.append(f"%{produto}%")
    sql = (
        "SELECT data_coleta, municipio, produto, bandeira, revenda, "
        "valor_venda, unidade "
        f'FROM "{DATASET_TABLE}" WHERE {" AND ".join(where)} '
        f"ORDER BY data_coleta DESC LIMIT {limite}"
    )
    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows:
        return "Nenhum preço encontrado para os filtros."
    table = [
        (
            r.get("data_coleta") or "—",
            (r.get("municipio") or "—")[:20],
            (r.get("produto") or "—"),
            (r.get("bandeira") or "—")[:20],
            (r.get("revenda") or "—")[:30],
            _fmt_brl(r.get("valor_venda")),
        )
        for r in rows
    ]
    return f"**{len(rows)} preços encontrados**\n\n" + markdown_table(
        ["Data", "Município", "Produto", "Bandeira", "Revenda", "Venda"], table
    )


async def media_preco_uf(
    ctx: Context,
    uf: str,
    produto: str,
    ano: int | None = None,
    mes: int | None = None,
) -> str:
    """Média, mínimo e máximo de preço de venda por UF/produto e período.

    Args:
        uf: UF (sigla).
        produto: Nome do produto (substring, ex: "GASOLINA").
        ano: Ano opcional — filtra por ano da data_coleta.
        mes: Mês (1-12) opcional.
    """
    where = [
        "UPPER(TRIM(estado)) = ?",
        "strip_accents(produto) ILIKE strip_accents(?)",
    ]
    params: list[Any] = [uf.strip().upper(), f"%{produto}%"]
    if ano is not None:
        where.append("CAST(SUBSTR(data_coleta, LENGTH(data_coleta)-3, 4) AS INT) = ?")
        params.append(ano)
    if mes is not None:
        where.append("CAST(SUBSTR(data_coleta, 4, 2) AS INT) = ?")
        params.append(mes)
    sql = (
        "SELECT COUNT(*) AS amostras, "
        "AVG(valor_venda) AS media, "
        "MIN(valor_venda) AS minimo, "
        "MAX(valor_venda) AS maximo "
        f'FROM "{DATASET_TABLE}" WHERE {" AND ".join(where)} '
        "AND valor_venda IS NOT NULL"
    )
    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows or not rows[0].get("amostras"):
        return "Nenhuma coleta no período especificado."
    r = rows[0]
    periodo = f"{mes:02d}/{ano}" if ano and mes else (str(ano) if ano else "período integral")
    return (
        f"**{produto} em {uf} — {periodo}**\n\n"
        f"- Amostras: {format_number_br(int(r['amostras']), 0)}\n"
        f"- Média: {_fmt_brl(r['media'])}\n"
        f"- Mínimo: {_fmt_brl(r['minimo'])}\n"
        f"- Máximo: {_fmt_brl(r['maximo'])}\n"
    )


async def top_postos_caros(
    ctx: Context,
    uf: str,
    produto: str,
    limite: int = 20,
) -> str:
    """Top postos mais caros observados na UF para um produto.

    Args:
        uf: UF (sigla).
        produto: Nome do produto.
        limite: Top N (padrão 20, máx 100).
    """
    limite = max(1, min(limite, 100))
    sql = (
        "SELECT revenda, municipio, bandeira, MAX(valor_venda) AS preco_max "
        f'FROM "{DATASET_TABLE}" '
        "WHERE UPPER(TRIM(estado)) = ? "
        "AND strip_accents(produto) ILIKE strip_accents(?) "
        "AND valor_venda IS NOT NULL "
        "GROUP BY revenda, municipio, bandeira "
        f"ORDER BY preco_max DESC LIMIT {limite}"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper(), f"%{produto}%"])
    if not rows:
        return "Nenhum resultado."
    table = [
        (
            (r.get("revenda") or "—")[:35],
            (r.get("municipio") or "—")[:20],
            (r.get("bandeira") or "—")[:20],
            _fmt_brl(r.get("preco_max")),
        )
        for r in rows
    ]
    return f"**Top {len(rows)} postos mais caros — {produto} / {uf}**\n\n" + markdown_table(
        ["Revenda", "Município", "Bandeira", "Preço máx"], table
    )


async def media_preco_por_bandeira(
    ctx: Context,
    uf: str,
    produto: str,
    limite: int = 20,
) -> str:
    """Preço médio de venda agrupado por bandeira na UF.

    Args:
        uf: UF (sigla).
        produto: Nome do produto.
        limite: Top N bandeiras (padrão 20).
    """
    limite = max(1, min(limite, 100))
    sql = (
        "SELECT bandeira, COUNT(*) AS amostras, AVG(valor_venda) AS media "
        f'FROM "{DATASET_TABLE}" '
        "WHERE UPPER(TRIM(estado)) = ? "
        "AND strip_accents(produto) ILIKE strip_accents(?) "
        "AND valor_venda IS NOT NULL "
        "GROUP BY bandeira "
        f"ORDER BY amostras DESC LIMIT {limite}"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper(), f"%{produto}%"])
    if not rows:
        return "Nenhum resultado."
    table = [
        (
            (r.get("bandeira") or "—")[:30],
            format_number_br(int(r.get("amostras") or 0), 0),
            _fmt_brl(r.get("media")),
        )
        for r in rows
    ]
    return f"**Preço médio por bandeira — {produto} / {uf}**\n\n" + markdown_table(
        ["Bandeira", "Amostras", "Média"], table
    )
