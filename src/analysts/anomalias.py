"""
Analista 6 — Anomalias e Fisiologismo.

Seção: "ANOMALIAS E FISIOLOGISMO (RED FLAGS)"
Chunks: [EMENDA], [CONEXAO_POLITICA], [RISCO_JUDICIAL], [COMPRAS_MUNICIPIO],
        [DIARIO_OFICIAL], [BENEFICIARIO]
Tarefa: Red flags: concentração suspeita, apadrinhamento, risco judicial.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, taxa_invencao_rs

log = logging.getLogger(__name__)


@register_analyst
class AnomaliasFisiologismo(AnalystBase):
    analyst_id = "anomalias"
    section_title = "ANOMALIAS E FISIOLOGISMO (RED FLAGS)"
    required_chunks = [
        "[EMENDA]",
        "[CONEXAO_POLITICA]",
        "[RISCO_JUDICIAL]",
        "[COMPRAS_MUNICIPIO]",
        "[DIARIO_OFICIAL]",
        "[BENEFICIARIO]",
    ]
    min_chunks = 3

    system_prompt = (
        "Você é um auditor de contas públicas especializado em detecção de "
        "anomalias, fisiologismo e riscos de compliance. Seja criterioso e "
        "baseie-se exclusivamente nos dados fornecidos. Se não houver "
        "anomalias, declare 'Nada anormal identificado.'"
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
            origem = "DADOS PARA AUDITORIA"

        return f"""Atue como auditor de contas públicas e identifique red flags no uso de emendas pelo deputado federal {nome}.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. **Concentração geográfica**: Há concentração anormal de emendas em poucos municípios, especialmente redutos eleitorais ou municípios muito pequenos?
2. **Apadrinhamento político**: As emendas beneficiam prefeituras comandadas por aliados políticos, familiares ou correligionários?
3. **Risco judicial**: Os beneficiários (CNPJs, prefeituras) têm processos judiciais? Há histórico de fraude, improbidade ou irregularidades?
4. **Proporcionalidade**: O valor das emendas é desproporcional ao porte do município (população, PIB, IDHM)?
5. **Compras públicas**: Há concentração de contratos com fornecedores específicos nos municípios beneficiados?
6. **Diário Oficial**: Há publicações suspeitas envolvendo o deputado ou beneficiários de suas emendas?

FORMATO DE SAÍDA (Markdown):
**1. CONCENTRAÇÃO GEOGRÁFICA**: [ALERTA / NORMAL / SEM DADOS]
- ...

**2. APADRINHAMENTO POLÍTICO**: [ALERTA / NORMAL / SEM DADOS]
- ...

**3. RISCO JUDICIAL**: [ALERTA / NORMAL / SEM DADOS]
- ...

**4. PROPORCIONALIDADE**: [ALERTA / NORMAL / SEM DADOS]
- ...

**5. COMPRAS PÚBLICAS**: [ALERTA / NORMAL / SEM DADOS]
- ...

**CONCLUSÃO**: (Resumo executivo dos riscos identificados ou "Nada anormal identificado nos dados disponíveis.")

Se NENHUMA anomalia for identificada em todas as categorias, responda apenas:
"Nada anormal identificado nos dados disponíveis para este deputado."
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        # 1. Deve conter pelo menos uma flag ou declarar "Nada anormal"
        tem_alerta = (
            "ALERTA" in output.upper()
            or "NADA ANORMAL" in output.upper()
            or "RED FLAG" in output.upper()
        )

        tem_r = bool(re.search(r"R\$\s*[\d.,]+", output))
        palavras = len(output.split())

        # 2. Validação de fidelidade numérica (parse BR/US + tolerância 2%)
        try:
            chunks_text = "\n".join(getattr(self, '_last_chunks', []))
            taxa_invencao = taxa_invencao_rs(output, chunks_text)
        except Exception:
            taxa_invencao = 0.0

        penalidade = max(0.0, 1.0 - taxa_invencao * 2.0)

        score_base = 0.0
        if tem_alerta and palavras >= 60:
            score_base = 85.0
        elif tem_alerta:
            score_base = 55.0
        elif tem_r and palavras >= 40:
            score_base = 40.0
        elif palavras >= 30:
            score_base = 30.0
        else:
            return False, 10.0

        bonus_profundidade = min(palavras / 500.0, 1.0) * 15.0

        score = (score_base + bonus_profundidade) * penalidade
        score = round(min(score, 100.0), 1)
        aprovado = score >= 35.0

        if taxa_invencao > 0.2:
            log.warning(
                f"[anomalias] {taxa_invencao:.0%} dos R$ parecem inventados "
                f"(score reduzido: {score})"
            )

        return aprovado, score
