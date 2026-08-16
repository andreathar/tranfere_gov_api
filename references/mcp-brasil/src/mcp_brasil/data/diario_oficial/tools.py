"""Tool functions for the Diário Oficial feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

import re

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table

from . import client, client_dou
from .constants import CAPITAIS_COBERTAS, DOU_ARTICLE_URL

_HTML_TAG_RE = re.compile(r"<[^>]+>")


async def buscar_diarios(
    texto: str,
    ctx: Context,
    territorio_id: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    pagina: int = 0,
    busca_exata: bool = True,
    ordenar_por: str = "relevance",
) -> str:
    """Busca em diários oficiais municipais por texto livre.

    Pesquisa full-text em diários oficiais de 5.000+ municípios brasileiros.
    Útil para encontrar menções a empresas, pessoas, contratos, licitações,
    nomeações, exonerações e atos administrativos.

    Args:
        texto: Termo de busca (nome de empresa, CNPJ, pessoa, palavra-chave).
        territorio_id: Código IBGE do município (opcional, ex: 3550308 para São Paulo).
        data_inicio: Data inicial no formato YYYY-MM-DD (opcional).
        data_fim: Data final no formato YYYY-MM-DD (opcional).
        pagina: Página de resultados (0-indexada, padrão 0).
        busca_exata: Se True, busca termo exato. Se False, busca flexível (padrão True).
        ordenar_por: "relevance" (padrão) ou "descending_date" para mais recentes primeiro.

    Returns:
        Lista de diários oficiais com trechos relevantes.
    """
    await ctx.info(f"Buscando diários oficiais para '{texto}'...")
    territory_ids = [territorio_id] if territorio_id else None
    resultado = await client.buscar_diarios(
        querystring=texto,
        territory_ids=territory_ids,
        since=data_inicio,
        until=data_fim,
        offset=pagina * 10,
        is_exact_search=busca_exata,
        sort_by=ordenar_por,
    )
    await ctx.info(f"{resultado.total_gazettes} diários encontrados")

    if not resultado.gazettes:
        return f"Nenhum diário oficial encontrado para '{texto}'."

    lines = [f"**Total:** {resultado.total_gazettes} diários encontrados\n"]
    for i, d in enumerate(resultado.gazettes[:10], 1):
        lines.append(f"### {i}. {d.territory_name or 'N/A'}/{d.state_code or '??'}")
        lines.append(f"**Data:** {d.date or 'N/A'} | **Edição:** {d.edition_number or 'N/A'}")
        if d.is_extra_edition:
            lines.append("**Edição Extra**")
        if d.excerpts:
            excerpt = _HTML_TAG_RE.sub("", d.excerpts[0])[:500]
            lines.append(f"\n> {excerpt}...")
        if d.txt_url:
            lines.append(f"\n[Texto completo]({d.txt_url})")
        lines.append("")

    if resultado.total_gazettes > 10:
        lines.append(
            f"\n*Mostrando 10 de {resultado.total_gazettes}. "
            f"Use pagina={pagina + 1} para mais resultados.*"
        )
    return "\n".join(lines)


async def buscar_diarios_regiao(
    texto: str,
    ctx: Context,
    uf: str | None = None,
    capitais_apenas: bool = False,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> str:
    """Busca em diários oficiais de múltiplos municípios de uma região.

    Permite buscar simultaneamente em todas as capitais cobertas,
    filtrar por UF, ou buscar só nas capitais. Ideal para pesquisas
    regionais como "licitações no Nordeste" ou "contratos nas capitais do Sul".

    Args:
        texto: Termo de busca (empresa, CNPJ, palavra-chave).
        uf: Sigla da UF para filtrar (ex: SP, RJ, BA). Opcional.
        capitais_apenas: Se True, busca apenas nas capitais cobertas (padrão False).
        data_inicio: Data inicial YYYY-MM-DD (opcional).
        data_fim: Data final YYYY-MM-DD (opcional).

    Returns:
        Resultados agregados de múltiplos municípios.
    """
    territory_ids: list[str] = []

    if capitais_apenas or uf:
        for code, nome_uf in CAPITAIS_COBERTAS.items():
            sigla = nome_uf.split("/")[1]
            if uf and sigla != uf.upper():
                continue
            territory_ids.append(code)

    if uf and not territory_ids:
        return f"Nenhuma capital coberta encontrada para a UF '{uf}'."

    scope = f"UF {uf.upper()}" if uf else "capitais cobertas"
    n = len(territory_ids) or "todos os"
    await ctx.info(f"Buscando '{texto}' em {n} municípios ({scope})")

    resultado = await client.buscar_diarios(
        querystring=texto,
        territory_ids=territory_ids if territory_ids else None,
        since=data_inicio,
        until=data_fim,
        size=20,
    )
    await ctx.info(f"{resultado.total_gazettes} diários encontrados em {scope}")

    if not resultado.gazettes:
        return f"Nenhum diário encontrado para '{texto}' em {scope}."

    lines = [f"**Total:** {resultado.total_gazettes} diários em {scope}\n"]
    for i, d in enumerate(resultado.gazettes[:20], 1):
        lines.append(f"### {i}. {d.territory_name or 'N/A'}/{d.state_code or '??'}")
        lines.append(f"**Data:** {d.date or 'N/A'} | **Edição:** {d.edition_number or 'N/A'}")
        if d.excerpts:
            excerpt = _HTML_TAG_RE.sub("", d.excerpts[0])[:300]
            lines.append(f"\n> {excerpt}...")
        lines.append("")

    return "\n".join(lines)


async def buscar_cidades(nome: str, ctx: Context) -> str:
    """Busca municípios disponíveis no Querido Diário pelo nome.

    Retorna os códigos IBGE necessários para filtrar buscas por território.

    Args:
        nome: Nome (ou parte do nome) da cidade.

    Returns:
        Lista de cidades encontradas com código IBGE.
    """
    await ctx.info(f"Buscando cidades '{nome}'...")
    cidades = await client.buscar_cidades(nome)
    await ctx.info(f"{len(cidades)} cidades encontradas")

    if not cidades:
        return f"Nenhuma cidade encontrada para '{nome}'."

    rows = [(c.territory_id, c.territory_name, c.state_code) for c in cidades]
    return markdown_table(["Código IBGE", "Cidade", "UF"], rows)


async def listar_territorios(ctx: Context) -> str:
    """Lista todos os municípios com diários oficiais no Querido Diário.

    Retorna a lista completa de territórios disponíveis para busca.
    Use o código IBGE retornado para filtrar buscas em buscar_diarios.

    Returns:
        Lista de municípios disponíveis com código IBGE e UF.
    """
    await ctx.info("Listando territórios disponíveis...")
    cidades = await client.listar_cidades()
    await ctx.info(f"{len(cidades)} territórios disponíveis")

    rows = [(c.territory_id, c.territory_name, c.state_code) for c in cidades]
    header = f"**{len(cidades)} municípios** com diários oficiais disponíveis:\n\n"
    return header + markdown_table(["Código IBGE", "Cidade", "UF"], rows[:100])


async def listar_diarios_recentes(
    ctx: Context,
    territorio_id: str,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> str:
    """Lista publicações recentes de um município sem termo de busca.

    Retorna os diários oficiais mais recentes de um município específico,
    sem necessidade de informar um termo de busca. Útil para acompanhar
    as publicações do dia ou da semana.

    Args:
        territorio_id: Código IBGE do município (ex: 3550308 para São Paulo).
        data_inicio: Data inicial YYYY-MM-DD (opcional).
        data_fim: Data final YYYY-MM-DD (opcional).

    Returns:
        Lista de diários recentes com data e edição.
    """
    await ctx.info(f"Listando diários recentes do território {territorio_id}...")
    resultado = await client.buscar_diarios(
        querystring="*",
        territory_ids=[territorio_id],
        since=data_inicio,
        until=data_fim,
        sort_by="descending_date",
    )
    await ctx.info(f"{resultado.total_gazettes} diários encontrados")

    if not resultado.gazettes:
        return f"Nenhum diário recente encontrado para o território {territorio_id}."

    lines = [f"**Total:** {resultado.total_gazettes} diários recentes\n"]
    for i, d in enumerate(resultado.gazettes[:10], 1):
        extra = " (Extra)" if d.is_extra_edition else ""
        lines.append(f"{i}. **{d.date or 'N/A'}** — Edição {d.edition_number or 'N/A'}{extra}")
        if d.txt_url:
            lines.append(f"   [Texto completo]({d.txt_url})")
    return "\n".join(lines)


async def buscar_diario_unificado(
    texto: str,
    ctx: Context,
    escopo: str = "ambos",
    territorio_id: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> str:
    """Busca em diários oficiais federais E municipais simultaneamente.

    Combina resultados do DOU (federal) e do Querido Diário (municipal)
    em uma única resposta. Ideal para rastrear a cadeia regulatória:
    lei federal -> regulamentação -> aplicação municipal.

    Args:
        texto: Termo de busca (empresa, CNPJ, lei, assunto).
        escopo: "federal" (só DOU), "municipal" (só QD), ou "ambos" (padrão).
        territorio_id: Código IBGE do município para filtrar QD (opcional).
        data_inicio: Data inicial YYYY-MM-DD (opcional).
        data_fim: Data final YYYY-MM-DD (opcional).

    Returns:
        Resultados combinados de DOU + Querido Diário.
    """
    await ctx.info(f"Busca unificada: '{texto}' (escopo={escopo})")
    lines: list[str] = []

    # --- DOU Federal ---
    if escopo in ("federal", "ambos"):
        await ctx.info("Buscando no DOU federal...")
        dou_result = await client_dou.buscar_dou(
            termo=texto,
            periodo="PERSONALIZADO" if (data_inicio and data_fim) else "ANO",
            data_inicio=data_inicio,
            data_fim=data_fim,
            tamanho=10,
        )
        lines.append(f"## DOU Federal — {dou_result.total} resultados\n")
        if dou_result.publicacoes:
            for i, p in enumerate(dou_result.publicacoes[:5], 1):
                meta = []
                if p.data_publicacao:
                    meta.append(p.data_publicacao)
                if p.orgao:
                    meta.append(p.orgao)
                meta_str = f" ({', '.join(meta)})" if meta else ""
                lines.append(f"{i}. **{p.titulo or 'Sem título'}**{meta_str}")
                if p.resumo:
                    lines.append(f"   > {p.resumo[:200]}...")
                if p.url_titulo:
                    url = f"{DOU_ARTICLE_URL}/{p.url_titulo}"
                    lines.append(f"   [Ler completo]({url})")
            lines.append("")
        else:
            lines.append("*Nenhum resultado no DOU.*\n")

    # --- Querido Diário Municipal ---
    if escopo in ("municipal", "ambos"):
        await ctx.info("Buscando no Querido Diário (municipal)...")
        territory_ids = [territorio_id] if territorio_id else None
        qd_result = await client.buscar_diarios(
            querystring=texto,
            territory_ids=territory_ids,
            since=data_inicio,
            until=data_fim,
            size=10,
        )
        lines.append(f"## Diários Municipais — {qd_result.total_gazettes} resultados\n")
        if qd_result.gazettes:
            for i, d in enumerate(qd_result.gazettes[:5], 1):
                local = f"{d.territory_name or 'N/A'}/{d.state_code or '??'}"
                lines.append(
                    f"{i}. **{local}** — {d.date or 'N/A'} (ed. {d.edition_number or 'N/A'})"
                )
                if d.excerpts:
                    excerpt = _HTML_TAG_RE.sub("", d.excerpts[0])[:200]
                    lines.append(f"   > {excerpt}...")
            lines.append("")
        else:
            lines.append("*Nenhum resultado nos diários municipais.*\n")

    return "\n".join(lines)
