"""Logit Lens Runner offline para RAG Efficiency.

Carrega o modelo via transformers, injeta o contexto real recuperado pelo RAG v7
(Qdrant + multi-query) e mede em qual camada a probabilidade do token alvo emerge.

Uso:
    .venv/bin/python -m scripts.logit_lens_runner --run-id 1
    .venv/bin/python -m scripts.logit_lens_runner --run-id 1 --limit 5
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, cast

import torch
from torch import Tensor
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedTokenizerBase
from transformers.modeling_outputs import CausalLMOutputWithPast

from src.db_utils import get_connection
from src.enrichers.rag_persona import search_context_multiquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"
EMERGENCE_THRESHOLD = 0.10
MAX_CONTEXT_CHARS = 2000
STOPWORDS_TARGET = frozenset(
    {
        "r$",
        "rs",
        "reais",
        "real",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "o",
        "a",
        "os",
        "as",
        "um",
        "uma",
        "e",
        "em",
        "no",
        "na",
        "nos",
        "nas",
    }
)
TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|[\wÀ-ÿ]+|R\$", re.UNICODE)


class LogitLensModel(Protocol):
    config: Any  # PretrainedConfig do HuggingFace
    device: torch.device

    def __call__(self, **kwargs: Tensor) -> CausalLMOutputWithPast: ...

    def get_output_embeddings(self) -> torch.nn.Module: ...


@dataclass(frozen=True, slots=True)
class MetricRow:
    id: int
    politico_id: int
    tipo_politico: str
    question: str
    expected_answer: str


@dataclass(frozen=True, slots=True)
class ProbeResult:
    emergence_layer: int
    total_layers: int
    target_token_prob: float


@dataclass(slots=True)
class RunSummary:
    processed: int = 0
    skipped: int = 0


def detect_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model(model_id: str) -> tuple[PreTrainedTokenizerBase, LogitLensModel]:
    if not os.getenv("HF_TOKEN"):
        log.warning("HF_TOKEN não configurado. Pode falhar ao carregar Llama-3.2-3B-Instruct.")

    device = detect_device()
    log.info("Carregando %s em %s (pode demorar...)", model_id, device)

    tokenizer = cast(
        PreTrainedTokenizerBase,
        AutoTokenizer.from_pretrained(model_id, token=os.getenv("HF_TOKEN")),
    )
    # Stub do transformers (_Wrapped/__getattr__) quebra mypy strict na chamada direta.
    auto_model: Any = AutoModelForCausalLM
    if device == "cuda":
        model = auto_model.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.float16,
            token=os.getenv("HF_TOKEN"),
            output_hidden_states=True,
        )
    else:
        model = auto_model.from_pretrained(
            model_id,
            token=os.getenv("HF_TOKEN"),
            output_hidden_states=True,
        )
        model.to(device)
    model.eval()
    return tokenizer, cast(LogitLensModel, model)


def select_target_token_id(tokenizer: PreTrainedTokenizerBase, expected_answer: str) -> int | None:
    raw_answer = expected_answer.strip()
    if not raw_answer:
        return None

    token_candidates = TOKEN_RE.findall(raw_answer)
    for candidate in token_candidates:
        normalized = candidate.casefold().strip(".,;:!?()[]{}\"'")
        if normalized and (normalized not in STOPWORDS_TARGET or normalized[0].isdigit()):
            token_ids = tokenizer(candidate, add_special_tokens=False).input_ids
            if token_ids:
                return int(token_ids[0])

    fallback_ids = tokenizer(raw_answer, add_special_tokens=False).input_ids
    return int(fallback_ids[0]) if fallback_ids else None


def build_probe_prompt(context_list: list[str], question: str) -> str:
    joined_context = "\n\n".join(context_list)[:MAX_CONTEXT_CHARS]
    return (
        f"Contexto:\n{joined_context}\n\n"
        f"Pergunta: {question}\n"
        "Responda com base SOMENTE no contexto."
    )


def get_context(
    politico_id: int,
    tipo_politico: str,
    context_cache: dict[tuple[int, str], list[str]],
) -> list[str] | None:
    cache_key = (politico_id, tipo_politico)
    if cache_key in context_cache:
        return context_cache[cache_key]

    try:
        context_list, _scored = search_context_multiquery(politico_id, tipo_politico=tipo_politico)
    except (RuntimeError, OSError, ConnectionError, TimeoutError) as exc:
        log.warning(
            "Falha ao recuperar contexto RAG para %s %s: %s. Linha será pulada.",
            tipo_politico,
            politico_id,
            exc,
        )
        return None

    context_cache[cache_key] = context_list
    return context_list


def final_layer_norm(model: LogitLensModel) -> torch.nn.Module | None:
    base_model = getattr(model, "model", None)
    norm = getattr(base_model, "norm", None)
    return norm if isinstance(norm, torch.nn.Module) else None


def probe_emergence(
    model: LogitLensModel,
    tokenizer: PreTrainedTokenizerBase,
    prompt: str,
    target_token_id: int,
) -> ProbeResult:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    unembedding = model.get_output_embeddings()
    layer_norm = final_layer_norm(model)
    num_layers = int(model.config.num_hidden_layers)

    emergence_layer: int | None = None
    target_prob_final = 0.0

    with torch.no_grad():
        outputs = model(**inputs)
        hidden_states = outputs.hidden_states
        if hidden_states is None:
            raise RuntimeError("Modelo não retornou hidden_states com output_hidden_states=True")

        for layer_idx, hidden_state in enumerate(hidden_states[1:], 1):
            projected_hidden = layer_norm(hidden_state) if layer_norm is not None else hidden_state
            logits = unembedding(projected_hidden)
            last_token_logits = logits[0, -1, :]
            target_prob = float(torch.softmax(last_token_logits, dim=-1)[target_token_id].item())

            if layer_idx == num_layers:
                target_prob_final = target_prob
            if emergence_layer is None and target_prob > EMERGENCE_THRESHOLD:
                emergence_layer = layer_idx

    return ProbeResult(
        emergence_layer=emergence_layer if emergence_layer is not None else num_layers,
        total_layers=num_layers,
        target_token_prob=target_prob_final,
    )


def fetch_pending_rows(run_id: int, limit: int | None) -> list[MetricRow]:
    query = """
        SELECT id, politico_id, tipo_politico, question, expected_answer
        FROM rag_efficiency_metrics
        WHERE run_id = %s AND emergence_layer IS NULL
        ORDER BY id
    """
    params: tuple[int] | tuple[int, int]
    if limit is not None:
        query += " LIMIT %s"
        params = (run_id, limit)
    else:
        params = (run_id,)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return [
            MetricRow(
                id=int(row[0]),
                politico_id=int(row[1]),
                tipo_politico=str(row[2]),
                question=str(row[3]),
                expected_answer=str(row[4]),
            )
            for row in cur.fetchall()
        ]


def persist_probe(metric_id: int, result: ProbeResult) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE rag_efficiency_metrics
            SET emergence_layer = %s, total_layers = %s, target_token_prob = %s
            WHERE id = %s
            """,
            (
                result.emergence_layer,
                result.total_layers,
                Decimal(str(round(result.target_token_prob, 4))),
                metric_id,
            ),
        )
        conn.commit()


