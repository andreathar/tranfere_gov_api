"""
Analista 4 — Alinhamento Político e Dissenso.

Seção: "ALINHAMENTO POLÍTICO E DISSENSO NO PLENÁRIO"
Chunks: [VOTO], [DISCURSO_PLENARIO]
Tarefa: % de alinhamento com governo, pautas de dissenso, obstrução.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing

log = logging.getLogger(__name__)


@register_analyst
class AlinhamentoPolitico(AnalystBase):
    analyst_id = "alinhamento"
    section_title = "ALINHAMENTO POLÍTICO E DISSENSO NO PLENÁRIO"
    required_chunks = ["[VOTO]", "[DISCURSO_PLENARIO]"]
    min_chunks = 2

    system_prompt = (
        "Você é um analise de comportamento legislativo. Analise padrões de "
        "votação nominal para determinar alinhamento partidário, dissenso e "
        "obstrução. Baseie-se exclusivamente nos dados de votação."
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
            origem = "DADOS DE VOTAÇÃO E DISCURSOS"

        return f"""Analise os padrões de voto do deputado federal {nome} para determinar alinhamento político e dissenso.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Calcule o percentual aproximado de alinhamento com o governo federal.
2. Identifique pautas específicas em que votou com o governo vs. contra.
3. Destaque votações onde houve dissenso partidário (votou contra a orientação do próprio partido).
4. Identifique padrões de obstrução (requerimentos, destaques, abstenções).
5. Analise se o alinhamento é consistente ou varia por tema (econômico, costumes, social).
6. Incorpore discursos de plenário que reforcem ou contradigam o padrão de votação.

FORMATO DE SAÍDA (Markdown):
**ALINHAMENTO COM O GOVERNO**: ~XX%
- *Pautas de convergência*: ...
- *Pautas de divergência*: ...

**DISSENSO PARTIDÁRIO**:
- *Votou contra o partido em*: ...

**PADRÃO DE OBSTRUÇÃO**: [SIM / NÃO / MODERADO]
- ...

**EVOLUÇÃO TEMPORAL** (se houver dados de mais de um ano):
- ...
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        has_pct = bool(re.search(r"\d+%", output))
        has_pauta = any(
            word in output.upper()
            for word in [
                "CONVERG",
                "DIVERG",
                "DISSENSO",
                "DISSENS",
                "ALINHAMENTO",
                "ABSTEN",
                "OBSTRU",
            ]
        )

        if has_pct and has_pauta:
            return True, 85.0
        elif has_pct:
            return True, 55.0
        else:
            return False, 15.0
