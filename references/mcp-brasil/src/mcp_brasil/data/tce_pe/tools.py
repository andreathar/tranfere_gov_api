"""Tool functions for the TCE-PE feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl

from . import client


async def buscar_unidades_pe(
    ctx: Context,
    natureza: str = "prefeitura",
    municipio: str | None = None,
) -> str:
    """Busca unidades jurisdicionadas do TCE-PE (prefeituras, câmaras, etc.).

    Dados do sistema SAGRES do TCE-PE. Retorna código e nome
    das unidades para uso nas demais consultas.

    Args:
        ctx: Contexto MCP.
        natureza: Tipo de unidade (ex: "prefeitura", "câmara").
        municipio: Filtrar por município (ex: "Recife").

    Returns:
        Lista de unidades com código, nome e município.
    """
    await ctx.info(f"Buscando unidades do TCE-PE (natureza={natureza})...")
    unidades = await client.buscar_unidades(natureza=natureza, municipio=municipio)

    if not unidades:
        return "Nenhuma unidade jurisdicionada encontrada no TCE-PE."

    lines: list[str] = [f"**{len(unidades)} unidades no TCE-PE:**\n"]
    for u in unidades[:50]:
        lines.append(
            f"- **{u.nome or '—'}** (código: `{u.codigo}`, município: {u.municipio or '—'})"
        )

    if len(unidades) > 50:
        lines.append(f"\n*Mostrando 50 de {len(unidades)} unidades.*")
    return "\n".join(lines)


async def buscar_licitacoes_pe(
    ctx: Context,
    ano: int,
    municipio: str | None = None,
    modalidade: str | None = None,
) -> str:
    """Busca licitações de Pernambuco registradas no TCE-PE.

    Dados do sistema LICON do TCE-PE. Inclui modalidade, objeto,
    valor estimado e situação da licitação.

    Args:
        ctx: Contexto MCP.
        ano: Ano da licitação (ex: 2024).
        municipio: Filtrar por município (ex: "Recife").
        modalidade: Filtrar por modalidade (ex: "Pregão Eletrônico").

    Returns:
        Lista de licitações com objeto, modalidade e valores.
    """
    await ctx.info(f"Buscando licitações no TCE-PE (ano={ano})...")
    licitacoes = await client.buscar_licitacoes(
        ano=ano, municipio=municipio, modalidade=modalidade
    )

    if not licitacoes:
        return "Nenhuma licitação encontrada no TCE-PE."

    lines: list[str] = [f"**{len(licitacoes)} licitações no TCE-PE:**\n"]
    for lic in licitacoes[:20]:
        valor = format_brl(lic.valor_estimado) if lic.valor_estimado else "—"
        objeto = (lic.objeto or "—")[:200]
        lines.append(f"### {lic.numero_licitacao or '—'}")
        lines.append(f"- **Município:** {lic.municipio or '—'}")
        lines.append(f"- **Modalidade:** {lic.modalidade or '—'}")
        lines.append(f"- **Objeto:** {objeto}")
        lines.append(f"- **Valor estimado:** {valor}")
        lines.append(f"- **Situação:** {lic.situacao or '—'}")
        lines.append("")

    if len(licitacoes) > 20:
        lines.append(f"*Mostrando 20 de {len(licitacoes)} licitações.*")
    return "\n".join(lines)


async def buscar_contratos_pe(
    ctx: Context,
    ano: int,
    municipio: str | None = None,
    cpf_cnpj: str | None = None,
) -> str:
    """Busca contratos de Pernambuco registrados no TCE-PE.

    Dados do sistema LICON do TCE-PE. Inclui objeto, valor,
    fornecedor e unidade gestora.

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        municipio: Filtrar por município (ex: "Recife").
        cpf_cnpj: Filtrar por CPF/CNPJ do fornecedor.

    Returns:
        Lista de contratos com objeto, valor e fornecedor.
    """
    await ctx.info(f"Buscando contratos no TCE-PE (ano={ano})...")
    contratos = await client.buscar_contratos(ano=ano, municipio=municipio, cpf_cnpj=cpf_cnpj)

    if not contratos:
        return "Nenhum contrato encontrado no TCE-PE."

    lines: list[str] = [f"**{len(contratos)} contratos no TCE-PE:**\n"]
    for c in contratos[:20]:
        valor = format_brl(c.valor_contrato) if c.valor_contrato else "—"
        objeto = (c.objeto or "—")[:200]
        lines.append(f"### {c.numero_contrato or '—'}")
        lines.append(f"- **Município:** {c.municipio or '—'}")
        lines.append(f"- **Fornecedor:** {c.fornecedor or '—'}")
        lines.append(f"- **Objeto:** {objeto}")
        lines.append(f"- **Valor:** {valor}")
        lines.append("")

    if len(contratos) > 20:
        lines.append(f"*Mostrando 20 de {len(contratos)} contratos.*")
    return "\n".join(lines)


async def buscar_despesas_pe(
    ctx: Context,
    ano: int,
    mes: int | None = None,
    municipio: str | None = None,
    codigo_municipio: str | None = None,
) -> str:
    """Busca despesas municipais de Pernambuco registradas no TCE-PE.

    Dados de execução orçamentária do sistema SAGRES do TCE-PE.
    Inclui empenhos com valores empenhados, liquidados e pagos.

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        mes: Mês de referência (1-12). Se omitido, retorna o ano todo.
        municipio: Filtrar por nome do município.
        codigo_municipio: Código SAGRES do município.

    Returns:
        Lista de despesas com empenho, fornecedor e valores.
    """
    await ctx.info(f"Buscando despesas no TCE-PE (ano={ano})...")
    despesas = await client.buscar_despesas(
        ano=ano, mes=mes, municipio=municipio, codigo_municipio=codigo_municipio
    )

    if not despesas:
        return "Nenhuma despesa encontrada no TCE-PE."

    lines: list[str] = [f"**{len(despesas)} despesas no TCE-PE:**\n"]
    for d in despesas[:20]:
        empenhado = format_brl(d.valor_empenhado) if d.valor_empenhado else "—"
        pago = format_brl(d.valor_pago) if d.valor_pago else "—"
        historico = (d.historico or "—")[:150]
        lines.append(f"### Empenho {d.numero_empenho or '—'}")
        lines.append(f"- **Fornecedor:** {d.fornecedor or '—'}")
        lines.append(f"- **Empenhado:** {empenhado}")
        lines.append(f"- **Pago:** {pago}")
        lines.append(f"- **Função:** {d.funcao or '—'}")
        lines.append(f"- **Descrição:** {historico}")
        lines.append("")

    if len(despesas) > 20:
        lines.append(f"*Mostrando 20 de {len(despesas)} despesas.*")
    return "\n".join(lines)


async def buscar_fornecedores_pe(
    ctx: Context,
    nome: str | None = None,
    cpf_cnpj: str | None = None,
) -> str:
    """Busca fornecedores registrados no TCE-PE.

    Dados do sistema SAGRES do TCE-PE. Busca parcial por nome ou CPF/CNPJ.
    Ao menos um filtro é recomendado para evitar resultados excessivos.

    Args:
        ctx: Contexto MCP.
        nome: Busca parcial por nome do fornecedor.
        cpf_cnpj: Busca parcial por CPF/CNPJ.

    Returns:
        Lista de fornecedores com nome e CPF/CNPJ.
    """
    await ctx.info("Buscando fornecedores no TCE-PE...")
    fornecedores = await client.buscar_fornecedores(nome=nome, cpf_cnpj=cpf_cnpj)

    if not fornecedores:
        return "Nenhum fornecedor encontrado no TCE-PE."

    lines: list[str] = [f"**{len(fornecedores)} fornecedores no TCE-PE:**\n"]
    for f in fornecedores[:30]:
        lines.append(f"- **{f.nome or '—'}** (CPF/CNPJ: `{f.cpf_cnpj or '—'}`)")

    if len(fornecedores) > 30:
        lines.append(f"\n*Mostrando 30 de {len(fornecedores)} fornecedores.*")
    return "\n".join(lines)
