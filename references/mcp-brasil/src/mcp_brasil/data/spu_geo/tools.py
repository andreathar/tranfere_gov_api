"""Tool functions for the spu_geo feature."""

from __future__ import annotations

from fastmcp import Context

from mcp_brasil._shared.formatting import format_number_br, markdown_table

from . import client
from .constants import LAYERS, PONTO_UNIAO_LAYERS


async def listar_camadas_spu(ctx: Context) -> str:
    """Lista as camadas geoespaciais disponíveis no GeoPortal SPU.

    Retorna o catálogo curado de camadas com identificador curto, nome
    completo no GeoServer, tipo de geometria e descrição. Use o campo
    `id` nas demais tools para referenciar a camada.

    Returns:
        Tabela com as camadas disponíveis.
    """
    await ctx.info("Listando camadas do GeoPortal SPU...")
    camadas = client.listar_camadas()
    rows = [
        (c.id, c.title, c.geometry, c.description[:70] + ("…" if len(c.description) > 70 else ""))
        for c in camadas
    ]
    return f"**GeoPortal SPU — {len(camadas)} camadas disponíveis**\n\n" + markdown_table(
        ["ID", "Título", "Geometria", "Descrição"], rows
    )


async def consultar_ponto_spu(
    ctx: Context,
    lat: float,
    lon: float,
) -> str:
    """Verifica se um ponto (lat, lon) cai em terras da União.

    Consulta as principais camadas territoriais da SPU (terrenos de marinha,
    acrescidos, marginais, ilhas federais, praias, manguezais) e reporta
    em quais o ponto está contido.

    Args:
        lat: Latitude em graus decimais (EPSG:4326).
        lon: Longitude em graus decimais (EPSG:4326).

    Returns:
        Resumo com as camadas atingidas e propriedades dos trechos.
    """
    await ctx.info(f"Verificando ponto ({lat}, {lon}) em {len(PONTO_UNIAO_LAYERS)} camadas SPU...")
    resultado = await client.verificar_ponto(lat, lon)

    if not resultado.camadas_encontradas:
        return (
            f"O ponto ({lat}, {lon}) **não está em nenhuma** das camadas "
            f"públicas de terras da União verificadas "
            f"({', '.join(PONTO_UNIAO_LAYERS)}).\n\n"
            "Isso não exclui a possibilidade de o imóvel estar em regime de "
            "aforamento/ocupação sem demarcação geoespacial oficial."
        )

    await ctx.info(f"{len(resultado.camadas_encontradas)} camada(s) atingida(s)")

    rows = []
    for feat in resultado.features:
        props = feat.properties
        area = props.get("area_aproximada") or props.get("area_oficial")
        area_fmt = format_number_br(float(area), 0) + " m²" if area else "—"
        rows.append(
            (
                feat.camada,
                props.get("nome_trecho") or props.get("endereco") or "—",
                props.get("uf") or "—",
                area_fmt,
                props.get("etapa_demarcacao") or props.get("situacao_trecho") or "—",
            )
        )

    header = (
        f"**Ponto ({lat}, {lon}) está em terras da União**\n\n"
        f"Camadas atingidas: {', '.join(resultado.camadas_encontradas)}\n\n"
    )
    return header + markdown_table(["Camada", "Nome/Endereço", "UF", "Área", "Situação"], rows)


async def buscar_imoveis_area_spu(
    ctx: Context,
    bbox: str,
    limite: int = 20,
) -> str:
    """Lista imóveis cadastrados da União dentro de uma área (bbox).

    Consulta a camada `vw_imv_localizacao_imovel_p` (pontos geocodificados
    de imóveis da SPU) dentro do retângulo fornecido.

    Args:
        bbox: "minLon,minLat,maxLon,maxLat" em EPSG:4326 (decimal degrees).
            Exemplo: "-43.3,-23.0,-43.1,-22.8" (zona portuária do Rio).
        limite: Máximo de imóveis a retornar (padrão 20, máximo razoável ~100).

    Returns:
        Tabela com RIP, tipo, endereço e coordenadas dos imóveis encontrados.
    """
    limite = max(1, min(limite, 100))
    await ctx.info(f"Buscando imóveis da União em bbox={bbox} (limite={limite})...")
    feats = await client.buscar_imoveis_bbox(bbox, feature_count=limite)

    if not feats:
        return f"Nenhum imóvel da União cadastrado em bbox={bbox}."

    rows = []
    for f in feats:
        p = f.properties
        rows.append(
            (
                p.get("rip") or "—",
                p.get("tipo_imovel") or "—",
                p.get("id_uf") or p.get("uf") or "—",
                p.get("municipio") or "—",
                (p.get("endereco") or "")[:50],
            )
        )
    header = f"**Imóveis da União em bbox={bbox}** — {len(feats)} encontrado(s)\n\n"
    return header + markdown_table(["RIP", "Tipo", "UF", "Município", "Endereço"], rows)


async def detalhar_camada_spu(ctx: Context, camada_id: str) -> str:
    """Retorna metadados detalhados de uma camada do GeoPortal SPU.

    Args:
        camada_id: Identificador curto (ex: 'terreno_marinha', 'imovel_localizacao').

    Returns:
        Metadados da camada (typename, geometria, descrição).
    """
    await ctx.info(f"Detalhando camada '{camada_id}'...")
    if camada_id not in LAYERS:
        return (
            f"Camada '{camada_id}' não encontrada. "
            f"Use `listar_camadas_spu` para ver os ids válidos."
        )
    info = LAYERS[camada_id]
    return (
        f"**Camada: {info['title']}** (`{camada_id}`)\n\n"
        f"- **GeoServer typename**: `{info['typename']}`\n"
        f"- **Tipo de geometria**: {info['geometry']}\n"
        f"- **Descrição**: {info['description']}\n\n"
        "Acessível via WMS GetFeatureInfo em "
        "`https://geoportal-spunet.gestao.gov.br/geoserver/ows`."
    )
