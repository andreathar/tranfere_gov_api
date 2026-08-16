"""Analysis prompts for the spu_imoveis feature."""

from __future__ import annotations


def patrimonio_orgao(sigla: str) -> str:
    """Análise do patrimônio imobiliário de um órgão federal.

    Args:
        sigla: Sigla do órgão superior (ex: 'MEC', 'MD', 'MGI').
    """
    return (
        f"Analise o patrimônio imobiliário do órgão {sigla}:\n\n"
        f"1. Use `buscar_imoveis_spu(orgao_sigla='{sigla}', limite=50)` para listar imóveis.\n"
        "2. Use `resumo_orgaos_spu(top=25)` para ver o ranking e a posição deste órgão.\n"
        "3. Identifique concentração geográfica (UFs com mais imóveis) e regimes "
        "predominantes.\n"
        "4. Comente tipos de destinação mais comuns (palácio, residência, "
        "sede administrativa, etc.).\n"
        "5. Se apropriado, cruze com `compras_pncp_*` para verificar alienações "
        "recentes (modalidade 1/13) envolvendo o órgão."
    )


def patrimonio_municipio(uf: str, municipio: str) -> str:
    """Análise do patrimônio da União em um município.

    Args:
        uf: Sigla da UF.
        municipio: Nome (ou substring) do município.
    """
    return (
        f"Levante o patrimônio da União em {municipio}/{uf}:\n\n"
        f"1. `buscar_imoveis_spu(uf='{uf}', municipio='{municipio}', limite=100)` "
        "para listar os imóveis.\n"
        "2. Agrupe por órgão e por regime (funcional, uso em serviço, cessão, etc.).\n"
        "3. Destaque os 5 imóveis de maior valor.\n"
        "4. Se houver imóveis em regime de aforamento/ocupação, considere chamar "
        "`spu_geo_consultar_ponto_spu` com coordenadas do município para identificar "
        "se estão em terreno de marinha."
    )
