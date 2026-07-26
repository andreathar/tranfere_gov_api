"""
Cliente local para LocalAI — interface OpenAI-compatível.

Uso:
    from src.localai_client import LocalAIClient

    client = LocalAIClient()

    # Chat simples
    resp = client.chat("Resuma este plano de ação: ...")

    # Classificação em lote
    labels = client.classify_batch(texts, labels=["APROVADO", "NEGADO", "PENDENTE"])

    # Embeddings
    vectors = client.embed(["texto 1", "texto 2"])

    # Streaming
    for chunk in client.chat_stream("Descreva..."):
        print(chunk, end="", flush=True)

    # Job assíncrono (para enriquecimento pesado)
    job_id = client.submit_job("Analise anomalias...", callback_url=None)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator, Iterator, Sequence

import httpx
import pandas as pd

from config.settings import (
    LOCALAI_BASE_URL,
    LOCALAI_DEFAULT_MODEL,
    LOCALAI_MAX_RETRIES,
    LOCALAI_MODELS,
    LOCALAI_TIMEOUT,
)

logger = logging.getLogger(__name__)


class LocalAIClient:
    """Cliente para LocalAI com retry, timeout e helpers de alto nível."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or LOCALAI_BASE_URL).rstrip("/")
        self.model = model or LOCALAI_DEFAULT_MODEL
        self.timeout = timeout or LOCALAI_TIMEOUT

    # ------------------------------------------------------------------
    # Chat (sync)
    # ------------------------------------------------------------------
    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Chat completion simples — retorna a resposta como string."""
        messages = self._build_messages(prompt, system)
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = self._post("/chat/completions", payload)
        return data["choices"][0]["message"]["content"]

    def chat_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Any:
        """Chat que espera JSON como resposta — parseia automaticamente."""
        sys_msg = (
            (system or "") + "\n\nIMPORTANTE: Responda APENAS com JSON válido, "
            "sem markdown, sem explicação."
        ).strip()
        raw = self.chat(
            prompt, system=sys_msg, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )
        # Limpar possíveis wrappers markdown
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        return json.loads(cleaned)

    # ------------------------------------------------------------------
    # Chat (async)
    # ------------------------------------------------------------------
    async def achat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Versão async do chat."""
        messages = self._build_messages(prompt, system)
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = await self._apost("/chat/completions", payload)
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    def chat_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Chat com streaming — yields chunks de texto."""
        messages = self._build_messages(prompt, system)
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        url = f"{self.base_url}/chat/completions"
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]

    # ------------------------------------------------------------------
    # Classificação em lote
    # ------------------------------------------------------------------
    def classify_batch(
        self,
        texts: Sequence[str],
        *,
        labels: Sequence[str],
        model: str | None = None,
        batch_size: int = 10,
    ) -> list[str]:
        """Classifica textos em labels predefinidos. Retorna lista de labels."""
        labels_str = ", ".join(labels)
        results: list[str] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            numbered = "\n".join(f"{j}. {t}" for j, t in enumerate(batch, 1))
            prompt = (
                f"Classifique cada texto abaixo em UMA das categorias: "
                f"[{labels_str}].\n\n"
                f"Responda APENAS com uma lista de labels, uma por linha, "
                f"na mesma ordem.\n\n{numbered}"
            )
            raw = self.chat(prompt, model=model, temperature=0.0, max_tokens=512)
            batch_labels = [
                line.strip().split(".")[-1].strip()
                for line in raw.strip().split("\n")
                if line.strip()
            ]
            # Garantir que temos o mesmo número de resultados
            while len(batch_labels) < len(batch):
                batch_labels.append(labels[0])
            results.extend(batch_labels[: len(batch)])
            logger.info(
                "Classificados %d/%d textos", min(i + batch_size, len(texts)), len(texts)
            )

        return results

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Gera embeddings para lista de textos."""
        payload = {
            "model": model or LOCALAI_MODELS["embedding"],
            "input": list(texts),
        }
        data = self._post("/embeddings", payload)
        # Ordenar por índice para garantir ordem
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    # ------------------------------------------------------------------
    # Jobs assíncronos (batch processing)
    # ------------------------------------------------------------------
    def submit_job(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        callback_url: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Submete um job assíncrono (compatível com /v1/jobs do LocalAI).
        Retorna info do job para polling.
        """
        messages = self._build_messages(prompt, system)
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata

        # LocalAI jobs endpoint (se disponível)
        try:
            data = self._post("/jobs", payload)
            logger.info("Job submetido: %s", data.get("id", "unknown"))
            return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning(
                    "LocalAI /v1/jobs não disponível — usando execução síncrona"
                )
                return self._sync_fallback(prompt, system=system, model=model)
            raise

    def poll_job(self, job_id: str) -> dict[str, Any]:
        """Verifica status de um job assíncrono."""
        url = f"{self.base_url}/jobs/{job_id}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def wait_for_job(
        self, job_id: str, *, poll_interval: float = 2.0, max_wait: float = 600.0
    ) -> dict[str, Any]:
        """Bloqueia até o job completar ou timeout."""
        start = time.monotonic()
        while True:
            status = self.poll_job(job_id)
            state = status.get("status", "unknown")
            if state in ("completed", "succeeded"):
                return status
            if state in ("failed", "cancelled"):
                raise RuntimeError(f"Job {job_id} falhou: {state}")
            if time.monotonic() - start > max_wait:
                raise TimeoutError(f"Job {job_id} excedeu {max_wait}s")
            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # DataFrame helpers (para enriquecimento)
    # ------------------------------------------------------------------
    def enrich_column(
        self,
        df: pd.DataFrame,
        column: str,
        *,
        task: str,
        new_column: str | None = None,
        model: str | None = None,
        batch_size: int = 10,
    ) -> pd.DataFrame:
        """Aplica uma tarefa de IA em cada valor de uma coluna do DataFrame.

        Args:
            df: DataFrame de entrada
            column: Coluna com os textos
            task: Instrução com {text} como placeholder
            new_column: Nome da coluna de saída (padrão: f"{column}_ai")
            model: Modelo a usar
            batch_size: Tamanho do lote

        Returns:
            DataFrame com coluna adicionada

        Exemplo:
            df = client.enrich_column(
                df, "motivo_impedimento",
                task="Classifique o motivo: {text}",
                new_column="motivo_categoria",
                labels=["FALTA_DOCUMENTACAO", "IRREGULARIDADE", "OUTROS"],
            )
        """
        out_col = new_column or f"{column}_ai"
        texts = df[column].fillna("").astype(str).tolist()

        results: list[str] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for text in batch:
                prompt = task.replace("{text}", text or "(vazio)")
                try:
                    result = self.chat(prompt, model=model, temperature=0.0)
                    results.append(result.strip())
                except Exception as exc:
                    logger.warning("Erro enriquecendo registro %d: %s", i, exc)
                    results.append(f"ERRO: {exc}")
            logger.info(
                "Enriquecidos %d/%d registros da coluna '%s'",
                min(i + batch_size, len(texts)),
                len(texts),
                column,
            )

        df[out_col] = results
        return df

    def summarize_plans(
        self,
        df: pd.DataFrame,
        *,
        group_by: str = "parlamentar_nome",
        value_col: str = "valor_total",
        situation_col: str = "plano_acao_situacao",
        model: str | None = None,
    ) -> pd.DataFrame:
        """Gera resumos de IA para grupos de planos de ação.

        Útil para criar narrativas de análise por parlamentar, estado, etc.
        """
        summaries: list[dict[str, Any]] = []

        for group_name, group_df in df.groupby(group_by):
            agg = (
                group_df.groupby(situation_col)
                .agg(count=(value_col, "count"), total=(value_col, "sum"))
                .reset_index()
            )
            agg_str = agg.to_string(index=False)
            prompt = (
                f"Gere um resumo analítico em PT-BR (máx 3 frases) sobre:\n"
                f"Parlamentar/Grupo: {group_name}\n"
                f"Dados:\n{agg_str}\n\n"
                f"Destaque o total investido e a situação predominante."
            )
            try:
                summary = self.chat(prompt, model=model, temperature=0.3)
            except Exception as exc:
                summary = f"Erro: {exc}"
                logger.warning("Erro resumindo %s: %s", group_name, exc)

            summaries.append({group_by: group_name, "resumo_ia": summary})

        return pd.DataFrame(summaries)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        """Verifica se o LocalAI está respondendo e lista modelos."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{self.base_url}/models")
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return {
                    "status": "ok",
                    "base_url": self.base_url,
                    "models_count": len(models),
                    "models": models,
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc), "base_url": self.base_url}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _build_messages(
        prompt: str, system: str | None = None
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _post(self, endpoint: str, payload: dict) -> dict:
        """POST com retry."""
        url = f"{self.base_url}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(1, LOCALAI_MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < LOCALAI_MAX_RETRIES:
                    wait = 2 ** attempt
                    logger.warning(
                        "LocalAI tentativa %d/%d falhou (%s), retry em %ds",
                        attempt, LOCALAI_MAX_RETRIES, exc, wait,
                    )
                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    async def _apost(self, endpoint: str, payload: dict) -> dict:
        """POST async com retry."""
        url = f"{self.base_url}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(1, LOCALAI_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < LOCALAI_MAX_RETRIES:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                    logger.warning(
                        "LocalAI async tentativa %d/%d falhou (%s)",
                        attempt, LOCALAI_MAX_RETRIES, exc,
                    )
        raise last_exc  # type: ignore[misc]

    def _sync_fallback(
        self, prompt: str, *, system: str | None = None, model: str | None = None
    ) -> dict[str, Any]:
        """Fallback quando jobs assíncronos não estão disponíveis."""
        result = self.chat(prompt, system=system, model=model)
        return {"status": "completed", "result": result}

    # ------------------------------------------------------------------
    # MCP Tool Calling (usa MCPToolBridge)
    # ------------------------------------------------------------------
    def chat_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        categories: list[str] | None = None,
        max_tools: int = 30,
        max_turns: int = 5,
    ) -> dict[str, Any]:
        """Chat com acesso a ferramentas MCP (agentic loop).

        O modelo pode chamar tools governamentais automaticamente para
        responder perguntas sobre dados públicos.

        Args:
            prompt: Pergunta do usuário
            system: System prompt opcional
            model: Modelo LocalAI (padrão: config default)
            categories: Filtrar tools (ex: ["camara", "ibge"])
            max_tools: Máximo de tools a expor ao modelo
            max_turns: Máximo de iterações tool→response

        Returns:
            {"response": "texto final", "tool_calls": [...], "turns": N}

        Exemplo:
            result = client.chat_with_tools(
                "Quais deputados de AL mais receberam emendas?",
                categories=["camara", "transferegov"],
            )
            print(result["response"])
        """
        from src.mcp_tool_bridge import get_mcp_bridge
        bridge = get_mcp_bridge()
        return bridge.agent_chat(
            prompt,
            system=system,
            model=model or self.model,
            categories=categories,
            max_tools=max_tools,
            max_turns=max_turns,
        )

    async def achat_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        categories: list[str] | None = None,
        max_tools: int = 30,
        max_turns: int = 5,
    ) -> dict[str, Any]:
        """Versão async do chat_with_tools."""
        from src.mcp_tool_bridge import get_mcp_bridge
        bridge = get_mcp_bridge()
        return await bridge.aagent_chat(
            prompt,
            system=system,
            model=model or self.model,
            categories=categories,
            max_tools=max_tools,
            max_turns=max_turns,
        )


# ---------------------------------------------------------------------------
# Instância global (lazy) para uso rápido
# ---------------------------------------------------------------------------
_default_client: LocalAIClient | None = None


def get_localai_client() -> LocalAIClient:
    """Retorna instância singleton do cliente LocalAI."""
    global _default_client
    if _default_client is None:
        _default_client = LocalAIClient()
    return _default_client