def run_logit_lens(
    run_id: int,
    model_id: str = DEFAULT_MODEL_ID,
    limit: int | None = None,
) -> RunSummary:
    log.info("Iniciando Logit Lens (offline) para Run %s", run_id)
    log.info(
        "Threshold emergência=%.2f; contexto máximo=%s caracteres",
        EMERGENCE_THRESHOLD,
        MAX_CONTEXT_CHARS,
    )

    try:
        tokenizer, model = load_model(model_id)
    except (OSError, RuntimeError, ValueError) as exc:
        log.error("Erro ao carregar modelo HuggingFace '%s': %s", model_id, exc)
        raise SystemExit(1) from exc

    rows = fetch_pending_rows(run_id, limit)
    log.info("Processando %s perguntas...", len(rows))

    summary = RunSummary()
    context_cache: dict[tuple[int, str], list[str]] = {}

    try:
        for row in rows:
            context_list = get_context(row.politico_id, row.tipo_politico, context_cache)
            if not context_list:
                log.warning("Sem contexto para %s. Usando placeholder vazio.", row.id)
                context_list = ["(Sem dados no Qdrant para este político)"]

            target_token_id = select_target_token_id(tokenizer, row.expected_answer)
            if target_token_id is None:
                log.warning("Resposta esperada vazia na métrica %s. Linha será pulada.", row.id)
                summary.skipped += 1
                continue

            prompt = build_probe_prompt(context_list, row.question)
            result = probe_emergence(model, tokenizer, prompt, target_token_id)
            persist_probe(row.id, result)
            summary.processed += 1
            log.info(
                "Pergunta '%s...' -> Emergence L%s/%s (Prob final: %.4f)",
                row.question[:30],
                result.emergence_layer,
                result.total_layers,
                result.target_token_prob,
            )
    finally:
        if detect_device() == "cuda":
            torch.cuda.empty_cache()

    log.info(
        "Logit Lens concluído. Processadas: %s | Puladas: %s",
        summary.processed,
        summary.skipped,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    run_logit_lens(args.run_id, limit=args.limit)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        log.error("Execução interrompida pelo usuário.")
        sys.exit(130)
