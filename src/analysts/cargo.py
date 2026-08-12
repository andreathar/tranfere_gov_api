"""Metadados de cargo político para prompts dos analistas (RAG v8, Fase 3).

Centraliza o vocabulário PT-BR (singular/plural) e as capacidades de cada
cargo usado pelos analistas — evita hardcode de "deputado" nos prompts
quando o dossier é de senador/governador/prefeito/vereador.
"""

from __future__ import annotations

from typing import Any

CARGO_INFO: dict[str, dict[str, Any]] = {
    "deputado": {
        "singular": "deputado federal",
        "plural": "deputados federais",
        "casa": "Câmara dos Deputados",
        "tem_votacao": True,   # votações nominais no plenário
        "unidade": "deputado",
    },
    "senador": {
        "singular": "senador",
        "plural": "senadores",
        "casa": "Senado Federal",
        "tem_votacao": True,   # votações nominais no plenário
        "unidade": "senador",
    },
    "governador": {
        "singular": "governador",
        "plural": "governadores",
        "casa": "executivo estadual",
        "tem_votacao": False,  # não há voto nominal legislativo
        "unidade": "governador",
    },
    "prefeito": {
        "singular": "prefeito",
        "plural": "prefeitos",
        "casa": "executivo municipal",
        "tem_votacao": False,
        "unidade": "prefeito",
    },
    "vereador": {
        "singular": "vereador",
        "plural": "vereadores",
        "casa": "Câmara Municipal",
        "tem_votacao": True,   # votações na câmara municipal
        "unidade": "vereador",
    },
}

DEFAULT_CARGO = CARGO_INFO["deputado"]


def get_cargo(tipo_politico: str) -> dict[str, Any]:
    """Retorna metadados do cargo (com fallback para deputado)."""
    return CARGO_INFO.get(tipo_politico, DEFAULT_CARGO)


def tem_votacao(tipo_politico: str) -> bool:
    """Cargos com voto nominal legislativo (votacao.py ativa só para eles)."""
    return bool(get_cargo(tipo_politico).get("tem_votacao"))
