"""Prompts for the Transparência feature — analysis templates for LLMs.

Prompts provide reusable message templates that guide LLM interactions.
They appear in client UIs (e.g., Claude Desktop) as slash-commands.
"""

from __future__ import annotations


def auditoria_fornecedor(cpf_cnpj: str) -> str:
    """Gera uma auditoria completa de um fornecedor do governo federal.

    Cria um template que orienta o LLM a consultar contratos, sanções
    e emendas relacionados a um fornecedor específico por CPF ou CNPJ.

    Args:
        cpf_cnpj: CPF ou CNPJ do fornecedor (ex: 12345678000190).
    """
    return (
        f"Faça uma auditoria completa do fornecedor {cpf_cnpj} "
        "usando os dados do Portal da Transparência.\n\n"
        "Passos:\n"
        f"1. Use buscar_contratos(cpf_cnpj='{cpf_cnpj}') para listar "
        "todos os contratos federais deste fornecedor\n"
        f"2. Use buscar_sancoes(consulta='{cpf_cnpj}') para verificar "
        "se há sanções nas bases CEIS, CNEP, CEPIM e CEAF\n"
        "3. Se houver contratos, analise os valores e períodos\n\n"
        "Apresente:\n"
        "- Resumo dos contratos (quantidade, valor total, órgãos contratantes)\n"
        "- Status nas bases de sanções (limpo ou sancionado)\n"
        "- Se sancionado: tipo, período e fundamentação da sanção\n"
        "- Análise de risco: o fornecedor apresenta irregularidades?"
    )


def analise_despesas(mes_ano_inicio: str, mes_ano_fim: str, uf: str = "") -> str:
    """Gera uma análise de despesas do governo federal em um período.

    Cria um template que orienta o LLM a consultar e analisar
    despesas públicas, emendas e licitações em um período.

    Args:
        mes_ano_inicio: Mês/ano de início no formato MM/AAAA (ex: 01/2024).
        mes_ano_fim: Mês/ano de fim no formato MM/AAAA (ex: 12/2024).
        uf: UF para filtrar análise (opcional, ex: PI, SP).
    """
    filtro_uf = f" no estado {uf.upper()}" if uf else ""
    return (
        f"Analise as despesas do governo federal de {mes_ano_inicio} a "
        f"{mes_ano_fim}{filtro_uf} usando o Portal da Transparência.\n\n"
        "Passos:\n"
        f"1. Use consultar_despesas(mes_ano_inicio='{mes_ano_inicio}', "
        f"mes_ano_fim='{mes_ano_fim}') para obter os dados de despesas\n"
        f"2. Use buscar_emendas(ano={mes_ano_inicio.split('/')[1]}) "
        "para verificar emendas parlamentares no período\n"
        f"3. Use buscar_licitacoes(data_inicial='01/{mes_ano_inicio}', "
        f"data_final='28/{mes_ano_fim}') para licitações no período\n\n"
        "Apresente:\n"
        "- Volume total de despesas no período\n"
        "- Principais favorecidos (top 10 por valor)\n"
        "- Distribuição por órgão\n"
        "- Emendas parlamentares executadas no período\n"
        "- Licitações abertas e concluídas no período\n"
        "- Distribuição dos recursos por área (saúde, educação, etc.)"
    )


def verificacao_compliance(consulta: str) -> str:
    """Verifica a situação de uma empresa ou pessoa nas bases de sanções federais.

    Cria um template de due diligence/compliance que consulta todas as
    bases de sanções (CEIS, CNEP, CEPIM, CEAF) simultaneamente.

    Args:
        consulta: CPF, CNPJ ou nome da pessoa/empresa a verificar.
    """
    return (
        f"Faça uma verificação de compliance para '{consulta}' "
        "usando o Portal da Transparência.\n\n"
        "Passos:\n"
        f"1. Use buscar_sancoes(consulta='{consulta}') para consultar "
        "todas as 4 bases de sanções simultaneamente:\n"
        "   - CEIS: Cadastro de Empresas Inidôneas e Suspensas\n"
        "   - CNEP: Cadastro Nacional de Empresas Punidas (Lei Anticorrupção)\n"
        "   - CEPIM: Cadastro de Entidades Privadas sem Fins Lucrativos Impedidas\n"
        "   - CEAF: Cadastro de Expulsões da Administração Federal\n"
        f"2. Use buscar_contratos(cpf_cnpj='{consulta}') para verificar "
        "se possui contratos ativos com o governo\n\n"
        "Apresente:\n"
        "- Status em cada base de sanções (limpo ou com registro)\n"
        "- Se houver sanção: tipo, órgão sancionador, período e fundamentação\n"
        "- Contratos ativos com o governo federal (se houver)\n"
        "- Parecer de compliance: apto ou inapto para contratar com o governo\n"
        "- Recomendações de due diligence adicional (se aplicável)"
    )
