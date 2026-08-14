"""Coletor de métricas de eficiência do RAG v7.

Este módulo monta um golden set factual dinâmico a partir do PostgreSQL,
executa a recuperação real do RAG (Qdrant + RRF via ``rag_persona``), gera
respostas com LocalAI e persiste uma execução nas tabelas
``rag_efficiency_runs`` e ``rag_efficiency_metrics``.

Fórmula do indicador para investidores:

``global_efficiency_score`` (0-100) = 40% média de ``hit_rate_at_k`` +
40% média de ``faithfulness_score`` + 20% média de
``context_utilization_score``.

Uso:
    python3 -m src.enrichers.rag_efficiency_collector --nome "AFONSO FLORENCE"
"""

from __future__ import annotations

import argparse
import logging
import re
import string
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from config.settings import RAG_LLM_MODEL
from src.db_utils import get_connection
from src.enrichers.rag_persona import _find_politico_por_tipo, search_context_multiquery
from src.localai_client import get_localai_client

TipoPolitico = Literal["deputado", "senador", "governador", "prefeito", "vereador"]

LOG_FORMAT: Final = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
TIPOS_POLITICOS: Final[tuple[TipoPolitico, ...]] = (
    "deputado",
    "senador",
    "governador",
    "prefeito",
    "vereador",
)
_SISTEMA: Final = (
    "Você é um analista imparcial de dados públicos. Responda objetivamente em PT-BR. "
    "Se não houver informação suficiente no contexto, responda 'não sei'."
)
_SISTEMA_JUIZ: Final = (
    "Você é um juiz imparcial de consistência factual. Responda apenas com um número "
    "decimal entre 0 e 1."
)
_PONTUACAO_TRANS: Final = str.maketrans("", "", string.punctuation + "“”‘’—–…ºª")
_FLOAT_RE: Final = re.compile(r"\d*\.?\d+")
_NUM_TOKEN_RE: Final = re.compile(r"[^\d,.-]")

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Politico:
    """Identificação mínima do político avaliado."""

    politico_id: int
    nome: str
    tipo: TipoPolitico
    parlamentar_id: int | None = None


@dataclass(frozen=True, slots=True)
class GoldenQuestion:
    """Pergunta factual com resposta esperada resolvida no banco."""

    question: str
    expected_answer: str
    numeric_expected: float | None = None


@dataclass(frozen=True, slots=True)
class QuestionMetric:
    """Métricas calculadas para uma pergunta do golden set."""

    politico: Politico
    question: GoldenQuestion
    retrieved_chunks_count: int
    hit_rate_at_k: float
    mrr_at_k: float
    actual_answer: str
    faithfulness_score: float
    context_utilization_score: float


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Resumo agregado de uma execução."""

    model_name: str
    golden_set_version: str
    total_questions: int
    global_efficiency_score: float
    avg_retrieval_hit_rate: float
    avg_generation_faithfulness: float
    avg_context_utilization: float


@dataclass(frozen=True, slots=True)
class CliArgs:
    """Argumentos validados da CLI."""

    politico_id: int | None
    tipo: TipoPolitico
    nome: str | None
    limit_politicos: int
    modelo: str
    golden_set_version: str
    dry_run: bool
    verbose: bool
    ano: int | None


def _normalize(text: object) -> str:
    """Normaliza texto para comparação lexical tolerante."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    without_punctuation = without_accents.lower().translate(_PONTUACAO_TRANS)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def _contains_bounded(haystack: str, needle: str) -> bool:
    """Contém o trecho com fronteira de palavra (evita falso positivo '3' dentro de '13')."""
    return bool(re.search(rf"\b{re.escape(needle)}\b", haystack))


