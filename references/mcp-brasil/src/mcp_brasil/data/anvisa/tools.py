"""Tool functions for the ANVISA feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table

from . import client
from .constants import CATEGORIAS_MEDICAMENTO, SECOES_BULA


async def buscar_medicamento(
    ctx: Context,
    nome: str,
    pagina: int = 1,
) -> str:
    """Busca medicamentos no Bulário Eletrônico da ANVISA por nome comercial.

    Consulta o Bulário oficial da ANVISA para encontrar medicamentos registrados.
    Retorna nome, empresa, princípio ativo, categoria e número do registro.

    Args:
        nome: Nome comercial do medicamento (ex: "dipirona", "amoxicilina").
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com medicamentos encontrados.
    """
    await ctx.info(f"Buscando '{nome}' no Bulário ANVISA...")

    resultados = await client.buscar_medicamento(nome=nome, pagina=pagina)

    if not resultados:
        return (
            f"Nenhum medicamento encontrado para '{nome}' no Bulário ANVISA. "
            "Tente um nome diferente ou verifique a grafia."
        )

    rows = [
        (
            m.nome_produto or "—",
            m.principio_ativo or "—",
            m.razao_social or "—",
            m.categoria_regulatoria or "—",
            m.numero_processo or "—",
        )
        for m in resultados
    ]

    header = f"**Medicamentos ANVISA** ({len(resultados)} resultado(s) para '{nome}')\n\n"
    return header + markdown_table(
        ["Nome", "Princípio Ativo", "Empresa", "Categoria", "Nº Processo"], rows
    )


async def buscar_por_principio_ativo(
    ctx: Context,
    principio_ativo: str,
    pagina: int = 1,
) -> str:
    """Busca medicamentos por princípio ativo no Bulário da ANVISA.

    Encontra todos os medicamentos registrados que contêm um dado princípio ativo.
    Útil para comparar genéricos, similares e referência do mesmo princípio ativo.

    Args:
        principio_ativo: Nome do princípio ativo (ex: "losartana", "metformina").
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com medicamentos encontrados.
    """
    await ctx.info(f"Buscando princípio ativo '{principio_ativo}' no Bulário...")

    resultados = await client.buscar_por_principio_ativo(
        principio_ativo=principio_ativo, pagina=pagina
    )

    if not resultados:
        return (
            f"Nenhum medicamento com princípio ativo '{principio_ativo}' encontrado. "
            "Tente o nome completo ou verifique a grafia."
        )

    rows = [
        (
            m.nome_produto or "—",
            m.principio_ativo or "—",
            m.razao_social or "—",
            m.categoria_regulatoria or "—",
            m.numero_registro or "—",
        )
        for m in resultados
    ]

    header = (
        f"**Medicamentos com princípio ativo '{principio_ativo}'** "
        f"({len(resultados)} resultado(s))\n\n"
    )
    return header + markdown_table(
        ["Nome", "Princípio Ativo", "Empresa", "Categoria", "Registro"], rows
    )


async def consultar_bula(
    ctx: Context,
    numero_processo: str,
) -> str:
    """Consulta as bulas disponíveis de um medicamento pelo número do processo ANVISA.

    Retorna links para bulas do paciente e do profissional de saúde.
    Use buscar_medicamento() primeiro para obter o número do processo.

    Args:
        numero_processo: Número do processo ANVISA (obtido via buscar_medicamento).

    Returns:
        Lista de bulas disponíveis com links para download.
    """
    await ctx.info(f"Consultando bulas do processo {numero_processo}...")

    resultados = await client.consultar_bula(numero_processo=numero_processo)

    if not resultados:
        return (
            f"Nenhuma bula encontrada para o processo {numero_processo}. "
            "Verifique se o número do processo está correto."
        )

    lines = [f"**Bulas disponíveis** (processo {numero_processo}, {len(resultados)} bula(s))\n"]

    for bula in resultados:
        lines.append(f"- **{bula.nome_produto or 'Medicamento'}**")
        lines.append(f"  - Empresa: {bula.empresa or '—'}")
        lines.append(f"  - Tipo: {bula.tipo_bula or '—'}")
        lines.append(f"  - Publicação: {bula.data_publicacao or '—'}")
        if bula.url_bula:
            lines.append(f"  - URL: {bula.url_bula}")
        lines.append("")

    return "\n".join(lines)


async def listar_categorias(ctx: Context) -> str:
    """Lista as categorias regulatórias de medicamentos da ANVISA.

    Categorias incluem: Novo, Genérico, Similar, Biológico, Específico,
    Fitoterápico, Dinamizado e Radiofármaco. Cada medicamento registrado
    pertence a uma dessas categorias.

    Returns:
        Tabela com códigos e descrições das categorias.
    """
    await ctx.info("Listando categorias de medicamentos ANVISA...")

    categorias = client.listar_categorias()

    rows = [(c.codigo, c.descricao) for c in categorias]

    header = f"**Categorias de medicamentos ANVISA** ({len(categorias)} categorias)\n\n"
    return header + markdown_table(["Código", "Descrição"], rows)


async def informacoes_bula(ctx: Context) -> str:
    """Informa as seções padrão de uma bula de medicamento no Brasil.

    Útil para orientar o usuário sobre o que encontrar em uma bula e
    como interpretar as informações. Segue o padrão definido pela ANVISA.

    Returns:
        Lista das seções padrão de uma bula.
    """
    await ctx.info("Consultando estrutura padrão de bulas...")

    secoes_lista = "\n".join(f"{i + 1}. {secao}" for i, secao in enumerate(SECOES_BULA))

    return (
        "**Seções padrão de uma bula de medicamento (ANVISA)**\n\n"
        f"{secoes_lista}\n\n"
        "**Dica:** A bula do paciente tem linguagem simplificada. "
        "A bula do profissional tem informações técnicas detalhadas.\n"
        "Use buscar_medicamento() e consultar_bula() para acessar bulas específicas."
    )


async def buscar_por_categoria(
    ctx: Context,
    categoria: str,
    nome: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca medicamentos por categoria regulatória no Bulário da ANVISA.

    Categorias disponíveis: Novo, Genérico, Similar, Biológico, Específico,
    Fitoterápico, Dinamizado, Radiofármaco.

    Args:
        categoria: Categoria regulatória (ex: "Genérico", "Similar", "Biológico").
        nome: Nome do medicamento para combinar com a categoria (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com medicamentos da categoria informada.
    """
    await ctx.info(f"Buscando medicamentos da categoria '{categoria}'...")

    resultados = await client.buscar_por_categoria(categoria=categoria, nome=nome, pagina=pagina)

    if not resultados:
        cats = ", ".join(CATEGORIAS_MEDICAMENTO.values())
        return (
            f"Nenhum medicamento encontrado na categoria '{categoria}'. "
            f"Categorias disponíveis: {cats}."
        )

    rows = [
        (
            m.nome_produto or "—",
            m.principio_ativo or "—",
            m.razao_social or "—",
            m.categoria_regulatoria or "—",
            m.numero_processo or "—",
        )
        for m in resultados
    ]

    filtro = f" contendo '{nome}'" if nome else ""
    header = (
        f"**Medicamentos — Categoria: {categoria}**{filtro} ({len(resultados)} resultado(s))\n\n"
    )
    return header + markdown_table(
        ["Nome", "Princípio Ativo", "Empresa", "Categoria", "Nº Processo"], rows
    )


