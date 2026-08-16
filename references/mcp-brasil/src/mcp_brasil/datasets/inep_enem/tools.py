"""Canned SQL tools for the inep_enem dataset."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from mcp_brasil._shared.datasets import executar_query, get_status, refresh_dataset
from mcp_brasil._shared.formatting import format_number_br, markdown_table

from . import DATASET_SPEC, DATASET_TABLE
from .constants import ANO_COBERTURA, COLUNAS_DISTINCT_PERMITIDAS, COR_RACA, ESCOLA, SEXOS


async def info_enem(ctx: Context) -> str:
    """Estado do cache local dos microdados ENEM."""
    await ctx.info("Consultando estado do cache ENEM...")
    st = await get_status(DATASET_SPEC)
    return "\n".join(
        [
            f"**ENEM {ANO_COBERTURA} — estado do cache**",
            "",
            f"- **Cached:** {'sim' if st['cached'] else 'não'}",
            f"- **Linhas:** {format_number_br(st['row_count'], 0) if st['cached'] else '—'}",
            f"- **Tamanho:** {st['size_bytes'] / 1024 / 1024:.1f} MB",
            "- **Idade:** "
            + (f"{st['age_days']:.2f} dias" if st.get("age_days") is not None else "—"),
            f"- **Fonte:** {st['source']}",
        ]
    )


async def refrescar_enem(ctx: Context) -> str:
    """Força re-download dos microdados ENEM. Pode levar 10+ min."""
    await ctx.info("Re-baixando ENEM... ZIP ~520 MB, descompressão demorada.")
    m = await refresh_dataset(DATASET_SPEC)
    return (
        f"**ENEM atualizado**\n\n"
        f"- Linhas: {format_number_br(m.row_count, 0)}\n"
        f"- Tamanho: {m.size_bytes / 1024 / 1024:.1f} MB\n"
    )


async def valores_distintos_enem(coluna: str, limite: int = 100) -> str:
    """Valores distintos de uma coluna categórica dos microdados ENEM.

    Args:
        coluna: Ex: SG_UF_PROVA, TP_COR_RACA, TP_ESCOLA, TP_SEXO.
        limite: Padrão 100, máx 500.
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
    return markdown_table(
        [coluna, "ocorrencias"],
        [(r["valor"], format_number_br(int(r["total"]), 0)) for r in rows],
    )


async def media_notas_uf(ctx: Context, uf: str) -> str:
    """Média das 4 áreas + redação para inscritos cuja prova foi em uma UF.

    Considera apenas presentes em ambos os dias (TP_PRESENCA_* = 1 para CN e LC).

    Args:
        uf: Sigla da UF de realização da prova (ex: 'SP').
    """
    sql = (
        "SELECT COUNT(*) AS n, "
        "AVG(NU_NOTA_CN) AS cn, AVG(NU_NOTA_CH) AS ch, "
        "AVG(NU_NOTA_LC) AS lc, AVG(NU_NOTA_MT) AS mt, "
        "AVG(NU_NOTA_REDACAO) AS red "
        f'FROM "{DATASET_TABLE}" '
        "WHERE UPPER(TRIM(SG_UF_PROVA)) = ? "
        "AND TP_PRESENCA_CN = 1 AND TP_PRESENCA_LC = 1 "
        "AND NU_NOTA_CN IS NOT NULL"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper()])
    if not rows or not rows[0].get("n"):
        return f"Sem dados para UF '{uf}'."
    r = rows[0]

    def _f(v: Any) -> str:
        try:
            return f"{float(v):.1f}"
        except (TypeError, ValueError):
            return "—"

    return (
        f"**ENEM {ANO_COBERTURA} — médias em {uf.upper()}**\n\n"
        f"- Presentes: {format_number_br(int(r['n']), 0)}\n"
        f"- Ciências da Natureza: {_f(r['cn'])}\n"
        f"- Ciências Humanas: {_f(r['ch'])}\n"
        f"- Linguagens e Códigos: {_f(r['lc'])}\n"
        f"- Matemática: {_f(r['mt'])}\n"
        f"- Redação: {_f(r['red'])}\n"
    )


