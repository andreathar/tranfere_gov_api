"""Analysis prompts for the Compras feature."""

from __future__ import annotations


def investigar_fornecedor(cnpj: str) -> str:
    """Investiga um fornecedor em contratações públicas.

    Args:
        cnpj: CNPJ do fornecedor a investigar.
    """
    return (
        f"Investigue o fornecedor com CNPJ {cnpj} em contratações públicas.\n\n"
        "Passos:\n"
        f"1. Use buscar_contratos(cnpj_fornecedor='{cnpj}') para ver contratos\n"
        f"2. Use buscar_contratacoes(texto='{cnpj}') para ver licitações\n\n"
        "Apresente um relatório com:\n"
        "- Total de contratos e valores\n"
        "- Órgãos contratantes\n"
        "- Objetos mais frequentes\n"
        "- Período de atuação"
    )


def alienacoes_imoveis_spu(
    data_inicial: str,
    data_final: str,
    uf: str | None = None,
) -> str:
    """Levanta alienações/leilões de imóveis da União no PNCP.

    Guia a análise de atos da Secretaria do Patrimônio da União (SPU) no
    Portal Nacional de Contratações Públicas, usando as modalidades de
    leilão como filtro primário e amparos legais da Lei 9.636/1998 como
    confirmação em nível de contrato individual.

    Args:
        data_inicial: Data inicial YYYYMMDD (ex: 20260101).
        data_final: Data final YYYYMMDD (ex: 20260331). Máx. 365 dias.
        uf: UF do órgão contratante (opcional, ex: 'DF', 'RJ').
    """
    uf_arg = f", uf='{uf}'" if uf else ""
    return (
        f"Levante as alienações de imóveis da União entre {data_inicial} "
        f"e {data_final}{(' na UF ' + uf) if uf else ''} via PNCP:\n\n"
        "1. **Leilão eletrônico** (modalidade 1):\n"
        f"   `buscar_contratacoes(data_inicial='{data_inicial}', "
        f"data_final='{data_final}', modalidade=1{uf_arg})`\n\n"
        "2. **Leilão presencial** (modalidade 13):\n"
        f"   `buscar_contratacoes(data_inicial='{data_inicial}', "
        f"data_final='{data_final}', modalidade=13{uf_arg})`\n\n"
        "3. Filtre localmente os resultados por termos como 'imóvel da União', "
        "'terreno de marinha', 'SPU' ou pelo CNPJ da SPU "
        "(00.394.460/0024-32 — Secretaria do Patrimônio da União / MGI).\n\n"
        "4. **Amparo legal Lei 9.636/1998** (confirmação em contratos):\n"
        "   A API de consulta do PNCP não expõe o código de amparo como filtro, "
        "mas nos detalhes individuais de cada contrato (tool "
        "`consultar_contratacao_detalhe`) o campo `amparoLegal` identifica os "
        "códigos **55 (art. 11-C, I), 56 (art. 11-C, II), 57, 58 e 59 "
        "(art. 24-C)** — todos dispositivos da Lei 9.636/1998, que regulamenta "
        "a gestão do patrimônio imobiliário da União.\n\n"
        "5. Para cada leilão relevante, informe: objeto, órgão, valor "
        "estimado/homologado, situação, UF/município e link do PNCP.\n\n"
        "6. Se houver imóveis geocodificados no resultado, considere cruzar "
        "com `spu_geo_consultar_ponto_spu` (se lat/lon disponíveis) e "
        "`spu_imoveis_buscar_imoveis_spu` (por UF/município) para enriquecer "
        "o dossiê patrimonial."
    )
