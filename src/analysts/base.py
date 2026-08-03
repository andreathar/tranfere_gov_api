"""
Classes base para o sistema Multi-Analista RAG v7.

Define:
    - AnalystResult: dataclass com resultado de um analista
    - AnalystBase: classe abstrata que cada analista concreto implementa
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.localai_client import LocalAIClient
from src.localai_manager import manager as localai_manager

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fidelidade numerica de valores R$ (compartilhado pelos analistas)
#
# ANTES: comparacao por STRING exata ("R$ 10.353.574,99" != "R$ 10,353,574.99")
#   -> penalizava valores corretos que o LLM reformatou ou somou (falso-positivo).
# AGORA: parse numerico (BR e US) + tolerancia relativa de 2% + aceite do total
#   agregado dos chunks. Só é "invencao" um valor que nao bate com NENHUM numero
#   real dos chunks (nem com a soma deles).
# ---------------------------------------------------------------------------

# Captura "R$ 10.353.574,99", "R$ 1,234,567.89", "R$ 2,5 milhões", "R$ 5 mil"...
_RE_RS_TOKEN = re.compile(
    r"R\$\s*([\d][\d.,]*)\s*"
    r"(bilhões|bilhoes|bilhão|bilhao|milhões|milhoes|milhão|milhao|mil|mi|bi)?",
    re.IGNORECASE,
)

_RS_SUFIXO_MULT = {
    "bi": 1e9,
    "bilhao": 1e9,
    "bilhões": 1e9,
    "bilhoes": 1e9,
    "bilhão": 1e9,
    "mi": 1e6,
    "milhao": 1e6,
    "milhões": 1e6,
    "milhoes": 1e6,
    "milhão": 1e6,
    "mil": 1e3,
}


def parse_brl_token(raw: str) -> float | None:
    """Converte token numerico em float, aceitando BR e US.

    '1.234.567,89' (BR) -> 1234567.89 ; '1,234,567.89' (US) -> 1234567.89
    '5.400.000,0' (BR sem 2 dec) -> 5400000.0 ; '1234567' -> 1234567.0
    O token pode vir com separador final de pontuacao ('.' de fim de frase ou
    ',' antes de texto) que e aparado antes do parse.
    """
    raw = raw.replace(" ", "").rstrip(".,")
    if not raw or not raw.replace(".", "").replace(",", "").isdigit():
        return None
    if "," in raw and "." in raw:
        # O separador que aparece por ultimo é o decimal
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        # So virgula(s): se a ultima delimitar 1-2 casas, ela e decimal e as
        # demais sao milhar (ex.: '123,45', '40,443,658,00' misto US+BR,
        # '5,444,39'). Caso contrario, virgulas sao separadores de milhar.
        partes = raw.split(",")
        if len(partes[-1]) in (1, 2):
            raw = "".join(partes[:-1]) + "." + partes[-1]
        else:
            raw = raw.replace(",", "")
    else:
        # So ponto(s): '1.234' (1 ponto, decimal) vs '40.443.658' (milhar BR
        # sem decimal — multiplos pontos com grupos de 3 digitos).
        if raw.count(".") >= 2:
            partes = raw.split(".")
            if all(len(p) == 3 for p in partes[1:]):
                raw = "".join(partes)
    try:
        return float(raw)
    except ValueError:
        return None


def coletar_valores_rs(texto: str) -> list[float]:
    """Extrai todos os valores numericos de tokens 'R$ ...' do texto."""
    valores: list[float] = []
    for num, suf in _RE_RS_TOKEN.findall(texto):
        v = parse_brl_token(num)
        if v is None:
            continue
        v *= _RS_SUFIXO_MULT.get(suf.lower(), 1.0)
        valores.append(v)
    return valores


def taxa_invencao_rs(output: str, chunks_text: str, tol: float = 0.02) -> float:
    """Fracao (0-1) dos R$ do output que NAO batem com os numeros dos chunks.

    Um valor do output é considerado fiel se:
      - bate com algum valor do chunk dentro de tol relativa (±2%), OU
      - bate com a SOMA de todos os R$ dos chunks (agregado "total").
    """
    out_vals = coletar_valores_rs(output)
    if not out_vals:
        return 0.0
    chunk_vals = coletar_valores_rs(chunks_text)
    if not chunk_vals:
        # Sem valores reais para comparar -> nao temos como acusar invencao
        return 0.0

    total = sum(chunk_vals)

    def fiel(v: float) -> bool:
        for c in chunk_vals:
            if abs(v - c) <= max(tol * max(abs(v), abs(c)), 1.0):
                return True
        return bool(total and abs(v - total) <= max(tol * max(abs(v), abs(total)), 1.0))

    falsos = [v for v in out_vals if not fiel(v)]
    return len(falsos) / len(out_vals)


# Import do Briefing (opcional — preparer pode nao estar disponivel)
try:
    from src.analysts.preparer import Briefing as _Briefing

    Briefing = _Briefing  # type: ignore[assignment]
except ImportError:
    # Fallback: Briefing dummy para compatibilidade quando preparer nao existe
    from dataclasses import dataclass as _dc

    @_dc
    class Briefing:  # type: ignore
        """Dummy briefing usado quando preparer nao esta disponivel."""

        text: str = ""
        fact_table: str = ""
        insights: list = field(default_factory=list)
        validation_pass: bool = False
        raw_fallback: bool = True
        chunks_pre_count: int = 0

        @property
        def is_useful(self) -> bool:
            return False

        @property
        def total_chars(self) -> int:
            return 0


@dataclass
class AnalystResult:
    """Resultado da execucao de um analista.

    Attributes:
        analyst_id: Identificador unico do analista (ex: "classificador").
        section_title: Titulo da secao para o dossier (ex: "CLASSIFICACAO POLITICA").
        content: Texto markdown da secao gerada.
        quality_ok: Se o quality check proprio foi aprovado.
        quality_score: Pontuacao 0-100 do quality check.
        duration: Duracao em segundos.
        chunks_used: Lista dos chunks usados (para rastreabilidade).
        briefing: Briefing preparado (se use_preparer=True).
    """

    analyst_id: str
    section_title: str
    content: str
    quality_ok: bool
    quality_score: float
    duration: float = 0.0
    chunks_used: list[str] = field(default_factory=list)
    briefing: Briefing | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyst_id": self.analyst_id,
            "section_title": self.section_title,
            "quality_ok": self.quality_ok,
            "quality_score": self.quality_score,
            "duration": self.duration,
            "content_len": len(self.content),
            "chunks_count": len(self.chunks_used),
            "briefing_chars": self.briefing.total_chars if self.briefing else 0,
        }


class AnalystBase(ABC):
    """Classe base para todos os analistas especialistas.

    Cada analista concreto deve definir:
        - analyst_id: str (ex: "classificador")
        - section_title: str (ex: "CLASSIFICACAO POLITICA")
        - required_chunks: list[str] (ex: ["[VOTO]", "[DISCURSO_PLENARIO]"])
        - min_chunks: int (minimo de chunks para ativar)
        - system_prompt: str (instrucao de sistema para o LLM)

    E implementar:
        - build_prompt(context, nome, briefing) -> str
        - quality_check(output) -> tuple[bool, float]

    Novas funcionalidades:
        - use_preparer: bool (default True) — ativa PromptPreparer para
          sintetizar chunks brutos em briefing antes de montar o prompt.
          O analista recebe o briefing em build_prompt() e pode optar por
          usá-lo ou ignorá-lo.
    """

    analyst_id: str = ""
    section_title: str = ""
    required_chunks: list[str] = []
    min_chunks: int = 1
    system_prompt: str = (
        "Voce e um analista investigativo especializado em contas publicas e ciencia politica."
    )
    use_preparer: bool = True  # Se True, usa PromptPreparer para sintetizar chunks

    @abstractmethod
    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        """Monta o prompt especifico para este analista.

        Args:
            context: Lista de chunks filtrados (raw).
            nome: Nome do deputado.
            briefing: Briefing opcional preparado pelo PromptPreparer.
                     Quando disponivel e is_useful, contém síntese dos
                     chunks + fact table + insights.
        """
        ...

    @abstractmethod
    def quality_check(self, output: str) -> tuple[bool, float]:
        """Valida a qualidade da secao gerada.

        Returns:
            (aprovado: bool, pontuacao: float 0-100)
        """
        ...

    def _format_context(self, context: list[str]) -> str:
        """Formata a lista de chunks para inclusao no prompt."""
        return "\n".join(f"  - {c}" for c in context)

    def _format_briefing(self, briefing: Briefing) -> str:
        """Formata o briefing para inclusao no prompt.

        Usado pelo fallback em build_prompt se o analista nao sobrescrever.
        Inclui texto narrativo + fact table + insights (se houver).
        """
        parts: list[str] = []

        if briefing.text:
            parts.append(briefing.text)

        if briefing.fact_table and briefing.fact_table.count("|") > 4:
            parts.append(f"\n---TABELA DE FATOS---\n{briefing.fact_table}")

        if briefing.insights:
            insights_fmt = "\n".join(f"- {insight}" for insight in briefing.insights)
            parts.append(f"\n---INSIGHTS DETECTADOS---\n{insights_fmt}")

        return "\n\n".join(parts) if parts else self._format_context([])

    def run(
        self,
        context: list[str],
        nome: str,
        llm_model: str = "",
        use_preparer: bool | None = None,
    ) -> AnalystResult:
        """Executa o analista: prepara briefing -> monta prompt -> chama LLM -> quality check.

        Com use_preparer=True (default):
          1. PromptPreparer sintetiza chunks brutos em briefing estruturado
             usando modelo rápido (qwen2.5-1.5b).
          2. build_prompt() recebe briefing + chunks.
          3. O analista pode usar o briefing (recomendado) ou ignorá-lo.

        Args:
            context: Lista de chunks filtrados para este analista.
            nome: Nome do deputado.
            llm_model: Modelo LLM a usar (padrao: definido em settings).

        Returns:
            AnalystResult com o resultado completo (incluindo briefing usado).
        """
        if not llm_model:
            from config.settings import RAG_LLM_MODEL

            llm_model = RAG_LLM_MODEL

        # 1. Preparacao do briefing (se ativado)
        # use_preparer: None usa o default da classe; True/False força.
        use_prep = self.use_preparer if use_preparer is None else use_preparer
        briefing: Briefing | None = None
        if use_prep:
            try:
                from src.analysts.preparer import PromptPreparer

                preparer = PromptPreparer()
                briefing = preparer.prepare(
                    chunks=context,
                    analyst_persona=self.system_prompt,
                    section_title=self.section_title,
                    nome=nome,
                )
            except Exception as e:
                log.warning(
                    f"[{self.analyst_id}] Preparer exception: {e}, " f"usando chunks crus."
                )

        # 2. Montar prompt (analista decide se usa briefing ou nao)
        prompt = self.build_prompt(context, nome, briefing)
        inicio = time.time()

        # 3. Chamar LLM com model_scope (refcount + VRAM inteligente)
        #    temperature=0.1: mais deterministico, reduz alucinacao de valores
        #    (taxa_invencao_rs e o QC penalizam fortemente R$ inventados).
        try:
            with localai_manager.model_scope(llm_model):
                ai_client = LocalAIClient(model=llm_model)
                resposta = ai_client.chat(
                    prompt=prompt,
                    system=self.system_prompt,
                    temperature=0.1,
                )
                duracao = time.time() - inicio
            log.info(
                f"  [{self.analyst_id}] Gerado em {duracao:.1f}s "
                f"({len(resposta)} chars, prompt ~{len(prompt)} chars)"
            )
        except Exception as e:
            duracao = time.time() - inicio
            log.error(f"  [{self.analyst_id}] Falha na geracao: {e}")
            return AnalystResult(
                analyst_id=self.analyst_id,
                section_title=self.section_title,
                content=f"*[Falha na geracao: {e}]*",
                quality_ok=False,
                quality_score=0.0,
                duration=duracao,
                chunks_used=context,
                briefing=briefing,
            )

        # 5. Quality check (com acesso aos chunks via self._last_chunks)
        self._last_chunks = context
        self._last_briefing = briefing
        qc_pass, qc_score = self.quality_check(resposta)

        return AnalystResult(
            analyst_id=self.analyst_id,
            section_title=self.section_title,
            content=resposta.strip(),
            quality_ok=qc_pass,
            quality_score=qc_score,
            duration=duracao,
            chunks_used=context,
            briefing=briefing,
        )
