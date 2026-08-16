"""Analysis prompts for TCE-PI."""


def analisar_municipio_pi(municipio: str, exercicio: int = 2024) -> str:
    """Prompt para análise fiscal de um município do Piauí.

    Args:
        municipio: Nome do município a ser analisado.
        exercicio: Ano do exercício fiscal.
    """
    return f"""Analise a situação fiscal do município de {municipio} (PI) no exercício {exercicio}.

Passos:
1. Use buscar_prefeitura_pi para encontrar o ID do município "{municipio}"
2. Use consultar_despesas_pi com o ID e exercício {exercicio} para ver despesas por função
3. Use consultar_receitas_pi para ver receitas detalhadas

Análise esperada:
- Maiores funções de despesa (saúde, educação, administração)
- Proporção entre receita prevista e arrecadada
- Evolução histórica das despesas (empenhada vs paga)
- Comparação com limites constitucionais (25% educação, 15% saúde)
"""
