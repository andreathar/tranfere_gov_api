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
    required_chunks = [
        "[EMENDA]",
        "[EMENDA_DISCRICIONARIA]",
        "[PROPOSICAO]",
        "[DISCURSO_PLENARIO]",
    ]
    min_chunks = 2
    # Data-first: usar os chunks crus (que trazem "Distribuição por área" com
    # TOTAIS EXATOS) em vez do briefing do preparer 1.5B. O modelo 4B principal
    # fabrica valores ao agregar; com os totais literais no contexto ele só
    # precisa transcrevê-los (mesmo approach que consertou o analista "anomalias").
    use_preparer = False

    system_prompt = (
        "Você é um analista de políticas públicas especializado em cruzamento "
        "de dados orçamentários. Compare capital alocado (emendas) com produção "
        "legislativa (PLs) e discursos para detectar prioridades reais. "
        "NUNCA invente, estime, some ou compute valores em R$: cite SOMENTE os "
        "totais exatos que aparecem literalmente nos dados."
    )

    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        ctx = self._format_context(context)
        origem = "DADOS (EMENDAS + PROPOSIÇÕES + DISCURSOS)"

        return f"""Identifique as áreas que mais receberam recursos do deputado federal {nome} via emendas e compare com a produção legislativa e os discursos dele.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Use a linha "Distribuição por área das emendas PIX de {nome}:" — ela traz o TOTAL EXATO de cada área (ex.: "Pavimentação...: R$ 10.353.574,99 (1 emenda(s), COARI)"). Se um total por município estiver explícito (ex.: "TOTAL exato R$ 28.788.030,99"), use-o também.
2. Ordene as 3-5 áreas pelo TOTAL EXATO (R$) em ordem decrescente. TRANSCREVA os valores literalmente, exatamente como aparecem (mantendo o formato R$ X,XX). NÃO reordene, recompute ou arredonde os valores.
3. Para cada área, informe o(s) município(s) beneficiário(s) e o número de emendas (apenas se constarem nos dados).
4. Compare com os temas das proposições legislativas (PLs, PECs) que ele apresentou.
5. Compare com os temas que ele mais discursa no plenário.
6. Aponte discrepâncias: "fala muito de saúde mas aloca mais recursos para agricultura".
7. FIDELIDADE NUMÉRICA (CRÍTICO): NUNCA invente, estime, some, compute percentuais ou crie valores em R$. Cite SOMENTE valores que apareçam literalmente nos dados. Se um total não estiver nos dados, escreva "não informado".

FORMATO DE SAÍDA (Markdown) — use SOMENTE valores literais dos dados:
| Ranking | Área (objeto) | Município(s) | Nº Emendas | TOTAL exato (R$) | Proposições | Discursos |
|---------|---------------|--------------|------------|------------------|-------------|-----------|
| 1º | [área] | [município] | [n] | R$ [total exato dos dados] | [tema] | [tema] |
| ... | ... | ... | ... | ... | ... | ... |

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
            chunks_text = "\n".join(getattr(self, "_last_chunks", []))
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
