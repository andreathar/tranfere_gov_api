"""Tool functions for the RENAME feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_number_br, markdown_table

from . import client
from .constants import GRUPOS_TERAPEUTICOS


async def buscar_medicamento_rename(ctx: Context, nome: str) -> str:
    """Busca medicamentos na RENAME (Relação Nacional de Medicamentos Essenciais) do SUS.

    Pesquisa por nome comercial ou princípio ativo. A RENAME lista os medicamentos
    que devem estar disponíveis em todas as unidades do SUS.

    Args:
        nome: Nome do medicamento ou princípio ativo (ex: "paracetamol", "insulina").

    Returns:
        Tabela com medicamentos encontrados na RENAME.
    """
    await ctx.info(f"Buscando '{nome}' na RENAME...")

    resultados = client.buscar_medicamento(nome)

    if not resultados:
        return (
            f"Nenhum medicamento encontrado para '{nome}' na RENAME. "
            "Isso não significa que o medicamento não existe — apenas que "
            "não consta na Relação Nacional de Medicamentos Essenciais."
        )

    rows = [
        (
            m.nome,
            m.principio_ativo,
            m.apresentacao,
            m.grupo,
            m.via,
            "Sim" if m.disponivel_ubs else "Não",
        )
        for m in resultados
    ]

    header = f"**RENAME — Medicamentos encontrados** ({len(resultados)} resultado(s))\n\n"
    return header + markdown_table(
        ["Nome", "Princípio Ativo", "Apresentação", "Grupo", "Via", "Disponível UBS"],
        rows,
    )


async def listar_por_grupo_terapeutico(ctx: Context, grupo: str) -> str:
    """Lista medicamentos da RENAME por grupo terapêutico.

    Exemplos de grupos: "antibióticos", "anti-hipertensivos", "antidiabéticos",
    "antidepressivos", "analgésicos", "antiparasitários".

    Args:
        grupo: Nome do grupo terapêutico (busca parcial, ex: "antibió").

    Returns:
        Tabela com medicamentos do grupo informado.
    """
    await ctx.info(f"Listando medicamentos do grupo '{grupo}'...")

    resultados = client.listar_por_grupo(grupo)

    if not resultados:
        grupos_str = ", ".join(GRUPOS_TERAPEUTICOS)
        return (
            f"Nenhum medicamento encontrado para o grupo '{grupo}'. "
            f"Grupos disponíveis: {grupos_str}."
        )

    rows = [
        (
            m.nome,
            m.principio_ativo,
            m.apresentacao,
            m.via,
            "Sim" if m.disponivel_ubs else "Não",
        )
        for m in resultados
    ]

    header = f"**RENAME — Grupo: {resultados[0].grupo}** ({len(resultados)} medicamento(s))\n\n"
    return header + markdown_table(
        ["Nome", "Princípio Ativo", "Apresentação", "Via", "Disponível UBS"],
        rows,
    )


async def verificar_disponibilidade_sus(ctx: Context, nome: str) -> str:
    """Verifica se um medicamento está na RENAME e disponível no SUS.

    Útil para saber se um medicamento deve ser fornecido gratuitamente
    nas Unidades Básicas de Saúde (UBS) ou apenas em unidades especializadas.

    Args:
        nome: Nome do medicamento ou princípio ativo (ex: "losartana").

    Returns:
        Status de disponibilidade do medicamento no SUS.
    """
    await ctx.info(f"Verificando disponibilidade de '{nome}' no SUS...")

    resultados = client.verificar_disponibilidade_sus(nome)

    if not resultados:
        return (
            f"O medicamento '{nome}' **não foi encontrado** na RENAME. "
            "Consulte a ANVISA para verificar se o medicamento é registrado no Brasil."
        )

    lines = [f"**Disponibilidade no SUS para '{nome}'** ({len(resultados)} resultado(s))\n"]

    for m in resultados:
        status = "Disponível em UBS" if m.disponivel_ubs else "Apenas unidades especializadas"
        lines.append(
            f"- **{m.nome}** ({m.principio_ativo}) — {m.apresentacao}\n"
            f"  Via: {m.via} | Grupo: {m.grupo} | **{status}**"
        )

    return "\n".join(lines)


async def listar_grupos_terapeuticos(ctx: Context) -> str:
    """Lista todos os grupos terapêuticos da RENAME.

    Retorna a lista completa de categorias de medicamentos na Relação
    Nacional de Medicamentos Essenciais.

    Returns:
        Lista numerada de grupos terapêuticos.
    """
    await ctx.info("Listando grupos terapêuticos da RENAME...")

    grupos = client.listar_grupos()

    lines = [f"**Grupos Terapêuticos da RENAME** ({len(grupos)} grupos)\n"]
    for i, grupo in enumerate(grupos, 1):
        lines.append(f"{i}. {grupo}")

    return "\n".join(lines)


async def estatisticas_rename(ctx: Context) -> str:
    """Retorna estatísticas consolidadas da RENAME.

    Mostra o total de medicamentos, grupos terapêuticos, distribuição
    por via de administração e disponibilidade em UBS.

    Returns:
        Resumo estatístico da RENAME.
    """
    await ctx.info("Calculando estatísticas da RENAME...")

    todos = client.listar_todos()
    grupos = client.listar_grupos()

    total = len(todos)
    disponiveis_ubs = sum(1 for m in todos if m.disponivel_ubs)

    # Contagem por via de administração
    vias: dict[str, int] = {}
    for m in todos:
        vias[m.via] = vias.get(m.via, 0) + 1

    # Contagem por grupo
    por_grupo: dict[str, int] = {}
    for m in todos:
        por_grupo[m.grupo] = por_grupo.get(m.grupo, 0) + 1

    lines = [
        "**Estatísticas da RENAME**\n",
        f"- **Total de medicamentos:** {format_number_br(float(total), 0)}",
        f"- **Grupos terapêuticos:** {format_number_br(float(len(grupos)), 0)}",
        f"- **Disponíveis em UBS:** {format_number_br(float(disponiveis_ubs), 0)}"
        f" ({disponiveis_ubs * 100 // total}%)",
        "",
        "**Por via de administração:**\n",
    ]

    via_rows = [(via, str(count)) for via, count in sorted(vias.items())]
    lines.append(markdown_table(["Via", "Medicamentos"], via_rows))

    lines.append("\n**Por grupo terapêutico:**\n")
    grupo_rows = [(g, str(c)) for g, c in sorted(por_grupo.items())]
    lines.append(markdown_table(["Grupo", "Medicamentos"], grupo_rows))

    return "\n".join(lines)
