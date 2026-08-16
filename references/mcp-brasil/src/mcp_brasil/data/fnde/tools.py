"""Tool functions for FNDE feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_brl, format_number_br, markdown_table

from . import client


async def consultar_fundeb_matriculas(
    ctx: Context,
    ano: int | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    limite: int = 50,
) -> str:
    """Consulta matrículas ponderadas do FUNDEB por ano, UF e município.

    O FUNDEB (Fundo de Manutenção e Desenvolvimento da Educação Básica)
    distribui recursos com base nas matrículas. Esta tool retorna dados
    de matrículas por tipo de ensino, rede, carga horária e localização.

    Dados disponíveis: 2017-2018.

    Args:
        ano: Ano do Censo Escolar (ex: 2017, 2018). Se omitido, retorna todos.
        uf: Sigla da UF com 2 letras (ex: SP, RJ, MG). Se omitido, todas.
        municipio: Nome parcial do município para busca. Se omitido, todos.
        limite: Máximo de registros a retornar (padrão: 50, máximo: 1000).

    Returns:
        Tabela com matrículas FUNDEB por município, tipo de ensino e localização.
    """
    await ctx.info("Consultando matrículas FUNDEB...")
    resultados = await client.consultar_fundeb_matriculas(
        ano=ano, uf=uf, municipio=municipio, top=limite
    )

    if not resultados:
        return "Nenhuma matrícula FUNDEB encontrada para os filtros informados."

    await ctx.info(f"{len(resultados)} registros encontrados")

    rows = [
        (
            r.ano_censo,
            r.uf,
            r.municipio,
            r.tipo_ensino,
            r.tipo_turma,
            r.localizacao,
            format_number_br(r.quantidade, 0),
        )
        for r in resultados
    ]
    headers = ["Ano", "UF", "Município", "Ensino", "Turma", "Local", "Matrículas"]
    return markdown_table(headers, rows)


async def consultar_pnae_alunos(
    ctx: Context,
    ano: str | None = None,
    estado: str | None = None,
    municipio: str | None = None,
    limite: int = 50,
) -> str:
    """Consulta alunos atendidos pelo PNAE (Programa Nacional de Alimentação Escolar).

    O PNAE garante alimentação escolar a todos os alunos da educação básica
    pública. Esta tool retorna a quantidade de alunos atendidos por estado,
    município e etapa de ensino.

    Dados disponíveis: 1999 a 2022.

    Args:
        ano: Ano de referência como texto (ex: "2022", "2020"). Se omitido, todos.
        estado: Sigla da UF com 2 letras (ex: SP, BA). Se omitido, todos.
        municipio: Nome parcial do município para busca. Se omitido, todos.
        limite: Máximo de registros a retornar (padrão: 50, máximo: 1000).

    Returns:
        Tabela com alunos atendidos pelo PNAE por município e etapa de ensino.
    """
    await ctx.info("Consultando alunos PNAE...")
    resultados = await client.consultar_pnae_alunos(
        ano=ano, estado=estado, municipio=municipio, top=limite
    )

    if not resultados:
        return "Nenhum registro PNAE encontrado para os filtros informados."

    await ctx.info(f"{len(resultados)} registros encontrados")

    rows = [
        (
            r.ano,
            r.estado,
            r.municipio,
            r.esfera_governo,
            r.etapa_ensino,
            format_number_br(r.quantidade, 0),
        )
        for r in resultados
    ]
    headers = ["Ano", "UF", "Município", "Esfera", "Etapa", "Alunos"]
    return markdown_table(headers, rows)


async def consultar_pnld_livros(
    ctx: Context,
    ano: str | None = None,
    editora: str | None = None,
    titulo: str | None = None,
    limite: int = 50,
) -> str:
    """Consulta livros didáticos distribuídos pelo PNLD.

    O PNLD (Programa Nacional do Livro e do Material Didático) distribui
    livros didáticos e materiais pedagógicos para escolas públicas.
    Retorna dados de distribuição por editora, título, quantidade e custo.

    Args:
        ano: Ano do programa (ex: "2019", "2020"). Se omitido, todos.
        editora: Nome parcial da editora. Se omitido, todas.
        titulo: Texto parcial do título do livro. Se omitido, todos.
        limite: Máximo de registros a retornar (padrão: 50, máximo: 1000).

    Returns:
        Tabela com livros distribuídos, quantidades e custos.
    """
    await ctx.info("Consultando livros PNLD...")
    resultados = await client.consultar_pnld_livros(
        ano=ano, editora=editora, titulo=titulo, top=limite
    )

    if not resultados:
        return "Nenhum livro PNLD encontrado para os filtros informados."

    await ctx.info(f"{len(resultados)} registros encontrados")

    rows = [
        (
            r.ano,
            r.editora[:30],
            r.titulo[:40],
            format_number_br(r.quantidade, 0),
            format_brl(r.custo),
        )
        for r in resultados
    ]
    headers = ["Ano", "Editora", "Título", "Qtd", "Custo"]
    return markdown_table(headers, rows)


async def consultar_pnate_transporte(
    ctx: Context,
    uf: str | None = None,
    municipio: str | None = None,
    limite: int = 50,
) -> str:
    """Consulta alunos atendidos pelo PNATE (transporte escolar).

    O PNATE (Programa Nacional de Apoio ao Transporte do Escolar) repassa
    recursos para transporte de alunos da educação básica rural.
    Retorna a quantidade de alunos por UF, município e entidade executora.

    Args:
        uf: Sigla da UF com 2 letras (ex: SP, AM). Se omitido, todas.
        municipio: Nome parcial do município para busca. Se omitido, todos.
        limite: Máximo de registros a retornar (padrão: 50, máximo: 1000).

    Returns:
        Tabela com alunos atendidos pelo PNATE por município.
    """
    await ctx.info("Consultando transporte escolar PNATE...")
    resultados = await client.consultar_pnate_transporte(uf=uf, municipio=municipio, top=limite)

    if not resultados:
        return "Nenhum registro PNATE encontrado para os filtros informados."

    await ctx.info(f"{len(resultados)} registros encontrados")

    rows = [
        (
            r.uf,
            r.municipio,
            r.entidade[:40],
            format_number_br(r.quantidade, 0),
        )
        for r in resultados
    ]
    headers = ["UF", "Município", "Entidade", "Alunos"]
    return markdown_table(headers, rows)
