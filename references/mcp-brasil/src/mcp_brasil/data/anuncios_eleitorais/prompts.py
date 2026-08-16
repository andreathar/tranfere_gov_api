"""Analysis prompts for the Anuncios Eleitorais feature.

Prompts are reusable templates that guide LLM interactions.
They instruct the LLM on which tools to call and how to analyze the data.

In Claude Desktop, prompts appear as selectable options (similar to slash commands).
"""

from __future__ import annotations


def transparencia_anuncios(termo: str = "", estado: str = "") -> str:
    """Consulta anúncios políticos para fiscalização cidadã.

    Permite ao cidadão verificar quanto está sendo gasto em propaganda
    política na sua região, promovendo transparência eleitoral.

    Args:
        termo: Termo de busca (candidato, partido ou tema).
        estado: Estado para filtrar (opcional).
    """
    local = f"no estado de {estado}" if estado else "no Brasil"
    instrucoes = (
        f"Consulte os anúncios políticos {local} para fins de transparência eleitoral:\n\n"
    )

    if termo and estado:
        instrucoes += (
            f"1. Use `buscar_anuncios_por_regiao` com região ['{estado}'] e termo '{termo}'\n"
        )
    elif estado:
        instrucoes += f"1. Use `buscar_anuncios_por_regiao` com região ['{estado}']\n"
    else:
        instrucoes += (
            f"1. Use `buscar_anuncios_eleitorais` com o termo '{termo}'\n"
            if termo
            else "1. Use `buscar_anuncios_eleitorais` com termos amplos\n"
        )

    instrucoes += (
        "2. Apresente um resumo de transparência com:\n"
        "   - Quantidade total de anúncios encontrados\n"
        "   - Faixa total de gastos com propaganda\n"
        "   - Plataformas utilizadas (Facebook, Instagram, etc.)\n"
        "   - Principais temas abordados nos anúncios\n"
        "   - Período de veiculação\n"
        "3. Destaque informações relevantes para o eleitor"
    )
    return instrucoes
