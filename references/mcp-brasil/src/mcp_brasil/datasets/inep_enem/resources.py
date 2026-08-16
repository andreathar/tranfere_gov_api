"""Reference data for the inep_enem feature."""

from __future__ import annotations

import json

from . import DATASET_SPEC
from .constants import ANO_COBERTURA, COR_RACA, ESCOLA, LINGUA, PRESENCA, SEXOS, STATUS_REDACAO


def schema_tabela() -> str:
    """Schema das principais colunas dos microdados ENEM."""
    cols = [
        {"name": "NU_INSCRICAO", "tipo": "BIGINT", "desc": "Identificador do inscrito (PII)"},
        {"name": "NU_ANO", "tipo": "INT", "desc": "Ano da edição"},
        {"name": "TP_FAIXA_ETARIA", "tipo": "INT", "desc": "Faixa etária (1-20)"},
        {"name": "TP_SEXO", "tipo": "VARCHAR", "desc": "M/F"},
        {"name": "TP_COR_RACA", "tipo": "INT", "desc": "0-6 cor/raça"},
        {"name": "TP_ESCOLA", "tipo": "INT", "desc": "1=Não resp, 2=Pública, 3=Privada"},
        {"name": "SG_UF_ESC", "tipo": "VARCHAR", "desc": "UF da escola"},
        {"name": "SG_UF_PROVA", "tipo": "VARCHAR", "desc": "UF onde fez a prova"},
        {"name": "NO_MUNICIPIO_PROVA", "tipo": "VARCHAR", "desc": "Município da prova"},
        {"name": "TP_PRESENCA_CN", "tipo": "INT", "desc": "0/1/2 — presença dia 2"},
        {"name": "TP_PRESENCA_CH", "tipo": "INT", "desc": "Presença dia 1 humanas"},
        {"name": "TP_PRESENCA_LC", "tipo": "INT", "desc": "Presença dia 1 linguagens"},
        {"name": "TP_PRESENCA_MT", "tipo": "INT", "desc": "Presença dia 2 matemática"},
        {"name": "NU_NOTA_CN", "tipo": "DOUBLE", "desc": "Nota Ciências da Natureza"},
        {"name": "NU_NOTA_CH", "tipo": "DOUBLE", "desc": "Nota Ciências Humanas"},
        {"name": "NU_NOTA_LC", "tipo": "DOUBLE", "desc": "Nota Linguagens e Códigos"},
        {"name": "NU_NOTA_MT", "tipo": "DOUBLE", "desc": "Nota Matemática"},
        {"name": "NU_NOTA_REDACAO", "tipo": "DOUBLE", "desc": "Nota da Redação (0-1000)"},
        {"name": "TP_LINGUA", "tipo": "INT", "desc": "0=Inglês, 1=Espanhol"},
        {"name": "Q001-Q025", "tipo": "VARCHAR", "desc": "Questionário socioeconômico"},
    ]
    return json.dumps(
        {
            "tabela": DATASET_SPEC.table,
            "ano": ANO_COBERTURA,
            "colunas_destaque": cols,
            "origem": DATASET_SPEC.source,
            "observacoes": [
                "Presença = 1 (presente), 0 (faltou), 2 (eliminado)",
                "Para análises de nota sempre filtrar TP_PRESENCA_CN=1 AND TP_PRESENCA_LC=1",
                "NU_INSCRICAO é identificador — mascarado por padrão (PII)",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def catalogo_valores() -> str:
    """Valores dos enums principais."""
    return json.dumps(
        {
            "TP_SEXO": SEXOS,
            "TP_COR_RACA": COR_RACA,
            "TP_ESCOLA": ESCOLA,
            "TP_PRESENCA": PRESENCA,
            "TP_LINGUA": LINGUA,
            "TP_STATUS_REDACAO": STATUS_REDACAO,
        },
        ensure_ascii=False,
        indent=2,
    )


def info_dataset() -> str:
    info = {
        "id": DATASET_SPEC.id,
        "cobertura": f"ENEM {ANO_COBERTURA}",
        "tamanho_aproximado": "~520 MB ZIP, ~2,5 GB descomprimido",
        "ttl_dias": DATASET_SPEC.ttl_days,
        "fonte": DATASET_SPEC.source,
        "ativacao": "Defina MCP_BRASIL_DATASETS=inep_enem no .env",
        "primeira_consulta": (
            "Download pesado. Recomendado rodar em server com ≥4 GB RAM e "
            "≥5 GB livres em disco durante ingestão."
        ),
        "lgpd": "NU_INSCRICAO (identificador) é PII — mascarado por padrão.",
    }
    return json.dumps(info, ensure_ascii=False, indent=2)
