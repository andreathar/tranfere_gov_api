"""Tool functions for the TCE-SC feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from . import client


async def listar_municipios_sc(ctx: Context) -> str:
    """Lista os municípios de Santa Catarina registrados no TCE-SC.

    Dados de referência do Portal da Transparência do TCE-SC.
    Retorna código IBGE e nome de cada município.

    Args:
        ctx: Contexto MCP.

    Returns:
        Lista de municípios de SC com código IBGE.
    """
    await ctx.info("Buscando municípios de SC no TCE-SC...")
    municipios = await client.listar_municipios()

    if not municipios:
        return "Nenhum município encontrado no TCE-SC."

    lines: list[str] = [f"**{len(municipios)} municípios de SC no TCE-SC:**\n"]
    for m in municipios[:50]:
        lines.append(f"- **{m.nome_municipio or '—'}** (IBGE: `{m.codigo_municipio}`)")

    if len(municipios) > 50:
        lines.append(f"\n*Mostrando 50 de {len(municipios)} municípios.*")
    return "\n".join(lines)


async def listar_unidades_gestoras_sc(
    ctx: Context,
    municipio: str | None = None,
) -> str:
    """Lista unidades gestoras de Santa Catarina no TCE-SC.

    Inclui prefeituras, câmaras, autarquias, consórcios e órgãos
    estaduais. Pode filtrar por nome do município.

    Args:
        ctx: Contexto MCP.
        municipio: Filtrar por nome do município (busca parcial).

    Returns:
        Lista de unidades gestoras com código, nome e município.
    """
    await ctx.info("Buscando unidades gestoras de SC no TCE-SC...")
    unidades = await client.listar_unidades_gestoras()

    if municipio:
        termo = municipio.upper()
        unidades = [u for u in unidades if termo in (u.nome_municipio or "").upper()]

    if not unidades:
        return "Nenhuma unidade gestora encontrada no TCE-SC."

    lines: list[str] = [f"**{len(unidades)} unidades gestoras no TCE-SC:**\n"]
    for u in unidades[:30]:
        sigla = f" ({u.sigla_unidade})" if u.sigla_unidade else ""
        lines.append(
            f"- **{u.nome_unidade or '—'}**{sigla} "
            f"(código: `{u.codigo_unidade}`, município: {u.nome_municipio or '—'})"
        )

    if len(unidades) > 30:
        lines.append(f"\n*Mostrando 30 de {len(unidades)} unidades.*")
    return "\n".join(lines)
