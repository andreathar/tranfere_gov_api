"""Canned SQL query tools for the spu_siapa dataset feature."""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from mcp_brasil._shared.datasets import executar_query, get_status, refresh_dataset
from mcp_brasil._shared.formatting import format_number_br, markdown_table

from . import DATASET_SPEC, DATASET_TABLE
from .constants import COLUNAS_DISTINCT_PERMITIDAS


def _fmt_m2(v: Any) -> str:
    try:
        n = float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return "—"
    return f"{format_number_br(n, 0)} m²" if n else "—"


async def info_spu_siapa(ctx: Context) -> str:
    """Estado do cache local do dataset SIAPA/SPU.

    Retorna tamanho, número de linhas, idade do cache e frescor. Não faz
    download — apenas introspecta o estado local.

    Returns:
        Metadados do cache do dataset.
    """
    await ctx.info("Consultando estado do cache SIAPA...")
    st = await get_status(DATASET_SPEC)
    lines = [
        "**Dataset SIAPA — estado do cache**",
        "",
        f"- **Cached localmente:** {'sim' if st['cached'] else 'não'}",
        f"- **Linhas:** {format_number_br(st['row_count'], 0) if st['cached'] else '—'}",
        f"- **Tamanho:** {st['size_bytes'] / 1024 / 1024:.1f} MB",
        "- **Idade:** "
        + (f"{st['age_days']:.2f} dias" if st.get("age_days") is not None else "—"),
        f"- **Fresh (dentro do TTL={st['ttl_days']}d):** {'sim' if st['fresh'] else 'não'}",
        f"- **Fonte:** {st['source']}",
        f"- **URL:** {st['url']}",
    ]
    return "\n".join(lines)


async def refrescar_spu_siapa(ctx: Context) -> str:
    """Força re-download do dataset SIAPA (ignora TTL).

    Use quando souber que os dados mudaram antes do ciclo de 30d.

    Returns:
        Confirmação com contagem de linhas da nova versão.
    """
    await ctx.info("Re-baixando SIAPA... isso pode levar 1-3 minutos.")
    manifest = await refresh_dataset(DATASET_SPEC)
    return (
        f"**Dataset SIAPA atualizado**\n\n"
        f"- Linhas: {format_number_br(manifest.row_count, 0)}\n"
        f"- Tamanho: {manifest.size_bytes / 1024 / 1024:.1f} MB\n"
        f"- Schema hash: `{manifest.schema_hash}`\n"
    )


async def buscar_imoveis_siapa(
    ctx: Context,
    uf: str | None = None,
    municipio: str | None = None,
    regime: str | None = None,
    conceituacao: str | None = None,
    classe: str | None = None,
    rip: str | None = None,
    limite: int = 30,
) -> str:
    """Busca imóveis da União no SIAPA consolidado por filtros combinados.

    Cobre imóveis **dominiais** (em aforamento/ocupação com particulares) e
    de **uso especial** (órgãos federais). Cobertura superior ao dataset
    Raio-X APF: ~787k imóveis vs 54k.

    Pelo menos um filtro é **altamente recomendado** — sem filtro, retorna
    apenas os primeiros `limite` registros.

    **Dica:** todos os filtros de texto são case/accent-insensitive — você
    pode passar 'Brasília' ou 'Brasilia', 'São Paulo' ou 'sao paulo'.
    Para descobrir valores válidos de regime / conceituacao / classe numa
    coluna, chame primeiro `valores_distintos_siapa(coluna)`.

    Args:
        uf: UF (sigla). Ex: 'RJ', 'SP', 'DF'.
        municipio: Nome do município (substring, accent-insensitive).
        regime: Regime de utilização — ex: 'Aforamento',
            'Inscrição de Ocupação', 'Concessão de Direito Real de Uso'.
        conceituacao: Conceituação do terreno — ex: 'Marinha',
            'Acrescido de Marinha', 'Marginal de Rio', 'Nacional Interior'.
            **Atenção:** 'Ilha' NÃO é um valor — ilhas federais vivem em
            'Nacional Interior' ou na feature `spu_geo`.
        classe: 'Dominial' (92%) ou 'Uso Especial' (8%).
        rip: RIP do imóvel (match exato ou prefixo).
        limite: Máximo de linhas (padrão 30, máximo 200).

    Returns:
        Tabela com RIP, UF, município, endereço, regime, conceituação e área.
    """
    limite = max(1, min(limite, 200))
    await ctx.info(
        f"SIAPA query (uf={uf}, municipio={municipio}, "
        f"regime={regime}, conceituacao={conceituacao}, classe={classe}, rip={rip})..."
    )

    where: list[str] = []
    params: list[Any] = []
    if uf:
        where.append("TRIM(uf) = ?")
        params.append(uf.strip().upper())
    if municipio:
        # Accent-insensitive match — SIAPA armazena municípios sem acento,
        # mas o usuário pode passar "Brasília", "São Paulo", etc.
        where.append("strip_accents(municipio) ILIKE strip_accents(?)")
        params.append(f"%{municipio}%")
    if regime:
        where.append("strip_accents(regime_utilizacao) ILIKE strip_accents(?)")
        params.append(f"%{regime}%")
    if conceituacao:
        where.append("strip_accents(conceituacao_terreno) ILIKE strip_accents(?)")
        params.append(f"%{conceituacao}%")
    if classe:
        where.append("classe ILIKE ?")
        params.append(f"%{classe}%")
    if rip:
        where.append("CAST(rip_imovel AS VARCHAR) LIKE ?")
        params.append(f"{rip}%")

    where_sql = " AND ".join(where) if where else "1=1"
    sql = (
        "SELECT classe, rip_imovel, rip_utilizacao, uf, municipio, endereco, "
        "regime_utilizacao, conceituacao_terreno, tipo_imovel, area_uniao_m2 "
        f'FROM "{DATASET_TABLE}" WHERE {where_sql} LIMIT {limite}'
    )

    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows:
        return (
            "Nenhum imóvel encontrado para os filtros informados. "
            "Dica: use `valores_distintos_siapa` para ver os valores exatos "
            "de regime/conceituacao/classe presentes na base."
        )

    table_rows = [
        (
            str(r.get("rip_imovel") or "—"),
            (r.get("uf") or "—").strip(),
            (r.get("municipio") or "—")[:20],
            (r.get("endereco") or "—")[:40],
            (r.get("regime_utilizacao") or "—")[:28],
            (r.get("conceituacao_terreno") or "—")[:22],
            _fmt_m2(r.get("area_uniao_m2")),
        )
        for r in rows
    ]
    return f"**SIAPA — {len(rows)} imóvel(is) encontrado(s)**\n\n" + markdown_table(
        ["RIP", "UF", "Município", "Endereço", "Regime", "Conceituação", "Área União"],
        table_rows,
    )


