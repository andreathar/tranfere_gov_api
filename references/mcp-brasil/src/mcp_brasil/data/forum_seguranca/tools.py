"""Tool functions for the Fórum Brasileiro de Segurança Pública feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from . import client
from .constants import COMUNIDADES


async def buscar_publicacoes_seguranca(
    query: str,
    ctx: Context,
    limite: int = 10,
    pagina: int = 0,
) -> str:
    """Busca publicações no repositório do Fórum Brasileiro de Segurança Pública.

    Pesquisa em 236+ publicações sobre segurança pública, violência,
    criminalidade, sistema prisional, policiamento e temas relacionados.

    Args:
        query: Termo de busca (ex: 'feminicídio', 'homicídio', 'policial', 'anuário').
        limite: Máximo de resultados por página (padrão 10, máximo 50).
        pagina: Número da página (começa em 0).

    Returns:
        Lista de publicações encontradas com título, autores e data.
    """
    await ctx.info(f"Buscando publicações sobre '{query}'...")
    resultado = await client.buscar_publicacoes(query, limite, pagina)

    if not resultado.publicacoes:
        return f"Nenhuma publicação encontrada para '{query}'."

    n = len(resultado.publicacoes)
    pag = f"página {resultado.pagina + 1}/{resultado.total_paginas}"
    lines = [f"**{resultado.total} publicações encontradas** (mostrando {n}, {pag})\n"]

    for i, pub in enumerate(resultado.publicacoes, 1):
        autores = ", ".join(pub.autores[:3]) if pub.autores else "N/A"
        if len(pub.autores) > 3:
            autores += f" e mais {len(pub.autores) - 3}"
        resumo = (pub.resumo or "")[:200]
        if len(pub.resumo or "") > 200:
            resumo += "..."
        lines.extend(
            [
                f"### {i}. {pub.titulo or 'Sem título'}",
                f"**Autores:** {autores} | **Data:** {pub.data_publicacao or 'N/A'}",
                f"**UUID:** `{pub.uuid}`",
            ]
        )
        if resumo:
            lines.append(resumo)
        if pub.uri:
            lines.append(f"**Link:** {pub.uri}")
        lines.append("")

    if resultado.pagina + 1 < resultado.total_paginas:
        lines.append(f"*Use pagina={resultado.pagina + 1} para próxima página.*")
    return "\n".join(lines)


async def listar_temas_seguranca(
    ctx: Context,
) -> str:
    """Lista as comunidades temáticas do Fórum Brasileiro de Segurança Pública.

    Mostra os 15 temas de pesquisa organizados no repositório
    (Atlas da Violência, Anuário, Sistema Prisional, etc.) com contagem de publicações.

    Returns:
        Lista de comunidades temáticas com UUID e quantidade de itens.
    """
    await ctx.info("Listando comunidades temáticas...")
    comunidades = await client.listar_comunidades()

    if not comunidades:
        return "Nenhuma comunidade encontrada."

    lines = [f"**{len(comunidades)} comunidades temáticas do FBSP**\n"]
    for i, com in enumerate(comunidades, 1):
        desc = (com.descricao or "")[:120]
        if len(com.descricao or "") > 120:
            desc += "..."
        lines.extend(
            [
                f"### {i}. {com.nome}",
                f"**UUID:** `{com.uuid}` | **Publicações:** {com.quantidade_itens}",
            ]
        )
        if desc:
            lines.append(desc)
        lines.append("")
    return "\n".join(lines)


async def detalhar_publicacao_seguranca(
    uuid: str,
    ctx: Context,
) -> str:
    """Detalha uma publicação do repositório do FBSP por UUID.

    Mostra informações completas: título, autores, resumo, data de publicação,
    assuntos/palavras-chave e link para acesso.

    Args:
        uuid: UUID da publicação (obtido via buscar_publicacoes_seguranca).

    Returns:
        Detalhes completos da publicação.
    """
    await ctx.info(f"Detalhando publicação '{uuid}'...")
    pub = await client.detalhar_publicacao(uuid)

    if not pub:
        return f"Publicação '{uuid}' não encontrada."

    autores = ", ".join(pub.autores) if pub.autores else "N/A"
    assuntos = ", ".join(pub.assuntos[:10]) if pub.assuntos else "N/A"
    if len(pub.assuntos) > 10:
        assuntos += f" e mais {len(pub.assuntos) - 10}"

    lines = [
        f"## {pub.titulo or 'Sem título'}",
        "",
        f"**Autores:** {autores}",
        f"**Data:** {pub.data_publicacao or 'N/A'}",
        f"**Editora:** {pub.editora or 'N/A'}",
    ]
    if pub.issn:
        lines.append(f"**ISSN:** {pub.issn}")
    lines.append(f"**Assuntos:** {assuntos}")
    if pub.resumo:
        lines.extend(["", "### Resumo", pub.resumo])
    if pub.uri:
        lines.extend(["", f"**Link:** {pub.uri}"])
    return "\n".join(lines)


async def buscar_por_tema_seguranca(
    comunidade_uuid: str,
    ctx: Context,
    query: str = "",
    limite: int = 10,
    pagina: int = 0,
) -> str:
    """Busca publicações dentro de uma comunidade temática específica do FBSP.

    Permite filtrar publicações por tema (ex: buscar dentro de "Atlas da Violência"
    ou "Anuário Brasileiro de Segurança Pública"). Use listar_temas_seguranca
    para obter os UUIDs das comunidades.

    Args:
        comunidade_uuid: UUID da comunidade (ex: 'd044c00f-7c26-4249-8da4-336e953fe557').
        query: Termo de busca dentro da comunidade (opcional, vazio retorna todos).
        limite: Máximo de resultados por página (padrão 10, máximo 50).
        pagina: Número da página (começa em 0).

    Returns:
        Publicações da comunidade com título, autores e data.
    """
    nome_comunidade = COMUNIDADES.get(comunidade_uuid, comunidade_uuid)
    desc_busca = f"sobre '{query}' " if query else ""
    await ctx.info(f"Buscando publicações {desc_busca}em '{nome_comunidade}'...")
    resultado = await client.buscar_por_tema(comunidade_uuid, query, limite, pagina)

    if not resultado.publicacoes:
        msg = f"Nenhuma publicação encontrada em '{nome_comunidade}'"
        if query:
            msg += f" para '{query}'"
        return msg + "."

    n = len(resultado.publicacoes)
    lines = [
        f"**{resultado.total} publicações em '{nome_comunidade}'** "
        f"(mostrando {n}, página {resultado.pagina + 1}/{resultado.total_paginas})\n"
    ]
    for i, pub in enumerate(resultado.publicacoes, 1):
        autores = ", ".join(pub.autores[:3]) if pub.autores else "N/A"
        if len(pub.autores) > 3:
            autores += f" e mais {len(pub.autores) - 3}"
        lines.extend(
            [
                f"### {i}. {pub.titulo or 'Sem título'}",
                f"**Autores:** {autores} | **Data:** {pub.data_publicacao or 'N/A'}",
                f"**UUID:** `{pub.uuid}`",
                "",
            ]
        )

    if resultado.pagina + 1 < resultado.total_paginas:
        lines.append(f"*Use pagina={resultado.pagina + 1} para próxima página.*")
    return "\n".join(lines)
