"""Prompts for IBAMA."""

from __future__ import annotations


def analise_autuacoes() -> str:
    """Análise de autuações ambientais do IBAMA."""
    return (
        "Analise as autuações ambientais do IBAMA.\n\n"
        "1. buscar_datasets_ibama('infração') para achar o package\n"
        "2. detalhe_dataset_ibama(package_id) para obter o CSV mais recente\n"
        "3. Agregue por UF, bioma e tipo de infração\n\n"
        "Apresente ranking de UFs, biomas mais autuados e evolução temporal."
    )
