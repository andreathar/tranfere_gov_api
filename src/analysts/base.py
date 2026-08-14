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

    # PITFALL 2026-08-11: o 3B preenche tabelas com 'R$ 0,00' para áreas
    # sem emenda do político (placeholder de tabela, não fabricação).
    # Contar zeros como invenção reprovava dossiers fieis (tematicas 82%).
    # Zeros são neutros: ignorados na contagem de falsos e no denominador.
    relevantes = [v for v in out_vals if v > 0]
    if not relevantes:
        return 0.0
    falsos = [v for v in relevantes if not fiel(v)]
    return len(falsos) / len(relevantes)

# ---------------------------------------------------------------------------
# Saída estruturada (JSON) — Fase 2 refactor 2026-08-10
#
# Contrato por analista:
#   {
#     "secoes": ["markdown narrativa..."],
#     "fatos": [{"categoria": "...", "valor": "R$ 1.234,56", "fonte_chunk_id": "EMENDA"}],
#     "flags": ["ALERTA", ...]
#   }
# - secoes[] alimenta o dossier final (renderização markdown inalterada)
# - fatos[] permite QC determinístico: fidelidade R$ + rastreabilidade por chunk
# - flags[] expõe alertas estruturados (anomalias, red flags)
# ---------------------------------------------------------------------------


def parse_structured_output(output: str) -> dict | None:
    """Tenta parsear o JSON estruturado do output de um analista.

    Estratégias em ordem: json.loads direto -> bloco ```json ... ``` ->
    primeiro bloco {...} balanceado. Retorna None se nenhuma funcionar.
    """
    import json

    output = output.strip()
    if not output:
        return None

    # 1) Direto
    try:
        parsed = json.loads(output)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    # 2) Bloco ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

    # 3) Primeiro bloco { ... } balanceado
    inicio = output.find("{")
    if inicio != -1:
        profundidade = 0
        for i in range(inicio, len(output)):
            ch = output[i]
            if ch == "{":
                profundidade += 1
            elif ch == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        parsed = json.loads(output[inicio : i + 1])
                        return parsed if isinstance(parsed, dict) else None
                    except Exception:
                        break
    return None


def render_secoes_markdown(content: str) -> str:
    """Extrai a narrativa markdown de um output estruturado (secoes[]).

    Se o conteúdo não for JSON estruturado, retorna o conteúdo original
    (backward-compat com analistas v7 em markdown puro).
    """
    dados = parse_structured_output(content)
    if dados and isinstance(dados.get("secoes"), list):
        secoes = [str(s) for s in dados["secoes"] if str(s).strip()]
        if secoes:
            return "\n\n".join(secoes)
    return content


def qc_estruturado(
    output: str,
    chunks: list[str],
    *,
    campos_obrigatorios: list[str],
    min_secoes: int = 1,
    max_taxa_invencao: float = 0.2,
) -> tuple[bool, float]:
    """QC determinístico para saída estruturada (JSON).

    Valida, nesta ordem:
      1. JSON válido com os campos obrigatórios (senão 0).
      2. Fidelidade R$: valores citados nos fatos/secoes devem existir nos
         chunks (taxa_invencao_rs, tolerância 2%).
      3. Rastreabilidade: cada fato com fonte_chunk_id deve corresponder a um
         tipo de chunk presente no contexto (ex.: "EMENDA").
      4. Cobertura: bônus por número de seções (>= min_secoes).

    Returns:
        (aprovado: bool, score: float 0-100). Aprovado se score >= 50.
    """
    dados = parse_structured_output(output)
    if dados is None:
        return False, 0.0

    faltando = [c for c in campos_obrigatorios if c not in dados]
    if faltando:
        return False, 10.0

    secoes = [str(s) for s in (dados.get("secoes") or []) if str(s).strip()]
    fatos = [f for f in (dados.get("fatos") or []) if isinstance(f, dict)]
    fatos_invalidos = sum(
        1
        for f in fatos
        if not str(f.get("valor", "")).strip() or not str(f.get("fonte_chunk_id", "")).strip()
    )

    # 2. Fidelidade R$ sobre o texto inteiro (fatos + secoes)
    texto_fatos = " ".join(str(f.get("valor", "")) for f in fatos)
    texto_total = texto_fatos + "\n" + "\n".join(secoes)
    chunks_text = "\n".join(chunks)
    taxa = 0.0
    try:
        taxa = taxa_invencao_rs(texto_total, chunks_text)
    except Exception as exc:
        # Falha ao medir fidelidade: pior caso, tratar como invenção total
        log.warning("taxa_invencao_rs falhou no QC estruturado: %s", exc)
        taxa = 1.0

    # 3. Rastreabilidade por tipo de chunk
    tipos_contexto = {
        c.split("]")[0].lstrip("[").strip().upper()
        for c in chunks
        if "]" in c
    }
    fontes_invalidas = sum(
        1
        for f in fatos
        if f.get("fonte_chunk_id")
        and str(f["fonte_chunk_id"]).strip().upper() not in tipos_contexto
    )

    # 4. Score
    score = 50.0
    score += min(len(secoes) / max(min_secoes, 1), 1.0) * 30.0
    if taxa <= max_taxa_invencao:
        score += 20.0
    else:
        score -= (taxa - max_taxa_invencao) * 100.0
    if fontes_invalidas:
        score -= min(fontes_invalidas * 5.0, 30.0)
    if not fatos:
        score -= 10.0
    if fatos_invalidos:
        score -= min(fatos_invalidos * 5.0, 20.0)

    score = round(min(max(score, 0.0), 100.0), 1)
    return score >= 50.0, score


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


