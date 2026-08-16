"""Tool functions for the OpenDataSUS feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table

from . import client
from .constants import DATASETS_CONHECIDOS, DATASETS_CONHECIDOS_MAP


async def buscar_datasets(
    ctx: Context,
    query: str,
    limite: int = 10,
) -> str:
    """Busca datasets no portal OpenDataSUS por palavra-chave.

    O OpenDataSUS é o portal de dados abertos do SUS com datasets sobre
    hospitais, leitos, vacinação, epidemiologia, qualidade da água e mais.

    Args:
        query: Palavra-chave para busca (ex: "vacinação", "leitos", "srag").
        limite: Número máximo de resultados (padrão: 10).

    Returns:
        Tabela com datasets encontrados.
    """
    await ctx.info(f"Buscando datasets no OpenDataSUS: '{query}'...")

    try:
        datasets, total = await client.buscar_datasets(query, limite=limite)
    except RuntimeError as exc:
        return str(exc)

    if not datasets:
        return (
            f"Nenhum dataset encontrado para '{query}' no OpenDataSUS. "
            "Tente termos como: vacinação, leitos, srag, sinan, sisagua."
        )

    rows = [
        (
            d.nome,
            (d.titulo or "—")[:60],
            d.organizacao or "—",
            str(d.total_recursos),
            (d.data_atualizacao or "—")[:10],
        )
        for d in datasets
    ]

    header = f"**OpenDataSUS — Datasets** ({len(datasets)} de {total} resultados)\n\n"
    return header + markdown_table(
        ["ID/Nome", "Título", "Organização", "Recursos", "Atualização"],
        rows,
    )


async def detalhar_dataset(ctx: Context, dataset_id: str) -> str:
    """Detalha um dataset específico do OpenDataSUS.

    Mostra título, descrição, tags, recursos (arquivos) disponíveis
    e links para download.

    Args:
        dataset_id: Nome (slug) ou UUID do dataset (ex: "hospitais-leitos").

    Returns:
        Detalhes completos do dataset com lista de recursos.
    """
    await ctx.info(f"Consultando dataset '{dataset_id}'...")

    ds = await client.detalhar_dataset(dataset_id)

    if not ds:
        return f"Dataset '{dataset_id}' não encontrado no OpenDataSUS."

    lines = [
        f"**{ds.titulo or ds.nome}**\n",
        f"- **ID:** {ds.nome}",
        f"- **Organização:** {ds.organizacao or '—'}",
        f"- **Tags:** {', '.join(ds.tags) if ds.tags else '—'}",
        f"- **Criação:** {(ds.data_criacao or '—')[:10]}",
        f"- **Atualização:** {(ds.data_atualizacao or '—')[:10]}",
    ]

    if ds.descricao:
        desc = ds.descricao[:500]
        lines.append(f"\n**Descrição:**\n{desc}")

    if ds.recursos:
        lines.append(f"\n**Recursos ({ds.total_recursos}):**\n")
        rec_rows = [
            (
                r.id[:12],
                (r.nome or "—")[:40],
                r.formato or "—",
                r.url or "—",
            )
            for r in ds.recursos[:20]
        ]
        lines.append(markdown_table(["ID", "Nome", "Formato", "URL"], rec_rows))

    return "\n".join(lines)


async def consultar_datastore(
    ctx: Context,
    resource_id: str,
    query: str | None = None,
    limite: int = 20,
    offset: int = 0,
) -> str:
    """Consulta registros de um recurso DataStore no OpenDataSUS.

    Permite acessar dados tabulares de datasets que possuem DataStore ativado.
    Use detalhar_dataset primeiro para obter o resource_id.

    Args:
        resource_id: UUID do recurso (obtido via detalhar_dataset).
        query: Busca textual nos registros (opcional).
        limite: Número máximo de registros (padrão: 20).
        offset: Deslocamento para paginação (padrão: 0).

    Returns:
        Tabela com registros encontrados.
    """
    await ctx.info(f"Consultando DataStore do recurso {resource_id[:12]}...")

    records, total = await client.consultar_datastore(
        resource_id=resource_id,
        query=query,
        limite=limite,
        offset=offset,
    )

    if not records:
        return "Nenhum registro encontrado no DataStore para os filtros informados."

    # Build table from first record's keys
    first = records[0].campos
    cols = list(first.keys())[:8]  # Limit columns for readability

    rows = [tuple(str(r.campos.get(c, "—"))[:40] for c in cols) for r in records[:50]]

    header = f"**DataStore** — {len(records)} registros (total: {total}, offset: {offset})\n\n"
    return header + markdown_table(cols, rows)


async def listar_datasets_conhecidos(ctx: Context) -> str:
    """Lista os datasets mais importantes do OpenDataSUS.

    Retorna uma lista curada dos principais datasets disponíveis:
    hospitais/leitos, vacinação, SRAG, SISAGUA (água) e SINAN (agravos).

    Returns:
        Lista dos datasets mais relevantes com descrição.
    """
    await ctx.info("Listando datasets conhecidos do OpenDataSUS...")

    rows = [(d["nome"], d["titulo"], d["descricao"]) for d in DATASETS_CONHECIDOS]

    header = f"**Datasets conhecidos do OpenDataSUS** ({len(DATASETS_CONHECIDOS)} itens)\n\n"
    return header + markdown_table(["ID/Nome", "Título", "Descrição"], rows)


async def buscar_com_filtro(
    ctx: Context,
    resource_id: str,
    campo: str,
    valor: str,
    limite: int = 20,
) -> str:
    """Busca registros no DataStore filtrando por um campo específico.

    Útil para filtrar dados por UF, município, ano, etc.

    Args:
        resource_id: UUID do recurso DataStore.
        campo: Nome do campo para filtrar (ex: "uf", "municipio", "ano").
        valor: Valor exato do filtro (ex: "SP", "2024").
        limite: Número máximo de registros (padrão: 20).

    Returns:
        Tabela com registros filtrados.
    """
    await ctx.info(f"Filtrando DataStore por {campo}={valor}...")

    filtros = {campo: valor}
    records, total = await client.consultar_datastore(
        resource_id=resource_id,
        filtros=filtros,
        limite=limite,
    )

    if not records:
        return f"Nenhum registro encontrado com {campo}='{valor}'."

    first = records[0].campos
    cols = list(first.keys())[:8]

    rows = [tuple(str(r.campos.get(c, "—"))[:40] for c in cols) for r in records[:50]]

    header = (
        f"**DataStore filtrado** ({campo}={valor}) — {len(records)} registros (total: {total})\n\n"
    )
    return header + markdown_table(cols, rows)


async def _consultar_dataset_dedicado(
    ctx: Context,
    dataset_slug: str,
    query: str | None = None,
    filtros: dict[str, str] | None = None,
    limite: int = 20,
) -> str:
    """Find dataset, pick first resource, and query its DataStore."""
    info = DATASETS_CONHECIDOS_MAP.get(dataset_slug)
    titulo = info["titulo"] if info else dataset_slug

    ds = await client.detalhar_dataset(dataset_slug)
    if not ds or not ds.recursos:
        return (
            f"Dataset '{titulo}' não encontrado ou sem recursos DataStore. "
            "Use buscar_datasets() para verificar a disponibilidade."
        )

    resource_id = ds.recursos[0].id
    records, total = await client.consultar_datastore(
        resource_id=resource_id,
        query=query,
        filtros=filtros,
        limite=limite,
    )

    if not records:
        filtro_desc = ""
        if query:
            filtro_desc = f" para '{query}'"
        elif filtros:
            filtro_desc = f" com filtros {filtros}"
        return f"Nenhum registro encontrado no dataset {titulo}{filtro_desc}."

    first = records[0].campos
    cols = list(first.keys())[:8]
    rows = [tuple(str(r.campos.get(c, "—"))[:40] for c in cols) for r in records[:50]]

    header = f"**{titulo}** — {len(records)} registros (total: {total})\n\n"
    return header + markdown_table(cols, rows)


async def consultar_vacinacao(
    ctx: Context,
    uf: str | None = None,
    municipio: str | None = None,
    limite: int = 20,
) -> str:
    """Consulta dados de vacinação contra Covid-19 no OpenDataSUS.

    Acessa diretamente o dataset de vacinação sem necessidade de buscar o
    resource_id manualmente. Filtros por UF e município são opcionais.

    Args:
        uf: Sigla da UF para filtrar (ex: "SP", "RJ"). Opcional.
        municipio: Nome do município para filtrar. Opcional.
        limite: Número máximo de registros (padrão: 20).

    Returns:
        Tabela com registros de vacinação.
    """
    filtros: dict[str, str] = {}
    if uf:
        filtros["paciente_endereco_uf"] = uf.upper()
    if municipio:
        filtros["paciente_endereco_nmMunicipio"] = municipio

    filtro_desc = uf or municipio or ""
    await ctx.info(f"Consultando vacinação Covid-19 {filtro_desc}...".strip())

    return await _consultar_dataset_dedicado(
        ctx,
        dataset_slug="covid-19-vacinacao",
        filtros=filtros if filtros else None,
        limite=limite,
    )


async def consultar_srag(
    ctx: Context,
    uf: str | None = None,
    ano: str | None = None,
    limite: int = 20,
) -> str:
    """Consulta dados de SRAG (Síndrome Respiratória Aguda Grave) no OpenDataSUS.

    Acessa diretamente o dataset SRAG sem necessidade de buscar o resource_id
    manualmente. Permite filtrar por UF e ano epidemiológico.

    Args:
        uf: Sigla da UF para filtrar (ex: "SP", "RJ"). Opcional.
        ano: Ano epidemiológico (ex: "2024"). Opcional.
        limite: Número máximo de registros (padrão: 20).

    Returns:
        Tabela com registros de SRAG.
    """
    filtros: dict[str, str] = {}
    if uf:
        filtros["SG_UF_NOT"] = uf.upper()
    if ano:
        filtros["NU_ANO"] = ano

    filtro_desc = uf or ano or ""
    await ctx.info(f"Consultando SRAG {filtro_desc}...".strip())

    return await _consultar_dataset_dedicado(
        ctx,
        dataset_slug="srag",
        filtros=filtros if filtros else None,
        limite=limite,
    )
