"""
Analista 1 — Perfil Bio-Político.

Seção: "PERFIL BIO-POLÍTICO"
Chunks: [PERFIL], [PARLAMENTAR_RESUMO]
Tarefa: Resumo conciso: partido, estado, formação, comissões, tempo de mandato.
"""

from __future__ import annotations

import logging

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing

log = logging.getLogger(__name__)


@register_analyst
class PerfilBiografico(AnalystBase):
    analyst_id = "perfil"
    section_title = "PERFIL BIO-POLÍTICO"
    required_chunks = ["[PERFIL]", "[PARLAMENTAR_RESUMO]"]
    min_chunks = 1

    system_prompt = (
        "Você é um analista de perfis parlamentares. Produza resumos biográficos "
        "concisos e objetivos baseados estritamente nos dados fornecidos."
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

FORMATO DE SAÍDA (Markdown):
**PARTIDO/UF**: ...
**FORMAÇÃO**: ...
**COMISSÕES**: ...
**MANDATO**: ...
**CARGOS ANTERIORES**: ...
**BASE ELEITORAL**: ...

Se algum dado não estiver disponível, escreva "N/I".
Mantenha o resumo em torno de 4-8 linhas.
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        palavras = len(output.split())
        # Bio valida pode ser curta quando os dados sao esparsos (formacao,
        # comissoes, cargos = N/I). Aprova se tiver PARTIDO/UF + info basica.
        tem_partido = "PARTIDO" in output.upper() or "UF" in output.upper()

        if palavras >= 40 and tem_partido:
            score = min(70.0 + (palavras / 200.0) * 30.0, 100.0)
            return True, round(score, 1)
        elif palavras >= 12 and tem_partido or palavras >= 20:
            return True, 50.0
        else:
            return False, 10.0
