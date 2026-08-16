"""Tool functions for INEP feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption

Note: The INEP does NOT have a REST API. These tools generate structured
download URLs and provide metadata about available datasets. For queryable
education data, use the FNDE tools (fnde_consultar_*).
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table, truncate_list

from . import client
from .constants import IDEB_ANOS, IDEB_ETAPAS, IDEB_NIVEIS


async def consultar_ideb(
    ctx: Context,
    ano: int | None = None,
    etapa: str | None = None,
    nivel: str | None = None,
) -> str:
    """Gera URLs para download dos resultados do IDEB.

    O IDEB (Índice de Desenvolvimento da Educação Básica) é o principal
    indicador de qualidade da educação básica brasileira (escala 0-10).
    Combina desempenho no SAEB com taxas de aprovação.

    O INEP não possui API REST. Esta tool gera as URLs oficiais para
    download dos arquivos XLSX com os resultados.

    Args:
        ano: Ano IDEB (bienal: 2005, 2007, ..., 2023). Se omitido, último disponível (2023).
        etapa: Etapa de ensino. Opções: "anos_iniciais" (1º-5º ano),
            "anos_finais" (6º-9º ano), "ensino_medio". Se omitido, todas.
        nivel: Nível de agregação. Opções: "brasil" (nacional),
            "regioes_ufs" (por estado), "municipios", "escolas".
            Se omitido, retorna brasil e regioes_ufs.

    Returns:
        Lista de URLs para download dos arquivos IDEB em XLSX.
    """
    if ano is None:
        ano = IDEB_ANOS[-1]  # último ano disponível

    nivel_filtro = "regioes_ufs" if nivel is None else nivel

    await ctx.info(f"Gerando URLs IDEB {ano}...")
    urls = await client.gerar_urls_ideb(ano=ano, etapa=etapa, nivel=nivel_filtro)

    if not urls:
        niveis_validos = ", ".join(IDEB_NIVEIS.keys())
        etapas_validas = ", ".join(IDEB_ETAPAS.keys())
        anos_validos = ", ".join(str(a) for a in IDEB_ANOS)
        return (
            f"Nenhum resultado encontrado.\n\n"
            f"**Níveis válidos:** {niveis_validos}\n"
            f"**Etapas válidas:** {etapas_validas}\n"
            f"**Anos válidos:** {anos_validos}"
        )

    await ctx.info(f"{len(urls)} URLs geradas")

    rows = [
        (
            u.ano,
            IDEB_NIVEIS.get(u.nivel, u.nivel),
            IDEB_ETAPAS.get(u.etapa, "Todas") if u.etapa else "Todas",
            u.tamanho_estimado,
            u.url,
        )
        for u in urls
    ]
    headers = ["Ano", "Nível", "Etapa", "Tamanho", "URL Download"]
    return markdown_table(headers, rows)


async def listar_microdados_inep(ctx: Context) -> str:
    """Lista todos os datasets de microdados do INEP disponíveis para download.

    O INEP publica microdados completos de todas as avaliações e censos
    educacionais em formato CSV comprimido (ZIP). Inclui: Censo Escolar,
    ENEM, SAEB, Censo da Educação Superior, ENADE e ENCCEJA.

    Cada dataset tem múltiplos anos disponíveis. Use a tool
    gerar_url_download_inep para obter a URL de um ano específico.

    Returns:
        Catálogo de microdados INEP com nome, descrição, frequência
        e anos disponíveis.
    """
    await ctx.info("Listando microdados INEP...")
    datasets = await client.listar_microdados()

    items = []
    for ds in datasets:
        anos = ds.anos_disponiveis
        primeiro = min(anos) if anos else "?"
        ultimo = max(anos) if anos else "?"
        items.append(
            f"**{ds.nome}** (`{ds.codigo}`)\n"
            f"  {ds.descricao}\n"
            f"  Frequência: {ds.frequencia} | Anos: {primeiro}-{ultimo} "
            f"({len(anos)} edições)"
        )

    await ctx.info(f"{len(datasets)} datasets encontrados")
    header = f"Microdados INEP — {len(datasets)} datasets disponíveis:\n\n"
    return header + "\n\n".join(items)


async def gerar_url_download_inep(
    ctx: Context,
    dataset: str,
    ano: int,
) -> str:
    """Gera a URL de download para um dataset específico de microdados INEP.

    Use a tool listar_microdados_inep para ver os datasets e anos disponíveis.

    Args:
        dataset: Código do dataset. Opções: "censo_escolar", "enem", "saeb",
            "censo_superior", "enade", "encceja".
        ano: Ano dos microdados (ex: 2023).

    Returns:
        URL direta para download do arquivo ZIP dos microdados.
    """
    await ctx.info(f"Gerando URL para {dataset} {ano}...")
    url = await client.gerar_url_microdados(dataset, ano)

    if url is None:
        datasets = await client.listar_microdados()
        codigos = [ds.codigo for ds in datasets]
        return (
            f"Dataset '{dataset}' ou ano {ano} não encontrado.\n\n"
            f"**Datasets válidos:** {', '.join(codigos)}\n"
            f"Use listar_microdados_inep para ver os anos disponíveis."
        )

    return (
        f"**Download:** {dataset} — {ano}\n\n"
        f"URL: {url}\n\n"
        f"Formato: CSV comprimido (ZIP). Arquivos grandes (100 MB a 5 GB).\n"
        f"Encoding: Latin-1 ou UTF-8. Separador: `|` ou `;`."
    )


async def listar_indicadores_educacionais(ctx: Context) -> str:
    """Lista os indicadores educacionais calculados pelo INEP.

    O INEP calcula anualmente 7 indicadores educacionais derivados do
    Censo Escolar, com granularidade por escola, município e UF.
    São a base para análises de qualidade da educação básica.

    Returns:
        Lista de indicadores com nome e descrição do que cada um mede.
    """
    await ctx.info("Listando indicadores educacionais...")
    indicadores = await client.listar_indicadores()

    items = [f"**{ind.nome}** (`{ind.codigo}`)\n  {ind.descricao}" for ind in indicadores]

    await ctx.info(f"{len(indicadores)} indicadores listados")
    header = f"Indicadores Educacionais INEP — {len(indicadores)} indicadores:\n\n"
    return header + truncate_list(items, max_items=20)
