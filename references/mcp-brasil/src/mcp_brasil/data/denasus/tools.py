"""Tool functions for the DENASUS feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table

from . import client
from .constants import INFO_SNA


async def buscar_auditorias(
    ctx: Context,
    uf: str | None = None,
    palavra_chave: str | None = None,
) -> str:
    """Busca atividades de auditoria do DENASUS (Departamento Nacional de Auditoria do SUS).

    Consulta atividades de auditoria finalizadas do Sistema Nacional de Auditoria.
    Os dados são obtidos da página pública do gov.br.

    Args:
        uf: Sigla do estado para filtrar (ex: "SP", "RJ"). Opcional.
        palavra_chave: Palavra-chave para filtrar nos títulos. Opcional.

    Returns:
        Tabela com atividades de auditoria encontradas.
    """
    await ctx.info("Buscando atividades de auditoria do DENASUS...")

    try:
        atividades = await client.listar_atividades_auditoria()
    except Exception as e:
        await ctx.warning(f"Erro ao acessar página do DENASUS: {e}")
        return (
            "Não foi possível acessar a página de atividades do DENASUS. "
            "O portal gov.br pode estar temporariamente indisponível."
        )

    # Filter by UF
    if uf:
        uf_upper = uf.upper()
        atividades = [a for a in atividades if a.uf == uf_upper]

    # Filter by keyword
    if palavra_chave:
        kw = palavra_chave.lower()
        atividades = [a for a in atividades if kw in a.titulo.lower()]

    if not atividades:
        filtros = []
        if uf:
            filtros.append(f"UF={uf}")
        if palavra_chave:
            filtros.append(f"palavra-chave='{palavra_chave}'")
        filtros_str = ", ".join(filtros) if filtros else "nenhum filtro"
        return f"Nenhuma atividade de auditoria encontrada ({filtros_str})."

    rows = [
        (
            a.titulo[:60],
            a.uf or "—",
            a.tipo or "—",
            a.data or "—",
            a.situacao or "—",
        )
        for a in atividades[:30]
    ]

    header = f"**DENASUS — Atividades de Auditoria** ({len(atividades)} resultado(s))\n\n"
    return header + markdown_table(
        ["Título", "UF", "Tipo", "Data", "Situação"],
        rows,
    )


async def listar_relatorios_anuais(ctx: Context) -> str:
    """Lista relatórios anuais de atividades do DENASUS.

    Retorna os relatórios consolidados do Departamento Nacional de Auditoria
    do SUS, com links para PDFs quando disponíveis.

    Returns:
        Tabela com relatórios anuais e links.
    """
    await ctx.info("Buscando relatórios anuais do DENASUS...")

    try:
        relatorios = await client.listar_relatorios_anuais()
    except Exception as e:
        await ctx.warning(f"Erro ao acessar página do DENASUS: {e}")
        return (
            "Não foi possível acessar a página de relatórios do DENASUS. "
            "O portal gov.br pode estar temporariamente indisponível."
        )

    if not relatorios:
        return "Nenhum relatório anual encontrado na página do DENASUS."

    rows = [
        (
            str(r.ano) if r.ano else "—",
            r.titulo[:60],
            r.url_pdf or "—",
        )
        for r in relatorios
    ]

    header = f"**DENASUS — Relatórios Anuais** ({len(relatorios)} relatório(s))\n\n"
    return header + markdown_table(["Ano", "Título", "PDF"], rows)


async def listar_planos(ctx: Context) -> str:
    """Lista planos anuais de auditoria interna do DENASUS.

    Os planos de auditoria definem as ações de controle interno previstas
    para cada exercício pelo Sistema Nacional de Auditoria.

    Returns:
        Tabela com planos de auditoria e links para PDFs.
    """
    await ctx.info("Buscando planos de auditoria do DENASUS...")

    try:
        planos = await client.listar_planos_auditoria()
    except Exception as e:
        await ctx.warning(f"Erro ao acessar página do DENASUS: {e}")
        return (
            "Não foi possível acessar a página de planos do DENASUS. "
            "O portal gov.br pode estar temporariamente indisponível."
        )

    if not planos:
        return "Nenhum plano de auditoria encontrado na página do DENASUS."

    rows = [
        (
            str(p.ano) if p.ano else "—",
            p.titulo[:60],
            p.url_pdf or "—",
        )
        for p in planos
    ]

    header = f"**DENASUS — Planos de Auditoria** ({len(planos)} plano(s))\n\n"
    return header + markdown_table(["Ano", "Título", "PDF"], rows)


async def verificar_municipio(
    ctx: Context,
    municipio: str,
    uf: str | None = None,
) -> str:
    """Verifica se um município ou hospital foi alvo de auditoria do DENASUS.

    Busca nas atividades de auditoria publicadas por referências ao município.

    Args:
        municipio: Nome do município (ex: "Teresina", "São Paulo").
        uf: Sigla do estado para refinar a busca (ex: "PI", "SP"). Opcional.

    Returns:
        Resultado da verificação com auditorias encontradas.
    """
    await ctx.info(f"Verificando auditorias em {municipio}...")

    try:
        atividades = await client.listar_atividades_auditoria()
    except Exception as e:
        await ctx.warning(f"Erro ao acessar DENASUS: {e}")
        return "Não foi possível acessar o DENASUS para verificação."

    mun_lower = municipio.lower()
    encontradas = [a for a in atividades if mun_lower in a.titulo.lower()]

    if uf:
        uf_upper = uf.upper()
        encontradas = [a for a in encontradas if a.uf == uf_upper or a.uf is None]

    if not encontradas:
        return (
            f"Nenhuma auditoria encontrada para '{municipio}'"
            f"{f' ({uf.upper()})' if uf else ''} "
            "nas atividades publicadas do DENASUS. "
            "Isso pode significar que não houve auditoria publicada "
            "ou que o município não aparece no título da atividade."
        )

    rows = [
        (
            a.titulo[:60],
            a.tipo or "—",
            a.data or "—",
            a.situacao or "—",
        )
        for a in encontradas
    ]

    header = f"**Auditorias em {municipio}** ({len(encontradas)} encontrada(s))\n\n"
    return header + markdown_table(["Título", "Tipo", "Data", "Situação"], rows)


async def informacoes_sna(ctx: Context) -> str:
    """Retorna informações sobre o Sistema Nacional de Auditoria do SUS (SNA).

    Apresenta a estrutura, competências, base legal e contatos do DENASUS
    e do Sistema Nacional de Auditoria.

    Returns:
        Informações detalhadas sobre o SNA/DENASUS.
    """
    await ctx.info("Consultando informações do SNA/DENASUS...")

    lines = [
        f"**{INFO_SNA['nome']}**\n",
        f"- **Órgão:** {INFO_SNA['orgao']}",
        f"- **Vinculação:** {INFO_SNA['vinculacao']}",
        f"- **Base legal:** {INFO_SNA['base_legal']}",
        f"- **Componentes:** {INFO_SNA['componentes']}",
        f"- **Portal:** {INFO_SNA['portal']}",
        f"- **Contato:** {INFO_SNA['contato']}",
        "",
        "**Competência:**",
        INFO_SNA["competencia"],
    ]

    return "\n".join(lines)
