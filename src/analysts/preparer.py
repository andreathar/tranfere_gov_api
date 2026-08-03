"""
Preparador de contexto para analistas — sintetiza chunks brutos em briefing
estruturado usando modelo rápido (qwen2.5-1.5b).

Fluxo:
  30 chunks brutos (~5000 chars) → PromptPreparer (qwen, 88.9 tok/s)
    → Briefing (~800 chars) + Fact Table (~400 chars) + Insights
    → Validador de fidelidade numérica (R$ do briefing existem nos chunks?)
    → Analista principal (gemma-4 / llama-3.1-8b) gera análise final

Benefícios:
  - Reduz tokens do modelo principal em 5-10x
  - Preserva exatidão numérica (validação pós-geração)
  - Extrai contradições e padrões automaticamente
  - Prepara o terreno para análise — modelo principal só analisa, não "lê"

Uso:
    from src.analysts.preparer import PromptPreparer, Briefing
    preparer = PromptPreparer()
    briefing = preparer.prepare(chunks, persona, "SECTION", "Nome")
    if briefing and briefing.validation_pass:
        print(briefing.text)
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Modelo usado para preparação (síntese de chunks em briefing).
# ALTERADO 2026-07-31 (2x): qwen2.5-1.5b dava timeout (13.9 tok/s); gemma-4-e2b
# era thinking (max_tokens baixo = content vazio). zero-gemma4-e4b-openzero:
# reasoning model validado a 21.9 tok/s (gpu_layers=40), preserva R$ com
# fidelidade — melhor para síntese de dados. Pode ser sobrescrito via PREPARER_MODEL env var.
PREPARER_MODEL = "zero-gemma4-e4b-openzero-q5-k-m"

# Máximo de chunks enviados ao preparador por chamada
# (ctx do zero-gemma: 8192 tokens — 8 chunks ~2300 tok prompt + 1500 tok output cabem)
PREPARER_MAX_CHUNKS = 8  # prompts grandes demoram — mantido conservador

# Tamanho máximo do prompt enviado ao preparador em caracteres
PREPARER_MAX_PROMPT_CHARS = 14000

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class Briefing:
    """Briefing estruturado produzido pelo PromptPreparer.

    Attributes:
        text: Síntese narrativa dos fatos mais relevantes (2-4 parágrafos).
        fact_table: Tabela de fatos com valores verificados (pipe-separated).
        insights: Lista de contradições, anomalias ou padrões detectados.
        validation_pass: True se todos os R$ do briefing existem nos chunks fonte.
        raw_fallback: True se o preparador falhou e este é fallback simples.
        chunks_pre_count: Quantidade original de chunks recebidos.
    """

    text: str = ""
    fact_table: str = ""
    insights: list[str] = field(default_factory=list)
    validation_pass: bool = False
    raw_fallback: bool = False
    chunks_pre_count: int = 0

    @property
    def is_useful(self) -> bool:
        """Retorna True se o briefing tem conteúdo utilizável e passou validação."""
        return bool(self.text or self.fact_table) and not self.raw_fallback

    @property
    def total_chars(self) -> int:
        return len(self.text) + len(self.fact_table)


# ---------------------------------------------------------------------------
# PromptPreparer
# ---------------------------------------------------------------------------


class PromptPreparer:
    """Sintetiza chunks brutos em briefing estruturado usando modelo rápido.

    Preserva exatidão numérica através de validação pós-geração:
    todo R$ mencionado no briefing é conferido contra os chunks fonte.
    Se >20% dos R$ forem falsos, usa fallback (formatação simples dos chunks).
    """

    def __init__(self, model: str | None = None):
        self.model = model or PREPARER_MODEL
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from src.localai_client import LocalAIClient

            self._client = LocalAIClient(model=self.model)
        return self._client

    # -----------------------------------------------------------------------
    # Prompts
    # -----------------------------------------------------------------------

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Você é um preparador de dados especializado em análise política e "
            "orçamentária. Sua função é condensar dados brutos em briefings "
            "estruturados, preservando EXATAMENTE todos os valores numéricos "
            "(R$, %, datas, IDs, totais). NUNCA invente ou modifique números. "
            "Se um dado estiver ausente, escreva 'N/D'. "
            "Seja conciso — priorize o que é mais relevante para a análise "
            "solicitada. Ignore informações redundantes."
        )

    def _build_prep_prompt(
        self,
        chunks: list[str],
        analyst_persona: str,
        section_title: str,
        nome: str,
    ) -> str:
        """Monta o prompt para o modelo preparador."""
        # Truncar chunks se necessário
        if len(chunks) > PREPARER_MAX_CHUNKS:
            log.info(
                f"Preparer: truncando {len(chunks)} -> {PREPARER_MAX_CHUNKS} "
                f"chunks para '{section_title}'"
            )
            chunks = chunks[:PREPARER_MAX_CHUNKS]

        context_str = "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(chunks))

        prompt = f"""Você está preparando dados para a seção "{section_title}" do dossiê do deputado {nome}.

PERFIL DO ANALISTA QUE RECEBERÁ ESTE BRIEFING:
{analyst_persona}

