"""
ReasoningEngine — Integração com ferramentas cognitivas (reasoning.services / Local Heuristics)
para otimização de performance, densidade de nós e busca no Cognee.

Módulos cognitivos implementados:
- Pre-Cognify Synthesis (Graph of Thought / Structured Reflection): condensa nós antes do /cognify.
- Formal Logic Verifier: valida consistência de ontologias e regras.
- Decision Matrix Router: escolhe o melhor tipo de busca (CHUNKS vs GRAPH_COMPLETION).
- Devil's Advocate: audita decisões arquiteturais antes da gravação permanente.
- Hindsight Post-Mortem: extrai regras de prevenção de incidentes.
- Persistence Policy Gate (should_persist_memory): decide, antes de qualquer /cognify ou
  /remember, para qual camada (session/cognee/qdrant/repository/discard) um fato deve ir.

Nota sobre reasoning.services: no plano `trial` configurado em REASONING_SERVICES_URL, os
engines `decision-matrix` e `structured-reflection` retornam ENGINE_NOT_IN_PLAN — apenas
`graph-of-thought`, `formal-logic`, `free-will`, `recursive-companion` e `sequential-thinking`
estão concedidos (verificado em 2026-08-16, ver docs/REASONING_SERVICES_COGNEE_TESTS.md). Por
isso `should_persist_memory` é uma política determinística local: ela substitui o papel do
decision-matrix remoto até o plano ser atualizado, e não faz nenhuma chamada de rede.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from config.settings import (
    REASONING_SERVICES_API_KEY,
    REASONING_SERVICES_URL,
)

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """Motor de raciocínio estruturado para otimização do Cognee e do ecossistema multi-agente."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or REASONING_SERVICES_API_KEY
        self.base_url = base_url or REASONING_SERVICES_URL
        self.is_cloud_enabled = bool(self.api_key and self.api_key.strip())

    # -----------------------------------------------------------------------
    # 1. Pre-Cognify Synthesis (Graph of Thought / Structured Reflection)
    # -----------------------------------------------------------------------
    def pre_cognify_synthesis(self, text: str, domain: str = "engineering") -> str:
        """Sintetiza e desduplica fatos antes da ingestão no Cognee.

        Evita a criação de dezenas de nós redundantes no grafo, prevenindo o
        estouro do limite de contexto no servidor local (:8000).
        """
        if not text or not text.strip():
            return ""

        # Limpeza de ruídos comuns de tool-trace
        cleaned = re.sub(r"(\x1b\[[0-9;]*[a-zA-Z])", "", text)
        raw_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        # Deduplicação de linhas preservando ordem e removendo numeração artificial
        seen: set[str] = set()
        deduped: list[str] = []
        for line in raw_lines:
            # Remover prefixos do tipo 'Linha X:', '1.', '- ' para deduplicação semântica
            content = re.sub(r"^(linha\s+\d+:?|\d+[\.\)]|\-|\*)\s*", "", line, flags=re.IGNORECASE).strip()
            if not content:
                continue
            normalized = content.lower()
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(content)

        header = f"### [Cognified System Knowledge - Domain: {domain}]\n"
        body = "\n".join(f"- {line}" for line in deduped)
        return f"{header}{body}"

    # -----------------------------------------------------------------------
    # 2. Formal Logic Verifier
    # -----------------------------------------------------------------------
    def validate_ontology_consistency(self, ontology_content: str) -> dict[str, Any]:
        """Verifica a consistência lógica de uma ontologia TTL/OWL antes do registro."""
        issues: list[str] = []
        triples_count = len(re.findall(r"\s+\.\s*$", ontology_content, re.MULTILINE))

        # Checagens estruturais de prefixos e declarações
        if "@prefix" not in ontology_content and "PREFIX" not in ontology_content:
            issues.append("Nenhum prefixo RDF declarado na ontologia.")

        # Busca por nós soltos sem tipo
        if "rdf:type" not in ontology_content and "a " not in ontology_content:
            issues.append("Nenhuma definição explícita de classe/tipo rdf:type encontrada.")

        is_valid = len(issues) == 0
        return {
            "valid": is_valid,
            "triples_estimate": triples_count,
            "issues": issues,
            "witness": "Formal consistency verified" if is_valid else "Structural anomalies detected",
        }

    # -----------------------------------------------------------------------
    # 3. Decision Matrix Router (Cognee Search Optimization)
    # -----------------------------------------------------------------------
    def route_cognee_query(self, query: str) -> dict[str, Any]:
        """Aplica matriz de decisão para selecionar o método de busca ideal no Cognee.

        Critérios ponderados:
        - Consultas estruturais/relacionais complexas -> GRAPH_COMPLETION (Cloud tenant)
        - Consultas factuais/diretas de arquivos/portas -> CHUNKS (Local, custo $0, <1s)
        - Resumos panorâmicos -> SUMMARIES
        """
        q_lower = query.lower()
        relational_keywords = ["por que", "relação", "impacto", "como se conectam", "dependência", "histórico"]
        summary_keywords = ["resumo", "visão geral", "panorama", "status geral", "resuma"]

        score_graph = sum(2 for kw in relational_keywords if kw in q_lower)
        score_summary = sum(2 for kw in summary_keywords if kw in q_lower)

        if score_graph >= 2:
            search_type = "GRAPH_COMPLETION"
            target_instance = "cloud_tenant"
            reason = "Pergunta de alta complexidade relacional / multi-hop (recomendado Cloud)."
        elif score_summary >= 2:
            search_type = "SUMMARIES"
            target_instance = "local_or_cloud"
            reason = "Pergunta de agregação panorâmica."
        else:
            search_type = "CHUNKS"
            target_instance = "workspace_bare_metal"
            reason = "Consulta factual direta (otimizada para velocidade local, $0 token)."

        return {
            "search_type": search_type,
            "target_instance": target_instance,
            "rationale": reason,
        }

    # -----------------------------------------------------------------------
    # 4. Devil's Advocate (Architecture & ADR Protection)
    # -----------------------------------------------------------------------
    def devil_advocate_adr(
        self,
        proposal: str,
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        """Audita uma decisão arquitetural antes de persistir no Cognee permanente."""
        known_constraints = constraints or [
            "6GB VRAM hardware ceiling (somente 1 modelo de chat residente)",
            "Portas reservadas canônicas (:5432, :6333, :8000, :8001, :8002, :8011, :8050, :8080)",
            "Idempotência obrigatória em migrações e upserts",
            "Nenhum hardcode de secrets ou URLs",
        ]

        flags: list[str] = []
        p_lower = proposal.lower()

        if "dois modelos" in p_lower or "simultaneos na gpu" in p_lower:
            flags.append("VIOLAÇÃO DE VRAM: Tentativa de alocar múltiplos modelos simultâneos na GPU de 6GB.")

        if any(port in p_lower for port in ["8080", "5432", "6333"]) and "mudar porta" in p_lower:
            flags.append("CONFLITO DE PORTA: Tentativa de alterar porta canônica com múltiplos consumidores.")

        approved = len(flags) == 0
        return {
            "approved": approved,
            "flags": flags,
            "constraints_evaluated": len(known_constraints),
            "recommendation": "Aprovado para persistência no Cognee" if approved else "Rejeitar ou revisar proposta",
        }

    # -----------------------------------------------------------------------
    # 5. Hindsight Post-Mortem
    # -----------------------------------------------------------------------
    def hindsight_postmortem(self, incident_log: str) -> dict[str, Any]:
        """Extrai regra causal a partir de logs de falha para aprendizado do grafo."""
        log_lower = incident_log.lower()
        root_cause = "Indeterminada"
        rule = "Monitorar métricas de execução."

        if "out of memory" in log_lower or "oom" in log_lower or "context size has been exceeded" in log_lower:
            root_cause = "Estouro de capacidade de VRAM / Limite de contexto do modelo"
            rule = "Reduzir tamanho de batch (EMBEDDING_BATCH_SIZE=5) ou direcionar query GRAPH_COMPLETION para Cloud."
        elif "connection refused" in log_lower or "econnrefused" in log_lower:
            root_cause = "Serviço dependente offline ou porta incorreta"
            rule = "Verificar status do serviço via ports-and-services.json antes de disparar requisições."
        elif "rate limit" in log_lower or "429" in log_lower:
            root_cause = "Rate limit de provedor externo atingido"
            rule = "Ativar fallback automático para provedores locais (LocalAI/vLLM) ou Zen Gateway."

        return {
            "root_cause": root_cause,
            "actionable_rule": rule,
            "formatted_memory": f"INCIDENT LESSON: {root_cause} -> PREVENTIVE ACTION: {rule}",
        }

    # -----------------------------------------------------------------------
    # 6. Persistence Policy Gate (fallback local do Decision Matrix Router)
    # -----------------------------------------------------------------------
    def should_persist_memory(self, fact: str, *, source: str | None = None) -> dict[str, Any]:
        """Decide para qual camada um fato deve ir antes de qualquer escrita durável.

        Substitui localmente o `decision-matrix` do reasoning.services (bloqueado no
        plano trial). Aplica, nesta ordem: limite de escopo do Cognee (nunca dados de
        domínio/pessoais — ver docs/cognee-architecture.json#scope_boundary), segredos,
        ruído transitório, sinais de decisão/incidente estável e conteúdo de referência.
        """
        sources = [source] if source else []
        text = (fact or "").strip()

        if not text:
            return {
                "destination": "discard",
                "confidence": 1.0,
                "sources": sources,
                "reason": "Fato vazio ou apenas espaços em branco.",
                "requires_review": False,
            }

        lower = text.lower()

        cpf_pattern = re.search(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", text)
        domain_data_markers = [
            "cpf de",
            "nome do cidadão",
            "nome da cidadã",
            "dados pessoais de",
            "voto do deputado",
            "registro de transferência de",
            "beneficiário:",
            "número do benefício",
        ]
        if cpf_pattern or any(marker in lower for marker in domain_data_markers):
            return {
                "destination": "discard",
                "confidence": 0.9,
                "sources": sources,
                "reason": (
                    "Conteúdo aparenta ser dado de domínio (pessoal/político/transferência), "
                    "fora do escopo do Cognee neste workspace."
                ),
                "requires_review": True,
            }

        secret_markers = ["api_key=", "api-key:", "senha:", "password:", "token:", "secret:", "bearer "]
        if any(marker in lower for marker in secret_markers):
            return {
                "destination": "discard",
                "confidence": 0.95,
                "sources": sources,
                "reason": "Conteúdo aparenta conter segredo/credencial; nunca persistir em nenhuma camada.",
                "requires_review": True,
            }

        # Checar marcadores de decisão/causa-raiz estável ANTES do filtro de
        # ruído/texto-curto: uma decisão concisa (ex.: "Decisão: usar X.", <80
        # chars) tem que ir para cognee, não ser descartada como ruído só por
        # ser curta. Regressão 2026-08-17 (docs/decision_reviews.md) — a ordem
        # antiga classificava decisões curtas como "session".
        stable_markers = ["decisão:", "causa raiz", "adr", "arquitetura", "lição", "incidente", "regra:", "convenção"]
        if any(marker in lower for marker in stable_markers):
            return {
                "destination": "cognee",
                "confidence": 0.75,
                "sources": sources,
                "reason": "Características de decisão arquitetural, causa raiz ou regra estável — bom nó de grafo.",
                "requires_review": False,
            }

        noise_markers = ["tool_call", "stdout:", "stderr:", "traceback (most recent", "exit code"]
        if any(marker in lower for marker in noise_markers) or len(text) < 80:
            return {
                "destination": "session",
                "confidence": 0.6,
                "sources": sources,
                "reason": "Ruído transitório de execução/trace, ou curto demais para ser um fato durável.",
                "requires_review": False,
            }

        doc_markers = ["```", "## ", "endpoint:", "parâmetros:", "exemplo:"]
        if any(marker in lower for marker in doc_markers):
            return {
                "destination": "qdrant",
                "confidence": 0.55,
                "sources": sources,
                "reason": (
                    "Trecho de documentação/referência operacional — recuperação semântica de "
                    "chunks é mais adequada que grafo, evita duplicar o RAG v8."
                ),
                "requires_review": False,
            }

        return {
            "destination": "cognee",
            "confidence": 0.4,
            "sources": sources,
            "reason": "Sem sinais fortes de categoria; default conservador com baixa confiança.",
            "requires_review": True,
        }