async def buscar_genericos(
    ctx: Context,
    nome: str,
    pagina: int = 1,
) -> str:
    """Busca genéricos equivalentes a um medicamento de referência.

    Dado o nome de um medicamento ou princípio ativo, encontra todas as
    versões genéricas registradas na ANVISA. Útil para comparar preços
    e encontrar alternativas mais acessíveis.

    Args:
        nome: Nome do medicamento de referência ou princípio ativo (ex: "losartana").
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com genéricos encontrados.
    """
    await ctx.info(f"Buscando genéricos para '{nome}'...")

    resultados = await client.buscar_generico(nome=nome, pagina=pagina)

    if not resultados:
        return (
            f"Nenhum genérico encontrado para '{nome}'. "
            "Tente buscar pelo princípio ativo exato ou verifique "
            "se o medicamento possui versão genérica registrada."
        )

    rows = [
        (
            m.nome_produto or "—",
            m.principio_ativo or "—",
            m.razao_social or "—",
            m.numero_registro or "—",
        )
        for m in resultados
    ]

    header = f"**Genéricos para '{nome}'** ({len(resultados)} resultado(s))\n\n"
    return header + markdown_table(["Nome", "Princípio Ativo", "Empresa", "Registro"], rows)


async def verificar_registro(
    ctx: Context,
    nome: str,
) -> str:
    """Verifica se um medicamento possui registro válido na ANVISA.

    Busca no Bulário e retorna informações de registro incluindo número,
    data de vencimento e categoria regulatória.

    Args:
        nome: Nome do medicamento a verificar (ex: "dipirona", "cloroquina").

    Returns:
        Status do registro do medicamento na ANVISA.
    """
    await ctx.info(f"Verificando registro de '{nome}' na ANVISA...")

    resultados = await client.buscar_medicamento(nome=nome)

    if not resultados:
        return (
            f"Nenhum registro encontrado para '{nome}' no Bulário ANVISA. "
            "Isso pode significar que o medicamento não está registrado ou "
            "que o nome está diferente do registro oficial."
        )

    lines = [f"**Registro ANVISA para '{nome}'** ({len(resultados)} registro(s))\n"]

    for m in resultados:
        status = "Registro ativo" if m.numero_registro else "Registro não informado"
        lines.append(f"- **{m.nome_produto or '—'}** ({m.categoria_regulatoria or '—'})")
        lines.append(f"  - Empresa: {m.razao_social or '—'}")
        lines.append(f"  - Princípio ativo: {m.principio_ativo or '—'}")
        lines.append(f"  - Registro: {m.numero_registro or '—'}")
        lines.append(f"  - Vencimento: {m.data_vencimento_registro or '—'}")
        lines.append(f"  - Processo: {m.numero_processo or '—'}")
        lines.append(f"  - Status: **{status}**")
        lines.append("")

    return "\n".join(lines)