async def media_notas_por_grupo(
    ctx: Context,
    coluna: str,
    uf: str | None = None,
) -> str:
    """Média das 5 notas agrupada por coluna categórica (ex: TP_ESCOLA, TP_COR_RACA).

    Args:
        coluna: Coluna categórica. Permitidas: TP_ESCOLA, TP_COR_RACA, TP_SEXO,
            TP_FAIXA_ETARIA, TP_LINGUA.
        uf: Filtra UF da prova (opcional).
    """
    if coluna not in {
        "TP_ESCOLA",
        "TP_COR_RACA",
        "TP_SEXO",
        "TP_FAIXA_ETARIA",
        "TP_LINGUA",
    }:
        return f"Coluna '{coluna}' não permitida para agrupamento."
    where = "TP_PRESENCA_CN = 1 AND TP_PRESENCA_LC = 1"
    params: list[Any] = []
    if uf:
        where += " AND UPPER(TRIM(SG_UF_PROVA)) = ?"
        params.append(uf.strip().upper())
    sql = (
        f'SELECT "{coluna}" AS g, COUNT(*) AS n, '
        "AVG(NU_NOTA_CN) AS cn, AVG(NU_NOTA_CH) AS ch, "
        "AVG(NU_NOTA_LC) AS lc, AVG(NU_NOTA_MT) AS mt, "
        "AVG(NU_NOTA_REDACAO) AS red "
        f'FROM "{DATASET_TABLE}" WHERE {where} '
        f'GROUP BY "{coluna}" ORDER BY g'
    )
    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows:
        return "Nenhum dado."

    def _f(v: Any) -> str:
        try:
            return f"{float(v):.1f}"
        except (TypeError, ValueError):
            return "—"

    def _label(v: Any) -> str:
        if coluna == "TP_COR_RACA" and v is not None:
            return COR_RACA.get(int(v), str(v))
        if coluna == "TP_ESCOLA" and v is not None:
            return ESCOLA.get(int(v), str(v))
        if coluna == "TP_SEXO":
            return SEXOS.get(str(v), str(v))
        return str(v) if v is not None else "—"

    table = [
        (
            _label(r.get("g")),
            format_number_br(int(r.get("n") or 0), 0),
            _f(r.get("cn")),
            _f(r.get("ch")),
            _f(r.get("lc")),
            _f(r.get("mt")),
            _f(r.get("red")),
        )
        for r in rows
    ]
    titulo = f"Médias por {coluna}" + (f" em {uf.upper()}" if uf else "")
    return f"**{titulo}**\n\n" + markdown_table(
        ["Grupo", "n", "CN", "CH", "LC", "MT", "Redação"], table
    )


async def top_municipios_por_media(
    ctx: Context,
    uf: str,
    minimo_participantes: int = 100,
    limite: int = 20,
) -> str:
    """Top municípios de uma UF pela média total (soma das 5 notas).

    Filtra municípios com pelo menos ``minimo_participantes`` inscritos
    presentes para reduzir ruído estatístico.

    Args:
        uf: Sigla da UF.
        minimo_participantes: Mínimo de inscritos presentes por município (padrão 100).
        limite: Top N (padrão 20, máx 100).
    """
    limite = max(1, min(limite, 100))
    sql = (
        "SELECT NO_MUNICIPIO_PROVA, COUNT(*) AS n, "
        "AVG(NU_NOTA_CN + NU_NOTA_CH + NU_NOTA_LC + NU_NOTA_MT + NU_NOTA_REDACAO) AS media_total "
        f'FROM "{DATASET_TABLE}" '
        "WHERE UPPER(TRIM(SG_UF_PROVA)) = ? "
        "AND TP_PRESENCA_CN = 1 AND TP_PRESENCA_LC = 1 "
        "AND NU_NOTA_CN IS NOT NULL "
        "GROUP BY NO_MUNICIPIO_PROVA "
        f"HAVING n >= {minimo_participantes} "
        f"ORDER BY media_total DESC LIMIT {limite}"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper()])
    if not rows:
        return f"Nenhum município atende ao mínimo em '{uf}'."

    def _f(v: Any) -> str:
        try:
            return f"{float(v):.1f}"
        except (TypeError, ValueError):
            return "—"

    table = [
        (
            (r.get("NO_MUNICIPIO_PROVA") or "—")[:30],
            format_number_br(int(r.get("n") or 0), 0),
            _f(r.get("media_total")),
        )
        for r in rows
    ]
    return (
        f"**Top {len(rows)} municípios em {uf.upper()} — média total (5 notas somadas)**\n\n"
        + markdown_table(["Município", "n", "Média total"], table)
    )
