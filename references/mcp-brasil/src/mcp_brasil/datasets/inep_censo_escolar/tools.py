"""Canned SQL tools for the inep_censo_escolar dataset."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from mcp_brasil._shared.datasets import executar_query, get_status, refresh_dataset
from mcp_brasil._shared.formatting import format_number_br, markdown_table

from . import DATASET_SPEC, DATASET_TABLE
from .constants import COLUNAS_DISTINCT_PERMITIDAS, DEPENDENCIAS, LOCALIZACOES, SITUACOES


async def info_censo_escolar(ctx: Context) -> str:
    """Estado do cache local do Censo Escolar."""
    await ctx.info("Consultando estado do cache Censo Escolar...")
    st = await get_status(DATASET_SPEC)
    return "\n".join(
        [
            "**Censo Escolar — estado do cache**",
            "",
            f"- **Cached:** {'sim' if st['cached'] else 'não'}",
            f"- **Linhas:** {format_number_br(st['row_count'], 0) if st['cached'] else '—'}",
            f"- **Tamanho:** {st['size_bytes'] / 1024 / 1024:.1f} MB",
            "- **Idade:** "
            + (f"{st['age_days']:.2f} dias" if st.get("age_days") is not None else "—"),
            f"- **Fonte:** {st['source']}",
        ]
    )


async def refrescar_censo_escolar(ctx: Context) -> str:
    """Força re-download do Censo Escolar (ignora TTL)."""
    await ctx.info("Re-baixando Censo Escolar... ZIP de ~32 MB + descompressão (~3-5 min).")
    m = await refresh_dataset(DATASET_SPEC)
    return (
        f"**Censo Escolar atualizado**\n\n"
        f"- Linhas: {format_number_br(m.row_count, 0)}\n"
        f"- Tamanho: {m.size_bytes / 1024 / 1024:.1f} MB\n"
    )


async def valores_distintos_censo(coluna: str, limite: int = 100) -> str:
    """Valores distintos de uma coluna categórica do Censo.

    Args:
        coluna: Ex: SG_UF, TP_DEPENDENCIA, NO_MUNICIPIO.
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


async def buscar_escolas(
    ctx: Context,
    uf: str | None = None,
    municipio: str | None = None,
    dependencia: int | None = None,
    localizacao: int | None = None,
    nome: str | None = None,
    limite: int = 50,
) -> str:
    """Busca escolas no Censo por filtros combinados.

    Args:
        uf: Sigla da UF (ex: "SP").
        municipio: Nome do município (substring, accent-insensitive).
        dependencia: 1=Federal, 2=Estadual, 3=Municipal, 4=Privada.
        localizacao: 1=Urbana, 2=Rural.
        nome: Substring do nome da escola (accent-insensitive).
        limite: Padrão 50, máx 200.
    """
    limite = max(1, min(limite, 200))
    where: list[str] = []
    params: list[Any] = []
    if uf:
        where.append("UPPER(TRIM(SG_UF)) = ?")
        params.append(uf.strip().upper())
    if municipio:
        where.append("strip_accents(NO_MUNICIPIO) ILIKE strip_accents(?)")
        params.append(f"%{municipio}%")
    if dependencia is not None:
        where.append("TP_DEPENDENCIA = ?")
        params.append(dependencia)
    if localizacao is not None:
        where.append("TP_LOCALIZACAO = ?")
        params.append(localizacao)
    if nome:
        where.append("strip_accents(NO_ENTIDADE) ILIKE strip_accents(?)")
        params.append(f"%{nome}%")
    where_sql = " AND ".join(where) if where else "1=1"
    sql = (
        "SELECT CO_ENTIDADE, NO_ENTIDADE, SG_UF, NO_MUNICIPIO, "
        "TP_DEPENDENCIA, TP_LOCALIZACAO, TP_SITUACAO_FUNCIONAMENTO "
        f'FROM "{DATASET_TABLE}" WHERE {where_sql} LIMIT {limite}'
    )
    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows:
        return "Nenhuma escola encontrada."
    table = [
        (
            r.get("CO_ENTIDADE") or "—",
            (r.get("NO_ENTIDADE") or "—")[:45],
            r.get("SG_UF") or "—",
            (r.get("NO_MUNICIPIO") or "—")[:20],
            DEPENDENCIAS.get(int(r["TP_DEPENDENCIA"]), "?") if r.get("TP_DEPENDENCIA") else "—",
            LOCALIZACOES.get(int(r["TP_LOCALIZACAO"]), "?") if r.get("TP_LOCALIZACAO") else "—",
            SITUACOES.get(int(r["TP_SITUACAO_FUNCIONAMENTO"]), "?")
            if r.get("TP_SITUACAO_FUNCIONAMENTO")
            else "—",
        )
        for r in rows
    ]
    return f"**{len(rows)} escolas encontradas**\n\n" + markdown_table(
        ["Código", "Nome", "UF", "Município", "Dependência", "Localização", "Situação"],
        table,
    )


