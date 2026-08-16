"""Constants for ANEEL feature."""

from __future__ import annotations

ANEEL_CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"

# Curated key datasets (CKAN package id → descrição)
DATASETS_CHAVE: dict[str, str] = {
    "siga-sistema-de-informacoes-de-geracao-da-aneel": (
        "SIGA — Empreendimentos de geração em operação (hidro, solar, eólico, térmico)"
    ),
    "relacao-de-empreendimentos-de-geracao-distribuida": (
        "Mini e Micro Geração Distribuída — usinas GD por estado/município/modalidade"
    ),
    "empreendimentos-em-operacao": "Quantidade de empreendimentos de geração em operação",
    "agentes-do-setor-eletrico": "Agentes do setor elétrico (concessionárias, permissionárias)",
    "bandeiras-tarifarias": "Histórico mensal de acionamento de bandeiras tarifárias",
    "tarifas-residenciais": "Tarifas residenciais aplicadas pelas distribuidoras",
    "auto-de-infracao": "Autos de infração aplicados pela ANEEL",
    "atendimento-ocorrencias-emergenciais": (
        "Atendimento a ocorrências emergenciais por distribuidora"
    ),
    "agentes-de-geracao-de-energia-eletrica": "Agentes de geração de energia elétrica",
    "atos-de-outorgas-de-geracao": "Atos de outorga de geração de energia",
}
