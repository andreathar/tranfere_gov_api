"""Tool functions for the Anuncios Eleitorais feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

import logging

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table
from mcp_brasil.exceptions import HttpClientError

from . import client
from .constants import BUSCA_FRASE_EXATA
from .schemas import AnuncioEleitoral

logger = logging.getLogger(__name__)

_TOKEN_AUSENTE = (
    "Token da Meta não configurado. Defina a variável de ambiente "
    "META_ACCESS_TOKEN ou META_AD_LIBRARY_TOKEN com um token válido. "
    "Obtenha em: https://developers.facebook.com/tools/explorer/"
)

_TOKEN_EXPIRADO = (
    "Token da Meta expirado ou inválido. Gere um novo token em: "
    "https://developers.facebook.com/tools/explorer/ e atualize a variável "
    "META_ACCESS_TOKEN ou META_AD_LIBRARY_TOKEN."
)


def _formatar_anuncio(ad: AnuncioEleitoral) -> str:
    """Format a single ad for LLM consumption."""
    lines: list[str] = []
    lines.append(f"### {ad.page_name or 'Página desconhecida'} (ID: {ad.id})")

    if ad.bylines:
        lines.append(f"**Financiado por:** {ad.bylines}")

    if ad.ad_delivery_start_time:
        periodo = f"**Período:** {ad.ad_delivery_start_time}"
        if ad.ad_delivery_stop_time:
            periodo += f" até {ad.ad_delivery_stop_time}"
        else:
            periodo += " (em veiculação)"
        lines.append(periodo)

    if ad.ad_creative_bodies:
        texto = ad.ad_creative_bodies[0]
        if len(texto) > 300:
            texto = texto[:300] + "..."
        lines.append(f"**Texto:** {texto}")

    if ad.spend:
        gasto = ""
        if ad.spend.lower_bound and ad.spend.upper_bound:
            gasto = f"{ad.spend.lower_bound} - {ad.spend.upper_bound}"
        elif ad.spend.lower_bound:
            gasto = f"> {ad.spend.lower_bound}"
        if gasto and ad.currency:
            lines.append(f"**Gasto:** {gasto} {ad.currency}")

    if ad.impressions:
        imp = ""
        if ad.impressions.lower_bound and ad.impressions.upper_bound:
            imp = f"{ad.impressions.lower_bound} - {ad.impressions.upper_bound}"
        elif ad.impressions.lower_bound:
            imp = f"> {ad.impressions.lower_bound}"
        if imp:
            lines.append(f"**Impressões:** {imp}")

    if ad.br_total_reach:
        lines.append(f"**Alcance Brasil:** {ad.br_total_reach:,}".replace(",", "."))

    if ad.publisher_platforms:
        lines.append(f"**Plataformas:** {', '.join(ad.publisher_platforms)}")

    if ad.ad_snapshot_url:
        lines.append(f"**Visualizar:** {ad.ad_snapshot_url}")

    return "\n".join(lines)


def _formatar_lista_anuncios(anuncios: list[AnuncioEleitoral], total: int | None = None) -> str:
    """Format a list of ads for LLM consumption."""
    if not anuncios:
        return "Nenhum anúncio encontrado para os critérios informados."

    lines: list[str] = []
    if total is not None:
        lines.append(f"**{total} anúncio(s) retornado(s)**\n")
    else:
        lines.append(f"**{len(anuncios)} anúncio(s) retornado(s)**\n")

    for ad in anuncios:
        lines.append(_formatar_anuncio(ad))
        lines.append("")

    return "\n".join(lines)


async def buscar_anuncios_eleitorais(
    search_terms: str,
    ctx: Context,
    ad_active_status: str | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    media_type: str | None = None,
    publisher_platforms: list[str] | None = None,
    search_type: str | None = None,
    limit: int = 25,
) -> str:
    """Busca anúncios eleitorais e políticos no Brasil por termos de pesquisa.

    Pesquisa na Biblioteca de Anúncios da Meta por anúncios sobre temas sociais,
    eleições ou política que contenham os termos informados e alcancem público no Brasil.

    Args:
        search_terms: Termos de busca (max 100 chars). Espaço entre palavras = AND.
            Exemplo: 'educação saúde' busca anúncios com ambas as palavras.
        ad_active_status: Status do anúncio (ACTIVE, INACTIVE, ALL). Padrão: ACTIVE.
        ad_delivery_date_min: Data mínima de veiculação no formato YYYY-mm-dd.
        ad_delivery_date_max: Data máxima de veiculação no formato YYYY-mm-dd.
        media_type: Tipo de mídia (ALL, IMAGE, MEME, VIDEO, NONE).
        publisher_platforms: Plataformas (ex: ['FACEBOOK', 'INSTAGRAM']).
        search_type: Tipo de busca. KEYWORD_UNORDERED (padrão) para palavras em
            qualquer ordem, KEYWORD_EXACT_PHRASE para frase exata.
        limit: Número máximo de resultados (1-500). Padrão: 25.

    Returns:
        Lista formatada de anúncios eleitorais com dados de gastos e alcance.
    """
    await ctx.info(f"Buscando anúncios eleitorais: '{search_terms}'...")
    kwargs: dict[str, object] = {
        "search_terms": search_terms,
        "ad_active_status": ad_active_status,
        "ad_delivery_date_min": ad_delivery_date_min,
        "ad_delivery_date_max": ad_delivery_date_max,
        "media_type": media_type,
        "publisher_platforms": publisher_platforms,
        "limit": limit,
    }
    if search_type is not None:
        kwargs["search_type"] = search_type
    try:
        resposta = await client.buscar_anuncios(**kwargs)  # type: ignore[arg-type]
    except RuntimeError:
        return _TOKEN_AUSENTE
    except HttpClientError as exc:
        logger.warning("buscar_anuncios_eleitorais failed: %s", exc)
        return _TOKEN_EXPIRADO
    return _formatar_lista_anuncios(resposta.data)


async def buscar_anuncios_por_pagina(
    search_page_ids: list[str],
    ctx: Context,
    ad_active_status: str | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    limit: int = 25,
) -> str:
    """Busca anúncios eleitorais de páginas específicas do Facebook.

    Use esta tool quando quiser ver todos os anúncios políticos de um candidato,
    partido ou organização específica, usando o ID da página do Facebook.

    Args:
        search_page_ids: Lista de IDs de páginas do Facebook (até 10).
            Exemplo: ['123456789', '987654321'].
        ad_active_status: Status do anúncio (ACTIVE, INACTIVE, ALL). Padrão: ACTIVE.
        ad_delivery_date_min: Data mínima de veiculação (YYYY-mm-dd).
        ad_delivery_date_max: Data máxima de veiculação (YYYY-mm-dd).
        limit: Número máximo de resultados (1-500). Padrão: 25.

    Returns:
        Lista formatada de anúncios da(s) página(s) com dados de gastos e alcance.
    """
    await ctx.info(f"Buscando anúncios das páginas: {', '.join(search_page_ids)}...")
    try:
        resposta = await client.buscar_anuncios(
            search_page_ids=search_page_ids,
            ad_active_status=ad_active_status,
            ad_delivery_date_min=ad_delivery_date_min,
            ad_delivery_date_max=ad_delivery_date_max,
            limit=limit,
        )
    except RuntimeError:
        return _TOKEN_AUSENTE
    except HttpClientError as exc:
        logger.warning("buscar_anuncios_por_pagina failed: %s", exc)
        return _TOKEN_EXPIRADO
    return _formatar_lista_anuncios(resposta.data)


async def buscar_anuncios_por_financiador(
    bylines: list[str],
    ctx: Context,
    search_terms: str = "",
    ad_active_status: str | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    limit: int = 25,
) -> str:
    """Busca anúncios eleitorais pelo nome do financiador (quem pagou).

    Filtra anúncios pelo campo 'Pago por' (byline). O nome deve ser o texto
    completo exibido no disclaimer do anúncio.

    Args:
        bylines: Nomes dos financiadores. Deve ser o texto exato do disclaimer.
            Exemplo: ['Partido X', 'Candidato Y para Prefeito'].
        search_terms: Termos de busca adicionais (opcional).
        ad_active_status: Status do anúncio (ACTIVE, INACTIVE, ALL). Padrão: ACTIVE.
        ad_delivery_date_min: Data mínima de veiculação (YYYY-mm-dd).
        ad_delivery_date_max: Data máxima de veiculação (YYYY-mm-dd).
        limit: Número máximo de resultados (1-500). Padrão: 25.

    Returns:
        Lista formatada de anúncios do(s) financiador(es).
    """
    await ctx.info(f"Buscando anúncios financiados por: {', '.join(bylines)}...")
    try:
        resposta = await client.buscar_anuncios(
            search_terms=search_terms,
            bylines=bylines,
            ad_active_status=ad_active_status,
            ad_delivery_date_min=ad_delivery_date_min,
            ad_delivery_date_max=ad_delivery_date_max,
            limit=limit,
        )
    except RuntimeError:
        return _TOKEN_AUSENTE
    except HttpClientError as exc:
        logger.warning("buscar_anuncios_por_financiador failed: %s", exc)
        return _TOKEN_EXPIRADO
    return _formatar_lista_anuncios(resposta.data)


async def buscar_anuncios_por_regiao(
    regiao: str,
    ctx: Context,
    search_terms: str = "",
    ad_active_status: str | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    limit: int = 50,
) -> str:
    """Busca anúncios eleitorais com alcance em uma região/estado do Brasil.

    Busca anúncios políticos e filtra os que tiveram alcance na região informada.
    A filtragem é feita pós-busca usando o campo delivery_by_region da resposta,
    pois a API não suporta filtro direto por região na busca.

    Args:
        regiao: Nome do estado brasileiro (ex: 'Piauí', 'São Paulo').
            Use o nome completo do estado, não a sigla.
        search_terms: Termos de busca adicionais (opcional). Se vazio, busca
            pelo nome da região automaticamente.
        ad_active_status: Status do anúncio (ACTIVE, INACTIVE, ALL). Padrão: ACTIVE.
        ad_delivery_date_min: Data mínima de veiculação (YYYY-mm-dd).
        ad_delivery_date_max: Data máxima de veiculação (YYYY-mm-dd).
        limit: Número de resultados a buscar antes de filtrar (1-500). Padrão: 50.

    Returns:
        Lista formatada de anúncios com alcance na região.
    """
    termo = search_terms or regiao
    await ctx.info(f"Buscando anúncios com alcance em {regiao}...")
    try:
        resposta = await client.buscar_anuncios(
            search_terms=termo,
            ad_active_status=ad_active_status,
            ad_delivery_date_min=ad_delivery_date_min,
            ad_delivery_date_max=ad_delivery_date_max,
            limit=limit,
        )
    except RuntimeError:
        return _TOKEN_AUSENTE
    except HttpClientError as exc:
        logger.warning("buscar_anuncios_por_regiao failed: %s", exc)
        return _TOKEN_EXPIRADO

    # Filtrar pós-busca: anúncios com alcance na região
    regiao_lower = regiao.lower()
    filtrados = []
    for ad in resposta.data:
        # Check delivery_by_region
        if ad.delivery_by_region:
            for r in ad.delivery_by_region:
                if r.region and regiao_lower in r.region.lower():
                    filtrados.append(ad)
                    break
        # Check target_locations
        if ad.target_locations:
            for loc in ad.target_locations:
                if loc.name and regiao_lower in loc.name.lower():
                    filtrados.append(ad)
                    break
        # Check ad text mentions
        texto = " ".join(ad.ad_creative_bodies or []).lower()
        if regiao_lower in texto and ad not in filtrados:
            filtrados.append(ad)

    return _formatar_lista_anuncios(filtrados)


async def analisar_demografia_anuncios(
    search_terms: str,
    ctx: Context,
    search_page_ids: list[str] | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    limit: int = 25,
) -> str:
    """Analisa a distribuição demográfica e regional dos anúncios eleitorais.

    Retorna dados de idade, gênero e região de alcance dos anúncios políticos
    encontrados. Útil para entender o público-alvo das campanhas.

    Args:
        search_terms: Termos de busca para filtrar anúncios.
        search_page_ids: IDs de páginas para filtrar (opcional).
        ad_delivery_date_min: Data mínima de veiculação (YYYY-mm-dd).
        ad_delivery_date_max: Data máxima de veiculação (YYYY-mm-dd).
        limit: Número máximo de anúncios a analisar (1-500). Padrão: 25.

    Returns:
        Análise demográfica e regional formatada.
    """
    await ctx.info(f"Analisando demografia dos anúncios: '{search_terms}'...")
    try:
        resposta = await client.buscar_anuncios(
            search_terms=search_terms,
            search_page_ids=search_page_ids,
            ad_delivery_date_min=ad_delivery_date_min,
            ad_delivery_date_max=ad_delivery_date_max,
            limit=limit,
        )
    except RuntimeError:
        return _TOKEN_AUSENTE
    except HttpClientError as exc:
        logger.warning("analisar_demografia_anuncios failed: %s", exc)
        return _TOKEN_EXPIRADO

    if not resposta.data:
        return "Nenhum anúncio encontrado para análise demográfica."

    lines: list[str] = [f"## Análise demográfica — {len(resposta.data)} anúncio(s)\n"]

    # Aggregate demographics
    demo_totals: dict[str, float] = {}
    region_totals: dict[str, float] = {}
    count_with_demo = 0
    count_with_region = 0

    for ad in resposta.data:
        if ad.demographic_distribution:
            count_with_demo += 1
            for d in ad.demographic_distribution:
                key = f"{d.age or '?'} / {d.gender or '?'}"
                pct = float(d.percentage) if d.percentage else 0.0
                demo_totals[key] = demo_totals.get(key, 0.0) + pct

        if ad.delivery_by_region:
            count_with_region += 1
            for r in ad.delivery_by_region:
                region = r.region or "Desconhecida"
                pct = float(r.percentage) if r.percentage else 0.0
                region_totals[region] = region_totals.get(region, 0.0) + pct

    # Format demographics
    if demo_totals and count_with_demo > 0:
        lines.append("### Distribuição por idade e gênero (média)\n")
        rows = []
        for key in sorted(demo_totals.keys()):
            avg = demo_totals[key] / count_with_demo * 100
            parts = key.split(" / ")
            rows.append((parts[0], parts[1], f"{avg:.1f}%"))
        lines.append(markdown_table(["Idade", "Gênero", "Alcance médio"], rows))
        lines.append("")

    # Format regions
    if region_totals and count_with_region > 0:
        lines.append("### Distribuição por região (média)\n")
        sorted_regions = sorted(region_totals.items(), key=lambda x: x[1], reverse=True)
        region_rows: list[tuple[str, str]] = []
        for region, total in sorted_regions[:15]:
            avg = total / count_with_region * 100
            region_rows.append((region, f"{avg:.1f}%"))
        lines.append(markdown_table(["Região", "Alcance médio"], region_rows))
        lines.append("")

    if not demo_totals and not region_totals:
        lines.append("Dados demográficos e regionais não disponíveis para estes anúncios.")

    return "\n".join(lines)


async def buscar_anuncios_frase_exata(
    frase: str,
    ctx: Context,
    ad_active_status: str | None = None,
    ad_delivery_date_min: str | None = None,
    ad_delivery_date_max: str | None = None,
    limit: int = 25,
) -> str:
    """Busca anúncios eleitorais por frase exata no Brasil.

    Diferente da busca padrão (que trata cada palavra separadamente),
    esta tool busca a frase completa exatamente como informada.
    Para buscar múltiplas frases, separe-as por vírgula.

    Args:
        frase: Frase exata para buscar. Para múltiplas frases, separe por vírgula.
            Exemplo: 'governo federal' ou 'saúde pública,educação básica'.
        ad_active_status: Status do anúncio (ACTIVE, INACTIVE, ALL). Padrão: ACTIVE.
        ad_delivery_date_min: Data mínima de veiculação (YYYY-mm-dd).
        ad_delivery_date_max: Data máxima de veiculação (YYYY-mm-dd).
        limit: Número máximo de resultados (1-500). Padrão: 25.

    Returns:
        Lista formatada de anúncios eleitorais que contêm a frase exata.
    """
    await ctx.info(f"Buscando anúncios com frase exata: '{frase}'...")
    try:
        resposta = await client.buscar_anuncios(
            search_terms=frase,
            search_type=BUSCA_FRASE_EXATA,
            ad_active_status=ad_active_status,
            ad_delivery_date_min=ad_delivery_date_min,
            ad_delivery_date_max=ad_delivery_date_max,
            limit=limit,
        )
    except RuntimeError:
        return _TOKEN_AUSENTE
    except HttpClientError as exc:
        logger.warning("buscar_anuncios_frase_exata failed: %s", exc)
        return _TOKEN_EXPIRADO
    return _formatar_lista_anuncios(resposta.data)