async def escola_detalhe(ctx: Context, co_entidade: int) -> str:
    """Detalhe de uma escola pelo código CO_ENTIDADE.

    Retorna atributos principais: identificação, localização, infraestrutura.

    Args:
        co_entidade: Código INEP da escola.
    """
    sql = (
        "SELECT CO_ENTIDADE, NO_ENTIDADE, SG_UF, NO_MUNICIPIO, DS_ENDERECO, "
        "NO_BAIRRO, CO_CEP, TP_DEPENDENCIA, TP_LOCALIZACAO, "
        "TP_SITUACAO_FUNCIONAMENTO, "
        "IN_AGUA_POTAVEL, IN_ENERGIA_REDE_PUBLICA, IN_ESGOTO_REDE_PUBLICA, "
        "IN_INTERNET, IN_BIBLIOTECA, IN_QUADRA_ESPORTES, IN_LABORATORIO_CIENCIAS, "
        "IN_LABORATORIO_INFORMATICA, IN_REFEITORIO "
        f'FROM "{DATASET_TABLE}" WHERE CO_ENTIDADE = ? LIMIT 1'
    )
    rows = await executar_query(DATASET_SPEC, sql, [co_entidade])
    if not rows:
        return f"Escola {co_entidade} não encontrada."
    r = rows[0]

    def _yn(v: Any) -> str:
        if v in (1, "1", True):
            return "✔"
        if v in (0, "0", False):
            return "✘"
        return "?"

    return "\n".join(
        [
            f"**{r.get('NO_ENTIDADE')}** ({r.get('CO_ENTIDADE')})",
            "",
            f"- **Endereço:** {r.get('DS_ENDERECO') or '—'}, {r.get('NO_BAIRRO') or '—'}",
            f"- **Município/UF:** {r.get('NO_MUNICIPIO')} / {r.get('SG_UF')}",
            f"- **CEP:** {r.get('CO_CEP') or '—'}",
            "- **Dependência:** "
            + (
                DEPENDENCIAS.get(int(r["TP_DEPENDENCIA"]), "?") if r.get("TP_DEPENDENCIA") else "—"
            ),
            "- **Localização:** "
            + (
                LOCALIZACOES.get(int(r["TP_LOCALIZACAO"]), "?") if r.get("TP_LOCALIZACAO") else "—"
            ),
            "- **Situação:** "
            + (
                SITUACOES.get(int(r["TP_SITUACAO_FUNCIONAMENTO"]), "?")
                if r.get("TP_SITUACAO_FUNCIONAMENTO")
                else "—"
            ),
            "",
            "**Infraestrutura:**",
            f"- Água potável: {_yn(r.get('IN_AGUA_POTAVEL'))}",
            f"- Energia (rede pública): {_yn(r.get('IN_ENERGIA_REDE_PUBLICA'))}",
            f"- Esgoto (rede pública): {_yn(r.get('IN_ESGOTO_REDE_PUBLICA'))}",
            f"- Internet: {_yn(r.get('IN_INTERNET'))}",
            f"- Biblioteca: {_yn(r.get('IN_BIBLIOTECA'))}",
            f"- Quadra de esportes: {_yn(r.get('IN_QUADRA_ESPORTES'))}",
            f"- Laboratório de ciências: {_yn(r.get('IN_LABORATORIO_CIENCIAS'))}",
            f"- Laboratório de informática: {_yn(r.get('IN_LABORATORIO_INFORMATICA'))}",
            f"- Refeitório: {_yn(r.get('IN_REFEITORIO'))}",
        ]
    )


async def resumo_uf(ctx: Context, uf: str) -> str:
    """Resumo de escolas por dependência em uma UF.

    Args:
        uf: Sigla da UF.
    """
    sql = (
        "SELECT TP_DEPENDENCIA, COUNT(*) AS total "
        f'FROM "{DATASET_TABLE}" '
        "WHERE UPPER(TRIM(SG_UF)) = ? "
        "GROUP BY TP_DEPENDENCIA ORDER BY TP_DEPENDENCIA"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper()])
    if not rows:
        return f"Nenhum dado para UF '{uf}'."
    table = [
        (
            DEPENDENCIAS.get(int(r["TP_DEPENDENCIA"]), "?") if r.get("TP_DEPENDENCIA") else "—",
            format_number_br(int(r.get("total") or 0), 0),
        )
        for r in rows
    ]
    return f"**Escolas em {uf.upper()} por dependência**\n\n" + markdown_table(
        ["Dependência", "Total"], table
    )


async def top_municipios_por_escolas(ctx: Context, uf: str, limite: int = 20) -> str:
    """Top N municípios de uma UF com mais escolas.

    Args:
        uf: Sigla da UF.
        limite: Padrão 20, máx 100.
    """
    limite = max(1, min(limite, 100))
    sql = (
        "SELECT NO_MUNICIPIO, COUNT(*) AS total "
        f'FROM "{DATASET_TABLE}" WHERE UPPER(TRIM(SG_UF)) = ? '
        f"GROUP BY NO_MUNICIPIO ORDER BY total DESC LIMIT {limite}"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper()])
    if not rows:
        return f"Sem dados para UF '{uf}'."
    return (
        f"**Top {len(rows)} municípios em {uf.upper()} por nº de escolas**\n\n"
        + markdown_table(
            ["Município", "Escolas"],
            [
                (
                    (r.get("NO_MUNICIPIO") or "—")[:30],
                    format_number_br(int(r.get("total") or 0), 0),
                )
                for r in rows
            ],
        )
    )
