"""Static reference data for the anp_precos feature."""

from __future__ import annotations

import json

from . import DATASET_SPEC
from .constants import ANO_COBERTURA, COLUMN_NAMES, PRODUTOS_COMUNS


def schema_tabela() -> str:
    """Schema da tabela precos_combustiveis."""
    cols = [
        {"name": "regiao", "tipo": "VARCHAR", "desc": "Sigla da região (N, NE, SE, S, CO)"},
        {"name": "estado", "tipo": "VARCHAR", "desc": "Sigla da UF"},
        {"name": "municipio", "tipo": "VARCHAR", "desc": "Nome do município"},
        {"name": "revenda", "tipo": "VARCHAR", "desc": "Razão social do posto"},
        {"name": "cnpj_revenda", "tipo": "VARCHAR", "desc": "CNPJ (PII — mascarado)"},
        {"name": "rua", "tipo": "VARCHAR", "desc": "Nome da rua"},
        {"name": "numero", "tipo": "VARCHAR", "desc": "Número"},
        {"name": "complemento", "tipo": "VARCHAR", "desc": "Complemento do endereço"},
        {"name": "bairro", "tipo": "VARCHAR", "desc": "Bairro"},
        {"name": "cep", "tipo": "VARCHAR", "desc": "CEP"},
        {"name": "produto", "tipo": "VARCHAR", "desc": "Tipo de combustível"},
        {"name": "data_coleta", "tipo": "VARCHAR", "desc": "Data (DD/MM/YYYY)"},
        {"name": "valor_venda", "tipo": "DOUBLE", "desc": "Preço de venda ao consumidor"},
        {"name": "valor_compra", "tipo": "DOUBLE", "desc": "Preço de aquisição pela revenda"},
        {"name": "unidade", "tipo": "VARCHAR", "desc": "R$/litro ou R$/13kg"},
        {"name": "bandeira", "tipo": "VARCHAR", "desc": "Bandeira do posto"},
    ]
    return json.dumps(
        {
            "tabela": DATASET_SPEC.table,
            "colunas": cols,
            "cobertura": f"{ANO_COBERTURA} integral (jan-dez)",
            "origem": DATASET_SPEC.source,
        },
        ensure_ascii=False,
        indent=2,
    )


def catalogo_valores() -> str:
    """Valores típicos observados em campos categóricos."""
    return json.dumps(
        {
            "produtos_comuns": list(PRODUTOS_COMUNS),
            "regioes": ["N", "NE", "SE", "S", "CO"],
            "observacoes": [
                "valor_venda é o preço ao consumidor (o mais relevante)",
                "unidade costuma ser 'R$/l' para líquidos e 'R$/13Kg' para GLP",
                "date coleta em formato DD/MM/YYYY — use SUBSTR para filtrar por ano/mês",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def info_dataset() -> str:
    """Metadados do dataset e orientações."""
    info = {
        "id": DATASET_SPEC.id,
        "cobertura": f"{ANO_COBERTURA} — 36 CSVs mensais (gasolina/etanol, diesel/GNV, GLP)",
        "tamanho_aproximado": f"{DATASET_SPEC.approx_size_mb} MB agregado",
        "ttl_dias": DATASET_SPEC.ttl_days,
        "fonte": DATASET_SPEC.source,
        "ativacao": "Defina MCP_BRASIL_DATASETS=anp_precos no seu .env",
        "primeira_consulta": (
            "A primeira tool executada dispara download (~2-5 min para 36 arquivos). "
            "Subsequentes usam cache local DuckDB em ms."
        ),
        "lgpd": "CNPJ da revenda é PII — mascarado por padrão.",
        "colunas": COLUMN_NAMES,
    }
    return json.dumps(info, ensure_ascii=False, indent=2)
