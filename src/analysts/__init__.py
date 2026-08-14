"""
Pacote Multi-Analista RAG v8.

Substitui o prompt monolitico do rag_persona.py por N analistas especialistas,
cada um com prompt focado, subconjunto de chunks e quality check proprio.

Uso:
    from src.analysts import run_analyst_pipeline, assemble_dossier

    results = run_analyst_pipeline(deputado_id, nome, context_list)
    dossier = assemble_dossier(results)
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysts.base import AnalystResult

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry (definido ANTES dos imports para evitar circular imports)
# ---------------------------------------------------------------------------

ANALYST_REGISTRY: dict[str, type] = {}
"""Mapeia analyst_id → classe do analista (registrada via @register_analyst)."""


def register_analyst(klass: type) -> type:
    """Decorator que registra automaticamente cada analista no registry."""
    analyst_id = getattr(klass, "analyst_id", None)
    if not analyst_id:
        raise ValueError(f"Classe {klass.__name__} precisa de attribute analyst_id")
    ANALYST_REGISTRY[analyst_id] = klass
    log.debug(f"Analista registrado: {analyst_id} -> {klass.__name__}")
    return klass


# ---------------------------------------------------------------------------
# Import todos os analistas para registrar os decorators @register_analyst
# (os imports ficam DEPOIS de ANALYST_REGISTRY e register_analyst)
# ---------------------------------------------------------------------------
from src.analysts import (  # noqa: E402
    anomalias,  # noqa: F401, E402
    cruzamento,  # noqa: F401, E402
    discursos,  # noqa: F401, E402
    perfil,  # noqa: F401, E402
    rede_politica,  # noqa: F401, E402
    tematicas,  # noqa: F401, E402
    votacao,  # noqa: F401, E402
)

# ---------------------------------------------------------------------------
# Orquestrador
# ---------------------------------------------------------------------------


def get_active_analysts(
    context_list: list[str],
) -> list[tuple[str, type]]:
    """Retorna lista de (analyst_id, classe) que tem dados suficientes.

    Para cada analista registrado, verifica se ha ao menos min_chunks
    chunks do tipo requerido no context_list.
    """
    from src.analysts.router import filter_chunks_by_analyst

    active: list[tuple[str, type]] = []
    for analyst_id, klass in ANALYST_REGISTRY.items():
        min_req = getattr(klass, "min_chunks", 1)
        filtered = filter_chunks_by_analyst(context_list, analyst_id)
        if len(filtered) >= min_req:
            active.append((analyst_id, klass))
        else:
            log.info(
                f"Analista {analyst_id} pulado: apenas {len(filtered)} chunks " f"(min {min_req})"
            )
    return active


def _ensure_tematicas_area_summary(
    deputado_id: int,
    filtered: list[str],
    nome: str,
    tipo_politico: str = "deputado",
) -> list[str]:
    """Garante que o chunk "Distribuição por área das emendas PIX" (resumo por
    objeto/área, ref "Resumo por área (objeto)") esteja no contexto do analista
    tematicas.

    O prompt do tematicas manda TRANSCREVER literalmente os TOTAIS EXATOS por
    área desse chunk. Porém ele compete com dezenas/centenas de chunks [EMENDA]
    no RRF top-30 e frequentemente fica de fora do contexto (ex.: ANDRÉ só tinha
    3 de 235 chunks [EMENDA]; o resumo de área não estava entre eles). Sem ele,
    o modelo cai para os resumos por município e FABRICA valores (ANDRÉ 36.6,
    ALICE 0.0). Uma busca dedicada no Qdrant injeta o chunk no topo do contexto,
    de onde o analista (e o QC via _last_chunks) o enxerga.
    """
    marker = "Distribuição por área das emendas PIX"
    if any(marker in c for c in filtered):
        return _dedupe_emendas_com_resumo(filtered)

    try:
        from src.enrichers.rag_persona import search_context_qdrant

        results = search_context_qdrant(
            deputado_id,
            "Distribuição por área das emendas PIX por objeto de execução, "
            "total exato por área e municípios beneficiários",
            limit=5,
            chunk_types=["EMENDA", "EMENDA_DISCRICIONARIA"],
            tipo_politico=tipo_politico,
        )
        for text, _score in results:
            if marker in text:
                injected = [text] + list(filtered)
                log.info(
                    f"[tematicas] chunk 'Resumo por área (objeto)' injetado no "
                    f"topo do contexto ({len(filtered)} -> {len(injected)} chunks)"
                )
                return _dedupe_emendas_com_resumo(injected)
    except Exception as e:
        log.warning(f"[tematicas] falha ao injetar resumo por área: {e}")
    return list(filtered)


def _dedupe_emendas_com_resumo(filtered: list[str]) -> list[str]:
    """Remove chunks de emendas INDIVIDUAIS quando o resumo agregado por área
    ('Distribuição por área das emendas PIX') já está no contexto.

    Causa raiz (golden set 2026-08-10, ADOLFO VIANA QC 65.0): o analista
    tematicas recebia o resumo com TOTAIS EXATOS + dezenas de chunks [EMENDA]
    individuais; o modelo 3B ecoava a tabela inteira (27+ linhas repetidas)
    em vez de agregar as 3-5 áreas. O resumo é a fonte canônica dos valores —
    os chunks individuais são redundantes e induzem o eco.
    """
    marker = "Distribuição por área das emendas PIX"
    if not any(marker in c for c in filtered):
        return list(filtered)
    out: list[str] = []
    for c in filtered:
        if marker in c:
            out.append(c)
            continue
        # [EMENDA]/[EMENDA_DISCRICIONARIA] individuais são redundantes agora
        if c.startswith("[EMENDA]") or c.startswith("[EMENDA_DISCRICIONARIA]"):
            continue
        out.append(c)
    removed = len(filtered) - len(out)
    if removed:
        log.info(f"[tematicas] {removed} chunk(s) de emenda individual removido(s) "
                 f"após injeção do resumo por área ({len(filtered)} -> {len(out)})")
    return out


def run_analyst_pipeline(
    deputado_id: int,
    nome: str,
    context_list: list[str],
    llm_model: str = "",
    use_preparer: bool | None = None,
    tipo_politico: str = "deputado",
) -> list[AnalystResult]:
    """Executa todos os analistas ativos em paralelo (ThreadPoolExecutor).

    Cada analista recebe apenas os chunks do tipo que lhe interessa,
    gera sua secao via LLM, e faz quality check proprio.

    Fase 3 (2026-08-10): `tipo_politico` (deputado/senador/governador/
    prefeito/vereador) ajusta o vocabulário dos prompts (via cargo.py) e
    remove o analista `votacao` para cargos sem voto nominal legislativo
    (governador/prefeito).

    A paralelizacao usa max_workers=3 para nao sobrecarregar a GPU
    (o RLock interno do LocalAIManager serializa TODAS as transicoes de
    load/unload de modelos; a preparacao do briefing e quality check
    rodam em paralelo).

    Returns:
        Lista de AnalystResults (na ordem do registro).
    """
    from src.analysts.cargo import tem_votacao
    from src.analysts.router import filter_chunks_by_analyst

    # Ordem deterministica (v8: classificador+alinhamento -> votacao;
    # novo analista rede_politica entre cruzamento e discursos)
    analyst_order = [
        "votacao",
        "perfil",
        "tematicas",
        "cruzamento",
        "rede_politica",
        "discursos",
        "anomalias",
    ]

    # Cargos sem voto nominal legislativo (governador/prefeito): sem votacao.py
    if not tem_votacao(tipo_politico):
        analyst_order = [aid for aid in analyst_order if aid != "votacao"]
        log.info(f"[{tipo_politico}] analista 'votacao' desativado (sem voto nominal).")

    # Preparar briefing ÚNICO do dossiê (Fase 1 refactor 2026-08-10):
    # antes eram até 7 preparações (uma por analista); agora 1 chamada de
    # preparação com o contexto completo, e cada analista recebe o mesmo
    # briefing via shared_briefing. Analistas com use_preparer=False
    # (ex.: tematicas, data-first) continuam usando chunks crus.
    use_prep_effective = use_preparer
    if use_prep_effective is None:
        use_prep_effective = any(
            getattr(ANALYST_REGISTRY.get(aid), "use_preparer", True)
            for aid in analyst_order
            if ANALYST_REGISTRY.get(aid) is not None
        )

    shared_briefing = None
    if use_prep_effective:
        try:
            from src.analysts.preparer import PromptPreparer

            preparer = PromptPreparer()
            shared_briefing = preparer.prepare(
                chunks=context_list,
                analyst_persona=(
                    "Analistas especialistas em análise política, orçamentária "
                    "e de rede (cross-esferas)."
                ),
                section_title="DOSSIE COMPLETO",
                nome=nome,
            )
            log.info(
                f"Briefing único preparado para {nome}: "
                f"{shared_briefing.total_chars} chars "
                f"(validação: {'OK' if shared_briefing.validation_pass else 'FALHOU'})"
            )
        except Exception as e:
            log.warning(f"Falha ao preparar briefing único: {e}; analistas usam chunks crus.")

    # Preparar tarefas: cada analista ativo vira uma task
    tasks: list[tuple[str, type, list[str]]] = []
    for analyst_id in analyst_order:
        klass = ANALYST_REGISTRY.get(analyst_id)
        if klass is None:
            continue

        min_req = getattr(klass, "min_chunks", 1)
        filtered = filter_chunks_by_analyst(context_list, analyst_id)
        # Garantir que o resumo por área (totais exatos R$ por objeto) esteja no
        # contexto do tematicas — sem isso o modelo fabrica valores quando o
        # chunk fica fora do RRF top-30 (fix 2026-07-31).
        if analyst_id == "tematicas":
            filtered = _ensure_tematicas_area_summary(deputado_id, filtered, nome, tipo_politico)
        if len(filtered) < min_req:
            log.info(
                f"Analista {analyst_id} ({getattr(klass, 'section_title', '?')}) "
                f"pulado: {len(filtered)} chunks (min {min_req})"
            )
            continue

        tasks.append((analyst_id, klass, filtered))

    if not tasks:
        log.warning("Nenhum analista ativo para os dados disponiveis.")
        return []

    # Decidir paralelismo. Com parallel=1 no YAML do modelo backend, o
    # llama.cpp só processa 1 requisição por vez — enviar 2 simultâneas causa
    # 500 imediato. Verificar a config do modelo antes de decidir workers.
    max_workers = 1  # default seguro; sobe para 2 apenas se modelo suportar
    try:
        from config.settings import RAG_LLM_MODEL
        from src.models_config import get_model_parallel
        _model_name = llm_model or RAG_LLM_MODEL
        _parallel = get_model_parallel(_model_name)  # None = auto (LocalAI decide)
        if _parallel is None or _parallel >= 2:
            max_workers = 2
            log.debug(
                f"Modelo {_model_name} suporta parallel={_parallel} → "
                f"analistas em paralelo (max_workers=2)."
            )
        else:
            log.info(
                f"Modelo {_model_name} tem parallel={_parallel} no YAML → "
                f"analistas em SÉRIE (max_workers=1) para evitar 500s."
            )
    except Exception as _e:
        log.debug(f"Não foi possível ler parallel do modelo: {_e} → max_workers=1 (seguro)")

    if use_prep_effective and shared_briefing is None:
        try:
            from config.settings import RAG_LLM_MODEL
            from src.analysts.preparer import PREPARER_MODEL
            from src.localai_manager import _SAFETY_MARGIN_MIB, _TOTAL_VRAM_MIB
            from src.vram_tracker import get_vram_mib

            ana_model = llm_model or RAG_LLM_MODEL
            prep_vram = get_vram_mib(PREPARER_MODEL)
            ana_vram = get_vram_mib(ana_model)
            if prep_vram + ana_vram > _TOTAL_VRAM_MIB - _SAFETY_MARGIN_MIB:
                max_workers = 1
                log.info(
                    f"Preparer ({PREPARER_MODEL}, ~{prep_vram} MiB) + modelo de "
                    f"analise ({ana_model}, ~{ana_vram} MiB) nao cabem juntos em "
                    f"{_TOTAL_VRAM_MIB} MiB -> analistas em SERIE "
                    f"(evita deadlock de VRAM)."
                )
        except Exception as e:
            log.debug(f"Nao foi possivel avaliar co-residencia de VRAM: {e}")

    log.info(
        f"Executando {len(tasks)} analistas "
        f"({'em paralelo' if max_workers > 1 else 'em SERIE'} "
        f"max_workers={max_workers}) para {nome}..."
    )

    results: list[AnalystResult] = []
    # Pool de threads: compartilham GPU (transicoes serializadas pelo RLock do
    # LocalAIManager). max_workers=1 quando preparer+LLM nao co-residem.
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map: dict[concurrent.futures.Future, str] = {}

        for analyst_id, analyst_klass, filtered in tasks:
            log.info(
                f"  Enfileirando {analyst_id} ({getattr(analyst_klass, 'section_title', '?')}) "
                f"com {len(filtered)} chunks..."
            )

            def _run_analyst(
                _aid: str = analyst_id,
                _klass: type = analyst_klass,
                _ctx: list[str] = filtered,
                _briefing: object = shared_briefing,
            ) -> AnalystResult:
                try:
                    instance = _klass()
                    return instance.run(
                        context=_ctx,
                        nome=nome,
                        llm_model=llm_model,
                        use_preparer=use_preparer,
                        shared_briefing=_briefing,
                        tipo_politico=tipo_politico,
                        politico_id=deputado_id,
                    )
                except Exception as e:
                    log.error(f"Analista {_aid} falhou: {e}")
                    from src.analysts.base import AnalystResult as AR

                    return AR(
                        analyst_id=_aid,
                        section_title=getattr(_klass, "section_title", _aid),
                        content=f"*[Falha na geracao: {e}]*",
                        quality_ok=False,
                        quality_score=0.0,
                        duration=0.0,
                        chunks_used=[],
                    )

            future = executor.submit(_run_analyst)
            future_map[future] = analyst_id

        # Coletar resultados na ordem de lancamento
        results_map: dict[str, AnalystResult] = {}
        for future in concurrent.futures.as_completed(future_map):
            aid = future_map[future]
            try:
                result = future.result()
                results_map[aid] = result
                log.info(
                    f"  -> [{aid}] '{result.section_title}': "
                    f"QC={'OK' if result.quality_ok else 'FAIL'} "
                    f"({result.quality_score:.1f}/100) em {result.duration:.1f}s"
                )
            except Exception as e:
                log.error(f"Analista {aid} falhou: {e}")

    # Reordenar conforme analyst_order
    for analyst_id in analyst_order:
        r = results_map.get(analyst_id)
        if r is not None:
            results.append(r)

    return results


def assemble_dossier(results: list[AnalystResult]) -> str:
    """Concatena as secoes na ordem correta para formar o dossier final.

    Usa a ordem definida em ANALYST_ORDER.
    v8 (Fase 2): analistas podem retornar JSON estruturado
    {"secoes": [...]}; aqui renderizamos a narrativa markdown de volta
    (render_secoes_markdown), mantendo o formato do dossier inalterado.
    """
    from src.analysts.base import render_secoes_markdown

    ANALYST_ORDER = [
        "votacao",
        "perfil",
        "tematicas",
        "cruzamento",
        "rede_politica",
        "discursos",
        "anomalias",
    ]

    # Mapa analyst_id -> result
    result_map = {r.analyst_id: r for r in results}

    parts: list[str] = []
    for _idx, analyst_id in enumerate(ANALYST_ORDER, start=1):
        r = result_map.get(analyst_id)
        if r is None:
            continue
        # Se falhou, ainda inclui (o texto de erro vai)
        section = render_secoes_markdown(r.content).strip()
        if not section:
            section = "*Dados insuficientes para esta seção.*"
        # Hardening 2026-08-14: QC reprovado fica visível no dossiê final —
        # sem isso uma seção que falhou parece ter sido aprovada.
        if not r.quality_ok:
            section = (
                f"> ⚠️ **QC reprovado** (score {r.quality_score:.1f}/100) — "
                f"seção com qualidade insuficiente, valide antes de usar.\n\n{section}"
            )
        parts.append(f"### {r.section_title}\n\n{section}")

    return "\n\n---\n\n".join(parts)


def calculate_global_score(results: list[AnalystResult]) -> tuple[float, bool]:
    """Calcula score global ponderado e decide aprovacao.

    Pesos (v8 — classificador+alinhamento fundidos em votacao 25%;
    novo analista rede_politica com 10%):
        votacao: 25%
        perfil: 10%
        tematicas: 20%
        cruzamento: 20%
        rede_politica: 10%
        discursos: 10%
        anomalias: 5%
    """
    PESOS = {
        "votacao": 0.25,
        "perfil": 0.10,
        "tematicas": 0.20,
        "cruzamento": 0.20,
        "rede_politica": 0.10,
        "discursos": 0.10,
        "anomalias": 0.05,
    }

    score_total = 0.0
    peso_total = 0.0

    # Hardening 2026-08-14: se NENHUMA seção passou no QC, o dossiê não pode
    # ser aprovado — média de reprovados não deve virar "aprovação".
    if results and not any(r.quality_ok for r in results):
        return 0.0, False

    for r in results:
        peso = PESOS.get(r.analyst_id, 0.10)
        score_total += r.quality_score * peso
        peso_total += peso

    if peso_total == 0:
        return 0.0, False

    score = score_total / peso_total
    aprovado = score >= 70.0
    return round(score, 1), aprovado


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

__all__ = [
    "ANALYST_REGISTRY",
    "register_analyst",
    "get_active_analysts",
    "run_analyst_pipeline",
    "assemble_dossier",
    "calculate_global_score",
]
