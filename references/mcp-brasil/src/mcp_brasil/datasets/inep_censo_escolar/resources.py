"""Reference data for the inep_censo_escolar feature."""

from __future__ import annotations

import json

from . import DATASET_SPEC
from .constants import ANO_COBERTURA, DEPENDENCIAS, LOCALIZACOES, SITUACOES


def schema_tabela() -> str:
    """Schema resumido — as 370+ colunas do arquivo, destaque das principais."""
    colunas_destaque = [
        {"name": "CO_ENTIDADE", "tipo": "BIGINT", "desc": "Código INEP da escola (PK)"},
        {"name": "NO_ENTIDADE", "tipo": "VARCHAR", "desc": "Nome da escola"},
        {"name": "NU_ANO_CENSO", "tipo": "INT", "desc": "Ano do censo"},
        {"name": "SG_UF", "tipo": "VARCHAR", "desc": "Sigla da UF"},
        {"name": "NO_UF", "tipo": "VARCHAR", "desc": "Nome da UF"},
        {"name": "NO_MUNICIPIO", "tipo": "VARCHAR", "desc": "Município"},
        {"name": "CO_MUNICIPIO", "tipo": "BIGINT", "desc": "Código IBGE do município"},
        {"name": "TP_DEPENDENCIA", "tipo": "INT", "desc": "1=Fed, 2=Est, 3=Mun, 4=Priv"},
        {"name": "TP_LOCALIZACAO", "tipo": "INT", "desc": "1=Urbana, 2=Rural"},
        {
            "name": "TP_SITUACAO_FUNCIONAMENTO",
            "tipo": "INT",
            "desc": "1=Ativa, 2=Paralisada, 3=Extinta, 4=Nova",
        },
        {"name": "DS_ENDERECO", "tipo": "VARCHAR", "desc": "Endereço"},
        {"name": "NO_BAIRRO", "tipo": "VARCHAR", "desc": "Bairro"},
        {"name": "CO_CEP", "tipo": "VARCHAR", "desc": "CEP"},
        {"name": "IN_AGUA_POTAVEL", "tipo": "INT", "desc": "0/1 — tem água potável"},
        {"name": "IN_ENERGIA_REDE_PUBLICA", "tipo": "INT", "desc": "0/1 — energia pública"},
        {"name": "IN_INTERNET", "tipo": "INT", "desc": "0/1 — tem internet"},
        {"name": "IN_BIBLIOTECA", "tipo": "INT", "desc": "0/1"},
        {"name": "IN_QUADRA_ESPORTES", "tipo": "INT", "desc": "0/1"},
        {"name": "IN_LABORATORIO_CIENCIAS", "tipo": "INT", "desc": "0/1"},
        {"name": "IN_LABORATORIO_INFORMATICA", "tipo": "INT", "desc": "0/1"},
        {"name": "IN_REFEITORIO", "tipo": "INT", "desc": "0/1"},
        {"name": "QT_MAT_BAS", "tipo": "INT", "desc": "Matrículas educação básica"},
    ]
    return json.dumps(
        {
            "tabela": DATASET_SPEC.table,
            "colunas_destaque": colunas_destaque,
            "total_colunas": "370+ (use DESCRIBE no DuckDB para lista completa)",
            "prefixos": {
                "NO_": "Nome (texto)",
                "CO_": "Código",
                "SG_": "Sigla",
                "TP_": "Tipo (enum)",
                "IN_": "Indicador binário 0/1",
                "NU_": "Número",
                "DT_": "Data",
                "DS_": "Descrição/string",
                "QT_": "Quantidade",
            },
            "origem": DATASET_SPEC.source,
        },
        ensure_ascii=False,
        indent=2,
    )


def catalogo_valores() -> str:
    """Valores típicos de colunas enum."""
    return json.dumps(
        {"dependencias": DEPENDENCIAS, "localizacoes": LOCALIZACOES, "situacoes": SITUACOES},
        ensure_ascii=False,
        indent=2,
    )


def info_dataset() -> str:
    info = {
        "id": DATASET_SPEC.id,
        "cobertura": f"Educação Básica, ano {ANO_COBERTURA}",
        "tamanho_aproximado": f"{DATASET_SPEC.approx_size_mb} MB descomprimido",
        "ttl_dias": DATASET_SPEC.ttl_days,
        "fonte": DATASET_SPEC.source,
        "ativacao": "Defina MCP_BRASIL_DATASETS=inep_censo_escolar no .env",
        "primeira_consulta": (
            "Primeira tool dispara download (~32 MB zipped, 3-5 min com "
            "descompressão). Subsequentes usam cache DuckDB."
        ),
        "lgpd": "Dataset de escolas (institucional) — não contém PII de alunos/docentes.",
    }
    return json.dumps(info, ensure_ascii=False, indent=2)
