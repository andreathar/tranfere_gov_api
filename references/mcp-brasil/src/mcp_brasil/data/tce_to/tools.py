"""Tool functions for the TCE-TO feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from . import client


async def buscar_pessoas_to(
    ctx: Context,
    nome: str | None = None,
    codigo: str | None = None,
) -> str:
    """Busca pessoas com processos no TCE-TO.

    Pesquisa por nome ou CPF (parcial) no sistema e-Contas.
    Retorna as pessoas encontradas e seus processos vinculados.
    Ao menos um filtro (nome ou codigo) é obrigatório.

    Args:
        ctx: Contexto MCP.
        nome: Nome da pessoa (busca parcial).
        codigo: CPF (busca parcial).

    Returns:
        Lista de pessoas com processos vinculados.
    """
    await ctx.info("Buscando pessoas no TCE-TO...")
    pessoas = await client.buscar_pessoas(nome=nome, codigo=codigo)

    if not pessoas:
        return "Nenhuma pessoa encontrada no TCE-TO."

    lines: list[str] = [f"**{len(pessoas)} pessoas encontradas:**\n"]
    for p in pessoas[:10]:
        n_procs = len(p.processos) if p.processos else 0
        lines.append(f"### {p.nome or '—'} (CPF: `{p.codigo or '—'}`)")
        lines.append(f"- **{n_procs} processos**")
        if p.processos:
            for proc in p.processos[:5]:
                lines.append(
                    f"  - `{proc.numero_ano}` — {proc.assunto or '—'} "
                    f"({proc.entidade_origem_municipio or '—'})"
                )
            if len(p.processos) > 5:
                lines.append(f"  - *... e mais {len(p.processos) - 5} processos*")
        lines.append("")

    if len(pessoas) > 10:
        lines.append(f"*Mostrando 10 de {len(pessoas)} pessoas.*")
    return "\n".join(lines)


async def consultar_processo_to(
    ctx: Context,
    numero: int,
    ano: int,
) -> str:
    """Consulta detalhes de um processo no TCE-TO.

    Retorna informações do processo: assunto, entidade de origem,
    departamento atual, complemento e distribuição.

    Args:
        ctx: Contexto MCP.
        numero: Número do processo.
        ano: Ano do processo.

    Returns:
        Detalhes do processo.
    """
    await ctx.info(f"Consultando processo {numero}/{ano} no TCE-TO...")
    proc = await client.consultar_processo(numero=numero, ano=ano)

    if not proc:
        return f"Processo {numero}/{ano} não encontrado no TCE-TO."

    lines = [
        f"### Processo {proc.numero_ano or f'{numero}/{ano}'}",
        f"- **Assunto:** {proc.assunto or '—'}",
        f"- **Classe:** {proc.classe_assunto or '—'}",
        f"- **Entidade:** {proc.entidade_origem or '—'}",
        f"- **Município:** {proc.entidade_origem_municipio or '—'}",
        f"- **CNPJ:** {proc.entidade_origem_cnpj or '—'}",
        f"- **Entrada:** {proc.data_entrada or '—'}",
        f"- **Departamento atual:** {proc.departamento_atual or '—'}",
        f"- **Distribuição:** {proc.distribuicao or '—'}",
    ]
    if proc.complemento:
        lines.append(f"- **Complemento:** {proc.complemento[:300]}")
    return "\n".join(lines)


async def listar_pautas_to(
    ctx: Context,
    tamanho: int = 10,
) -> str:
    """Lista pautas de sessões do TCE-TO.

    Retorna as pautas mais recentes (sessões ordinárias, virtuais,
    por videoconferência) das câmaras e do plenário do TCE-TO.

    Args:
        ctx: Contexto MCP.
        tamanho: Número de pautas a retornar (padrão: 10).

    Returns:
        Lista de pautas com data, tipo e origem.
    """
    await ctx.info("Buscando pautas de sessões do TCE-TO...")
    pautas = await client.listar_pautas(tamanho=tamanho)

    if not pautas:
        return "Nenhuma pauta encontrada no TCE-TO."

    lines: list[str] = [f"**{len(pautas)} pautas de sessão:**\n"]
    for p in pautas:
        lines.append(f"- **{p.data or '—'}** {p.hora or ''} — {p.tipo or '—'}")
        lines.append(f"  Origem: {p.origem or '—'}")
        if p.url:
            lines.append(f"  [Ver pauta]({p.url})")

    return "\n".join(lines)
