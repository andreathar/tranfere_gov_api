"""Constants for IBAMA feature."""

from __future__ import annotations

IBAMA_CKAN_BASE = "https://dadosabertos.ibama.gov.br/api/3/action"

DATASETS_CHAVE: dict[str, str] = {
    "fiscalizacao-auto-de-infracao": "Autos de infração lavrados pelo IBAMA",
    "pessoas-juridicas-inscritas-no-ctf-app": (
        "PJ inscritas no CTF/APP (atividades potencialmente poluidoras)"
    ),
    "arrecadacao-com-tcfa": "Arrecadação com Taxa de Controle e Fiscalização Ambiental",
    "arrecadacao-de-multas-ambientais-bens-tutelados": "Arrecadação de multas ambientais",
    "ato-declaratorio-ambiental-ada": "Ato Declaratório Ambiental (ADA) — imóveis rurais",
    "antropizacao-dos-biomas-extra-amazonicos": "Antropização dos biomas extra-amazônicos",
}
