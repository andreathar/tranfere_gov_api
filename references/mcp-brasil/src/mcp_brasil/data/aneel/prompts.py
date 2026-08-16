"""Prompts for ANEEL."""

from __future__ import annotations


def analise_geracao_distribuida() -> str:
    """Análise de mini/micro geração distribuída via SIGA."""
    return (
        "Analise os dados de mini/micro geração distribuída da ANEEL.\n\n"
        "1. buscar_datasets_aneel('geração distribuída') para localizar o package\n"
        "2. detalhe_dataset_aneel(package_id) para obter URLs de CSVs\n"
        "3. Baixe e analise o arquivo mais recente por UF, modalidade (fotovoltaica/hídrica), "
        "classe de consumo\n\n"
        "Apresente: potência total instalada, ranking de UFs, crescimento da fotovoltaica."
    )
