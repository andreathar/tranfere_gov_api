"""Analista 2 — Áreas Temáticas Prioritárias.

Seção: "ÁREAS TEMÁTICAS PRIORITÁRIAS"
Chunks: [EMENDA], [EMENDA_DISCRICIONARIA], [PROPOSICAO], [DISCURSO_PLENARIO]
Tarefa: Mapear onde o dinheiro vai (R$) vs. o que ele propõe (PLs) vs. o que ele fala.

Fase 2 (2026-08-10): saída JSON estruturada + QC determinístico com fallback.
Data-first: continua usando chunks crus (não briefing) — os totais exatos R$
por área precisam ser transcritos literalmente.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, qc_estruturado

log = logging.getLogger(__name__)

_SCHEMA = """{
  "secoes": [
    "| Ranking | Área (objeto) | Município(s) | Nº Emendas | TOTAL exato (R$) | Proposições | Discursos |\\n|---|---|---|---|---|---|---|\\n| 1º | ... | ... | ... | R$ ... | ... | ... |",
    "**ANÁLISE**: (2-4 parágrafos interpretativos)\\n- Discrepâncias entre discurso e alocação:\\n- Áreas emergentes ou sazonais:"
  ],
  "fatos": [
    {"categoria": "emenda_area", "valor": "R$ 10.353.574,99", "fonte_chunk_id": "EMENDA"},
    {"categoria": "proposicao_tema", "valor": "TEMA", "fonte_chunk_id": "PROPOSICAO"}
  ],
  "flags": ["DISCREPANCIA_DISCURSO_ALOCACAO" | "AREA_DOMINANTE" | ...]
}"""


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
    # TOTAIS EXATOS) em vez do briefing do preparer. O modelo fabrica valores
    # ao agregar; com os totais literais no contexto ele só transcreve.
    use_preparer = False

    system_prompt = (
        "Você é um analista de políticas públicas especializado em cruzamento "
        "de dados orçamentários. Compare capital alocado (emendas) com produção "
        "legislativa (PLs) e discursos para detectar prioridades reais. "
        "NUNCA invente, estime, some ou compute valores em R$: cite SOMENTE os "
        "totais exatos que aparecem literalmente nos dados. "
        "Responda APENAS com JSON válido."
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

        # Fallback legado (markdown) — mantém a validação de fidelidade R$
        tem_r = bool(re.search(r"R\$\s*[\d.,]+", output))
        linhas_tabela = output.count("|") >= 4
        palavras = len(output.split())

        from src.analysts.base import taxa_invencao_rs

        try:
            chunks_text = "\n".join(getattr(self, "_last_chunks", []))
            taxa_invencao = taxa_invencao_rs(output, chunks_text)
        except Exception:
            taxa_invencao = 0.0
        penalidade = max(0.0, 1.0 - taxa_invencao * 2.0)

        score_base = 0.0
        if tem_r and linhas_tabela:
            score_base = 85.0
        elif tem_r:
            score_base = 60.0
        elif palavras >= 60:
            score_base = 40.0
        else:
            return False, 15.0

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
