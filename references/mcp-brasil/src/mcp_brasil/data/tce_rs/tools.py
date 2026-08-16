"""Tool functions for the TCE-RS feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl, format_percent

from . import client


async def listar_municipios_rs(ctx: Context) -> str:
    """Lista os municípios do Rio Grande do Sul registrados no TCE-RS.

    Dados de referência do portal de dados abertos do TCE-RS.
    Retorna código, nome e código IBGE de cada município.

    Args:
        ctx: Contexto MCP.

    Returns:
        Lista de municípios do RS com códigos.
    """
    await ctx.info("Buscando municípios do RS no TCE-RS...")
    municipios = await client.listar_municipios()

    if not municipios:
        return "Nenhum município encontrado no TCE-RS."

    lines: list[str] = [f"**{len(municipios)} municípios do RS no TCE-RS:**\n"]
    for m in municipios[:50]:
        ibge = f", IBGE: {m.codigo_ibge}" if m.codigo_ibge else ""
        lines.append(f"- **{m.nome or '—'}** (código: `{m.codigo}`{ibge})")

    if len(municipios) > 50:
        lines.append(f"\n*Mostrando 50 de {len(municipios)} municípios.*")
    return "\n".join(lines)


async def buscar_indices_educacao_rs(
    ctx: Context,
    ano: int,
    municipio: str | None = None,
) -> str:
    """Busca índices de aplicação em educação dos municípios do RS.

    Dados do TCE-RS sobre o cumprimento do mínimo constitucional de 25%
    em Manutenção e Desenvolvimento do Ensino (MDE). Útil para verificar
    se municípios estão cumprindo a obrigação legal.

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        municipio: Filtrar por nome do município (busca parcial).

    Returns:
        Lista de municípios com índice de educação.
    """
    await ctx.info(f"Buscando índices de educação no TCE-RS (ano={ano})...")
    indices = await client.buscar_indices_educacao(ano)

    if municipio:
        termo = municipio.upper()
        indices = [i for i in indices if termo in (i.nome_orgao or "").upper()]

    if not indices:
        return "Nenhum índice de educação encontrado no TCE-RS."

    lines: list[str] = [f"**{len(indices)} índices de educação ({ano}):**\n"]
    for idx in indices[:30]:
        indice_fmt = format_percent(idx.indice) if idx.indice is not None else "—"
        despesa = format_brl(idx.valor_despesa) if idx.valor_despesa else "—"
        receita = format_brl(idx.valor_receita) if idx.valor_receita else "—"
        lines.append(f"- **{idx.nome_orgao or '—'}** — Índice: {indice_fmt}")
        lines.append(f"  Despesa: {despesa} | Receita: {receita}")

    if len(indices) > 30:
        lines.append(f"\n*Mostrando 30 de {len(indices)} municípios.*")
    return "\n".join(lines)


async def buscar_indices_saude_rs(
    ctx: Context,
    ano: int,
    municipio: str | None = None,
) -> str:
    """Busca índices de aplicação em saúde dos municípios do RS.

    Dados do TCE-RS sobre o cumprimento do mínimo constitucional de 15%
    em Ações e Serviços Públicos de Saúde (ASPS). Útil para verificar
    se municípios estão cumprindo a obrigação legal.

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        municipio: Filtrar por nome do município (busca parcial).

    Returns:
        Lista de municípios com índice de saúde.
    """
    await ctx.info(f"Buscando índices de saúde no TCE-RS (ano={ano})...")
    indices = await client.buscar_indices_saude(ano)

    if municipio:
        termo = municipio.upper()
        indices = [i for i in indices if termo in (i.nome_orgao or "").upper()]

    if not indices:
        return "Nenhum índice de saúde encontrado no TCE-RS."

    lines: list[str] = [f"**{len(indices)} índices de saúde ({ano}):**\n"]
    for idx in indices[:30]:
        indice_fmt = format_percent(idx.indice) if idx.indice is not None else "—"
        despesa = format_brl(idx.valor_despesa) if idx.valor_despesa else "—"
        receita = format_brl(idx.valor_receita) if idx.valor_receita else "—"
        lines.append(f"- **{idx.nome_orgao or '—'}** — Índice: {indice_fmt}")
        lines.append(f"  Despesa: {despesa} | Receita: {receita}")

    if len(indices) > 30:
        lines.append(f"\n*Mostrando 30 de {len(indices)} municípios.*")
    return "\n".join(lines)


async def buscar_gestao_fiscal_rs(
    ctx: Context,
    ano: int,
    municipio: str | None = None,
) -> str:
    """Busca dados de gestão fiscal (LRF) dos municípios do RS.

    Dados do TCE-RS sobre a Lei de Responsabilidade Fiscal: receita corrente
    líquida, despesa com pessoal, dívida consolidada, operações de crédito,
    e gastos com educação (MDE) e saúde (ASPS).

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        municipio: Filtrar por nome do município (busca parcial).

    Returns:
        Lista de municípios com dados de gestão fiscal.
    """
    await ctx.info(f"Buscando gestão fiscal no TCE-RS (ano={ano})...")
    dados = await client.buscar_gestao_fiscal(ano)

    if municipio:
        termo = municipio.upper()
        dados = [d for d in dados if termo in (d.nome_orgao or "").upper()]

    if not dados:
        return "Nenhum dado de gestão fiscal encontrado no TCE-RS."

    lines: list[str] = [f"**{len(dados)} registros de gestão fiscal ({ano}):**\n"]
    for d in dados[:20]:
        rcl = format_brl(d.receita_corrente_liquida) if d.receita_corrente_liquida else "—"
        pessoal = format_brl(d.despesa_pessoal) if d.despesa_pessoal else "—"
        divida = format_brl(d.divida_consolidada) if d.divida_consolidada else "—"
        lines.append(f"### {d.nome_orgao or '—'}")
        lines.append(f"- **Receita corrente líquida:** {rcl}")
        lines.append(f"- **Despesa com pessoal:** {pessoal}")
        lines.append(f"- **Dívida consolidada:** {divida}")
        lines.append("")

    if len(dados) > 20:
        lines.append(f"*Mostrando 20 de {len(dados)} registros.*")
    return "\n".join(lines)


async def buscar_datasets_rs(
    ctx: Context,
    query: str,
    grupo: str | None = None,
    limite: int = 10,
) -> str:
    """Busca datasets no portal de dados abertos do TCE-RS.

    O portal CKAN do TCE-RS possui ~69.000 datasets organizados em 16 grupos:
    despesa, receita, licitacoes, contratos, decisoes, educacao, saude,
    previdencia, gestao-fiscal, ouvidoria, entre outros.

    Args:
        ctx: Contexto MCP.
        query: Termo de busca (ex: "consolidado 2024", "licitacoes recife").
        grupo: Filtrar por grupo (ex: "despesa", "licitacoes", "contratos").
        limite: Máximo de resultados (1-50, padrão 10).

    Returns:
        Lista de datasets com título, grupo e link para download.
    """
    await ctx.info(f"Buscando datasets no TCE-RS (query='{query}')...")
    datasets, total = await client.buscar_datasets(query, grupo=grupo, limite=limite)

    if not datasets:
        return "Nenhum dataset encontrado no portal do TCE-RS."

    lines: list[str] = [f"**{total} datasets encontrados (mostrando {len(datasets)}):**\n"]
    for ds in datasets:
        notas = f" — {ds.notas}" if ds.notas else ""
        grupo_txt = f" [{ds.grupo}]" if ds.grupo else ""
        recursos = f" ({ds.num_recursos} recursos)" if ds.num_recursos else ""
        lines.append(f"### {ds.titulo or ds.nome or '—'}{grupo_txt}")
        lines.append(f"- **URL:** {ds.url or '—'}{recursos}")
        if notas:
            lines.append(f"- **Descrição:** {notas}")
        lines.append("")

    return "\n".join(lines)
