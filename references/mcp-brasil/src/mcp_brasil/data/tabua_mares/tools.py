"""Tool functions for the Tabua Mares feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import markdown_table

from . import client
from .constants import ESTADOS_COSTEIROS


async def listar_estados_costeiros(ctx: Context) -> str:
    """Lista os 17 estados costeiros do Brasil com portos disponíveis para consulta de marés.

    Use esta tool para descobrir quais estados têm dados de maré disponíveis.

    Returns:
        Tabela com sigla e nome de cada estado costeiro.
    """
    await ctx.info("Buscando estados costeiros...")
    estados = await client.listar_estados()
    rows = [(sigla.upper(), ESTADOS_COSTEIROS.get(sigla, sigla)) for sigla in estados]
    return markdown_table(["Sigla", "Estado"], rows)


async def listar_portos(estado: str, ctx: Context) -> str:
    """Lista todos os portos disponíveis em um estado costeiro.

    Use esta tool para descobrir os portos de um estado antes de consultar a tábua de marés.

    Args:
        estado: Sigla do estado em minúsculo (ex: pb, rj, sp, sc).

    Returns:
        Tabela com ID, nome do porto e instituição coletora de dados.
    """
    await ctx.info(f"Buscando portos de {estado.upper()}...")
    portos = await client.listar_portos_estado(estado)
    rows = [(str(p.id), p.harbor_name, str(p.year), p.data_collection_institution) for p in portos]
    return markdown_table(["ID", "Porto", "Ano", "Instituição"], rows)


async def buscar_portos(ids: list[str], ctx: Context) -> str:
    """Busca informações detalhadas de portos específicos pelo ID.

    Retorna dados como localização geográfica, fuso horário e nível médio do mar.

    Args:
        ids: Lista de IDs de portos (ex: ['pb01', 'al01', 'rj02']).

    Returns:
        Detalhes de cada porto encontrado.
    """
    await ctx.info(f"Buscando detalhes dos portos: {', '.join(ids)}...")
    portos = await client.buscar_portos(ids)
    lines: list[str] = []
    for p in portos:
        lines.append(f"## {p.harbor_name}")
        lines.append(f"- **Estado:** {p.state.upper()}")
        lines.append(f"- **Fuso horário:** {p.timezone}")
        lines.append(f"- **Carta náutica:** {p.card}")
        if p.mean_level is not None:
            lines.append(f"- **Nível médio:** {p.mean_level:.2f} m")
        if p.geo_location:
            geo = p.geo_location[0]
            lines.append(f"- **Coordenadas:** {geo.decimal_lat}, {geo.decimal_lng}")
        lines.append("")
    return "\n".join(lines) if lines else "Nenhum porto encontrado."


async def consultar_tabua_mare(
    porto_id: str,
    mes: int,
    dias: str,
    ctx: Context,
) -> str:
    """Consulta a tábua de marés de um porto para dias específicos de um mês.

    Retorna os horários e níveis de maré alta e baixa para cada dia solicitado.
    Use listar_portos primeiro para descobrir o ID do porto desejado.

    Args:
        porto_id: ID do porto (ex: 'pb01', 'al01').
        mes: Mês desejado (1-12).
        dias: Dias no formato '1,2,3' ou '1,5-13' (dias específicos e/ou intervalos).

    Returns:
        Tábua de marés formatada com horários e níveis.
    """
    await ctx.info(f"Consultando tábua de marés do porto {porto_id}, mês {mes}...")
    tabuas = await client.consultar_tabua_mare(porto_id, mes, dias)
    if not tabuas:
        return "Nenhum dado de maré encontrado para os parâmetros informados."

    lines: list[str] = []
    for tabua in tabuas:
        lines.append(f"## {tabua.harbor_name} ({tabua.state.upper()})")
        lines.append(
            f"Ano: {tabua.year} | Fuso: {tabua.timezone} | Nível médio: {tabua.mean_level:.2f} m"
        )
        lines.append("")
        for mes_data in tabua.months:
            lines.append(f"### {mes_data.month_name}")
            for dia in mes_data.days:
                lines.append(f"\n**{dia.weekday_name.capitalize()}, dia {dia.day}:**")
                rows = [(h.hour, f"{h.level:.2f} m") for h in dia.hours]
                lines.append(markdown_table(["Horário", "Nível"], rows))
    return "\n".join(lines)


async def porto_mais_proximo(
    estado: str,
    lat: float,
    lng: float,
    ctx: Context,
) -> str:
    """Encontra o porto mais próximo de uma coordenada dentro de um estado.

    Use esta tool quando souber o estado e as coordenadas do usuário.

    Args:
        estado: Sigla do estado (ex: pb, rj, sp).
        lat: Latitude (ex: -7.11509).
        lng: Longitude (ex: -34.864).

    Returns:
        Dados do porto mais próximo.
    """
    await ctx.info(f"Buscando porto mais próximo em {estado.upper()}...")
    portos = await client.porto_mais_proximo(estado, lat, lng)
    if not portos:
        return "Nenhum porto encontrado próximo às coordenadas informadas."
    p = portos[0]
    lines = [
        f"## {p.harbor_name}",
        f"- **Estado:** {p.state.upper()}",
        f"- **Fuso horário:** {p.timezone}",
        f"- **Carta náutica:** {p.card}",
    ]
    if p.mean_level is not None:
        lines.append(f"- **Nível médio:** {p.mean_level:.2f} m")
    if p.geo_location:
        geo = p.geo_location[0]
        lines.append(f"- **Coordenadas:** {geo.decimal_lat}, {geo.decimal_lng}")
    return "\n".join(lines)


async def porto_mais_proximo_geral(lat: float, lng: float, ctx: Context) -> str:
    """Encontra o porto mais próximo de uma coordenada, independente do estado.

    Use esta tool quando não souber o estado do usuário, apenas as coordenadas.

    Args:
        lat: Latitude (ex: -7.11509).
        lng: Longitude (ex: -34.864).

    Returns:
        Dados do porto mais próximo.
    """
    await ctx.info("Buscando porto mais próximo (qualquer estado)...")
    portos = await client.porto_mais_proximo_geral(lat, lng)
    if not portos:
        return "Nenhum porto encontrado próximo às coordenadas informadas."
    p = portos[0]
    lines = [
        f"## {p.harbor_name}",
        f"- **Estado:** {p.state.upper()}",
        f"- **Fuso horário:** {p.timezone}",
        f"- **Carta náutica:** {p.card}",
    ]
    if p.mean_level is not None:
        lines.append(f"- **Nível médio:** {p.mean_level:.2f} m")
    if p.geo_location:
        geo = p.geo_location[0]
        lines.append(f"- **Coordenadas:** {geo.decimal_lat}, {geo.decimal_lng}")
    return "\n".join(lines)


async def tabua_mare_por_geolocalizacao(
    lat: float,
    lng: float,
    estado: str,
    mes: int,
    dias: str,
    ctx: Context,
) -> str:
    """Obtém a tábua de marés do porto mais próximo usando coordenadas geográficas.

    Combina a busca do porto mais próximo com a consulta da tábua de marés
    em uma única chamada. Ideal quando o usuário informa sua localização.

    Args:
        lat: Latitude (ex: -7.11509).
        lng: Longitude (ex: -34.864).
        estado: Sigla do estado (ex: pb, rj, sp).
        mes: Mês desejado (1-12).
        dias: Dias no formato '1,2,3' ou '1,5-13' (dias específicos e/ou intervalos).

    Returns:
        Tábua de marés do porto mais próximo.
    """
    await ctx.info(f"Consultando marés por geolocalização ({lat}, {lng})...")
    tabuas = await client.tabua_mare_por_geolocalizacao(lat, lng, estado, mes, dias)
    if not tabuas:
        return "Nenhum dado de maré encontrado para as coordenadas informadas."

    lines: list[str] = []
    for tabua in tabuas:
        lines.append(f"## {tabua.harbor_name} ({tabua.state.upper()})")
        lines.append(
            f"Ano: {tabua.year} | Fuso: {tabua.timezone} | Nível médio: {tabua.mean_level:.2f} m"
        )
        lines.append("")
        for mes_data in tabua.months:
            lines.append(f"### {mes_data.month_name}")
            for dia in mes_data.days:
                lines.append(f"\n**{dia.weekday_name.capitalize()}, dia {dia.day}:**")
                rows = [(h.hour, f"{h.level:.2f} m") for h in dia.hours]
                lines.append(markdown_table(["Horário", "Nível"], rows))
    return "\n".join(lines)
