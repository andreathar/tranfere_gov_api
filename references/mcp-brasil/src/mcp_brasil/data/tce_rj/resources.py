"""Static reference data for the TCE-RJ feature."""

from __future__ import annotations

import json


def endpoints_disponiveis() -> str:
    """Endpoints disponíveis na API de Dados Abertos do TCE-RJ.

    Lista os módulos de dados abertos com descrição e filtros disponíveis.
    """
    endpoints = [
        {
            "modulo": "Licitações",
            "descricao": "Processos licitatórios dos 92 municípios fluminenses",
            "filtros": ["ano", "municipio"],
            "paginacao": True,
        },
        {
            "modulo": "Contratos Municipais",
            "descricao": "Contratos firmados pelos municípios com fornecedores",
            "filtros": ["ano", "municipio"],
            "paginacao": True,
        },
        {
            "modulo": "Compras Diretas",
            "descricao": "Dispensas e inexigibilidades de licitação (municipal e estadual)",
            "filtros": ["ano", "municipio"],
            "paginacao": True,
        },
        {
            "modulo": "Obras Paralisadas",
            "descricao": "Obras públicas paralisadas (estado e municípios)",
            "filtros": [],
            "paginacao": False,
        },
        {
            "modulo": "Penalidades",
            "descricao": "Multas e débitos impostos pelo TCE-RJ a gestores municipais",
            "filtros": ["tipo"],
            "paginacao": False,
        },
        {
            "modulo": "Prestação de Contas",
            "descricao": "Parecer do TCE-RJ sobre contas dos prefeitos",
            "filtros": [],
            "paginacao": False,
        },
        {
            "modulo": "Concessões Públicas",
            "descricao": "PPPs e concessões de serviços públicos municipais",
            "filtros": ["municipio"],
            "paginacao": False,
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
