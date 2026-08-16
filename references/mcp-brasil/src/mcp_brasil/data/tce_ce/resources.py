"""Static reference data for the TCE-CE feature."""

from __future__ import annotations

import json


def endpoints_tce_ce() -> str:
    """Endpoints disponíveis na API de Dados Abertos do TCE-CE (SIM).

    Lista os principais módulos com parâmetros obrigatórios.
    """
    endpoints = [
        {
            "endpoint": "/municipios",
            "descricao": "Lista dos 184 municípios cearenses com código e nome",
            "parametros_obrigatorios": [],
        },
        {
            "endpoint": "/licitacoes",
            "descricao": "Processos licitatórios municipais",
            "parametros_obrigatorios": [
                "codigo_municipio",
                "data_realizacao_autuacao_licitacao",
            ],
        },
        {
            "endpoint": "/contrato",
            "descricao": "Contratos municipais (paginado, max 100/página)",
            "parametros_obrigatorios": [
                "codigo_municipio",
                "data_contrato",
                "quantidade",
                "deslocamento",
            ],
        },
        {
            "endpoint": "/notas_empenhos",
            "descricao": "Notas de empenho (paginado, max 100/página)",
            "parametros_obrigatorios": [
                "codigo_municipio",
                "data_referencia_empenho (yyyymm)",
                "codigo_orgao",
                "quantidade",
                "deslocamento",
            ],
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