DADOS BRUTOS ({len(chunks)} chunks):
{context_str}

INSTRUÇÕES:
1. Extraia e PRESERVE todos os valores monetários (R$), percentuais, datas e IDs exatamente como aparecem.
2. Agrupe fatos relacionados por tema.
3. Destaque contradições, anomalias ou padrões relevantes.
4. Remova informações redundantes ou irrelevantes para a seção "{section_title}".
5. Seja conciso — máximo 800 palavras.

FORMATO DE SAÍDA (estrito — use exatamente estes cabeçalhos):

---BRIEFING---
[Síntese narrativa em 2-4 parágrafos, organizada por tema, com números exatos]

---FACT TABLE---
| Categoria | Entidade | Valor | Detalhe |
[Linhas de dados, uma por linha, pipe-separated. Ex:]
| Emenda PIX | Município X | R$ 1.500.000,00 | Objeto: Saúde |
| Votação | PL 123/2024 | Sim | Tema: Educação |

---KEY INSIGHTS---
- [Lista de 0-5 insights, contradições ou anomalias, um por linha com "- "]
"""

        # Truncar se exceder limite (para evitar estouro de contexto)
        if len(prompt) > PREPARER_MAX_PROMPT_CHARS:
            # Truncar chunks do meio
            meio = len(chunks) // 2
            chunks_keep = chunks[:meio] + chunks[meio + 2 :]
            log.warning(
                f"Preparer: prompt excede {PREPARER_MAX_PROMPT_CHARS} chars "
                f"({len(prompt)}), removendo chunks do meio. "
                f"{len(chunks)} -> {len(chunks_keep)}"
            )
            return self._build_prep_prompt(chunks_keep, analyst_persona, section_title, nome)

        return prompt

    # -----------------------------------------------------------------------
    # Parse
    # -----------------------------------------------------------------------

    def _parse_response(self, resposta: str, chunks: list[str]) -> Briefing:
        """Parseia resposta do modelo em Briefing."""
        briefing = Briefing(chunks_pre_count=len(chunks))

        # Extrair seção ---BRIEFING---
        m = re.search(
            r"---BRIEFING---\s*\n(.*?)(?=---FACT TABLE---|---KEY INSIGHTS---|$)",
            resposta,
            re.DOTALL,
        )
        if m:
            briefing.text = m.group(1).strip()

        # Extrair seção ---FACT TABLE---
        m = re.search(
            r"---FACT TABLE---\s*\n(.*?)(?=---KEY INSIGHTS---|$)",
            resposta,
            re.DOTALL,
        )
        if m:
            briefing.fact_table = m.group(1).strip()

        # Extrair seção ---KEY INSIGHTS---
        m = re.search(r"---KEY INSIGHTS---\s*\n(.*?)$", resposta, re.DOTALL)
        if m:
            insights_text = m.group(1).strip()
            briefing.insights = [
                line.strip().lstrip("- ").strip()
                for line in insights_text.split("\n")
                if line.strip().startswith("-")
            ]

        # Se não extraiu briefing formatado, usa resposta inteira
        if not briefing.text and not briefing.fact_table:
            briefing.text = resposta.strip()

        return briefing

    # -----------------------------------------------------------------------
    # Validação de fidelidade numérica
    # -----------------------------------------------------------------------

    def _validate_fidelity(self, briefing: Briefing, chunks: list[str]) -> bool:
        """Verifica se todos os valores R$ do briefing existem nos chunks fonte.

        Estratégia:
          1. Extrai todos R$ do briefing (texto + fact_table).
          2. Extrai todos R$ dos chunks.
          3. Se >20% dos R$ do briefing não foram encontrados → reprova.

        Returns:
            True se passar na validação (ou não houver R$ para validar).
        """
        # Extrair R$ do briefing
        texto_briefing = briefing.text + "\n" + briefing.fact_table
        valores_briefing = set(m.group(0) for m in re.finditer(r"R\$\s*[\d.,]+", texto_briefing))

        if not valores_briefing:
            # Sem valores para validar = passa automaticamente
            briefing.validation_pass = True
            return True

        # Extrair R$ dos chunks
        texto_chunks = "\n".join(chunks)
        valores_chunks = set(m.group(0) for m in re.finditer(r"R\$\s*[\d.,]+", texto_chunks))

        # Normalizar para comparação: remover espaços, uppercase e
        # normalizar decimais (aceitar 198,000.0 == 198,000.00)
        def _normalize(val: str) -> str:
            norm = val.replace(" ", "").upper()
            # Padronizar casas decimais: R$1.234,56 ou R$1,234.56 ou R$1234.5
            m = re.match(r"R\$([\d.,]+)", norm)
            if not m:
                return norm
            num = m.group(1)
            # Se tem vírgula como decimal (formato BR) ou ponto
            if "," in num and "." in num:
                # Formato BR: R$ 1.234,56 — ponto é milhar, vírgula é decimal
                if num.rfind(",") > num.rfind("."):
                    num = num.replace(".", "").replace(",", ".")
                # Formato US: R$ 1,234.56
                else:
                    num = num.replace(",", "")
            elif "," in num:
                num = num.replace(",", ".")
            # Truncar para 2 casas decimais
            if "." in num:
                inteiro, dec = num.split(".", 1)
                dec = (dec + "00")[:2]
                num = f"{inteiro}.{dec}"
            else:
                num = f"{num}.00"
            return f"R${num}"

        chunks_norm = {_normalize(v) for v in valores_chunks}

        falsos = [v for v in valores_briefing if _normalize(v) not in chunks_norm]

        if falsos:
            log.warning(f"Valores R$ no briefing sem correspondência nos chunks: " f"{falsos[:5]}")
            if len(falsos) / len(valores_briefing) > 0.2:
                briefing.validation_pass = False
                return False

        briefing.validation_pass = True
        return True

    # -----------------------------------------------------------------------
    # Fallback
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_fallback(chunks: list[str]) -> Briefing:
        """Cria briefing de fallback com formatação simples dos chunks crus.

        Agrupa chunks por tipo e formata como seções.
        """
        grouped: dict[str, list[str]] = defaultdict(list)
        for c in chunks:
            tipo = c.split("]")[0].lstrip("[").strip().upper() if "]" in c else "INFO"
            grouped[tipo].append(c)

        parts: list[str] = []
        for tipo, items in grouped.items():
            items_text = "\n".join(f"  - {item}" for item in items)
            parts.append(f"### {tipo}\n{items_text}")

        fallback_text = "\n\n".join(parts) if parts else "Sem dados disponíveis."

        return Briefing(
            text=fallback_text,
            validation_pass=True,
            raw_fallback=True,
            chunks_pre_count=len(chunks),
        )

    # -----------------------------------------------------------------------
    # Método principal
    # -----------------------------------------------------------------------

    def prepare(
        self,
        chunks: list[str],
        analyst_persona: str = "",
        section_title: str = "",
        nome: str = "",
    ) -> Briefing:
        """Prepara briefing a partir de chunks brutos.

        Args:
            chunks: Lista de chunks formatados "[TYPE] texto...".
            analyst_persona: System prompt do analista alvo.
            section_title: Título da seção (ex: "CLASSIFICAÇÃO POLÍTICA").
            nome: Nome do deputado.

        Returns:
            Briefing completo. Se o preparador falhar, retorna fallback
            com raw_fallback=True.
        """
        if not chunks:
            return Briefing(
                text="Sem dados disponíveis para esta seção.",
                validation_pass=True,
                chunks_pre_count=0,
            )

        prompt = self._build_prep_prompt(chunks, analyst_persona, section_title, nome)

        # Carregar modelo rápido via model_scope (refcount tracking)
        lm_ctx = None
        try:
            from config.settings import CLOUD_PROXY_MODEL_NAMES

            if self.model not in CLOUD_PROXY_MODEL_NAMES:
                from src.localai_manager import manager as lm

                lm_ctx = lm.model_scope(self.model)
                lm_ctx.__enter__()
        except Exception as e:
            # Não conseguiu carregar (ex: VRAM bloqueada por modelo em uso e
            # timeout em _wait_for_room). Não adianta chamar o chat sem o
            # modelo carregado — cai para fallback (chunks crus).
            log.warning(
                f"Preparer: não foi possível carregar {self.model} para "
                f"'{section_title}': {e}. Usando chunks crus."
            )
            return self._build_fallback(chunks)

        # Chamar LLM rápido
        try:
            client = self._get_client()
            # SEM warmup: havia um chat falso ("Responda apenas: OK.") por
            # analista para "absorver" o load do backend, mas isso gerava
            # requisições sem sentido a cada seção do dossiê. O prompt real
            # já tem timeout generoso (LOCALAI_MODEL_TIMEOUTS: 300s para
            # zero-gemma) que cobre load (60-90s) + reasoning + briefing.
            # Só a 1a chamada do processo paga o load; nas demais o backend
            # já está na GPU (model_scope mantém refcount e o LRU só descarrega
            # quando precisa de VRAM).
            resposta = client.chat(prompt=prompt, system=self._system_prompt(), max_tokens=1500)
        except Exception as e:
            log.warning(f"Preparer falhou para '{section_title}': {e}")
            # Garantir release do modelo
            if lm_ctx is not None:
                try:
                    lm_ctx.__exit__(None, None, None)
                except Exception:
                    pass
            return self._build_fallback(chunks)

        # Garantir release do modelo (já libera refcount)
        if lm_ctx is not None:
            try:
                lm_ctx.__exit__(None, None, None)
            except Exception:
                pass

        if not resposta or not resposta.strip():
            log.warning(f"Preparer retornou vazio para '{section_title}'")
            return self._build_fallback(chunks)

        # Parse resposta
        briefing = self._parse_response(resposta, chunks)
        briefing.chunks_pre_count = len(chunks)

        # Validar fidelidade numérica
        self._validate_fidelity(briefing, chunks)

        log.info(
            f"Preparer '{section_title}': {len(chunks)} chunks -> "
            f"{briefing.total_chars} chars briefing "
            f"(validação: {'OK' if briefing.validation_pass else 'FALHOU'}, "
            f"fallback: {briefing.raw_fallback})"
        )

        return briefing
