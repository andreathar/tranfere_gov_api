"""Tool functions for the INPE feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

import logging

from fastmcp import Context

from mcp_brasil._shared.formatting import format_number_br, markdown_table
from mcp_brasil.exceptions import HttpClientError

from . import client
from .constants import BIOMAS, DEFAULT_LIMIT

logger = logging.getLogger(__name__)

_API_INDISPONIVEL = (
    "A API do INPE (TerraBrasilis/BD Queimadas) está indisponível. "
    "Os endpoints foram descontinuados. Dados de queimadas podem ser obtidos em: "
    "https://data.inpe.br/queimadas/pages/secao_downloads/dados-abertos/"
)


async def buscar_focos_queimadas(
    ctx: Context,
    estado: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    satelite: str | None = None,
    limite: int = DEFAULT_LIMIT,
) -> str:
    """Busca focos de queimadas detectados por satélite no Brasil.

    Dados do BD Queimadas (INPE). Retorna informações sobre incêndios
    detectados incluindo localização, satélite, bioma e risco de fogo.

    Args:
        estado: Sigla do estado com 2 letras (ex: PA, MT, AM). Opcional.
        data_inicio: Data inicial no formato YYYY-MM-DD. Opcional.
        data_fim: Data final no formato YYYY-MM-DD. Opcional.
        satelite: Nome do satélite (ex: AQUA_M-T, NPP-375). Opcional.
        limite: Número máximo de resultados (padrão: 50).

    Returns:
        Tabela com os focos de queimadas encontrados.
    """
    filtros = []
    if estado:
        filtros.append(f"estado={estado.upper()}")
    if data_inicio:
        filtros.append(f"de {data_inicio}")
    if data_fim:
        filtros.append(f"até {data_fim}")
    if satelite:
        filtros.append(f"satélite={satelite}")

    filtro_str = f" ({', '.join(filtros)})" if filtros else ""
    await ctx.info(f"Buscando focos de queimadas{filtro_str}...")

    try:
        focos = await client.buscar_focos(
            estado=estado,
            data_inicio=data_inicio,
            data_fim=data_fim,
            satelite=satelite,
            limite=limite,
        )
    except HttpClientError as exc:
        logger.warning("buscar_focos_queimadas failed: %s", exc)
        return _API_INDISPONIVEL

    if not focos:
        return "Nenhum foco de queimada encontrado para os filtros informados."

    await ctx.info(f"{len(focos)} focos encontrados")

    rows = [
        (
            f.municipio,
            f.estado,
            f.bioma,
            f"{f.latitude:.4f}",
            f"{f.longitude:.4f}",
            f.satelite,
            f.data_hora,
            format_number_br(f.risco_fogo, 2) if f.risco_fogo is not None else "—",
        )
        for f in focos
    ]

    header = f"**Focos de queimadas** ({len(focos)} resultados{filtro_str}):\n\n"
    table = markdown_table(
        ["Município", "UF", "Bioma", "Lat", "Lon", "Satélite", "Data/Hora", "Risco"],
        rows,
    )
    return header + table


async def consultar_desmatamento(
    ctx: Context,
    bioma: str | None = None,
    estado: str | None = None,
    ano: int | None = None,
) -> str:
    """Consulta dados históricos de desmatamento do PRODES/INPE.

    O PRODES monitora o desmatamento por corte raso na Amazônia Legal
    e outros biomas desde 1988. Dados anuais consolidados.

    Biomas disponíveis: amazonia, cerrado, mata_atlantica, caatinga, pampa, pantanal.

    Args:
        bioma: Nome do bioma (ex: amazonia, cerrado). Opcional.
        estado: Sigla do estado com 2 letras (ex: PA, MT). Opcional.
        ano: Ano de referência (ex: 2023). Opcional.

    Returns:
        Tabela com dados de desmatamento.
    """
    bioma_nome = BIOMAS.get(bioma, bioma) if bioma else None

    filtros = []
    if bioma_nome:
        filtros.append(f"bioma={bioma_nome}")
    if estado:
        filtros.append(f"estado={estado.upper()}")
    if ano:
        filtros.append(f"ano={ano}")

    filtro_str = f" ({', '.join(filtros)})" if filtros else ""
    await ctx.info(f"Consultando desmatamento PRODES{filtro_str}...")

    try:
        dados = await client.buscar_dados_prodes(
            bioma=bioma_nome,
            estado=estado,
            ano=ano,
        )
    except HttpClientError as exc:
        logger.warning("consultar_desmatamento failed: %s", exc)
        return _API_INDISPONIVEL

    if not dados:
        return "Nenhum dado de desmatamento encontrado para os filtros informados."

    await ctx.info(f"{len(dados)} registros encontrados")

    rows = [
        (
            str(d.ano),
            d.bioma,
            d.estado,
            d.municipio,
            format_number_br(d.area_km2, 2),
        )
        for d in dados
    ]

    header = f"**Desmatamento PRODES** ({len(dados)} registros{filtro_str}):\n\n"
    table = markdown_table(["Ano", "Bioma", "UF", "Município", "Área (km²)"], rows)
    return header + table


async def alertas_deter(
    ctx: Context,
    bioma: str | None = None,
    estado: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> str:
    """Consulta alertas de desmatamento do sistema DETER/INPE.

    O DETER (Detecção de Desmatamento em Tempo Real) emite alertas
    diários de desmatamento e degradação florestal usando imagens de satélite.

    Biomas disponíveis: amazonia, cerrado, mata_atlantica, caatinga, pampa, pantanal.

    Args:
        bioma: Nome do bioma (ex: amazonia, cerrado). Opcional.
        estado: Sigla do estado com 2 letras (ex: PA, MT). Opcional.
        data_inicio: Data inicial no formato YYYY-MM-DD. Opcional.
        data_fim: Data final no formato YYYY-MM-DD. Opcional.

    Returns:
        Tabela com alertas de desmatamento.
    """
    bioma_nome = BIOMAS.get(bioma, bioma) if bioma else None

    filtros = []
    if bioma_nome:
        filtros.append(f"bioma={bioma_nome}")
    if estado:
        filtros.append(f"estado={estado.upper()}")
    if data_inicio:
        filtros.append(f"de {data_inicio}")
    if data_fim:
        filtros.append(f"até {data_fim}")

    filtro_str = f" ({', '.join(filtros)})" if filtros else ""
    await ctx.info(f"Consultando alertas DETER{filtro_str}...")

    try:
        alertas = await client.buscar_alertas_deter(
            bioma=bioma_nome,
            estado=estado,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
    except HttpClientError as exc:
        logger.warning("alertas_deter failed: %s", exc)
        return _API_INDISPONIVEL

    if not alertas:
        return "Nenhum alerta DETER encontrado para os filtros informados."

    await ctx.info(f"{len(alertas)} alertas encontrados")

    rows = [
        (
            a.data,
            a.municipio,
            a.estado,
            a.bioma,
            a.classe,
            format_number_br(a.area_km2, 2),
            a.satelite,
        )
        for a in alertas
    ]

    header = f"**Alertas DETER** ({len(alertas)} alertas{filtro_str}):\n\n"
    table = markdown_table(
        ["Data", "Município", "UF", "Bioma", "Classe", "Área (km²)", "Satélite"],
        rows,
    )
    return header + table


async def dados_satelite(ctx: Context) -> str:
    """Lista os satélites disponíveis para monitoramento ambiental do INPE.

    Retorna os satélites usados pelo INPE para detecção de queimadas
    e desmatamento, incluindo satélites da NASA, NOAA e INPE/CBERS.

    Returns:
        Tabela com os satélites disponíveis.
    """
    await ctx.info("Listando satélites disponíveis...")

    try:
        satelites = await client.listar_satelites()
    except HttpClientError as exc:
        logger.warning("dados_satelite failed: %s", exc)
        return _API_INDISPONIVEL

    if not satelites:
        return "Nenhum satélite disponível no momento."

    await ctx.info(f"{len(satelites)} satélites encontrados")

    rows = [(s.nome, s.descricao) for s in satelites]
    header = f"**Satélites de monitoramento** ({len(satelites)} disponíveis):\n\n"
    table = markdown_table(["Satélite", "Descrição"], rows)
    return header + table
