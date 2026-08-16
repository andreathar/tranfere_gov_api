"""Prompts for the Saúde feature — analysis templates for LLMs.

Prompts provide reusable message templates that guide LLM interactions.
They appear in client UIs (e.g., Claude Desktop) as slash-commands.
"""

from __future__ import annotations


def analise_rede_saude(codigo_municipio: str) -> str:
    """Gera uma análise da rede de saúde de um município.

    Cria um template de análise que orienta o LLM a consultar dados
    de estabelecimentos, profissionais e leitos hospitalares do município.

    Args:
        codigo_municipio: Código IBGE do município (ex: "355030" para São Paulo).
    """
    return (
        f"Faça uma análise da rede de saúde do município {codigo_municipio} "
        "usando os dados do CNES/DataSUS.\n\n"
        "Passos:\n"
        f"1. Use buscar_estabelecimentos(codigo_municipio='{codigo_municipio}') "
        "para listar os estabelecimentos de saúde\n"
        "2. Use listar_tipos_estabelecimento() para entender os tipos disponíveis\n"
        f"3. Use buscar_profissionais(codigo_municipio='{codigo_municipio}') "
        "para ver os profissionais atuantes\n"
        f"4. Use consultar_leitos(codigo_municipio='{codigo_municipio}') "
        "para analisar a capacidade de leitos\n\n"
        "Apresente:\n"
        "- Quantidade e tipos de estabelecimentos\n"
        "- Distribuição de profissionais por especialidade\n"
        "- Capacidade de leitos (existentes vs SUS)\n"
        "- Avaliação geral da cobertura de saúde no município"
    )


def analise_epidemiologica(doenca: str, municipio: str) -> str:
    """Gera uma análise epidemiológica de arbovirose em um município.

    Cria um template de análise que orienta o LLM a consultar dados de
    alertas de dengue/chikungunya/zika e cruzar com dados do SINAN.

    Args:
        doenca: Doença a analisar ("dengue", "chikungunya" ou "zika").
        municipio: Nome do município (ex: "Fortaleza").
    """
    return (
        f"Faça uma análise epidemiológica de {doenca} no município de {municipio}.\n\n"
        "Passos:\n"
        f"1. Use buscar_municipio_geocodigo(nome='{municipio}') para obter o geocódigo IBGE\n"
        f"2. Use buscar_alertas_dengue(municipio='{municipio}', doenca='{doenca}') "
        "para obter os alertas semanais do InfoDengue\n"
        "3. Use listar_doencas_notificaveis(categoria='Arbovirose') para contexto sobre "
        "doenças notificáveis relacionadas\n"
        "4. Use buscar_situacao_gripe() para verificar se há co-circulação de "
        "vírus respiratórios\n\n"
        "Apresente:\n"
        "- Evolução semanal do nível de alerta (Verde/Amarelo/Laranja/Vermelho)\n"
        "- Tendência de casos estimados e notificados\n"
        "- Número reprodutivo (Rt) — acima de 1 indica transmissão em expansão\n"
        "- Incidência por 100 mil habitantes\n"
        "- Comparação com limiares epidêmicos\n"
        "- Recomendações baseadas no nível de alerta atual"
    )