def persistir_qc(
    *,
    politico_id: int,
    tipo_politico: str,
    analyst_id: str,
    section_title: str,
    quality_ok: bool,
    quality_score: float,
    duration: float,
    chunks_count: int,
    briefing_chars: int,
    llm_model: str,
) -> None:
    """Persiste o resultado do QC de um analista em dossie_analyst_qc.

    Best-effort: nunca levanta exceção — telemetria não pode quebrar a
    geração do dossiê. Controlada por RAG_PERSIST_QC (config/settings.py).
    """
    try:
        from config.settings import RAG_PERSIST_QC

        if not RAG_PERSIST_QC:
            return

        from src.db_utils import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dossie_analyst_qc
                        (politico_id, tipo_politico, analyst_id, section_title,
                         quality_ok, quality_score, duration_sec, chunks_count,
                         briefing_chars, llm_model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        politico_id,
                        tipo_politico,
                        analyst_id,
                        section_title,
                        quality_ok,
                        quality_score,
                        duration,
                        chunks_count,
                        briefing_chars,
                        llm_model,
                    ),
                )
            conn.commit()
    except Exception as e:
        log.warning(
            f"persistir_qc: falha ao salvar QC do analista {analyst_id} "
            f"({tipo_politico} {politico_id}): {e}"
        )


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
        shared_briefing: Briefing | None = None,
        tipo_politico: str = "deputado",
        politico_id: int | None = None,
    ) -> AnalystResult:
        """Executa o analista: prepara briefing -> monta prompt -> chama LLM -> quality check.

        Com use_preparer=True (default):
          1. PromptPreparer sintetiza chunks brutos em briefing estruturado
             usando modelo rápido (qwen2.5-1.5b).
          2. build_prompt() recebe briefing + chunks.
          3. O analista pode usar o briefing (recomendado) ou ignorá-lo.

        Fase 1 (2026-08-10): se `shared_briefing` for fornecido (briefing ÚNICO
        preparado pelo orquestrador), pula a preparação local — reduz o número
        de chamadas LLM de ~7 para 1 por dossiê.

        Args:
            context: Lista de chunks filtrados para este analista.
            nome: Nome do deputado.
            llm_model: Modelo LLM a usar (padrao: definido em settings).
            use_preparer: Força liga/desliga a preparação local (None = default da classe).
            shared_briefing: Briefing compartilhado do dossiê (preparado 1× pelo
                             orquestrador). Quando presente, use_preparer é ignorado.

        Returns:
            AnalystResult com o resultado completo (incluindo briefing usado).
        """
        if not llm_model:
            from config.settings import RAG_LLM_MODEL

            llm_model = RAG_LLM_MODEL

        # Cargo do político (Fase 3): expõe vocabulário PT-BR aos prompts
        # via self._cargo (analistas usam self._cargo["singular"], etc.)
        from src.analysts.cargo import get_cargo

        self._cargo = get_cargo(tipo_politico)
        self._tipo_politico = tipo_politico

        # 1. Preparacao do briefing (se ativado e sem briefing compartilhado)
        # use_preparer: None usa o default da classe; True/False força.
        use_prep = self.use_preparer if use_preparer is None else use_preparer
        briefing: Briefing | None = None
        if shared_briefing is not None:
            briefing = shared_briefing
        elif use_prep:
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
                # Enquadramento de cargo (Fase 3): instrui o LLM a usar o
                # termo correto do cargo (senador, governador, etc.) mesmo
                # quando o template do prompt cita "deputado".
                cargo_line = (
                    f"\nO político analisado é um(a) {self._cargo['singular']} "
                    f"({self._tipo_politico}). Refira-se a ele(a) sempre como "
                    f"'{self._cargo['singular']}' e à casa/instituição como "
                    f"'{self._cargo['casa']}'."
                )
                resposta = ai_client.chat(
                    prompt=prompt,
                    system=self.system_prompt + cargo_line,
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
        # Quando o analista usa o briefing COMPARTILHADO (preparado com o
        # contexto completo), os valores R$ que ele cita podem vir do briefing
        # (já validado por fidelidade na preparação) e não dos seus chunks
        # filtrados. O QC então valida contra a UNIÃO (chunks + briefing):
        # valores do briefing são fontes legítimas — sem isso o QC acusa
        # "invenção" para valores corretos vindos de outros chunk types.
        self._last_chunks = list(context)
        if briefing is not None and briefing.is_useful:
            self._last_chunks.append(briefing.text)
            if briefing.fact_table:
                self._last_chunks.append(briefing.fact_table)
        self._last_briefing = briefing
        qc_pass, qc_score = self.quality_check(resposta)

        if politico_id is not None:
            persistir_qc(
                politico_id=politico_id,
                tipo_politico=tipo_politico,
                analyst_id=self.analyst_id,
                section_title=self.section_title,
                quality_ok=qc_pass,
                quality_score=qc_score,
                duration=duracao,
                chunks_count=len(context),
                briefing_chars=briefing.total_chars if briefing else 0,
                llm_model=llm_model,
            )

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