def _parse_number(value: object) -> float | None:
    """Converte número em formato BR/US para float, quando possível."""
    raw = str(value).strip()
    if not raw:
        return None
    cleaned = _NUM_TOKEN_RE.sub("", raw)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned or "," in cleaned:
        normalized = cleaned.replace(".", "").replace(",", ".")
    else:
        normalized = cleaned.replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def _format_brl(value: float) -> str:
    """Formata valor monetário em PT-BR sem depender de locale."""
    us = f"{value:,.2f}"
    br = us.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {br}"


def _as_non_empty(value: object) -> str | None:
    """Retorna string limpa somente se houver conteúdo útil."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_positive_float(value: object) -> float | None:
    """Retorna float positivo para métricas monetárias ou contagens relevantes."""
    if value is None:
        return None
    number = float(value) if isinstance(value, Decimal | int | float) else _parse_number(value)
    if number is None or number <= 0:
        return None
    return number


def _contains_expected(chunk: str, expected: GoldenQuestion) -> bool:
    """Verifica se um chunk contém a resposta esperada, com tolerância numérica."""
    expected_number = expected.numeric_expected
    if expected_number is not None:
        for token in re.findall(r"R?\$?\s*[\d.,]+", chunk):
            found = _parse_number(token)
            if found is None:
                continue
            tolerance = max(abs(expected_number) * 0.01, 0.01)
            if abs(found - expected_number) <= tolerance:
                return True
    normalized_chunk = _normalize(chunk)
    normalized_expected = _normalize(expected.expected_answer)
    return bool(normalized_expected) and normalized_expected in normalized_chunk


def _bigrams(text: str) -> set[tuple[str, str]]:
    """Extrai bigramas de palavras do texto normalizado."""
    tokens = _normalize(text).split()
    return set(zip(tokens, tokens[1:], strict=False))


def _clamp01(value: float) -> float:
    """Limita uma métrica ao intervalo 0..1."""
    return max(0.0, min(1.0, value))


def _mean(values: Sequence[float]) -> float:
    """Média simples segura para sequências possivelmente vazias."""
    return sum(values) / len(values) if values else 0.0


def _fetchone(query: str, params: Sequence[object]) -> tuple[object, ...] | None:
    """Executa SELECT de uma linha usando o pool centralizado."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    return tuple(row) if row else None


