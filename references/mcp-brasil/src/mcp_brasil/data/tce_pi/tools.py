"""MCP tools for TCE-PI — Portal da Cidadania do Piauí.

Each tool delegates HTTP to client.py and returns LLM-formatted strings.
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl

from . import client


async def listar_prefeituras_pi(ctx: Context) -> str:
    """Lista todas as prefeituras (municípios) do estado do Piauí.

    Retorna nome, código IBGE e links dos 224 municípios piauienses
    registrados no TCE-PI.
    """
    await ctx.info("Listando prefeituras do Piauí...")
    items = await client.listar_prefeituras()
    if not items:
        return "Nenhuma prefeitura encontrada."

    lines: list[str] = [f"## Prefeituras do Piauí ({len(items)} municípios)\n"]
    for p in items[:50]:
        line = f"- **{p.nome}** (ID: {p.id}"
        if p.codIBGE:
            line += f", IBGE: {p.codIBGE}"
        line += ")"
        lines.append(line)

    if len(items) > 50:
        lines.append(f"\n_... e mais {len(items) - 50} municípios._")
    return "\n".join(lines)


async def buscar_prefeitura_pi(ctx: Context, nome: str) -> str:
    """Busca prefeituras do Piauí por nome.

    Args:
        nome: Nome ou parte do nome do município (ex: 'Teresina', 'Picos').
    """
    await ctx.info(f"Buscando prefeitura: {nome}")
    items = await client.buscar_prefeitura(nome)
    if not items:
        return f"Nenhuma prefeitura encontrada para '{nome}'."

    lines: list[str] = [f"## Prefeituras encontradas: {len(items)}\n"]
    for p in items:
        lines.append(f"### {p.nome} (ID: {p.id})")
        if p.codIBGE:
            lines.append(f"- Código IBGE: {p.codIBGE}")
        if p.urlPrefeitura:
            lines.append(f"- Site: {p.urlPrefeitura}")
        if p.urlCamara:
            lines.append(f"- Câmara: {p.urlCamara}")

        gestor = await client.consultar_gestor(p.id)
        if gestor:
            lines.append(f"- Prefeito(a): {gestor.nome}")
            if gestor.inicio_gestao:
                lines.append(f"- Início gestão: {gestor.inicio_gestao[:10]}")
        lines.append("")
    return "\n".join(lines)


async def consultar_despesas_pi(
    ctx: Context,
    id_prefeitura: int,
    exercicio: int | None = None,
) -> str:
    """Consulta despesas de um município do Piauí.

    Retorna o histórico anual de despesas (empenhada, liquidada, paga).
    Se o exercício for informado, também detalha por função de governo.

    Args:
        id_prefeitura: ID da prefeitura no TCE-PI (obtido via buscar_prefeitura_pi).
        exercicio: Ano do exercício (ex: 2024). Se omitido, retorna histórico.
    """
    await ctx.info(f"Consultando despesas: prefeitura={id_prefeitura}")
    anuais = await client.consultar_despesas(id_prefeitura)
    if not anuais:
        return f"Nenhuma despesa encontrada para prefeitura {id_prefeitura}."

    lines: list[str] = [f"## Despesas — Prefeitura {id_prefeitura}\n"]
    lines.append("### Histórico anual\n")
    lines.append("| Exercício | Empenhada | Liquidada | Paga |")
    lines.append("|-----------|-----------|-----------|------|")
    for d in anuais:
        lines.append(
            f"| {d.exercicio} | {format_brl(d.empenhada)} "
            f"| {format_brl(d.liquidada)} | {format_brl(d.paga)} |"
        )

    if exercicio:
        funcoes = await client.consultar_despesas_por_funcao(id_prefeitura, exercicio)
        if funcoes:
            lines.append(f"\n### Despesas por função — {exercicio}\n")
            for f in funcoes:
                lines.append(f"- **{f.funcao}**: {format_brl(f.paga)}")
    return "\n".join(lines)


async def consultar_receitas_pi(
    ctx: Context,
    id_prefeitura: int,
    exercicio: int,
) -> str:
    """Consulta receitas de um município do Piauí em determinado exercício.

    Retorna receitas detalhadas (categoria, origem, valores previstos e
    arrecadados).

    Args:
        id_prefeitura: ID da prefeitura no TCE-PI.
        exercicio: Ano do exercício (ex: 2024).
    """
    await ctx.info(f"Consultando receitas: prefeitura={id_prefeitura}, ano={exercicio}")
    items = await client.consultar_receitas(id_prefeitura, exercicio)
    if not items:
        return (
            f"Nenhuma receita encontrada para prefeitura {id_prefeitura} no exercício {exercicio}."
        )

    lines: list[str] = [
        f"## Receitas — Prefeitura {id_prefeitura} ({exercicio})\n",
        f"Total de {len(items)} itens de receita.\n",
    ]
    for r in items[:30]:
        cat = r.categoria or "N/A"
        desc = r.receita or r.detalhamento or "Sem descrição"
        lines.append(f"- **{cat}** — {desc}")
        lines.append(
            f"  Prevista: {format_brl(r.prevista)} | Arrecadada: {format_brl(r.arrecadada)}"
        )

    if len(items) > 30:
        lines.append(f"\n_... e mais {len(items) - 30} itens._")
    return "\n".join(lines)


async def listar_orgaos_pi(ctx: Context, exercicio: int) -> str:
    """Lista órgãos estaduais do Piauí em determinado exercício.

    Retorna a lista de órgãos/entidades estaduais registrados no TCE-PI.

    Args:
        exercicio: Ano do exercício (ex: 2024).
    """
    await ctx.info(f"Listando órgãos do Piauí: exercicio={exercicio}")
    items = await client.listar_orgaos(exercicio)
    if not items:
        return f"Nenhum órgão encontrado para o exercício {exercicio}."

    lines: list[str] = [f"## Órgãos do Piauí — {exercicio} ({len(items)} órgãos)\n"]
    for o in items:
        sigla = f" ({o.sigla})" if o.sigla and o.sigla != "TODOS" else ""
        lines.append(f"- **{o.nome}**{sigla} — ID: {o.id}")
    return "\n".join(lines)
