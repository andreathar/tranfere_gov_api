"""
Analista 2 — Áreas Temáticas Prioritárias.

Seção: "ÁREAS TEMÁTICAS PRIORITÁRIAS"
Chunks: [EMENDA], [EMENDA_DISCRICIONARIA], [PROPOSICAO], [DISCURSO_PLENARIO]
Tarefa: Mapear onde o dinheiro vai (R$) vs. o que ele propõe (PLs) vs. o que ele fala.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, taxa_invencao_rs

log = logging.getLogger(__name__)


@register_analyst
class AreasTematicas(AnalystBase):
    analyst_id = "tematicas"
    section_title = "ÁREAS TEMÁTICAS PRIORITÁRIAS"
    required_chunks = ["[EMENDA]", "[EMENDA_DISCRICIONARIA]", "[PROPOSICAO]", "[DISCURSO_PLENARIO]"]
    min_chunks = 2

    system_prompt = (
        "Você é um analista de políticas públicas especializado em cruzamento "
        "de dados orçamentários. Compare capital alocado (emendas) com produção "
        "legislativa (PLs) e discursos para detectar prioridades reais."
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
            origem = "DADOS CRUZADOS (EMENDAS + PROPOSIÇÕES + DISCURSOS)"

        return f"""Compare o volume de capital alocado por área temática com a produção legislativa e os discursos do deputado federal {nome}.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Identifique as 3-5 áreas temáticas que mais receberam recursos via emendas (PIX + discricionárias).
2. Ordene por valor total alocado (R$), não por número de projetos.
3. Compare com os temas das proposições legislativas (PLs, PECs) que ele apresentou.
4. Compare com os temas que ele mais discursa no plenário.
5. Aponte discrepâncias: "fala muito de saúde mas aloca mais recursos para agricultura".
6. Destaque se as emendas seguem a retórica ou se há pragmatismo eleitoral.

FORMATO DE SAÍDA (Markdown):
| Ranking | Área | Valor Estimado (R$) | % do Total | Proposições | Discursos |
|---------|------|--------------------|------------|-------------|-----------|
| 1º | Saúde | R$ X | XX% | N PLs | N discursos |
| ... | ... | ... | ... | ... | ... |

**ANÁLISE**: (2-4 parágrafos interpretativos)
- Discrepâncias entre discurso e alocação:
- Áreas emergentes ou sazonais:
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        # 1. Deve conter pelo menos 2 áreas com valores R$
        tem_r = bool(re.search(r"R\$\s*[\d.,]+", output))
        linhas_tabela = output.count("|") >= 4
        palavras = len(output.split())

        # 2. Validação de fidelidade numérica (parse BR/US + tolerância 2%)
        try:
            chunks_text = "\n".join(getattr(self, '_last_chunks', []))
            taxa_invencao = taxa_invencao_rs(output, chunks_text)
        except Exception:
            taxa_invencao = 0.0

        penalidade = max(0.0, 1.0 - taxa_invencao * 2.0)  # 0% invenção = 1.0, 50%+ = 0.0

        score_base = 0.0
        if tem_r and linhas_tabela:
            score_base = 85.0
        elif tem_r:
            score_base = 60.0
        elif palavras >= 60:
            score_base = 40.0
        else:
            return False, 15.0

        # Bônus por profundidade
        bonus_profundidade = min(palavras / 400.0, 1.0) * 15.0

        score = (score_base + bonus_profundidade) * penalidade
        score = round(min(score, 100.0), 1)

        aprovado = score >= 40.0
        if taxa_invencao > 0.2:
            log.warning(
                f"[tematicas] {taxa_invencao:.0%} dos R$ parecem inventados "
                f"(score reduzido: {score})"
            )

        return aprovado, score
