"""Client for the DENASUS feature.

Scrapes public gov.br pages (Plone CMS) using httpx + BeautifulSoup.
Rate-limited to 1 request per 3 seconds. No auth required.
"""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup, Tag

from .constants import (
    ATIVIDADES_URL,
    HEADERS,
    PLANOS_URL,
    RATE_LIMIT_DELAY,
    RELATORIOS_URL,
    UFS_BRASIL,
)
from .schemas import AtividadeAuditoria, PlanoAuditoria, RelatorioAnual


async def _fetch_page(url: str) -> BeautifulSoup:
    """Fetch and parse a gov.br page with rate limiting."""
    await asyncio.sleep(RATE_LIMIT_DELAY)
    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    ) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")


def _extrair_uf(titulo: str) -> str | None:
    """Extract UF (state code) from audit activity title."""
    match = re.search(r"\b([A-Z]{2})\b", titulo)
    if match and match.group(1) in UFS_BRASIL:
        return match.group(1)
    return None


def _classificar_tipo(titulo: str) -> str:
    """Classify audit activity type from title."""
    titulo_lower = titulo.lower()
    if "auditoria" in titulo_lower:
        return "Auditoria"
    if "verificação" in titulo_lower or "verificacao" in titulo_lower:
        return "Verificação"
    if "monitoramento" in titulo_lower:
        return "Monitoramento"
    if "inspeção" in titulo_lower or "inspecao" in titulo_lower:
        return "Inspeção"
    return "Outro"


def _extrair_ano(texto: str) -> int | None:
    """Extract year from text like 'Relatório 2024'."""
    match = re.search(r"20[12]\d", texto)
    return int(match.group()) if match else None


def _get_link_href(element: Tag) -> str | None:
    """Extract href from a tag that is or contains a link."""
    if element.name == "a":
        href = element.get("href")
        return str(href) if href else None
    link = element.find("a")
    if isinstance(link, Tag):
        href = link.get("href")
        return str(href) if href else None
    return None


def _find_content_items(soup: BeautifulSoup) -> tuple[list[Tag], str]:
    """Find content items from a gov.br page using multiple strategies.

    Returns (items, strategy) where strategy indicates which pattern matched.
    Current gov.br pages use <h2> headings or <dt> definition lists for
    document listings inside #content-core.
    """
    content = soup.select_one("#content-core, #content, .documentContent")

    # Strategy 1: <h2> with <a> inside content area (most common current pattern)
    if content and isinstance(content, Tag):
        h2s = [t for t in content.select("h2") if isinstance(t, Tag) and t.find("a")]
        if h2s:
            return h2s, "h2"

    # Strategy 2: <dt> with <a> (definition list pattern)
    if content and isinstance(content, Tag):
        dts = [t for t in content.select("dt") if isinstance(t, Tag) and t.find("a")]
        if dts:
            return dts, "dt"

    # Strategy 3: fallback — try full page h2/h3 with links
    headings = [t for t in soup.select("h2, h3") if isinstance(t, Tag) and t.find("a")]
    if headings:
        return headings, "h2"

    # Strategy 4: classic Plone CMS selectors (legacy fallback)
    items = [t for t in soup.select("article, .item-lista, .tileItem") if isinstance(t, Tag)]
    return items, "legacy"


async def listar_atividades_auditoria() -> list[AtividadeAuditoria]:
    """Scrape audit activities from the DENASUS public page.

    The gov.br page structure may vary (Plone CMS updates). We try multiple
    selector strategies via ``_find_content_items``.
    """
    soup = await _fetch_page(ATIVIDADES_URL)
    atividades: list[AtividadeAuditoria] = []
    items, strategy = _find_content_items(soup)

    for item in items:
        link = item.find("a") if strategy in ("dt", "h2") else None
        titulo_el = link if isinstance(link, Tag) else item.select_one("h2, h3, a")
        if not titulo_el:
            continue
        titulo = titulo_el.get_text(strip=True)
        if not titulo:
            continue

        # Look for date/description in sibling elements
        sibling = item.find_next_sibling()
        data_text: str | None = None
        resumo_text: str | None = None
        if isinstance(sibling, Tag) and sibling.name in ("dd", "p"):
            text = sibling.get_text(strip=True)
            date_match = re.search(r"\d{2}/\d{2}/\d{4}", text)
            data_text = date_match.group() if date_match else None
            resumo_text = text[:500] if text else None

        atividades.append(
            AtividadeAuditoria(
                titulo=titulo,
                data=data_text,
                uf=_extrair_uf(titulo),
                tipo=_classificar_tipo(titulo),
                situacao="Concluída",
                resumo=resumo_text,
                url_detalhe=_get_link_href(titulo_el),
            )
        )

    return atividades


async def listar_relatorios_anuais() -> list[RelatorioAnual]:
    """Scrape annual activity reports from the DENASUS page.

    Current gov.br structure uses <h2> headings with <a> links inside
    #content-core. Falls back to <dt>, legacy selectors.
    """
    soup = await _fetch_page(RELATORIOS_URL)
    relatorios: list[RelatorioAnual] = []
    items, _strategy = _find_content_items(soup)

    for item in items:
        link = item.find("a")
        if not isinstance(link, Tag):
            continue
        titulo = link.get_text(strip=True)
        if not titulo:
            continue
        href = str(link.get("href", ""))
        ano = _extrair_ano(titulo)

        # Extract description from sibling <dd> or <p>
        resumo: str | None = None
        sibling = item.find_next_sibling()
        if isinstance(sibling, Tag) and sibling.name in ("dd", "p"):
            resumo = sibling.get_text(strip=True)[:500]

        relatorios.append(
            RelatorioAnual(
                ano=ano,
                titulo=titulo,
                url_pdf=href or None,
                resumo=resumo,
            )
        )

    return relatorios


async def listar_planos_auditoria() -> list[PlanoAuditoria]:
    """Scrape annual audit plans from the DENASUS page.

    Current gov.br structure uses <h2> headings with <a> links (e.g.
    ``<h2><a href="...">Plano Anual ... 2024</a></h2>``).
    Falls back to <dt>, legacy selectors.
    """
    soup = await _fetch_page(PLANOS_URL)
    planos: list[PlanoAuditoria] = []
    items, _strategy = _find_content_items(soup)

    for item in items:
        link = item.find("a")
        if not isinstance(link, Tag):
            continue
        titulo = link.get_text(strip=True)
        if not titulo:
            continue
        href = str(link.get("href", ""))
        ano = _extrair_ano(titulo)

        planos.append(
            PlanoAuditoria(
                ano=ano,
                titulo=titulo,
                url_pdf=href or None,
            )
        )

    return planos
