"""Static reference data for TCE-PI."""

import json


def endpoints_tce_pi() -> str:
    """Return a JSON description of all TCE-PI endpoints."""
    return json.dumps(
        {
            "api_base": "https://sistemas.tce.pi.gov.br/api/portaldacidadania",
            "auth": "Nenhuma",
            "endpoints": [
                {
                    "path": "/prefeituras",
                    "descricao": "Lista todas as 224 prefeituras do Piauí",
                },
                {
                    "path": "/prefeituras/:nome",
                    "descricao": "Busca prefeituras por nome",
                },
                {
                    "path": "/prefeituras/:id/gestor",
                    "descricao": "Consulta prefeito(a) atual",
                },
                {
                    "path": "/despesas/:id",
                    "descricao": "Histórico anual de despesas de um município",
                },
                {
                    "path": "/despesas/:id/:exercicio/porFuncao",
                    "descricao": "Despesas por função de governo",
                },
                {
                    "path": "/despesas/total",
                    "descricao": "Total de despesas do estado por ano",
                },
                {
                    "path": "/receitas/:id/:exercicio",
                    "descricao": "Receitas detalhadas de um município",
                },
                {
                    "path": "/receitas/total",
                    "descricao": "Total de receitas do estado por ano",
                },
                {
                    "path": "/orgaos/lista/:exercicio",
                    "descricao": "Lista órgãos estaduais por exercício",
                },
                {
                    "path": "/credores/:id/:exercicio",
                    "descricao": "Top 10 credores de um município",
                },
            ],
        },
        ensure_ascii=False,
    )
