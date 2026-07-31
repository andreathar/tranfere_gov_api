"""
Analista 3 — Cruzamento de Dados (Pragmatismo).

Seção: "CRUZAMENTO DE DADOS"
Chunks: TODOS (visão 360°)
Tarefa: Identificar contradições entre votos, emendas, discursos e perfil.
"""

from __future__ import annotations

import logging
import re

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, taxa_invencao_rs

log = logging.getLogger(__name__)


@register_analyst
class CruzamentoDados(AnalystBase):
    analyst_id = "cruzamento"
    section_title = "CRUZAMENTO DE DADOS (O PRAGMATISMO POLÍTICO)"
    required_chunks = []  # Todos os chunks
    min_chunks = 5

    system_prompt = (
        "Você é um analista de inteligência financeira e política. Seu papel é "
        "cruzar dados de diferentes fontes (votação, emendas, discursos, "
        "indicadores sociais) para identificar contradições, padrões de "
        "pragmatismo e incoerências. Seja objetivo e aponte exemplos concretos."
    )

    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        if briefing and briefing.is_useful:
            ctx = self._format_briefing(briefing)
            origem = "BRIEFING SINTETIZADO (TODAS AS FONTES)"
        else:
            ctx = self._format_context(context)
            origem = "TODOS OS DADOS DISPONÍVEIS"

        return f"""Realize uma análise de pragmatismo político do deputado federal {nome}, cruzando TODAS as fontes disponíveis.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. Compare o posicionamento em votações com o destino das emendas.
   - Ex: "Votou contra pautas ambientais, mas destinou emendas para projetos de sustentabilidade"
   - Ex: "Votou com a base do governo e recebeu emendas para seus redutos"
2. Compare discursos com votos: "Fala em plenário contra corrupção, mas destinou emendas para entidades sob investigação".
3. Compare perfil com alocação: "Deputado de região rica (alto IDHM) destina mais emendas para regiões pobres (baixo IDHM) — pragmatismo eleitoral ou redistribuição?".
4. Identifique padrões de pragmatismo: vota contra o governo em pautas ideológicas mas apoia em pautas econômicas (ou vice-versa).

FORMATO DE SAÍDA (Markdown):
**1. CONTRADIÇÕES VOTO vs. EMENDA**
- Insight 1: ...
- Insight 2: ...

**2. CONTRADIÇÕES DISCURSO vs. PRÁTICA**
- Insight 1: ...

**3. PADRÕES DE PRAGMATISMO**
- ...

**4. ANÁLISE GERAL**: (parágrafo conclusivo)

Se não houver contradições significativas, declare "Nenhuma contradição significativa identificada — votos, emendas e discursos são coerentes."
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        # 1. Deve conter ao menos 1 insight de contradicao ou analise
        palavras = len(output.split())
        tem_insight = any(
            word in output.upper()
            for word in [
                "CONTRADI",
                "INSIGHT",
                "PRAGMATISMO",
                "DISCURSO",
                "VOTOU",
                "DESTINOU",
            ]
        )
        tem_r = bool(re.search(r"R\$\s*[\d.,]+", output))

        # 2. Validação de fidelidade numérica (parse BR/US + tolerância 2%)
        try:
            chunks_text = "\n".join(getattr(self, '_last_chunks', []))
            taxa_invencao = taxa_invencao_rs(output, chunks_text)
        except Exception:
            taxa_invencao = 0.0

        penalidade = max(0.0, 1.0 - taxa_invencao * 2.0)

        score_base = 0.0
        if palavras >= 100 and tem_insight:
            score_base = 60.0 + min((palavras / 500.0) * 40.0, 40.0)
        elif palavras >= 50:
            score_base = 40.0
        elif tem_r and palavras >= 30:
            score_base = 30.0
        else:
            return False, 10.0

        score = score_base * penalidade
        score = round(min(score, 100.0), 1)
        aprovado = score >= 35.0

        if taxa_invencao > 0.2:
            log.warning(
                f"[cruzamento] {taxa_invencao:.0%} dos R$ parecem inventados "
                f"(score reduzido: {score})"
            )

        return aprovado, score
