"""Tool functions for the spu_imoveis feature."""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl, format_number_br, markdown_table

from . import client


async def info_dataset_spu(ctx: Context) -> str:
    """Metadados do dataset de patrimônio da União (Raio-X APF).

    Retorna total de imóveis, mês(es) de referência e URLs originais do
    dataset republicado pelo MGI em repositorio.dados.gov.br.

    Returns:
        Resumo com metadados do dataset e estado do cache.
    """
    await ctx.info("Obtendo metadados do dataset SPU...")
    info = await client.info_dataset()
    return (
        f"**{info.nome}**\n\n"
        f"- Total de imóveis: **{format_number_br(info.total_linhas, 0)}**\n"
        f"- Meses de referência: {', '.join(info.meses_referencia) or '—'}\n"
        f"- CSV: {info.url_csv}\n"
        f"- Datapackage: {info.url_datapackage}\n"
        f"- Cache atualizado em: {info.ultima_atualizacao_cache or '—'}\n"
    )


async def buscar_imoveis_spu(
    ctx: Context,
    orgao_sigla: str | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    regime: str | None = None,
    tipo_destinacao: str | None = None,
    limite: int = 30,
) -> str:
    """Lista imóveis da União filtrados por órgão, UF, município, regime ou tipo.

    Todos os parâmetros são opcionais e combináveis (AND lógico). Pelo menos um
    filtro é **altamente recomendado** — sem filtros, retorna apenas os primeiros
    `limite` registros.

    Args:
        orgao_sigla: Sigla do órgão ou órgão superior (ex: "MEC", "MD", "MGI").
            Compara case-insensitive contra `orgao_superior_sigla` e `orgao_sigla`.
        uf: Sigla da UF (ex: "DF", "SP", "RJ").
        municipio: Substring do nome do município (ex: "Rio de Janeiro", "brasília").
        regime: Substring do regime de utilização (ex: "aforamento", "imóvel funcional",
            "cessão", "uso em serviço público").
        tipo_destinacao: Substring do tipo (ex: "apartamento", "terreno", "fazenda").
        limite: Máximo de imóveis a retornar (padrão 30, máximo 200).

    Returns:
        Tabela com órgão, UF, município, regime, tipo, endereço e valor.
    """
    limite = max(1, min(limite, 200))
    await ctx.info(
        f"Buscando imóveis SPU (orgao={orgao_sigla}, uf={uf}, "
        f"municipio={municipio}, regime={regime}, tipo={tipo_destinacao})..."
    )
    imoveis = await client.buscar_imoveis(
        orgao_sigla=orgao_sigla,
        uf=uf,
        municipio=municipio,
        regime=regime,
        tipo_destinacao=tipo_destinacao,
        limite=limite,
    )
    if not imoveis:
        return "Nenhum imóvel encontrado para os filtros informados."

    await ctx.info(f"{len(imoveis)} imóvel(is) retornado(s)")

    rows = []
    for i in imoveis:
        rows.append(
            (
                (i.orgao_superior_sigla or "?"),
                i.uf or "—",
                (i.municipio_nome or "—")[:25],
                (i.regime_utilizacao or "—")[:35],
                (i.tipo_destinacao or "—")[:20],
                (i.endereco or "—")[:40],
                format_brl(i.valor_imovel) if i.valor_imovel else "—",
            )
        )
    return f"**Imóveis da União — {len(imoveis)} resultado(s)**\n\n" + markdown_table(
        ["Órgão", "UF", "Município", "Regime", "Tipo", "Endereço", "Valor"],
        rows,
    )


async def resumo_orgaos_spu(ctx: Context, top: int = 15) -> str:
    """Agrega o patrimônio da União por órgão superior.

    Args:
        top: Quantidade de órgãos a exibir no ranking (padrão 15).

    Returns:
        Tabela ordenada pelo número de imóveis (desc) com contagem, área
        total, área construída e valor total por órgão superior.
    """
    await ctx.info("Agregando patrimônio por órgão superior...")
    top = max(1, min(top, 50))
    resumos = await client.resumo_por_orgao(top=top)
    if not resumos:
        return "Nenhum dado disponível."

    rows = [
        (
            r.orgao_superior_sigla,
            (r.orgao_superior_nome or "—")[:45],
            format_number_br(r.total_imoveis, 0),
            format_number_br(r.area_total_m2 / 1_000_000, 2) + " km²",
            format_brl(r.valor_total),
        )
        for r in resumos
    ]
    return f"**Patrimônio da União por Órgão Superior — Top {len(resumos)}**\n\n" + markdown_table(
        ["Sigla", "Órgão", "Imóveis", "Área (km²)", "Valor total"],
        rows,
    )


async def resumo_ufs_spu(ctx: Context) -> str:
    """Agrega o patrimônio da União por UF.

    Returns:
        Tabela com contagem de imóveis, área total, valor total e valor
        total de aluguel por UF (ordenado desc por quantidade).
    """
    await ctx.info("Agregando patrimônio por UF...")
    resumos = await client.resumo_por_uf()
    if not resumos:
        return "Nenhum dado disponível."

    rows = [
        (
            r.uf,
            format_number_br(r.total_imoveis, 0),
            format_number_br(r.area_total_m2 / 1_000_000, 2) + " km²",
            format_brl(r.valor_total),
            format_brl(r.valor_aluguel_total),
        )
        for r in resumos
    ]
    return "**Patrimônio da União por UF**\n\n" + markdown_table(
        ["UF", "Imóveis", "Área (km²)", "Valor total", "Aluguel anual"],
        rows,
    )
