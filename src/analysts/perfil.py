"""Analista 1 — Perfil Bio-Político.

Seção: "PERFIL BIO-POLÍTICO"
Chunks: [PERFIL], [PARLAMENTAR_RESUMO]
Tarefa: Resumo conciso: partido, estado, formação, comissões, tempo de mandato.

Fase 2 (2026-08-10): saída JSON estruturada + QC determinístico com fallback
legado por keywords.
"""

from __future__ import annotations

import logging

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, qc_estruturado

log = logging.getLogger(__name__)

_SCHEMA = """{
  "secoes": [
    "**PARTIDO/UF**: ...\\n**FORMAÇÃO**: ...\\n**COMISSÕES**: ...\\n**MANDATO**: ...\\n**CARGOS ANTERIORES**: ...\\n**BASE ELEITORAL**: ..."
  ],
  "fatos": [
    {"categoria": "partido", "valor": "PARTIDO", "fonte_chunk_id": "PERFIL"},
    {"categoria": "uf", "valor": "UF", "fonte_chunk_id": "PERFIL"}
  ],
  "flags": []
}"""


@register_analyst
class PerfilBiografico(AnalystBase):
    analyst_id = "perfil"
    section_title = "PERFIL BIO-POLÍTICO"
    required_chunks = ["[PERFIL]", "[PARLAMENTAR_RESUMO]"]
    min_chunks = 1

    system_prompt = (
        "Você é um analista de perfis parlamentares. Produza resumos biográficos "
        "concisos e objetivos baseados estritamente nos dados fornecidos. "
        "Responda APENAS com JSON válido."
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
            origem = "DADOS DE PERFIL"

        return f"""Com base nos dados abaixo, produza um resumo bio-político do deputado federal {nome}.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Partido atual e histórico partidário (se disponível).
2. Estado que representa.
3. Formação acadêmica e profissão antes da política.
4. Comissões que integra ou integrou.
5. Tempo de mandato (em anos/legislaturas).
6. Cargos anteriores relevantes (prefeito, secretário, etc.).
7. Base eleitoral principal (região/cidade).
Se algum dado não estiver disponível, escreva "N/I".
Mantenha o resumo em torno de 4-8 linhas.

RESPONDA APENAS COM JSON VÁLIDO, neste schema exato (sem texto fora do JSON):
{_SCHEMA}
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        # QC estruturado determinístico
        qc_pass, qc_score = qc_estruturado(
            output,
            getattr(self, "_last_chunks", []),
            campos_obrigatorios=["secoes", "fatos"],
            min_secoes=1,
        )
        if qc_pass or qc_score > 0:
            return qc_pass, qc_score

        # Fallback legado (markdown): bio pode ser curta quando dados esparsos
        palavras = len(output.split())
        tem_partido = "PARTIDO" in output.upper() or "UF" in output.upper()
        if palavras >= 40 and tem_partido:
            score = min(70.0 + (palavras / 200.0) * 30.0, 100.0)
            return True, round(score, 1)
        elif palavras >= 12 and tem_partido or palavras >= 20:
            return True, 50.0
        else:
            return False, 10.0
