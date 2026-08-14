"""
Roteador de chunks para analistas especialistas.

Mapeia tipos de chunk (prefixos [TYPE]) para os analistas que os consomem.
Permite que cada analista receba apenas os chunks que lhe interessam.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa: analyst_id -> lista de prefixos de chunk que ele consome
# ---------------------------------------------------------------------------

CHUNK_TYPE_TO_ANALYST: dict[str, list[str]] = {
    "votacao": [
        "[VOTO]",
        "[DISCURSO_PLENARIO]",
    ],
    "perfil": [
        "[PERFIL]",
        "[PARLAMENTAR_RESUMO]",
        # Fase 3 (multi-cargo): dossiês de senador/governador/prefeito/vereador
        "[SENADOR]",
        "[GOVERNADOR]",
        "[PREFEITO]",
        "[VEREADOR]",
    ],
    "tematicas": [
        "[EMENDA]",
        "[EMENDA_DETALHE]",
        "[EMENDA_DISCRICIONARIA]",
        "[PROPOSICAO]",
        "[DISCURSO_PLENARIO]",
    ],
    "cruzamento": [
        # Todos os tipos — visao 360°
        "[VOTO]",
        "[EMENDA]",
        "[EMENDA_DETALHE]",
        "[PROPOSICAO]",
        "[DISCURSO_PLENARIO]",
        "[DIARIO_OFICIAL]",
        "[PERFIL]",
        "[CONEXAO_POLITICA]",
        "[EMENDA_DISCRICIONARIA]",
        "[COMPRAS_MUNICIPIO]",
        "[INDICADORES_SOCIAIS]",
        "[RISCO_JUDICIAL]",
        "[DEMOGRAFIA_MUNICIPIO]",
        "[MUNICIPIO_FINANCEIRO]",
        "[PARLAMENTAR_RESUMO]",
        "[BENEFICIARIO]",
        "[PREFEITO]",
        "[SENADOR]",
        "[FNDE_REPASSES]",
        "[INDICADORES_MUNICIPAL]",
        "[VEREADORES_RESUMO]",
        "[GOVERNADOR]",
        "[VEREADOR]",
    ],
    "rede_politica": [
        "[CONEXAO_POLITICA]",
        "[PREFEITO]",
        "[SENADOR]",
        "[GOVERNADOR]",
        "[VEREADOR]",
        "[VEREADORES_RESUMO]",
        "[ESTADO_FINANCEIRO]",
        "[EMENDA]",
        "[EMENDA_DETALHE]",
        "[DIARIO_OFICIAL]",
    ],
    "discursos": [
        "[DISCURSO_PLENARIO]",
    ],
    "anomalias": [
        "[EMENDA]",
        "[EMENDA_DETALHE]",
        "[CONEXAO_POLITICA]",
        "[RISCO_JUDICIAL]",
        "[COMPRAS_MUNICIPIO]",
        "[DIARIO_OFICIAL]",
        "[BENEFICIARIO]",
        "[DEMOGRAFIA_MUNICIPIO]",
        "[MUNICIPIO_FINANCEIRO]",
        "[FNDE_REPASSES]",
        "[INDICADORES_SOCIAIS]",
        "[VEREADORES_RESUMO]",
    ],
}

# ---------------------------------------------------------------------------
# Funcoes de roteamento
# ---------------------------------------------------------------------------


def filter_chunks_by_analyst(
    context_list: list[str],
    analyst_id: str,
) -> list[str]:
    """Filtra a lista de chunks para conter apenas os tipos que o analista consome.

    Args:
        context_list: Lista de chunks no formato "[TYPE] texto...".
        analyst_id: Identificador do analista.

    Returns:
        Lista filtrada de chunks (ordem original preservada).
    """
    prefixes = CHUNK_TYPE_TO_ANALYST.get(analyst_id, [])
    if not prefixes:
        # Se nao tem mapa especifico, retorna tudo
        log.warning(f"Analista '{analyst_id}' sem mapa de chunk types. Retornando todos.")
        return list(context_list)

    # "cruzamento" consome todos — atalho
    if analyst_id == "cruzamento":
        return list(context_list)

    filtered: list[str] = []
    for chunk in context_list:
        upper = chunk.upper()
        for prefix in prefixes:
            if upper.startswith(prefix):
                filtered.append(chunk)
                break

    # Prioridade de ordenação (Fase 2, plano 2.4): para o analista tematicas,
    # chunks do resumo por área ("Distribuição por área das emendas PIX" — que
    # traz os TOTAIS EXATOS R$ por objeto) sobem para o topo do contexto.
    # Antes isso era garantido apenas por busca dedicada no Qdrant
    # (_ensure_tematicas_area_summary), que agora vira fallback.
    if analyst_id == "tematicas":
        marker = "DISTRIBUIÇÃO POR ÁREA DAS EMENDAS PIX"
        com_marker = [c for c in filtered if marker in c.upper()]
        sem_marker = [c for c in filtered if marker not in c.upper()]
        if com_marker:
            log.info(
                f"[tematicas] {len(com_marker)} chunk(s) de resumo por área "
                f"priorizados no topo do contexto"
            )
            filtered = com_marker + sem_marker
    return filtered


def count_chunks_by_type(context_list: list[str]) -> dict[str, int]:
    """Conta chunks por tipo para diagnostico."""
    counts: dict[str, int] = {}
    for chunk in context_list:
        tipo = chunk.split("]")[0].lstrip("[") if "]" in chunk else "unknown"
        counts[tipo] = counts.get(tipo, 0) + 1
    return counts


def which_analysts_have_data(context_list: list[str]) -> list[str]:
    """Retorna lista de analyst_id que tem dados suficientes."""
    from src.analysts import ANALYST_REGISTRY

    active: list[str] = []
    for analyst_id, klass in ANALYST_REGISTRY.items():
        min_req = getattr(klass, "min_chunks", 1)
        filtered = filter_chunks_by_analyst(context_list, analyst_id)
        if len(filtered) >= min_req:
            active.append(analyst_id)
    return active
