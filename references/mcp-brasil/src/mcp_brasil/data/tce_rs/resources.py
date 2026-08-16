"""Static reference data for the TCE-RS feature."""

from __future__ import annotations

import json


def endpoints_tce_rs() -> str:
    """Catálogo de endpoints e dados disponíveis no portal TCE-RS."""
    endpoints = [
        {
            "grupo": "Dados auxiliares",
            "url": "dados/auxiliar/municipios.json",
            "descricao": "Lista de municípios do RS com códigos TCE e IBGE",
        },
        {
            "grupo": "Educação",
            "url": "dados/municipal/educacao-indice/{ano}.json",
            "descricao": "Índice de aplicação em educação (MDE) por município e ano",
        },
        {
            "grupo": "Saúde",
            "url": "dados/municipal/saude-indice/{ano}.json",
            "descricao": "Índice de aplicação em saúde (ASPS) por município e ano",
        },
        {
            "grupo": "Gestão fiscal",
            "url": "dados/municipal/gastos-lrf-mde-asps/{ano}.json",
            "descricao": "Dados de gestão fiscal (LRF) do executivo municipal",
        },
        {
            "grupo": "Despesa",
            "url": "dados/municipal/balancete-despesa/{ano}.json",
            "descricao": "Balancete de despesa consolidado (arquivo grande, >100MB)",
        },
        {
            "grupo": "Receita",
            "url": "dados/municipal/balancete-receita/{ano}.json",
            "descricao": "Balancete de receita consolidado (arquivo grande)",
        },
        {
            "grupo": "Licitações",
            "url": "dados/licitacon/licitacao/ano/{ano}.csv.zip",
            "descricao": "Licitações consolidadas LicitaCon (ZIP com CSVs)",
        },
        {
            "grupo": "Contratos",
            "url": "dados/licitacon/contrato/ano/{ano}.csv.zip",
            "descricao": "Contratos consolidados LicitaCon (ZIP com CSVs)",
        },
        {
            "grupo": "CKAN API",
            "url": "api/3/action/package_search",
            "descricao": "Busca de datasets por texto e grupo (16 grupos, ~69k datasets)",
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)
