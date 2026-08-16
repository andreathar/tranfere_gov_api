"""Analysis prompts for the DENASUS feature.

Prompts are reusable templates that guide LLM interactions.
They instruct the LLM on which tools to call and how to analyze the data.
"""

from __future__ import annotations


def analise_auditoria_municipal(municipio: str, uf: str) -> str:
    """Assistente para análise de auditorias do SUS em um município.

    Orienta o LLM a verificar se o município foi alvo de auditoria
    e consolidar informações relevantes.

    Args:
        municipio: Nome do município (ex: "Teresina").
        uf: Sigla do estado (ex: "PI").
    """
    return (
        f"Atue como um analista de controle público para investigar a situação "
        f"de auditoria do SUS em {municipio}/{uf}.\n\n"
        "Passos:\n"
        f"1. Use verificar_municipio(municipio='{municipio}', uf='{uf}') "
        "para verificar auditorias registradas\n"
        f"2. Use buscar_auditorias(uf='{uf}') para ver todas as auditorias no estado\n"
        "3. Use listar_relatorios_anuais() para contexto temporal\n"
        "4. Use informacoes_sna() para explicar a estrutura do sistema de auditoria\n\n"
        "Apresente:\n"
        "- Se o município foi alvo de auditoria e quando\n"
        "- Tipo de auditoria realizada (auditoria, verificação, monitoramento)\n"
        "- Contexto estadual: quantas auditorias no estado\n"
        "- Informações sobre como o cidadão pode acompanhar"
    )
