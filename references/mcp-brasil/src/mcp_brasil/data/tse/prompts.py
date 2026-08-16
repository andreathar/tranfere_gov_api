"""Prompts for the TSE feature — analysis templates for LLMs."""

from __future__ import annotations


def analise_candidato(
    nome: str,
    ano: int,
    municipio: int,
    eleicao_id: int,
    cargo: int,
) -> str:
    """Gera uma análise completa de um candidato.

    Orienta o LLM a consultar dados do candidato, patrimônio e prestação de contas.

    Args:
        nome: Nome do candidato para buscar.
        ano: Ano da eleição.
        municipio: Código do município.
        eleicao_id: ID da eleição.
        cargo: Código do cargo.
    """
    return (
        f"Consulte os dados públicos do candidato '{nome}' "
        f"na eleição {ano} usando os dados do TSE.\n\n"
        "Passos:\n"
        f"1. Use listar_candidatos(ano={ano}, municipio={municipio}, "
        f"eleicao_id={eleicao_id}, cargo={cargo}) para encontrar o candidato\n"
        "2. Com o ID do candidato, use buscar_candidato() para detalhes completos\n"
        "3. Use consultar_prestacao_contas() para ver as finanças de campanha\n\n"
        "Apresente:\n"
        "- Dados eleitorais: partido, número, cargo\n"
        "- Escolaridade e ocupação declaradas\n"
        "- Receitas e despesas de campanha declaradas ao TSE\n"
        "- Situação da candidatura e regularidade"
    )


def panorama_eleicao(ano: int, municipio: int, eleicao_id: int, cargo: int) -> str:
    """Lista os candidatos registrados em uma eleição para consulta cidadã.

    Args:
        ano: Ano da eleição.
        municipio: Código do município.
        eleicao_id: ID da eleição.
        cargo: Código do cargo.
    """
    return (
        f"Liste os candidatos registrados na eleição {ano} "
        "usando os dados do TSE.\n\n"
        "Passos:\n"
        f"1. Use listar_candidatos(ano={ano}, municipio={municipio}, "
        f"eleicao_id={eleicao_id}, cargo={cargo})\n"
        "2. Para cada candidato, use buscar_candidato() para detalhes\n\n"
        "Apresente uma tabela informativa com:\n"
        "- Nome, partido, número\n"
        "- Situação da candidatura (apto/inapto)\n"
        "- Escolaridade e ocupação declaradas"
    )
