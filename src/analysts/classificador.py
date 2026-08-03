"""
Analista 0 — Classificador Político.

Seção: "CLASSIFICAÇÃO POLÍTICA"
Chunks: [VOTO], [DISCURSO_PLENARIO]
Tarefa: Classificar GOVERNO/OPOSIÇÃO/INDEPENDENTE com % de alinhamento.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing

log = logging.getLogger(__name__)


@register_analyst
class ClassificadorPolitico(AnalystBase):
    analyst_id = "classificador"
    section_title = "CLASSIFICAÇÃO POLÍTICA"
    required_chunks = ["[VOTO]", "[DISCURSO_PLENARIO]"]
    min_chunks = 2

    system_prompt = (
        "Você é um analista político especializado em classificar o alinhamento "
        "de parlamentares com base exclusivamente em dados empíricos de votação "
        "nominal. Seja objetivo e baseie-se nos números."
    )

    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        # Usar briefing se disponível (mais conciso e focado)
        if briefing and briefing.is_useful:
            ctx = self._format_briefing(briefing)
            origem = "BRIEFING SINTETIZADO"
        else:
            ctx = self._format_context(context)
            origem = "DADOS CRUZ (TODOS OS CHUNKS)"

        return f"""Analise os dados abaixo e classifique o deputado federal {nome} em uma das três categorias:

**GOVERNO** — vota com o governo >70% das vezes (inclui base aliada e partidos da coalizão)
**OPOSIÇÃO** — vota contra o governo >60% das vezes
**INDEPENDENTE** — alinhamento entre 40% e 70%, ou vota com o governo em pautas econômicas e contra em pautas de costumes (ou vice-versa)

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Calcule o percentual aproximado de alinhamento com o governo federal.
2. Identifique pautas específicas onde houve dissenso partidário.
3. Considere que tipo de pauta gera alinhamento vs. oposição.
4. Se houver discursos, use o tom e posicionamento para corroborar ou contrastar com os votos.

FORMATO DE SAÍDA (Markdown):
**CLASSIFICAÇÃO**: [GOVERNO | OPOSIÇÃO | INDEPENDENTE | SEM DADOS SUFICIENTES]
- **Alinhamento estimado**: XX%
- **Fundamentação**: Breve explicação baseada nos dados de votação.
- **Dissenso relevante**: Pautas onde votou contra a orientação do próprio partido (se houver).
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        import unicodedata

        normalized = (
            unicodedata.normalize("NFKD", output).encode("ascii", "ignore").decode("ascii").upper()
        )

        # Deve conter uma das classificacoes
        has_classif = any(
            word in normalized for word in ["GOVERNO", "OPOSICAO", "INDEPENDENTE", "SEM DADOS"]
        )
        # Deve conter percentual
        has_pct = bool(re.search(r"\d+%", output))

        if has_classif and has_pct:
            return True, 90.0
        elif has_classif:
            return True, 60.0
        else:
            return False, 20.0
