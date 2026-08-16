"""Tool functions for the Jurisprudência feature (STF, STJ, TST).

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

from . import client
from .constants import DEFAULT_PAGE_SIZE


def _format_ementa(ementa: str | None, max_len: int = 300) -> str:
    """Truncate ementa for table display."""
    if not ementa:
        return "—"
    text = ementa.strip().replace("\n", " ")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


async def buscar_jurisprudencia_stf(
    query: str,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> str:
    """Busca jurisprudência no Supremo Tribunal Federal (STF).

    Pesquisa acórdãos do STF por ementa, tema ou termos jurídicos.
    Suporta operadores: E, OU, NÃO, aspas para expressão exata,
    ~ para busca fuzzy, $ para curinga.

    Exemplos: "direito E privacidade", "súmula vinculante", "ADPF 153".

    Args:
        query: Termos de busca (suporta operadores lógicos).
        pagina: Página de resultados (default: 1).
        tamanho: Resultados por página (default: 10).

    Returns:
        Lista de acórdãos com ementa, relator e data.
    """
    resultados = await client.buscar_stf(query, pagina, tamanho)
    if not resultados:
        return f"Nenhum acórdão do STF encontrado para '{query}'."

    lines = [f"**Jurisprudência STF** — '{query}' (página {pagina}):\n"]
    for i, r in enumerate(resultados, 1):
        lines.append(f"**{i}. {r.classe or ''} {r.numero_processo or ''}**")
        lines.append(f"   Relator: {r.relator or '—'}")
        lines.append(f"   Julgamento: {r.data_julgamento or '—'}")
        lines.append(f"   Órgão: {r.orgao_julgador or '—'}")
        lines.append(f"   Ementa: {_format_ementa(r.ementa)}")
        if r.url:
            lines.append(f"   Link: {r.url}")
        lines.append("")

    if len(resultados) >= tamanho:
        lines.append(f"> Use `pagina={pagina + 1}` para ver mais resultados.")

    return "\n".join(lines)


async def buscar_jurisprudencia_stj(
    query: str,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> str:
    """Busca jurisprudência no Superior Tribunal de Justiça (STJ).

    Pesquisa acórdãos do STJ via sistema SCON.
    Suporta operadores: e, ou, não, mesmo, com, PROX(N), ADJ(N),
    aspas para expressão exata, $ para curinga.

    Exemplos: "consumidor e dano moral", "recurso especial e FGTS".

    Args:
        query: Termos de busca (suporta operadores lógicos).
        pagina: Página de resultados (default: 1).
        tamanho: Resultados por página (default: 10).

    Returns:
        Lista de acórdãos com ementa, relator e data.
    """
    resultados = await client.buscar_stj(query, pagina, tamanho)
    if not resultados:
        return f"Nenhum acórdão do STJ encontrado para '{query}'."

    lines = [f"**Jurisprudência STJ** — '{query}' (página {pagina}):\n"]
    for i, r in enumerate(resultados, 1):
        lines.append(f"**{i}. {r.classe or ''} {r.numero_processo or ''}**")
        lines.append(f"   Relator: {r.relator or '—'}")
        lines.append(f"   Julgamento: {r.data_julgamento or '—'}")
        lines.append(f"   Órgão: {r.orgao_julgador or '—'}")
        lines.append(f"   Ementa: {_format_ementa(r.ementa)}")
        if r.url:
            lines.append(f"   Link: {r.url}")
        lines.append("")

    if len(resultados) >= tamanho:
        lines.append(f"> Use `pagina={pagina + 1}` para ver mais resultados.")

    return "\n".join(lines)


async def buscar_jurisprudencia_tst(
    query: str,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> str:
    """Busca jurisprudência no Tribunal Superior do Trabalho (TST).

    Pesquisa acórdãos do TST por ementa ou termos trabalhistas.
    Suporta aspas para expressão exata.

    Exemplos: "horas extras", "dano moral trabalhista", "FGTS".

    Args:
        query: Termos de busca.
        pagina: Página de resultados (default: 1).
        tamanho: Resultados por página (default: 10).

    Returns:
        Lista de acórdãos com ementa, relator e data.
    """
    resultados = await client.buscar_tst(query, pagina, tamanho)
    if not resultados:
        return f"Nenhum acórdão do TST encontrado para '{query}'."

    lines = [f"**Jurisprudência TST** — '{query}' (página {pagina}):\n"]
    for i, r in enumerate(resultados, 1):
        lines.append(f"**{i}. {r.classe or ''} {r.numero_processo or ''}**")
        lines.append(f"   Relator: {r.relator or '—'}")
        lines.append(f"   Julgamento: {r.data_julgamento or '—'}")
        lines.append(f"   Órgão: {r.orgao_julgador or '—'}")
        lines.append(f"   Ementa: {_format_ementa(r.ementa)}")
        if r.url:
            lines.append(f"   Link: {r.url}")
        lines.append("")

    if len(resultados) >= tamanho:
        lines.append(f"> Use `pagina={pagina + 1}` para ver mais resultados.")

    return "\n".join(lines)


async def buscar_sumulas(
    tribunal: str = "stf",
    query: str | None = None,
) -> str:
    """Busca súmulas dos tribunais superiores.

    Pesquisa súmulas do STF (incluindo vinculantes).

    Args:
        tribunal: Tribunal (stf). Default: stf.
        query: Filtro por texto da súmula (opcional).

    Returns:
        Lista de súmulas com número e enunciado.
    """
    if tribunal.lower() != "stf":
        return "Busca de súmulas atualmente disponível apenas para o STF."

    sumulas = await client.buscar_sumulas_stf(query)
    if not sumulas:
        msg = "Nenhuma súmula encontrada"
        if query:
            msg += f" para '{query}'"
        return msg + "."

    lines = [f"**Súmulas {tribunal.upper()}** ({len(sumulas)} resultados):\n"]
    for s in sumulas:
        vinc = " [VINCULANTE]" if s.vinculante else ""
        lines.append(f"**Súmula {s.numero or '?'}{vinc}**")
        lines.append(f"  {_format_ementa(s.enunciado, 500)}")
        if s.situacao:
            lines.append(f"  Situação: {s.situacao}")
        lines.append("")

    return "\n".join(lines)


async def buscar_repercussao_geral(
    query: str | None = None,
    tema: int | None = None,
) -> str:
    """Busca temas de repercussão geral do STF.

    Repercussão geral são temas que o STF reconhece como relevantes
    e cuja decisão se aplica a todos os processos similares.

    Args:
        query: Busca por texto no tema (opcional).
        tema: Número do tema específico (opcional).

    Returns:
        Lista de temas com tese fixada e situação.
    """
    temas = await client.buscar_repercussao_geral(query, tema)
    if not temas:
        msg = "Nenhum tema de repercussão geral encontrado"
        if query:
            msg += f" para '{query}'"
        if tema:
            msg += f" (tema {tema})"
        return msg + "."

    lines = [f"**Repercussão Geral STF** ({len(temas)} temas):\n"]
    for t in temas:
        lines.append(f"**Tema {t.numero_tema or '?'}:** {t.titulo or '—'}")
        lines.append(f"  Relator: {t.relator or '—'}")
        lines.append(f"  Leading case: {t.leading_case or '—'}")
        lines.append(f"  Situação: {t.situacao or '—'}")
        if t.tese:
            lines.append(f"  Tese: {_format_ementa(t.tese, 400)}")
        lines.append("")

    return "\n".join(lines)


async def buscar_informativos(
    tribunal: str = "stf",
    query: str | None = None,
) -> str:
    """Busca informativos de jurisprudência dos tribunais superiores.

    Informativos são resumos periódicos das decisões mais relevantes.
    Atualmente busca via acórdãos com filtro por informativo.

    Args:
        tribunal: Tribunal (stf, stj, tst). Default: stf.
        query: Termos de busca (opcional).

    Returns:
        Lista de decisões relevantes dos informativos.
    """
    search = query or "informativo"
    tribunal_lower = tribunal.lower()

    if tribunal_lower == "stf":
        resultados = await client.buscar_stf(search)
    elif tribunal_lower == "stj":
        resultados = await client.buscar_stj(search)
    elif tribunal_lower == "tst":
        resultados = await client.buscar_tst(search)
    else:
        return f"Tribunal '{tribunal}' não suportado. Use: stf, stj ou tst."

    if not resultados:
        return f"Nenhum informativo encontrado no {tribunal.upper()}."

    lines = [f"**Informativos {tribunal.upper()}** ({len(resultados)} resultados):\n"]
    for i, r in enumerate(resultados, 1):
        lines.append(f"**{i}. {r.classe or ''} {r.numero_processo or ''}**")
        lines.append(f"   Relator: {r.relator or '—'}")
        lines.append(f"   Julgamento: {r.data_julgamento or '—'}")
        lines.append(f"   Ementa: {_format_ementa(r.ementa)}")
        lines.append("")

    return "\n".join(lines)