def _fetchall(query: str, params: Sequence[object]) -> list[tuple[object, ...]]:
    """Executa SELECT de múltiplas linhas usando o pool centralizado."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [tuple(row) for row in rows]


def _resolve_deputado(nome: str | None, politico_id: int | None) -> Politico | None:
    """Resolve deputado por ID Câmara/parlamentar ou por nome."""
    if politico_id is not None:
        row = _fetchone(
            """
            SELECT deputado_id, nome, parlamentar_id
            FROM parlamentares_dados
            WHERE deputado_id = %s OR parlamentar_id = %s
            LIMIT 1
            """,
            (politico_id, politico_id),
        )
    elif nome:
        row = _fetchone(
            """
            SELECT deputado_id, nome, parlamentar_id
            FROM parlamentares_dados
            WHERE nome ILIKE %s OR nome_urna ILIKE %s
            LIMIT 1
            """,
            (f"%{nome}%", f"%{nome}%"),
        )
    else:
        row = None
    if row is None:
        return None
    parlamentar_raw = row[2]
    parlamentar_id = int(str(parlamentar_raw)) if parlamentar_raw is not None else None
    return Politico(
        politico_id=int(str(row[0])),
        nome=str(row[1]),
        tipo="deputado",
        parlamentar_id=parlamentar_id,
    )


def _resolve_non_deputado(tipo: TipoPolitico, nome: str | None, politico_id: int | None) -> Politico | None:
    """Resolve cargos não-deputado reaproveitando o resolvedor do RAG."""
    resolved_id, resolved_name, parlamentar_id = _find_politico_por_tipo(
        tipo,
        nome or "",
        politico_id,
    )
    if resolved_id is None or resolved_name is None:
        return None
    return Politico(
        politico_id=int(resolved_id),
        nome=str(resolved_name),
        tipo=tipo,
        parlamentar_id=int(parlamentar_id) if parlamentar_id is not None else None,
    )


def resolve_politico(tipo: TipoPolitico, nome: str | None, politico_id: int | None) -> Politico | None:
    """Resolve político de qualquer tipo suportado."""
    if tipo == "deputado":
        return _resolve_deputado(nome, politico_id)
    return _resolve_non_deputado(tipo, nome, politico_id)


def _top_deputados(limit: int) -> list[Politico]:
    """Seleciona top-N deputados por valor total de emendas PIX."""
    rows = _fetchall(
        """
        SELECT pd.deputado_id, pd.nome, pd.parlamentar_id
        FROM parlamentares_dados pd
        JOIN planos_acao pa ON pa.parlamentar_id = pd.parlamentar_id
        WHERE pd.deputado_id IS NOT NULL AND pd.parlamentar_id IS NOT NULL
        GROUP BY pd.deputado_id, pd.nome, pd.parlamentar_id
        ORDER BY SUM(COALESCE(pa.valor_total, 0)) DESC
        LIMIT %s
        """,
        (limit,),
    )
    return [
        Politico(
            politico_id=int(str(row[0])),
            nome=str(row[1]),
            tipo="deputado",
            parlamentar_id=int(str(row[2])),
        )
        for row in rows
    ]


def _append_text_question(questions: list[GoldenQuestion], question: str, value: object) -> None:
    """Adiciona pergunta textual se a resposta foi resolvida."""
    answer = _as_non_empty(value)
    if answer is not None:
        questions.append(GoldenQuestion(question=question, expected_answer=answer))


def _append_count_question(questions: list[GoldenQuestion], question: str, value: object) -> None:
    """Adiciona pergunta de contagem se o total for positivo."""
    number = _as_positive_float(value)
    if number is not None:
        answer = str(int(number)) if number.is_integer() else str(number)
        questions.append(GoldenQuestion(question=question, expected_answer=answer, numeric_expected=number))


def _append_money_question(questions: list[GoldenQuestion], question: str, value: object) -> None:
    """Adiciona pergunta monetária se o total for positivo."""
    number = _as_positive_float(value)
    if number is not None:
        questions.append(
            GoldenQuestion(question=question, expected_answer=_format_brl(number), numeric_expected=number)
        )


def _ano_filter(ano: int | None) -> tuple[str, tuple[object, ...]]:
    """Monta filtro opcional por ano de emenda."""
    if ano is None:
        return "", ()
    return " AND emenda_ano = %s", (ano,)


def _golden_deputado(politico: Politico, ano: int | None) -> list[GoldenQuestion]:
    """Monta golden set de deputado."""
    questions: list[GoldenQuestion] = []
    row = _fetchone(
        "SELECT sigla_partido, uf FROM parlamentares_dados WHERE deputado_id = %s LIMIT 1",
        (politico.politico_id,),
    )
    if row is not None:
        _append_text_question(questions, "Qual o partido político do deputado?", row[0])
        _append_text_question(questions, "Qual a UF do deputado?", row[1])
    if politico.parlamentar_id is None:
        return questions

    filtro_ano, params_ano = _ano_filter(ano)
    params = (politico.parlamentar_id, *params_ano)
    count_row = _fetchone(
        f"SELECT COUNT(*) FROM planos_acao WHERE parlamentar_id = %s{filtro_ano}",
        params,
    )
    if count_row is not None:
        _append_count_question(questions, "Quantas emendas PIX o deputado enviou?", count_row[0])
    total_row = _fetchone(
        f"SELECT SUM(valor_total) FROM planos_acao WHERE parlamentar_id = %s{filtro_ano}",
        params,
    )
    if total_row is not None:
        _append_money_question(questions, "Qual o total em reais das emendas PIX do deputado?", total_row[0])
    top_row = _fetchone(
        f"""
        SELECT b.nome
        FROM planos_acao pa
        JOIN beneficiarios b ON b.beneficiario_id = pa.beneficiario_id
        WHERE pa.parlamentar_id = %s{filtro_ano}
        GROUP BY b.nome
        ORDER BY SUM(COALESCE(pa.valor_total, 0)) DESC
        LIMIT 1
        """,
        params,
    )
    if top_row is not None:
        _append_text_question(
            questions,
            "Qual o principal município beneficiado pelas emendas do deputado?",
            top_row[0],
        )
    impedido_row = _fetchone(
        f"""
        SELECT COUNT(*)
        FROM planos_acao
        WHERE parlamentar_id = %s AND plano_acao_situacao = 'IMPEDIDO'{filtro_ano}
        """,
        params,
    )
    if impedido_row is not None:
        _append_count_question(
            questions,
            "Quantas emendas do deputado estão com situação IMPEDIDO?",
            impedido_row[0],
        )
    return questions


def _golden_senador(politico: Politico, ano: int | None) -> list[GoldenQuestion]:
    """Monta golden set de senador com as colunas existentes."""
    questions: list[GoldenQuestion] = []
    row = _fetchone(
        "SELECT sigla_partido, uf FROM senadores_dados WHERE senador_codigo = %s LIMIT 1",
        (politico.politico_id,),
    )
    if row is not None:
        _append_text_question(questions, "Qual o partido político do senador?", row[0])
        _append_text_question(questions, "Qual a UF do senador?", row[1])
    filtro_ano, params_ano = _ano_filter(ano)
    total_row = _fetchone(
        f"SELECT SUM(valor_total) FROM planos_acao WHERE parlamentar_id = %s{filtro_ano}",
        (politico.politico_id, *params_ano),
    )
    if total_row is not None:
        _append_money_question(questions, "Qual o total em reais das emendas PIX do senador?", total_row[0])
    return questions


def _golden_governador(politico: Politico) -> list[GoldenQuestion]:
    """Monta golden set de governador."""
    questions: list[GoldenQuestion] = []
    row = _fetchone(
        "SELECT sigla_partido, uf FROM governadores_dados WHERE uf = %s OR nome_governador = %s LIMIT 1",
        (politico.nome, politico.nome),
    )
    if row is not None:
        _append_text_question(questions, "Qual o partido político do governador?", row[0])
        _append_text_question(questions, "Qual a UF do governador?", row[1])
    return questions


def _golden_prefeito(politico: Politico) -> list[GoldenQuestion]:
    """Monta golden set de prefeito."""
    questions: list[GoldenQuestion] = []
    row = _fetchone(
        "SELECT sigla_partido, municipio_nome FROM prefeitos_dados WHERE municipio_id = %s LIMIT 1",
        (politico.politico_id,),
    )
    if row is not None:
        _append_text_question(questions, "Qual o partido político do prefeito?", row[0])
        _append_text_question(questions, "Qual o município do prefeito?", row[1])
    return questions


def _golden_vereador(politico: Politico) -> list[GoldenQuestion]:
    """Monta golden set de vereador."""
    questions: list[GoldenQuestion] = []
    row = _fetchone(
        "SELECT sigla_partido, municipio_nome FROM vereadores_dados WHERE sq_candidato = %s LIMIT 1",
        (politico.politico_id,),
    )
    if row is not None:
        _append_text_question(questions, "Qual o partido político do vereador?", row[0])
        _append_text_question(questions, "Qual o município do vereador?", row[1])
    return questions


def build_golden_set(politico: Politico, ano: int | None) -> list[GoldenQuestion]:
    """Monta o golden set factual para o tipo do político."""
    match politico.tipo:
        case "deputado":
            return _golden_deputado(politico, ano)
        case "senador":
            return _golden_senador(politico, ano)
        case "governador":
            return _golden_governador(politico)
        case "prefeito":
            return _golden_prefeito(politico)
        case "vereador":
            return _golden_vereador(politico)


def _retrieval_scores(context_list: Sequence[str], question: GoldenQuestion) -> tuple[float, float]:
    """Calcula hit-rate e MRR a partir dos chunks recuperados."""
    for rank, chunk in enumerate(context_list):
        if _contains_expected(chunk, question):
            return 1.0, 1.0 / (rank + 1)
    return 0.0, 0.0


def _context_utilization(context_list: Sequence[str], actual_answer: str) -> float:
    """Calcula utilização lexical do contexto por sobreposição de bigramas."""
    answer_bigrams = _bigrams(actual_answer)
    if not context_list or not answer_bigrams:
        return 0.0
    scores: list[float] = []
    for chunk in context_list:
        chunk_bigrams = _bigrams(chunk)
        overlap = len(chunk_bigrams & answer_bigrams)
        scores.append(overlap / max(len(chunk_bigrams), 1))
    return _clamp01(_mean(scores))


def _generate_answer(model: str, nome: str, context_list: Sequence[str], pergunta: str) -> str:
    """Gera resposta com LocalAI usando somente o contexto recuperado."""
    contexto_texto = "\n\n".join(context_list)
    prompt = (
        f"Contexto:\n{contexto_texto}\n\nPergunta: {pergunta}\nSobre: {nome}.\n"
        "Responda com base SOMENTE no contexto. Se não houver informação suficiente, "
        "responda 'não sei'."
    )
    return str(get_localai_client().chat(prompt, system=_SISTEMA, model=model, max_tokens=150)).strip()


def _judge_faithfulness(model: str, expected_answer: str, actual_answer: str) -> float:
    """Avalia fidelidade: match lexical normalizado primeiro; LLM-as-judge só em caso ambíguo."""
    exp_norm = _normalize(expected_answer)
    act_norm = _normalize(actual_answer)
    if not exp_norm or not act_norm:
        return 0.0
    # "não sei" = ausência de grounding no contexto -> fidelidade zero.
    if "nao sei" in act_norm:
        return 0.0
    # Resposta esperada presente na gerada (ou vice-versa) com fronteira de palavra:
    # julga 1.0 sem custo de LLM (o juiz 3B erra matches exatos como 'R$ 28.788.030,99.').
    if _contains_bounded(act_norm, exp_norm) or _contains_bounded(exp_norm, act_norm):
        return 1.0
    prompt = (
        "Compare a resposta esperada com a resposta gerada.\n\n"
        f"Resposta esperada: {expected_answer}\n"
        f"Resposta gerada: {actual_answer}\n\n"
        "A resposta gerada é factualmente consistente com a resposta esperada? "
        "Apenas o número."
    )
    raw = str(get_localai_client().chat(prompt, system=_SISTEMA_JUIZ, model=model, max_tokens=20))
    match = _FLOAT_RE.search(raw.replace(",", "."))
    if match is None:
        log.warning("Juiz retornou resposta sem número: %r", raw)
        return 0.0
    return _clamp01(float(match.group(0)))


def _ensure_model_loaded(model: str) -> None:
    """Tenta carregar o modelo LocalAI sem abortar a coleta em caso de falha."""
    try:
        from src.localai_manager import manager as localai_manager

        localai_manager.ensure_model_loaded(model)
    except (ImportError, RuntimeError, OSError) as exc:  # pragma: no cover
        log.warning("ensure_model_loaded falhou (%s) — continuando mesmo assim.", exc)


def collect_for_politico(politico: Politico, model: str, ano: int | None) -> list[QuestionMetric]:
    """Executa recuperação, geração e métricas para um político."""
    golden_set = build_golden_set(politico, ano)
    if not golden_set:
        log.warning("Golden set vazio para %s (%s).", politico.nome, politico.tipo)
        return []
    log.info("Coletando %s (%s): %d perguntas.", politico.nome, politico.tipo, len(golden_set))
    context_list, _scored = search_context_multiquery(politico.politico_id, tipo_politico=politico.tipo)
    contexts = [str(chunk) for chunk in context_list]
    log.info("Contexto recuperado para %s: %d chunks.", politico.nome, len(contexts))

    metrics: list[QuestionMetric] = []
    for question in golden_set:
        hit_rate, mrr = _retrieval_scores(contexts, question)
        actual_answer = _generate_answer(model, politico.nome, contexts, question.question)
        faithfulness = _judge_faithfulness(model, question.expected_answer, actual_answer)
        utilization = _context_utilization(contexts, actual_answer)
        metrics.append(
            QuestionMetric(
                politico=politico,
                question=question,
                retrieved_chunks_count=len(contexts),
                hit_rate_at_k=hit_rate,
                mrr_at_k=mrr,
                actual_answer=actual_answer,
                faithfulness_score=faithfulness,
                context_utilization_score=utilization,
            )
        )
    return metrics


def _summarize(metrics: Sequence[QuestionMetric], model: str, golden_set_version: str) -> RunSummary:
    """Agrega métricas no nível da execução."""
    avg_hit = _mean([metric.hit_rate_at_k for metric in metrics])
    avg_faithfulness = _mean([metric.faithfulness_score for metric in metrics])
    avg_utilization = _mean([metric.context_utilization_score for metric in metrics])
    composite = 100.0 * ((0.4 * avg_hit) + (0.4 * avg_faithfulness) + (0.2 * avg_utilization))
    return RunSummary(
        model_name=model,
        golden_set_version=golden_set_version,
        total_questions=len(metrics),
        global_efficiency_score=composite,
        avg_retrieval_hit_rate=avg_hit,
        avg_generation_faithfulness=avg_faithfulness,
        avg_context_utilization=avg_utilization,
    )


def persist_run(summary: RunSummary, metrics: Sequence[QuestionMetric]) -> int:
    """Persiste uma execução e suas linhas por pergunta em uma transação."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rag_efficiency_runs (
                        model_name,
                        golden_set_version,
                        total_questions,
                        global_efficiency_score,
                        avg_retrieval_hit_rate,
                        avg_generation_faithfulness,
                        avg_emergence_layer
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NULL)
                    RETURNING id
                    """,
                    (
                        summary.model_name,
                        summary.golden_set_version,
                        summary.total_questions,
                        round(summary.global_efficiency_score, 2),
                        round(summary.avg_retrieval_hit_rate, 2),
                        round(summary.avg_generation_faithfulness, 2),
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    msg = "INSERT em rag_efficiency_runs não retornou id."
                    raise RuntimeError(msg)
                run_id = int(row[0])
                for metric in metrics:
                    cur.execute(
                        """
                        INSERT INTO rag_efficiency_metrics (
                            run_id,
                            politico_id,
                            tipo_politico,
                            question,
                            expected_answer,
                            retrieved_chunks_count,
                            hit_rate_at_k,
                            mrr_at_k,
                            actual_answer,
                            faithfulness_score,
                            context_utilization_score,
                            emergence_layer,
                            total_layers,
                            target_token_prob
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL)
                        """,
                        (
                            run_id,
                            metric.politico.politico_id,
                            metric.politico.tipo,
                            metric.question.question,
                            metric.question.expected_answer,
                            metric.retrieved_chunks_count,
                            round(metric.hit_rate_at_k, 2),
                            round(metric.mrr_at_k, 2),
                            metric.actual_answer,
                            round(metric.faithfulness_score, 2),
                            round(metric.context_utilization_score, 2),
                        ),
                    )
            conn.commit()
            return run_id
        except (RuntimeError, OSError) as exc:
            conn.rollback()
            log.exception("Falha ao persistir execução RAG Efficiency.")
            raise exc


def print_summary(summary: RunSummary, metrics: Sequence[QuestionMetric], run_id: int | None) -> None:
    """Imprime relatório compacto no console."""
    title = "RAG Efficiency — dry-run" if run_id is None else f"RAG Efficiency — run #{run_id}"
    print("\n" + "=" * 98)
    print(title)
    print("=" * 98)
    print(f"Modelo: {summary.model_name} | Golden set: {summary.golden_set_version}")
    print(
        "Médias: "
        f"hit={summary.avg_retrieval_hit_rate:.2f} | "
        f"faithfulness={summary.avg_generation_faithfulness:.2f} | "
        f"utilização={summary.avg_context_utilization:.2f} | "
        f"score={summary.global_efficiency_score:.2f}"
    )
    print("-" * 98)
    print(f"{'Político':24} {'Pergunta':42} {'Hit':>5} {'MRR':>5} {'Faith':>7} {'Util':>6}")
    print("-" * 98)
    for metric in metrics:
        nome = metric.politico.nome[:24]
        pergunta = metric.question.question[:42]
        print(
            f"{nome:24} {pergunta:42} {metric.hit_rate_at_k:5.2f} "
            f"{metric.mrr_at_k:5.2f} {metric.faithfulness_score:7.2f} "
            f"{metric.context_utilization_score:6.2f}"
        )
    print("=" * 98 + "\n")


def _parse_tipo(value: str) -> TipoPolitico:
    """Converte argparse string para literal validado."""
    if value not in TIPOS_POLITICOS:
        msg = f"Tipo político inválido: {value}"
        raise argparse.ArgumentTypeError(msg)
    return value


def _parse_args(argv: Sequence[str] | None = None) -> CliArgs:
    """Parseia argumentos da CLI."""
    parser = argparse.ArgumentParser(description="Coletor RAG Efficiency — métricas do RAG v7")
    parser.add_argument("--politico-id", type=int, help="ID do político no cargo")
    parser.add_argument("--tipo", type=_parse_tipo, default="deputado", choices=TIPOS_POLITICOS)
    parser.add_argument("--nome", type=str, help="Nome do político")
    parser.add_argument("--limit-politicos", type=int, default=3, help="Top-N deputados sem filtro")
    parser.add_argument("--modelo", type=str, default=RAG_LLM_MODEL, help="Modelo LocalAI")
    parser.add_argument("--golden-set-version", type=str, default="v1")
    parser.add_argument("--ano", type=int, default=None, help="Filtra emendas por ano")
    parser.add_argument("--dry-run", action="store_true", help="Imprime relatório sem persistir")
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs detalhados")
    ns = parser.parse_args(argv)
    return CliArgs(
        politico_id=ns.politico_id,
        tipo=ns.tipo,
        nome=ns.nome,
        limit_politicos=ns.limit_politicos,
        modelo=ns.modelo,
        golden_set_version=ns.golden_set_version,
        dry_run=ns.dry_run,
        verbose=ns.verbose,
        ano=ns.ano,
    )


def _select_politicos(args: CliArgs) -> list[Politico]:
    """Seleciona políticos alvo conforme filtros da CLI."""
    if args.nome or args.politico_id is not None:
        politico = resolve_politico(args.tipo, args.nome, args.politico_id)
        if politico is None:
            log.error("Político não encontrado (use --nome ou --politico-id).")
            return []
        return [politico]
    if args.tipo != "deputado":
        log.error("Sem --nome/--politico-id, a seleção automática só suporta deputados.")
        return []
    return _top_deputados(args.limit_politicos)


def run(args: CliArgs) -> RunSummary | None:
    """Executa coleta completa conforme argumentos validados."""
    politicos = _select_politicos(args)
    if not politicos:
        return None
    _ensure_model_loaded(args.modelo)
    all_metrics: list[QuestionMetric] = []
    for politico in politicos:
        all_metrics.extend(collect_for_politico(politico, args.modelo, args.ano))
    summary = _summarize(all_metrics, args.modelo, args.golden_set_version)
    run_id = None if args.dry_run else persist_run(summary, all_metrics)
    print_summary(summary, all_metrics, run_id)
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    """Ponto de entrada da CLI."""
    args = _parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format=LOG_FORMAT)
    run(args)


if __name__ == "__main__":
    main()
