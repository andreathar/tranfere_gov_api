"""Analista 5 — Posicionamento Público e Discursos.

Seção: "POSICIONAMENTO PÚBLICO E DISCURSOS"
Chunks: [DISCURSO_PLENARIO]
Tarefa: Análise profunda de discursos: ideologia, pautas, tom, contradições.

Fase 2 (2026-08-10): saída JSON estruturada + QC determinístico com fallback.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, qc_estruturado

log = logging.getLogger(__name__)

_SCHEMA = """{
  "secoes": [
    "**POSICIONAMENTO IDEOLÓGICO**: [Esquerda | Centro-Esquerda | Centro | Centro-Direita | Direita | Não Classificado]\\n**TAGS/KEYWORDS**: `tag1`, `tag2`, `tag3`",
    "**TOM PREDOMINANTE**: ...",
    "**PAUTAS RECORRENTES**:\\n1. ...\\n2. ...",
    "**CONSISTÊNCIA RETÓRICA vs. AÇÃO**:\\n- ...\\n\\n**EVOLUÇÃO TEMPORAL**: ..."
  ],
  "fatos": [
    {"categoria": "posicionamento", "valor": "CENTRO-DIREITA", "fonte_chunk_id": "DISCURSO_PLENARIO"},
    {"categoria": "pauta", "valor": "SEGURANCA PUBLICA", "fonte_chunk_id": "DISCURSO_PLENARIO"}
  ],
  "flags": ["CONTRADICAO_RETORICA_ACAO" | "MUDANCA_TEMPORAL" | ...]
}"""


@register_analyst
class AnalistaDiscursos(AnalystBase):
    analyst_id = "discursos"
    section_title = "POSICIONAMENTO PÚBLICO E DISCURSOS"
    required_chunks = ["[DISCURSO_PLENARIO]"]
    min_chunks = 1

    system_prompt = (
        "Você é um analista de discursos políticos especializado em análise de "
        "conteúdo legislativo. Extraia posicionamento ideológico, bandeiras, "
        "tom e consistência entre retórica e ação parlamentar. "
        "Responda APENAS com JSON válido."
    )

    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        # GPU zero-gemma4 (2026-08-12): Agora suportamos o briefing sintetizado
        # com maior precisão e menor risco de confabulação do modelo legado 3B.
        if briefing and briefing.is_useful:
            ctx = self._format_briefing(briefing)
            origem = "BRIEFING SINTETIZADO DE DISCURSOS"
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
6. **Contradições**: Identifique se há contradição entre o discurso e os dados de votação ou emendas.
7. **Bases teóricas**: Menção a autores, constituição, doutrinas ou referências ideológicas.

RESPONDA APENAS COM JSON VÁLIDO, neste schema exato (sem texto fora do JSON):
{_SCHEMA}
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        qc_pass, qc_score = qc_estruturado(
            output,
            getattr(self, "_last_chunks", []),
            campos_obrigatorios=["secoes", "fatos"],
            min_secoes=1,
        )
        if qc_pass or qc_score > 0:
            return qc_pass, qc_score

        # Fallback legado (markdown)
        tags_encontradas = len(re.findall(r"`[^`]+`", output))
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
            return True, 60.0
        elif tags_encontradas >= 1 and has_ideologia:
            return True, 50.0
        elif tags_encontradas >= 3:
            return True, 45.0
        elif has_ideologia:
            return True, 40.0
        else:
            return False, 10.0
