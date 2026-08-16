"""Static reference data for the TCE-PE feature."""

from __future__ import annotations

import json


def endpoints_tce_pe() -> str:
    """Endpoints disponíveis na API de Dados Abertos do TCE-PE.

    Lista os principais módulos com parâmetros típicos.
    """
    endpoints = [
        {
            "endpoint": "UnidadesJurisdicionadas",
            "descricao": "Unidades jurisdicionadas (prefeituras, câmaras, etc.)",
            "parametros": ["NATUREZA", "MUNICIPIO"],
        },
        {
            "endpoint": "LicitacaoUG",
            "descricao": "Licitações por unidade gestora",
            "parametros": ["ANOLICITACAO", "MUNICIPIO", "MODALIDADE"],
        },
        {
            "endpoint": "Contratos",
            "descricao": "Contratos municipais e estaduais",
            "parametros": ["ANOREFERENCIA", "MUNICIPIO", "CPFCNPJ"],
        },
        {
            "endpoint": "DespesasMunicipais",
            "descricao": "Despesas municipais (empenhos, liquidações, pagamentos)",
            "parametros": [
                "ANOREFERENCIA",
                "MESREFERENCIA",
                "CODIGO_MUNICIPIO",
            ],
        },
        {
            "endpoint": "Fornecedores",
            "descricao": "Fornecedores registrados no SAGRES",
            "parametros": ["NOME", "CPFCNPJ"],
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
