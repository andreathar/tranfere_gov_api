"""
Analista 5 — Posicionamento Público e Discursos.

Seção: "POSICIONAMENTO PÚBLICO E DISCURSOS"
Chunks: [DISCURSO_PLENARIO]
Tarefa: Análise profunda de discursos: ideologia, pautas, tom, contradições.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing

log = logging.getLogger(__name__)


@register_analyst
class AnalistaDiscursos(AnalystBase):
    analyst_id = "discursos"
    section_title = "POSICIONAMENTO PÚBLICO E DISCURSOS"
    required_chunks = ["[DISCURSO_PLENARIO]"]
    min_chunks = 1

    system_prompt = (
        "Você é um analista de discursos políticos especializado em análise de "
        "conteúdo legislativo. Extraia posicionamento ideológico, bandeiras, "
        "tom e consistência entre retórica e ação parlamentar."
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
            origem = "DISCURSOS DE PLENÁRIO"

        return f"""Analise os discursos do deputado federal {nome} no plenário da Câmara.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. **Posicionamento ideológico**: Classifique o deputado em um espectro (esquerda, centro-esquerda, centro, centro-direita, direita) com base nos discursos.
2. **Tags e keywords**: Extraia 3-8 palavras-chave ou tags que representam as bandeiras do deputado (ex: "segurança pública", "família", "reforma tributária", "anticorrupção").
3. **Tom predominante**: Descreva o tom (combativo, conciliador, técnico, ideológico, populista).
4. **Pautas recorrentes**: Liste os 3-5 temas mais frequentes.
5. **Consistência temporal**: Os discursos mudaram de tom ou tema ao longo do tempo?
6. **Contradições**: Identifique se há contradição entre o discurso e os dados de votação ou emendas (ex: "discurso contra corrupção, mas destinou emendas para entidades investigadas").
7. **Bases teóricas**: Menção a autores, constituição, doutrinas ou referências ideológicas.

FORMATO DE SAÍDA (Markdown):
**POSICIONAMENTO IDEOLÓGICO**: [Esquerda | Centro-Esquerda | Centro | Centro-Direita | Direita | Não Classificado]
**TAGS/KEYWORDS**: `tag1`, `tag2`, `tag3`, `tag4`, `tag5`

**TOM PREDOMINANTE**: ...

**PAUTAS RECORRENTES**:
1. ...
2. ...

**CONSISTÊNCIA RETÓRICA vs. AÇÃO**:
- ...

**EVOLUÇÃO TEMPORAL** (se houver): ...
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        # Deve conter ao menos 3 tags/keywords
        tags_encontradas = len(re.findall(r"`[^`]+`", output))
        # Ou pelo menos mencione posicionamento ideologico
        has_ideologia = any(
            word in output.upper()
            for word in [
                "ESQUERDA",
                "DIREITA",
                "CENTRO",
                "IDEOLOG",
                "POSICIONAMENTO",
            ]
        )

        if tags_encontradas >= 3 and has_ideologia:
            return True, 90.0
        elif tags_encontradas >= 1 and has_ideologia:
            return True, 60.0
        elif tags_encontradas >= 3:
            return True, 50.0
        elif has_ideologia:
            return True, 40.0
        else:
            return False, 10.0