async def resumo_regime_siapa(
    ctx: Context,
    uf: str | None = None,
) -> str:
    """Agrega imóveis SIAPA por regime de utilização (opcionalmente por UF).

    Args:
        uf: Filtra por UF (opcional). Se omitido, retorna Brasil todo.

    Returns:
        Tabela com regime, contagem e área total por regime.
    """
    await ctx.info(f"Agregando SIAPA por regime (uf={uf})...")

    where = "TRIM(uf) = ?" if uf else "1=1"
    params: list[Any] = [uf.strip().upper()] if uf else []
    sql = (
        "SELECT regime_utilizacao, COUNT(*) AS total, "
        "SUM(COALESCE(area_uniao_m2, 0)) AS area_total "
        f'FROM "{DATASET_TABLE}" WHERE {where} '
        "GROUP BY regime_utilizacao ORDER BY total DESC"
    )
    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows:
        return "Nenhum dado disponível."

    table_rows = [
        (
            r.get("regime_utilizacao") or "—",
            format_number_br(int(r.get("total") or 0), 0),
            _fmt_m2(r.get("area_total")),
        )
        for r in rows
    ]
    titulo = f"SIAPA — regimes em {uf}" if uf else "SIAPA — regimes (Brasil)"
    return f"**{titulo}**\n\n" + markdown_table(["Regime", "Imóveis", "Área União"], table_rows)


async def resumo_conceituacao_siapa(
    ctx: Context,
    uf: str | None = None,
) -> str:
    """Agrega imóveis SIAPA por conceituação do terreno (marinha, marginal, etc.).

    Args:
        uf: Filtra por UF (opcional).

    Returns:
        Tabela com conceituação, contagem e área total.
    """
    await ctx.info(f"Agregando SIAPA por conceituação (uf={uf})...")

    where = "TRIM(uf) = ?" if uf else "1=1"
    params: list[Any] = [uf.strip().upper()] if uf else []
    sql = (
        "SELECT conceituacao_terreno, COUNT(*) AS total, "
        "SUM(COALESCE(area_uniao_m2, 0)) AS area_total "
        f'FROM "{DATASET_TABLE}" WHERE {where} '
        "GROUP BY conceituacao_terreno ORDER BY total DESC"
    )
    rows = await executar_query(DATASET_SPEC, sql, params)
    if not rows:
        return "Nenhum dado disponível."

    table_rows = [
        (
            r.get("conceituacao_terreno") or "—",
            format_number_br(int(r.get("total") or 0), 0),
            _fmt_m2(r.get("area_total")),
        )
        for r in rows
    ]
    titulo = f"SIAPA — conceituação em {uf}" if uf else "SIAPA — conceituação (Brasil)"
    return f"**{titulo}**\n\n" + markdown_table(
        ["Conceituação", "Imóveis", "Área União"], table_rows
    )


