"""Tool functions for the TCE-RN feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl

from . import client


async def listar_jurisdicionados_rn(ctx: Context) -> str:
    """Lista entidades jurisdicionadas pelo TCE-RN.

    Dados do sistema SIAI do TCE-RN. Retorna o identificador da unidade,
    necessário para as demais consultas (despesas, receitas, licitações).

    Args:
        ctx: Contexto MCP.

    Returns:
        Lista de entidades com identificador, nome e CNPJ.
    """
    await ctx.info("Buscando jurisdicionados do TCE-RN...")
    entidades = await client.listar_jurisdicionados()

    if not entidades:
        return "Nenhuma entidade jurisdicionada encontrada no TCE-RN."

    lines: list[str] = [f"**{len(entidades)} jurisdicionados no TCE-RN:**\n"]
    for e in entidades[:50]:
        cnpj = f", CNPJ: `{e.cnpj}`" if e.cnpj else ""
        lines.append(f"- **{e.nome_orgao or '—'}** (id: `{e.identificador_unidade}`{cnpj})")

    if len(entidades) > 50:
        lines.append(f"\n*Mostrando 50 de {len(entidades)} entidades.*")
    return "\n".join(lines)


async def buscar_despesas_rn(
    ctx: Context,
    ano: int,
    bimestre: int,
    id_unidade: int,
) -> str:
    """Busca despesas orçamentárias de uma unidade no TCE-RN.

    Dados do balanço orçamentário (Anexo 01) com valores de dotação,
    empenho, liquidação e pagamento por elemento de despesa.

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        bimestre: Bimestre (1-6).
        id_unidade: ID da unidade (obtido via listar_jurisdicionados_rn).

    Returns:
        Lista de despesas com valores por elemento.
    """
    await ctx.info(f"Buscando despesas no TCE-RN (ano={ano}, bim={bimestre})...")
    despesas = await client.buscar_despesas(ano=ano, bimestre=bimestre, id_unidade=id_unidade)

    if not despesas:
        return "Nenhuma despesa encontrada no TCE-RN."

    lines: list[str] = [f"**{len(despesas)} itens de despesa:**\n"]
    for d in despesas[:20]:
        empenhado = format_brl(d.valor_empenho_ate_periodo) if d.valor_empenho_ate_periodo else "—"
        pago = format_brl(d.valor_pago_ate_periodo) if d.valor_pago_ate_periodo else "—"
        lines.append(f"- **{d.descricao_elemento_despesa or '—'}**")
        lines.append(f"  Empenhado: {empenhado} | Pago: {pago}")

    if len(despesas) > 20:
        lines.append(f"\n*Mostrando 20 de {len(despesas)} itens.*")
    return "\n".join(lines)


async def buscar_receitas_rn(
    ctx: Context,
    ano: int,
    bimestre: int,
    id_unidade: int,
) -> str:
    """Busca receitas orçamentárias de uma unidade no TCE-RN.

    Dados do balanço orçamentário (Anexo 01) com valores previstos
    e realizados por natureza de receita.

    Args:
        ctx: Contexto MCP.
        ano: Ano de referência (ex: 2024).
        bimestre: Bimestre (1-6).
        id_unidade: ID da unidade (obtido via listar_jurisdicionados_rn).

    Returns:
        Lista de receitas com valores previstos e realizados.
    """
    await ctx.info(f"Buscando receitas no TCE-RN (ano={ano}, bim={bimestre})...")
    receitas = await client.buscar_receitas(ano=ano, bimestre=bimestre, id_unidade=id_unidade)

    if not receitas:
        return "Nenhuma receita encontrada no TCE-RN."

    lines: list[str] = [f"**{len(receitas)} itens de receita:**\n"]
    for r in receitas[:20]:
        previsto = format_brl(r.valor_previsto_atualizado) if r.valor_previsto_atualizado else "—"
        realizado = (
            format_brl(r.valor_realizado_no_exercicio) if r.valor_realizado_no_exercicio else "—"
        )
        lines.append(f"- **{r.descricao_receita or '—'}**")
        lines.append(f"  Previsto: {previsto} | Realizado: {realizado}")

    if len(receitas) > 20:
        lines.append(f"\n*Mostrando 20 de {len(receitas)} itens.*")
    return "\n".join(lines)


async def buscar_licitacoes_rn(
    ctx: Context,
    id_unidade: int,
    data_inicio: str,
    data_fim: str,
) -> str:
    """Busca licitações públicas de uma unidade no TCE-RN.

    Dados do Anexo 38 do SIAI. Requer o ID da unidade (obtido via
    listar_jurisdicionados_rn) e um período de datas.

    Args:
        ctx: Contexto MCP.
        id_unidade: ID da unidade jurisdicionada.
        data_inicio: Data inicial (formato yyyy-MM-dd, ex: "2024-01-01").
        data_fim: Data final (formato yyyy-MM-dd, ex: "2024-12-31").

    Returns:
        Lista de licitações com modalidade, objeto e valores.
    """
    await ctx.info(f"Buscando licitações no TCE-RN (unidade={id_unidade})...")
    licitacoes = await client.buscar_licitacoes(
        id_unidade=id_unidade, data_inicio=data_inicio, data_fim=data_fim
    )

    if not licitacoes:
        return "Nenhuma licitação encontrada no TCE-RN."

    lines: list[str] = [f"**{len(licitacoes)} licitações no TCE-RN:**\n"]
    for lic in licitacoes[:20]:
        valor = format_brl(lic.valor_total_orcado) if lic.valor_total_orcado else "—"
        objeto = (lic.descricao_objeto or "—")[:200]
        lines.append(f"### {lic.numero_licitacao or '—'}/{lic.ano_licitacao or '—'}")
        lines.append(f"- **Modalidade:** {lic.modalidade or '—'}")
        lines.append(f"- **Objeto:** {objeto}")
        lines.append(f"- **Valor orçado:** {valor}")
        lines.append(f"- **Situação:** {lic.situacao or '—'}")
        lines.append("")

    if len(licitacoes) > 20:
        lines.append(f"*Mostrando 20 de {len(licitacoes)} licitações.*")
    return "\n".join(lines)


async def buscar_contratos_rn(
    ctx: Context,
    id_unidade: int,
    considerar_hierarquia: bool = False,
) -> str:
    """Busca contratos de uma unidade no TCE-RN.

    Dados do Anexo 13 do SIAI. Inclui objeto, valor, contratado
    e vigência. Use considerar_hierarquia=True para incluir sub-órgãos.

    Args:
        ctx: Contexto MCP.
        id_unidade: ID da unidade jurisdicionada.
        considerar_hierarquia: Incluir sub-órgãos (padrão: False).

    Returns:
        Lista de contratos com objeto, valor e contratado.
    """
    await ctx.info(f"Buscando contratos no TCE-RN (unidade={id_unidade})...")
    contratos = await client.buscar_contratos(
        id_unidade=id_unidade, considerar_hierarquia=considerar_hierarquia
    )

    if not contratos:
        return "Nenhum contrato encontrado no TCE-RN."

    lines: list[str] = [f"**{len(contratos)} contratos no TCE-RN:**\n"]
    for c in contratos[:20]:
        valor = format_brl(c.valor_contrato) if c.valor_contrato else "—"
        objeto = (c.objeto_contrato or "—")[:200]
        lines.append(f"### Contrato {c.numero_contrato or '—'}/{c.ano_contrato or '—'}")
        lines.append(f"- **Contratado:** {c.nome_contratado or '—'}")
        lines.append(f"- **Objeto:** {objeto}")
        lines.append(f"- **Valor:** {valor}")
        lines.append("")

    if len(contratos) > 20:
        lines.append(f"*Mostrando 20 de {len(contratos)} contratos.*")
    return "\n".join(lines)
