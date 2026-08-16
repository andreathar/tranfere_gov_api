"""Tool functions for the Bacen feature.

Ported from bcb-br-mcp/src/tools.ts (8 handler functions).
Covers: series data, metadata, catalog, indicators, variation, comparison.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context

from mcp_brasil._shared.formatting import format_number_br, markdown_table
from mcp_brasil.exceptions import HttpClientError

from . import client
from .catalog import (
    buscar_serie_por_codigo,
    buscar_series_por_termo,
    listar_por_categoria,
)
from .constants import CATEGORIAS


def _calculate_variation(initial: float, final: float) -> float:
    """Calculate percentage variation: ((final - initial) / |initial|) * 100."""
    if initial == 0:
        return 0.0
    return ((final - initial) / abs(initial)) * 100


async def consultar_serie(
    codigo: int,
    ctx: Context,
    data_inicial: str | None = None,
    data_final: str | None = None,
) -> str:
    """Consulta valores de uma série temporal do Banco Central por código.

    Retorna dados históricos com data e valor de qualquer série do SGS
    (Sistema Gerenciador de Séries Temporais). O catálogo tem 190+ séries
    populares. Use buscar_serie() para encontrar códigos.

    Args:
        codigo: Código da série no SGS/BCB (ex: 433 para IPCA, 432 para Selic).
        data_inicial: Data inicial yyyy-MM-dd ou dd/MM/yyyy (opcional).
        data_final: Data final yyyy-MM-dd ou dd/MM/yyyy (opcional).

    Returns:
        Tabela com dados da série.
    """
    await ctx.info(f"Consultando série {codigo}...")
    valores = await client.buscar_valores(codigo, data_inicial, data_final)

    if not valores:
        return f"Nenhum dado encontrado para a série {codigo} no período solicitado."

    serie_info = buscar_serie_por_codigo(codigo)
    nome = serie_info.nome if serie_info else f"Série {codigo}"
    categoria = serie_info.categoria if serie_info else "Desconhecida"

    await ctx.info(f"{len(valores)} registros encontrados para {nome}")

    header = f"**{nome}** (código {codigo} | {categoria})\n"
    header += f"Total: {len(valores)} registros | "
    header += f"Período: {valores[0].data} a {valores[-1].data}\n\n"

    rows = [(v.data, format_number_br(v.valor, 4)) for v in valores]
    return header + markdown_table(["Data", "Valor"], rows)


async def ultimos_valores(codigo: int, ctx: Context, quantidade: int = 10) -> str:
    """Obtém os últimos N valores de uma série temporal do BCB.

    Útil para consultar os dados mais recentes de qualquer indicador.
    Padrão: últimos 10 valores.

    Args:
        codigo: Código da série no SGS/BCB (ex: 433, 432, 3698).
        quantidade: Quantidade de valores (1 a 1000, padrão 10).

    Returns:
        Tabela com os últimos valores da série.
    """
    await ctx.info(f"Buscando últimos {quantidade} valores da série {codigo}...")
    valores = await client.buscar_ultimos(codigo, quantidade)

    if not valores:
        return f"Nenhum dado encontrado para a série {codigo}."

    serie_info = buscar_serie_por_codigo(codigo)
    nome = serie_info.nome if serie_info else f"Série {codigo}"

    header = f"**{nome}** (código {codigo}) — últimos {len(valores)} valores\n\n"

    rows = [(v.data, format_number_br(v.valor, 4)) for v in valores]
    return header + markdown_table(["Data", "Valor"], rows)


async def metadados_serie(codigo: int, ctx: Context) -> str:
    """Obtém metadados/informações de uma série do Banco Central.

    Retorna nome, periodicidade, unidade, fonte e outras informações.
    Tenta o endpoint de metadados e, se indisponível, usa o catálogo interno.

    Args:
        codigo: Código da série no SGS/BCB.

    Returns:
        Informações da série.
    """
    await ctx.info(f"Buscando metadados da série {codigo}...")
    try:
        meta = await client.buscar_metadados(codigo)
        serie_info = buscar_serie_por_codigo(codigo)
        categoria = serie_info.categoria if serie_info else "Não categorizada"

        lines = [
            f"**{meta.nome}** (código {meta.codigo})",
            f"- Unidade: {meta.unidade}",
            f"- Periodicidade: {meta.periodicidade}",
            f"- Fonte: {meta.fonte}",
            f"- Categoria: {categoria}",
            f"- Especial: {'Sim' if meta.especial else 'Não'}",
        ]
        return "\n".join(lines)
    except HttpClientError:
        await ctx.warning(f"Metadados da API indisponíveis para série {codigo}, usando catálogo")
        serie_info = buscar_serie_por_codigo(codigo)
        if serie_info:
            lines = [
                f"**{serie_info.nome}** (código {serie_info.codigo})",
                f"- Periodicidade: {serie_info.periodicidade}",
                f"- Categoria: {serie_info.categoria}",
                "- Fonte: Banco Central do Brasil",
                "- _(metadados obtidos do catálogo interno)_",
            ]
            return "\n".join(lines)
        return f"Série {codigo} não encontrada no catálogo e metadados indisponíveis."


async def series_populares(ctx: Context, categoria: str | None = None) -> str:
    """Lista as 190+ séries temporais do BCB disponíveis no catálogo.

    Inclui séries de juros, inflação, câmbio, PIB, emprego, crédito,
    fiscal, setor externo, agregados monetários, poupança e expectativas.
    Use o código da série com consultar_serie() ou ultimos_valores().

    Args:
        categoria: Filtrar por categoria (ex: Juros, Inflação, Câmbio). Opcional.

    Returns:
        Lista de séries agrupadas por categoria.
    """
    await ctx.info("Listando séries populares do catálogo BCB...")
    grupos = listar_por_categoria(categoria)

    if not grupos:
        return f"Nenhuma série encontrada para a categoria '{categoria}'."

    total = sum(len(ss) for ss in grupos.values())
    lines = [f"**Catálogo BCB** — {total} séries em {len(grupos)} categorias\n"]

    for cat in CATEGORIAS:
        if cat not in grupos:
            continue
        series = grupos[cat]
        lines.append(f"\n### {cat} ({len(series)} séries)")
        for s in series:
            lines.append(f"- **{s.codigo}** — {s.nome} ({s.periodicidade})")

    lines.append(
        "\n_Use consultar_serie(codigo) ou ultimos_valores(codigo) para acessar os dados._"
    )
    return "\n".join(lines)


async def buscar_serie(termo: str, ctx: Context) -> str:
    """Busca séries no catálogo do BCB por nome ou descrição.

    Busca por texto sem acentos (ex: 'inflacao' encontra 'Inflação').
    Retorna séries com código, nome, categoria e periodicidade.

    Args:
        termo: Termo de busca (mínimo 2 caracteres).

    Returns:
        Séries encontradas ou sugestão de termos.
    """
    await ctx.info(f"Buscando séries com termo '{termo}'...")
    encontradas = buscar_series_por_termo(termo)

    if not encontradas:
        return (
            f"Nenhuma série encontrada para '{termo}'.\n\n"
            "Sugestões de busca: selic, ipca, dolar, cambio, pib, inflacao, "
            "credito, emprego, divida, reservas\n\n"
            "Para séries fora do catálogo, consulte: https://www3.bcb.gov.br/sgspub/"
        )

    header = f"**{len(encontradas)} séries encontradas para '{termo}':**\n\n"
    rows = [(str(s.codigo), s.nome, s.categoria, s.periodicidade) for s in encontradas]
    return header + markdown_table(["Código", "Nome", "Categoria", "Periodicidade"], rows)


async def indicadores_atuais(ctx: Context) -> str:
    """Obtém os valores mais recentes dos principais indicadores econômicos.

    Consulta em paralelo: Selic (a.a.), IPCA mensal, IPCA 12 meses,
    Dólar PTAX (venda) e IBC-Br. Útil para um panorama rápido da economia.

    Returns:
        Tabela com indicadores atuais.
    """
    await ctx.info("Buscando indicadores econômicos atuais (5 séries em paralelo)...")
    resultados = await client.buscar_indicadores_atuais()
    await ctx.info("Indicadores recebidos")

    rows: list[tuple[str, ...]] = []
    for r in resultados:
        if "erro" in r:
            rows.append((r["indicador"], "—", r.get("erro", "")))
        else:
            rows.append(
                (
                    r["indicador"],
                    format_number_br(r["valor"], 4),
                    r["data"],
                )
            )

    return "**Indicadores Econômicos Atuais**\n\n" + markdown_table(
        ["Indicador", "Valor", "Data"], rows
    )


async def calcular_variacao(
    codigo: int,
    ctx: Context,
    data_inicial: str | None = None,
    data_final: str | None = None,
    periodos: int | None = None,
) -> str:
    """Calcula a variação percentual de uma série do BCB entre datas ou períodos.

    Mostra variação absoluta e percentual, além de estatísticas
    (máximo, mínimo, média, amplitude). Útil para análise de tendências.

    Args:
        codigo: Código da série no SGS/BCB.
        data_inicial: Data inicial (yyyy-MM-dd ou dd/MM/yyyy).
        data_final: Data final (yyyy-MM-dd ou dd/MM/yyyy).
        periodos: Alternativa: usar os últimos N períodos (ignora datas).

    Returns:
        Análise de variação da série.
    """
    await ctx.info(f"Calculando variação da série {codigo}...")
    if periodos and periodos > 1:
        valores = await client.buscar_ultimos(codigo, periodos)
    else:
        valores = await client.buscar_valores(codigo, data_inicial, data_final)

    if len(valores) < 2:
        return "Dados insuficientes para calcular variação. São necessários pelo menos 2 valores."

    serie_info = buscar_serie_por_codigo(codigo)
    nome = serie_info.nome if serie_info else f"Série {codigo}"

    nums = [v.valor for v in valores]
    inicial = nums[0]
    final = nums[-1]
    variacao = _calculate_variation(inicial, final)
    diff = final - inicial
    maximo = max(nums)
    minimo = min(nums)
    media = sum(nums) / len(nums)

    sinal = "+" if variacao >= 0 else ""

    lines = [
        f"**{nome}** (código {codigo})",
        f"\nPeríodo: {valores[0].data} → {valores[-1].data} ({len(valores)} registros)",
        "\n**Variação:**",
        f"- Valor inicial: {format_number_br(inicial, 4)}",
        f"- Valor final: {format_number_br(final, 4)}",
        f"- Diferença absoluta: {format_number_br(diff, 4)}",
        f"- Variação percentual: {sinal}{format_number_br(variacao, 2)}%",
        "\n**Estatísticas:**",
        f"- Máximo: {format_number_br(maximo, 4)}",
        f"- Mínimo: {format_number_br(minimo, 4)}",
        f"- Média: {format_number_br(media, 4)}",
        f"- Amplitude: {format_number_br(maximo - minimo, 4)}",
    ]
    return "\n".join(lines)


async def comparar_series(
    codigos: list[int],
    data_inicial: str,
    data_final: str,
    ctx: Context,
) -> str:
    """Compara 2 a 5 séries temporais do BCB no mesmo período.

    Calcula variação, máximo, mínimo e média de cada série,
    e ordena por variação percentual. Útil para análise comparativa.

    Args:
        codigos: Lista de 2 a 5 códigos de séries para comparar.
        data_inicial: Data inicial (yyyy-MM-dd ou dd/MM/yyyy).
        data_final: Data final (yyyy-MM-dd ou dd/MM/yyyy).

    Returns:
        Ranking comparativo das séries.
    """
    if len(codigos) < 2 or len(codigos) > 5:
        return "Informe entre 2 e 5 códigos de séries para comparar."

    await ctx.info(f"Comparando {len(codigos)} séries em paralelo...")

    async def _fetch_and_analyze(codigo: int) -> dict[str, Any]:
        serie_info = buscar_serie_por_codigo(codigo)
        nome = serie_info.nome if serie_info else f"Série {codigo}"
        try:
            valores = await client.buscar_valores(codigo, data_inicial, data_final)
            if not valores:
                return {"codigo": codigo, "nome": nome, "erro": "Sem dados no período"}

            nums = [v.valor for v in valores]
            variacao = _calculate_variation(nums[0], nums[-1])
            return {
                "codigo": codigo,
                "nome": nome,
                "registros": len(valores),
                "inicial": nums[0],
                "final": nums[-1],
                "variacao": variacao,
                "maximo": max(nums),
                "minimo": min(nums),
                "media": sum(nums) / len(nums),
            }
        except Exception as exc:
            return {"codigo": codigo, "nome": nome, "erro": str(exc)}

    resultados = list(await asyncio.gather(*[_fetch_and_analyze(c) for c in codigos]))

    com_dados = [r for r in resultados if "erro" not in r]
    com_erro = [r for r in resultados if "erro" in r]

    com_dados.sort(key=lambda r: r["variacao"], reverse=True)

    lines = [
        f"**Comparação de {len(codigos)} séries**",
        f"Período: {data_inicial} → {data_final}\n",
    ]

    if com_dados:
        rows = []
        for i, r in enumerate(com_dados, 1):
            sinal = "+" if r["variacao"] >= 0 else ""
            rows.append(
                (
                    str(i),
                    r["nome"],
                    str(r["codigo"]),
                    format_number_br(r["inicial"], 2),
                    format_number_br(r["final"], 2),
                    f"{sinal}{format_number_br(r['variacao'], 2)}%",
                )
            )
        lines.append(
            markdown_table(
                ["#", "Série", "Código", "Inicial", "Final", "Variação"],
                rows,
            )
        )

    if com_erro:
        lines.append(f"\n**Séries com erro ({len(com_erro)}):**")
        for r in com_erro:
            lines.append(f"- {r['nome']} ({r['codigo']}): {r['erro']}")

    return "\n".join(lines)


async def expectativas_focus(
    ctx: Context,
    indicador: str = "IPCA",
    data_inicio: str | None = None,
    limite: int = 10,
) -> str:
    """Consulta expectativas do mercado do Boletim Focus do BCB.

    O Boletim Focus é publicado semanalmente pelo Banco Central com as
    projeções do mercado para os principais indicadores econômicos.
    Indicadores disponíveis: IPCA, IGP-M, Selic, Câmbio, PIB.

    Args:
        indicador: Indicador econômico (IPCA, IGP-M, Selic, Câmbio, PIB). Padrão: IPCA.
        data_inicio: Data mínima das expectativas (YYYY-MM-DD). Opcional.
        limite: Número máximo de registros (padrão 10).

    Returns:
        Tabela com expectativas do mercado.
    """
    from .constants import FOCUS_INDICADORES

    if indicador not in FOCUS_INDICADORES:
        return (
            f"Indicador '{indicador}' não disponível. "
            f"Use um dos seguintes: {', '.join(FOCUS_INDICADORES)}"
        )

    await ctx.info(f"Buscando expectativas Focus para {indicador}...")
    expectativas = await client.buscar_expectativas_focus(
        indicador=indicador,
        data_inicio=data_inicio,
        limite=limite,
    )

    if not expectativas:
        return f"Nenhuma expectativa encontrada para {indicador}."

    header = f"**Boletim Focus — {indicador}**\n"
    header += f"Últimas {len(expectativas)} expectativas\n\n"

    rows = [
        (
            e.data,
            e.data_referencia,
            format_number_br(e.mediana, 2) if e.mediana is not None else "N/A",
            format_number_br(e.media, 2) if e.media is not None else "N/A",
            format_number_br(e.minimo, 2) if e.minimo is not None else "N/A",
            format_number_br(e.maximo, 2) if e.maximo is not None else "N/A",
            str(e.base_calculo or "N/A"),
        )
        for e in expectativas
    ]
    return header + markdown_table(
        ["Data", "Ref.", "Mediana", "Média", "Mín.", "Máx.", "Base"],
        rows,
    )