async def resumo_uf_siapa(ctx: Context) -> str:
    """Agrega imóveis SIAPA por UF — contagem, área e breakdown dominial/uso especial.

    Returns:
        Tabela ordenada desc por número de imóveis.
    """
    await ctx.info("Agregando SIAPA por UF...")
    sql = (
        "SELECT TRIM(uf) AS uf, COUNT(*) AS total, "
        "SUM(CASE WHEN classe ILIKE 'Dominial%' THEN 1 ELSE 0 END) AS dominiais, "
        "SUM(CASE WHEN classe ILIKE 'Uso Especial%' THEN 1 ELSE 0 END) AS uso_especial, "
        "SUM(COALESCE(area_uniao_m2, 0)) AS area_total "
        f'FROM "{DATASET_TABLE}" '
        "GROUP BY TRIM(uf) ORDER BY total DESC"
    )
    rows = await executar_query(DATASET_SPEC, sql)
    if not rows:
        return "Nenhum dado disponível."

    table_rows = [
        (
            r.get("uf") or "—",
            format_number_br(int(r.get("total") or 0), 0),
            format_number_br(int(r.get("dominiais") or 0), 0),
            format_number_br(int(r.get("uso_especial") or 0), 0),
            _fmt_m2(r.get("area_total")),
        )
        for r in rows
    ]
    return "**SIAPA — imóveis da União por UF**\n\n" + markdown_table(
        ["UF", "Total", "Dominiais", "Uso Especial", "Área União"],
        table_rows,
    )


async def valores_distintos_siapa(
    ctx: Context,
    coluna: str,
    top: int = 30,
) -> str:
    """Descobre os valores reais de uma coluna categórica do SIAPA.

    Use **antes** de `buscar_imoveis_siapa` quando não souber o nome exato
    de um regime, conceituação, tipo ou classe. Retorna os valores únicos
    ordenados por frequência — o que existe de fato na base vem primeiro.

    Args:
        coluna: Nome da coluna. Valores permitidos:
            'classe', 'regime_utilizacao', 'conceituacao_terreno',
            'tipo_imovel', 'proprietario_oficial', 'nivel_precisao', 'uf'.
        top: Máximo de valores a retornar (padrão 30).

    Returns:
        Tabela com valor + contagem, ordenada desc por contagem.
    """
    if coluna not in COLUNAS_DISTINCT_PERMITIDAS:
        return f"Coluna '{coluna}' não suportada. Use uma de: " + ", ".join(
            sorted(COLUNAS_DISTINCT_PERMITIDAS)
        )
    top = max(1, min(top, 100))
    await ctx.info(f"Listando valores distintos de {coluna}...")

    # coluna já validada contra allowlist → interpolação direta é segura
    sql = (
        f'SELECT "{coluna}" AS valor, COUNT(*) AS total '
        f'FROM "{DATASET_TABLE}" GROUP BY "{coluna}" '
        f"ORDER BY total DESC LIMIT {top}"
    )
    rows = await executar_query(DATASET_SPEC, sql)
    if not rows:
        return f"Nenhum valor encontrado para coluna '{coluna}'."

    table_rows = [
        (
            str(r.get("valor")) if r.get("valor") is not None else "(null)",
            format_number_br(int(r.get("total") or 0), 0),
        )
        for r in rows
    ]
    return (
        f"**SIAPA — valores distintos em `{coluna}`** ({len(rows)} valores)\n\n"
        + markdown_table(["Valor", "Ocorrências"], table_rows)
    )


async def top_municipios_siapa(
    ctx: Context,
    uf: str,
    top: int = 20,
) -> str:
    """Top municípios de uma UF por número de imóveis da União.

    Args:
        uf: UF (sigla obrigatória).
        top: Quantidade de municípios (padrão 20, máx 100).

    Returns:
        Tabela ordenada desc por contagem de imóveis.
    """
    top = max(1, min(top, 100))
    await ctx.info(f"Top {top} municípios de {uf}...")
    sql = (
        "SELECT municipio, COUNT(*) AS total, "
        "SUM(COALESCE(area_uniao_m2, 0)) AS area_total "
        f'FROM "{DATASET_TABLE}" WHERE TRIM(uf) = ? '
        f"GROUP BY municipio ORDER BY total DESC LIMIT {top}"
    )
    rows = await executar_query(DATASET_SPEC, sql, [uf.strip().upper()])
    if not rows:
        return f"Nenhum imóvel da União em {uf}."

    table_rows = [
        (
            r.get("municipio") or "—",
            format_number_br(int(r.get("total") or 0), 0),
            _fmt_m2(r.get("area_total")),
        )
        for r in rows
    ]
    return f"**SIAPA — Top {len(rows)} municípios de {uf}**\n\n" + markdown_table(
        ["Município", "Imóveis", "Área União"], table_rows
    )
