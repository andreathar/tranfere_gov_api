"""Analysis prompts for the spu_geo feature."""

from __future__ import annotations


def analise_terreno_uniao(lat: float, lon: float) -> str:
    """Analisa se um ponto está em terras da União e suas implicações.

    Args:
        lat: Latitude em graus decimais.
        lon: Longitude em graus decimais.
    """
    return (
        f"Analise o ponto ({lat}, {lon}) quanto à natureza patrimonial federal:\n\n"
        "1. Chame `consultar_ponto_spu(lat, lon)` para verificar se o ponto cai em "
        "alguma camada de terreno da União (marinha, acrescido, marginal, ilha, "
        "praia, manguezal).\n"
        "2. Se o ponto estiver em terreno de marinha/acrescido:\n"
        "   - Explique o regime (aforamento ou ocupação) e obrigações (foro 0,6% "
        "ou taxa 2%/5%, laudêmio 5% em transferência onerosa).\n"
        "   - Cite a base legal (DL 9.760/1946, Lei 9.636/1998).\n"
        "3. Se estiver em ilha federal ou praia, explique que são bens da União de uso "
        "comum do povo (Art. 20 da CF/88).\n"
        "4. Forneça a referência da fonte (Secretaria do Patrimônio da União - SPU) "
        "e oriente o usuário a consultar o RIP específico no SPUnet para dados "
        "cadastrais individualizados."
    )


def imoveis_em_area(bbox: str, objetivo: str = "mapeamento") -> str:
    """Levanta imóveis da União dentro de um bbox com objetivo específico.

    Args:
        bbox: "minLon,minLat,maxLon,maxLat" em EPSG:4326.
        objetivo: "mapeamento" | "alienacao" | "auditoria".
    """
    return (
        f"Levante imóveis da União no bbox={bbox} com objetivo de {objetivo}:\n\n"
        "1. Chame `buscar_imoveis_area_spu(bbox, limite=50)` para listar imóveis "
        "cadastrados no SPUnet na área.\n"
        "2. Agrupe por tipo (Gleba/Terreno, Edificação, etc.) e por UF/município.\n"
        "3. Para cada imóvel, inclua o RIP e endereço.\n"
        f"4. Se o objetivo for '{objetivo}':\n"
        "   - **mapeamento**: priorize a distribuição geográfica.\n"
        "   - **alienação**: considere cruzar com o PNCP (modalidade 1/13 de "
        "leilão) via ferramentas do módulo `compras` para encontrar editais ativos.\n"
        "   - **auditoria**: liste RIPs para posterior consulta em dados abertos "
        "(CSV de arrecadação/responsáveis do dataset `imoveis-da-uniao`)."
    )
