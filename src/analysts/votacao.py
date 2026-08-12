"""Analista — Classificação Política + Alinhamento e Dissenso (FUSÃO).

Fase 2 refactor (2026-08-10): substitui os analistas `classificador` e
`alinhamento` (que consumiam o MESMO par [VOTO]+[DISCURSO_PLENARIO] e ambos
calculavam "% de alinhamento com o governo") por UMA chamada LLM com duas
subseções.

Seção: "CLASSIFICAÇÃO POLÍTICA + ALINHAMENTO E DISSENSO"
Chunks: [VOTO], [DISCURSO_PLENARIO]
Saída: JSON estruturado (secoes[], fatos[], flags[]) — ver base.qc_estruturado.

Fallback: se o modelo não emitir JSON válido, o QC legado por keywords ainda
avalia o markdown (teto de 60 pontos) — evita regressão total.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import (
    AnalystBase,
    Briefing,
    qc_estruturado,
)

log = logging.getLogger(__name__)

_SCHEMA = """{
  "secoes": [
    "**CLASSIFICAÇÃO**: [GOVERNO | OPOSIÇÃO | INDEPENDENTE | SEM DADOS SUFICIENTES]\\n- **Alinhamento estimado**: XX%\\n- **Fundamentação**: ...\\n- **Dissenso relevante**: ...",
    "**ALINHAMENTO COM O GOVERNO**: ~XX%\\n- *Pautas de convergência*: ...\\n- *Pautas de divergência*: ...\\n\\n**DISSENSO PARTIDÁRIO**: ...\\n\\n**PADRÃO DE OBSTruÇÃO**: [SIM/NÃO/MODERADO]\\n\\n**EVOLUÇÃO TEMPORAL**: ..."
  ],
  "fatos": [
    {"categoria": "alinhamento", "valor": "XX%", "fonte_chunk_id": "VOTO"},
    {"categoria": "classificacao", "valor": "GOVERNO", "fonte_chunk_id": "VOTO"}
  ],
  "flags": ["DISSENSO_PARTIDARIO" | "OBSTRUCAO" | "ALINHADO" | "OPOSICAO" | "INDEPENDENTE"]
}"""


@register_analyst
class AnalistaVotacao(AnalystBase):
    analyst_id = "votacao"
    section_title = "CLASSIFICAÇÃO POLÍTICA + ALINHAMENTO E DISSENSO"
    required_chunks = ["[VOTO]", "[DISCURSO_PLENARIO]"]
    min_chunks = 2

    system_prompt = (
        "Você é um analista político especializado em comportamento legislativo. "
        "Classifique o alinhamento do parlamentar com o governo federal com base "
        "exclusivamente em dados empíricos de votação nominal e discursos. "
        "Seja objetivo e baseie-se nos números. Responda APENAS com JSON válido."
    )

    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        if briefing and briefing.is_useful:
            ctx = self._format_briefing(briefing)
            origem = "BRIEFING SINTETIZADO"
        else:
            ctx = self._format_context(context)
            origem = "DADOS CRUZ (VOTAÇÕES + DISCURSOS)"

        return f"""Analise os dados abaixo e produza a classificação política E o alinhamento do deputado federal {nome}.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Classifique em uma das categorias:
   **GOVERNO** — vota com o governo >70% das vezes
   **OPOSIÇÃO** — vota contra o governo >60% das vezes
   **INDEPENDENTE** — alinhamento entre 40% e 70%, ou vota com o governo em pautas econômicas e contra em costumes (ou vice-versa)
2. Calcule o percentual aproximado de alinhamento com o governo federal.
3. Identifique pautas específicas de convergência e divergência.
4. Destaque votações com dissenso partidário (contra a orientação do próprio partido).
5. Identifique padrões de obstrução (requerimentos, destaques, abstenções).
6. Use discursos para corroborar ou contrastar com os votos.

RESPONDA APENAS COM JSON VÁLIDO, neste schema exato (sem texto fora do JSON):
{_SCHEMA}
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        # QC estruturado determinístico
        qc_pass, qc_score = qc_estruturado(
            output,
            getattr(self, "_last_chunks", []),
            campos_obrigatorios=["secoes", "fatos"],
            min_secoes=2,
        )
        if qc_pass or qc_score > 0:
            return qc_pass, qc_score

        # Fallback legado (markdown): teto de 60 — estruturado é preferido
        normalized = (
            __import__("unicodedata")
            .normalize("NFKD", output)
            .encode("ascii", "ignore")
            .decode("ascii")
            .upper()
        )
        has_classif = any(
            w in normalized
            for w in ["GOVERNO", "OPOSICAO", "INDEPENDENTE", "SEM DADOS"]
        )
        has_pct = bool(re.search(r"\d+%", output))
        has_pauta = any(
            w in normalized
            for w in ["CONVERG", "DIVERG", "DISSENSO", "ALINHAMENTO", "OBSTRU"]
        )
        if has_classif and has_pct and has_pauta:
            return True, 60.0
        elif has_classif and has_pct:
            return True, 50.0
        elif has_classif:
            return True, 40.0
        return False, 10.0
