"""Static reference data for the TCE-RN feature."""

from __future__ import annotations

import json


def endpoints_tce_rn() -> str:
    """Catálogo de endpoints disponíveis no TCE-RN."""
    endpoints = [
        {
            "grupo": "Informações Básicas",
            "endpoint": "/InformacoesBasicasApi/JurisdicionadosTCE/{formato}",
            "descricao": "Lista de entidades jurisdicionadas pelo TCE-RN (~914)",
        },
        {
            "grupo": "Balanço Orçamentário",
            "endpoint": "/BalancoOrcamentarioApi/Despesa/{fmt}/{ano}/{bimestre}/{id}",
            "descricao": "Despesas orçamentárias por unidade, ano e bimestre",
        },
        {
            "grupo": "Balanço Orçamentário",
            "endpoint": "/BalancoOrcamentarioApi/Receita/{fmt}/{ano}/{bimestre}/{id}",
            "descricao": "Receitas orçamentárias por unidade, ano e bimestre",
        },
        {
            "grupo": "Procedimentos Licitatórios",
            "endpoint": "/ProcedimentosLicitatoriosApi/LicitacaoPublica/{fmt}/{id}/{di}/{df}",
            "descricao": "Licitações públicas por unidade e período",
        },
        {
            "grupo": "Contratos",
            "endpoint": "/ContratosApi/Contratos/{fmt}/{id}/{hierarquia}",
            "descricao": "Contratos por unidade jurisdicionada",
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
