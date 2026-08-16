"""Tool functions for the TCE-CE feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl

from . import client


async def listar_municipios_ce(ctx: Context) -> str:
    """Lista os municípios cearenses sob jurisdição do TCE-CE.

    Retorna código e nome de cada município. O código é usado
    como parâmetro nas demais consultas.

    Args:
        ctx: Contexto MCP.

    Returns:
        Lista de municípios com código e nome.
    """
    await ctx.info("Listando municípios do TCE-CE...")
    municipios = await client.listar_municipios()

    if not municipios:
        return "Nenhum município encontrado no TCE-CE."

    lines: list[str] = [f"**{len(municipios)} municípios no TCE-CE:**\n"]
    for m in municipios[:50]:
        lines.append(f"- **{m.nome_municipio or '—'}** (código: `{m.codigo_municipio}`)")

    if len(municipios) > 50:
        lines.append(f"\n*Mostrando 50 de {len(municipios)} municípios.*")
    return "\n".join(lines)


async def buscar_licitacoes_ce(
    ctx: Context,
    codigo_municipio: str,
    data_realizacao: str,
) -> str:
    """Busca licitações de um município cearense por período.

    Dados do SIM (Sistema de Informações Municipais) do TCE-CE.
    Inclui modalidade, objeto, valor estimado e homologação.

    Args:
        ctx: Contexto MCP.
        codigo_municipio: Código do município (ex: "057" para Fortaleza).
            Use listar_municipios_ce para obter códigos.
        data_realizacao: Data ou intervalo no formato yyyy-mm-dd
            ou yyyy-mm-dd_yyyy-mm-dd (ex: "2024-01-01_2024-12-31").

    Returns:
        Lista de licitações com objeto, modalidade e valores.
    """
    await ctx.info(f"Buscando licitações no TCE-CE (município {codigo_municipio})...")
    licitacoes = await client.buscar_licitacoes(
        codigo_municipio=codigo_municipio,
        data_realizacao=data_realizacao,
    )

    if not licitacoes:
        return "Nenhuma licitação encontrada no TCE-CE."

    lines: list[str] = [f"**{len(licitacoes)} licitações no TCE-CE:**\n"]
    for lic in licitacoes[:20]:
        valor = format_brl(lic.valor_orcado_estimado) if lic.valor_orcado_estimado else "—"
        objeto = (lic.objeto or "—")[:200]
        lines.append(f"### {lic.numero_licitacao or '—'}")
        lines.append(f"- **Data:** {lic.data_realizacao or '—'}")
        lines.append(f"- **Modalidade:** {lic.modalidade_licitacao or '—'}")
        lines.append(f"- **Objeto:** {objeto}")
        lines.append(f"- **Valor estimado:** {valor}")
        if lic.data_homologacao:
            lines.append(f"- **Homologação:** {lic.data_homologacao}")
        lines.append("")

    if len(licitacoes) > 20:
        lines.append(f"*Mostrando 20 de {len(licitacoes)} licitações.*")
    return "\n".join(lines)


async def buscar_contratos_ce(
    ctx: Context,
    codigo_municipio: str,
    data_contrato: str,
    deslocamento: int = 0,
) -> str:
    """Busca contratos de um município cearense por período.

    Dados do SIM do TCE-CE. Inclui objeto, valor total,
    tipo e vigência do contrato.

    Args:
        ctx: Contexto MCP.
        codigo_municipio: Código do município (ex: "057" para Fortaleza).
        data_contrato: Data ou intervalo no formato yyyy-mm-dd
            ou yyyy-mm-dd_yyyy-mm-dd.
        deslocamento: Offset para paginação.

    Returns:
        Lista de contratos com objeto, valor e vigência.
    """
    await ctx.info(f"Buscando contratos no TCE-CE (município {codigo_municipio})...")
    resultado = await client.buscar_contratos(
        codigo_municipio=codigo_municipio,
        data_contrato=data_contrato,
        deslocamento=deslocamento,
    )

    if not resultado.contratos:
        return "Nenhum contrato encontrado no TCE-CE."

    lines: list[str] = [f"**{resultado.total} contratos no TCE-CE:**\n"]
    for c in resultado.contratos[:20]:
        valor = format_brl(c.valor_total_contrato) if c.valor_total_contrato else "—"
        objeto = (c.objeto or "—")[:200]
        lines.append(f"### {c.numero_contrato or '—'}")
        lines.append(f"- **Data:** {c.data_contrato or '—'}")
        lines.append(f"- **Tipo:** {c.tipo_contrato or '—'}")
        lines.append(f"- **Objeto:** {objeto}")
        lines.append(f"- **Valor:** {valor}")
        if c.data_fim_vigencia:
            lines.append(f"- **Vigência até:** {c.data_fim_vigencia}")
        lines.append("")

    if resultado.total > 20:
        lines.append(
            f"*Mostrando 20 de {resultado.total}. "
            f"Use deslocamento={deslocamento + 50} para próxima página.*"
        )
    return "\n".join(lines)


async def buscar_empenhos_ce(
    ctx: Context,
    codigo_municipio: int,
    data_referencia: int,
    codigo_orgao: str = "02",
    deslocamento: int = 0,
) -> str:
    """Busca notas de empenho de um município cearense.

    Empenhos são o primeiro estágio da despesa pública.
    Dados do SIM do TCE-CE.

    Args:
        ctx: Contexto MCP.
        codigo_municipio: Código numérico do município (ex: 57 para Fortaleza).
        data_referencia: Ano-mês no formato yyyymm (ex: 202401 para jan/2024).
        codigo_orgao: Código do órgão ("01" = Câmara, "02" = Prefeitura).
        deslocamento: Offset para paginação.

    Returns:
        Lista de empenhos com credor, valor e descrição.
    """
    await ctx.info(f"Buscando empenhos no TCE-CE (município {codigo_municipio})...")
    resultado = await client.buscar_empenhos(
        codigo_municipio=codigo_municipio,
        data_referencia=data_referencia,
        codigo_orgao=codigo_orgao,
        deslocamento=deslocamento,
    )

    if not resultado.empenhos:
        return "Nenhum empenho encontrado no TCE-CE."

    lines: list[str] = [f"**{resultado.total} empenhos no TCE-CE:**\n"]
    for e in resultado.empenhos[:20]:
        valor = format_brl(e.valor_empenho) if e.valor_empenho else "—"
        historico = (e.historico or "—")[:150]
        lines.append(f"### Empenho {e.numero_empenho or '—'}")
        lines.append(f"- **Data:** {e.data_emissao or '—'}")
        lines.append(f"- **Credor:** {e.nome_negociante or '—'}")
        lines.append(f"- **Valor:** {valor}")
        lines.append(f"- **Descrição:** {historico}")
        lines.append("")

    if resultado.total > 20:
        lines.append(
            f"*Mostrando 20 de {resultado.total}. "
            f"Use deslocamento={deslocamento + 50} para próxima página.*"
        )
    return "\n".join(lines)
