"""Resources for the TransfereGov feature — static reference data for LLM context."""

from __future__ import annotations

import json


def info_api() -> str:
    """Informações sobre a API do TransfereGov e como usar."""
    data = {
        "nome": "API TransfereGov (PostgREST)",
        "url_base": "https://api.transferegov.gestao.gov.br",
        "autenticacao": "Nenhuma (API pública)",
        "formato": "JSON array (sem wrapper)",
        "paginacao": "limit/offset via query params",
        "filtros": {
            "descricao": "PostgREST: column=operator.value",
            "operadores": ["eq", "neq", "gt", "lt", "gte", "lte", "like", "ilike", "in"],
            "exemplos": [
                "ano_plano_acao=eq.2024",
                "nome_parlamentar_emenda_plano_acao=ilike.*nome*",
                "uf_beneficiario_plano_acao=eq.PI",
            ],
        },
        "endpoint_principal": "/transferenciasespeciais/plano_acao_especial",
        "colunas_principais": [
            "id_plano_acao",
            "ano_plano_acao",
            "numero_emenda_parlamentar_plano_acao",
            "nome_parlamentar_emenda_plano_acao",
            "valor_custeio_plano_acao",
            "valor_investimento_plano_acao",
            "nome_beneficiario_plano_acao",
            "uf_beneficiario_plano_acao",
            "situacao_plano_acao",
        ],
    }
    return json.dumps(data, ensure_ascii=False)
