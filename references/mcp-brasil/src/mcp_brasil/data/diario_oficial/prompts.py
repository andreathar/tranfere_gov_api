"""Analysis prompts for the Diário Oficial feature."""

from __future__ import annotations


def investigar_empresa(nome_empresa: str, cidade: str = "") -> str:
    """Investiga menções de uma empresa em diários oficiais municipais.

    Args:
        nome_empresa: Nome da empresa ou CNPJ para investigar.
        cidade: Nome da cidade para filtrar (opcional).
    """
    passos = f"Investigue a empresa '{nome_empresa}' nos diários oficiais municipais.\n\nPassos:\n"
    if cidade:
        passos += (
            f"1. Use buscar_cidades(nome='{cidade}') para obter o código IBGE\n"
            f"2. Use buscar_diarios(texto='{nome_empresa}', territorio_id=<código>) "
            "para buscar menções\n"
        )
    else:
        passos += f"1. Use buscar_diarios(texto='{nome_empresa}') para buscar menções\n"
    passos += (
        "\nAnalise os resultados procurando:\n"
        "- Contratos e licitações\n"
        "- Sanções e penalidades\n"
        "- Nomeações e exonerações\n"
        "- Licenças e alvarás\n\n"
        "Apresente um relatório com os achados mais relevantes."
    )
    return passos


def monitorar_licitacoes(cidade: str, periodo_dias: int = 30) -> str:
    """Monitora licitações publicadas em diários oficiais de um município.

    Args:
        cidade: Nome da cidade para monitorar.
        periodo_dias: Período em dias para retroagir (padrão: 30).
    """
    return (
        f"Monitore licitações publicadas nos diários oficiais de {cidade} "
        f"nos últimos {periodo_dias} dias.\n\n"
        "Passos:\n"
        f"1. Use buscar_cidades(nome='{cidade}') para obter o código IBGE\n"
        "2. Use buscar_diarios(texto='licitação OR pregão OR tomada de preço', "
        "territorio_id=<código>, data_inicio=<hoje - período>)\n"
        "3. Analise os resultados e categorize:\n"
        "   - Pregões eletrônicos\n"
        "   - Tomadas de preço\n"
        "   - Concorrências\n"
        "   - Dispensas de licitação\n\n"
        "Apresente tabela com: data, tipo, objeto, valor (se disponível)."
    )


def rastrear_nomeacoes(nome_pessoa: str, uf: str = "") -> str:
    """Rastreia nomeações e exonerações de uma pessoa em diários oficiais.

    Args:
        nome_pessoa: Nome da pessoa para rastrear.
        uf: Sigla da UF para filtrar (opcional).
    """
    filtro = f" na UF {uf}" if uf else " em todos os municípios"
    return (
        f"Rastreie nomeações e exonerações de '{nome_pessoa}'{filtro}.\n\n"
        "Passos:\n"
        f"1. Use buscar_diarios(texto='{nome_pessoa}') para buscar menções\n"
        f"2. Se especificado UF, use buscar_diarios_regiao(texto='{nome_pessoa}', uf='{uf}')\n"
        "3. Filtre resultados procurando:\n"
        "   - Nomeações e designações\n"
        "   - Exonerações\n"
        "   - Substituições temporárias\n"
        "   - Funções gratificadas\n\n"
        "Apresente cronologia dos cargos ocupados."
    )


def comparar_municipios(tema: str, cidades: str) -> str:
    """Compara publicações sobre um tema entre múltiplos municípios.

    Args:
        tema: Tema para comparar (ex: "saúde", "educação", "transporte").
        cidades: Cidades separadas por vírgula (ex: "São Paulo, Rio de Janeiro").
    """
    lista = [c.strip() for c in cidades.split(",")]
    return (
        f"Compare publicações sobre '{tema}' entre: {', '.join(lista)}.\n\n"
        "Passos:\n"
        + "".join(
            f"{i}. Use buscar_cidades(nome='{c}') para obter código IBGE de {c}\n"
            for i, c in enumerate(lista, 1)
        )
        + f"{len(lista) + 1}. Para cada cidade, busque: buscar_diarios(texto='{tema}', "
        "territorio_id=<código>)\n"
        f"{len(lista) + 2}. Compare:\n"
        "   - Volume de publicações por cidade\n"
        "   - Tipos de atos (licitações, contratos, portarias)\n"
        "   - Valores envolvidos (quando disponível)\n\n"
        "Apresente comparativo em tabela."
    )


def rastrear_cadeia_regulatoria(tema: str) -> str:
    """Rastreia como uma lei/decreto federal se desdobra em atos municipais.

    Args:
        tema: Tema ou número da lei/decreto (ex: "Lei 14.133", "saneamento básico").
    """
    return (
        f"Rastreie a cadeia regulatória do tema '{tema}' do nível federal ao municipal.\n\n"
        "Passos:\n"
        f"1. Use dou_buscar(termo='{tema}') para encontrar atos federais no DOU\n"
        f"2. Use buscar_diarios(texto='{tema}') para encontrar reflexos municipais\n"
        "3. Analise a cadeia:\n"
        "   - Qual ato federal originou? (lei, decreto, portaria)\n"
        "   - Quais municípios regulamentaram localmente?\n"
        "   - Há diferenças na aplicação entre municípios?\n"
        "   - Qual o intervalo entre publicação federal e municipal?\n\n"
        "Apresente a cadeia regulatória em ordem cronológica."
    )


def investigar_cnpj_diarios(cnpj: str) -> str:
    """Investiga menções a um CNPJ em diários federais e municipais.

    Args:
        cnpj: CNPJ da empresa (com ou sem pontuação).
    """
    cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return (
        f"Investigue o CNPJ {cnpj} em diários oficiais federais e municipais.\n\n"
        "Passos:\n"
        f"1. Use buscar_diario_unificado(texto='{cnpj_limpo}', escopo='ambos') "
        "para busca simultânea\n"
        f"2. Use dou_buscar(termo='{cnpj_limpo}') para detalhes federais\n"
        f"3. Use buscar_diarios(texto='{cnpj_limpo}') para detalhes municipais\n"
        "4. Analise os resultados procurando:\n"
        "   - Contratos e licitações federais\n"
        "   - Contratos e licitações municipais\n"
        "   - Sanções e penalidades (CEIS, CNEP)\n"
        "   - Autorizações, licenças, alvarás\n"
        "\n"
        "Apresente relatório consolidado com achados por esfera (federal/municipal)."
    )


def monitorar_diario_completo(orgao: str, tipo_publicacao: str = "") -> str:
    """Monitora publicações de um órgão no DOU federal.

    Args:
        orgao: Nome do órgão federal (ex: "Ministério da Saúde", "ANVISA").
        tipo_publicacao: Tipo de ato a filtrar (ex: "Portaria", "Resolução"). Opcional.
    """
    filtro_tipo = f" do tipo '{tipo_publicacao}'" if tipo_publicacao else ""
    return (
        f"Monitore publicações{filtro_tipo} de '{orgao}' no DOU.\n\n"
        "Passos:\n"
        f"1. Use dou_buscar_por_orgao(orgao='{orgao}', periodo='SEMANA') "
        "para atos recentes\n"
        + (
            f"2. Use dou_buscar_avancado(orgao='{orgao}', tipo='{tipo_publicacao}') "
            "para filtrar tipo\n"
            if tipo_publicacao
            else ""
        )
        + "3. Categorize os atos por tipo (portarias, resoluções, despachos)\n"
        "4. Destaque atos que afetam o público (mudanças regulatórias, prazos)\n\n"
        "Apresente resumo executivo com os atos mais relevantes."
    )