async def buscar_por_empresa(
    ctx: Context,
    empresa: str,
    pagina: int = 1,
) -> str:
    """Busca medicamentos registrados por uma empresa/laboratório específico.

    Pesquisa no Bulário por nome da empresa (razão social) que detém
    o registro do medicamento na ANVISA.

    Args:
        empresa: Nome da empresa ou laboratório (ex: "EMS", "Medley", "Eurofarma").
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com medicamentos da empresa.
    """
    await ctx.info(f"Buscando medicamentos de '{empresa}'...")

    # The Bulário API uses 'nome' for general search - we search and filter by razao_social
    resultados = await client.buscar_medicamento(nome=empresa, pagina=pagina)

    # Filter results that match the company name
    empresa_lower = empresa.lower()
    filtrados = [
        m for m in resultados if m.razao_social and empresa_lower in m.razao_social.lower()
    ]

    if not filtrados:
        return (
            f"Nenhum medicamento encontrado para a empresa '{empresa}'. "
            "Tente o nome completo da razão social do laboratório."
        )

    rows = [
        (
            m.nome_produto or "—",
            m.principio_ativo or "—",
            m.categoria_regulatoria or "—",
            m.numero_registro or "—",
        )
        for m in filtrados
    ]

    header = f"**Medicamentos de '{empresa}'** ({len(filtrados)} resultado(s))\n\n"
    return header + markdown_table(["Nome", "Princípio Ativo", "Categoria", "Registro"], rows)


async def resumo_regulatorio(ctx: Context, nome: str) -> str:
    """Gera um resumo regulatório completo de um medicamento na ANVISA.

    Consolida informações de registro, bulas disponíveis e categoria
    regulatória em uma visão única.

    Args:
        nome: Nome do medicamento (ex: "dipirona", "losartana").

    Returns:
        Resumo com registro, categoria, bulas e empresa.
    """
    await ctx.info(f"Gerando resumo regulatório para '{nome}'...")

    resultados = await client.buscar_medicamento(nome=nome)

    if not resultados:
        return f"Nenhum medicamento '{nome}' encontrado no Bulário ANVISA."

    lines = [f"**Resumo Regulatório — '{nome}'** ({len(resultados)} registro(s))\n"]

    for m in resultados[:5]:  # Limit to 5 for readability
        lines.append(f"### {m.nome_produto or '—'}")
        lines.append(f"- **Empresa:** {m.razao_social or '—'}")
        lines.append(f"- **Princípio ativo:** {m.principio_ativo or '—'}")
        lines.append(f"- **Categoria:** {m.categoria_regulatoria or '—'}")
        lines.append(f"- **Registro:** {m.numero_registro or '—'}")
        lines.append(f"- **Vencimento:** {m.data_vencimento_registro or '—'}")
        lines.append(f"- **Processo:** {m.numero_processo or '—'}")

        # Try to get bulas
        if m.numero_processo:
            try:
                bulas = await client.consultar_bula(numero_processo=m.numero_processo)
                if bulas:
                    tipos = [b.tipo_bula or "—" for b in bulas]
                    lines.append(f"- **Bulas disponíveis:** {', '.join(tipos)}")
            except Exception:
                lines.append("- **Bulas:** Não foi possível consultar")

        lines.append("")

    if len(resultados) > 5:
        lines.append(f"_... e mais {len(resultados) - 5} registro(s)_")

    return "\n".join(lines)
