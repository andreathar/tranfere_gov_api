"""Analista — Rede Política e Apadrinhamento (CROSS-ESFERAS) [NOVO v8].

Fase 2 refactor (2026-08-10): analista que cruza dados de DIFERENTES esferas
de poder — deputado × prefeito × senador × governador × vereador — para mapear
a rede política do parlamentar:

  - prefeitos aliados que recebem emendas do deputado (conexão política)
  - senadores/governadores do mesmo partido ou coligação
  - vereadores do reduto eleitoral
  - publicações no DOU envolvendo a rede

Seção: "REDE POLÍTICA E APADRINHAMENTO (CROSS-ESFERAS)"
Chunks: [CONEXAO_POLITICA], [PREFEITO], [SENADOR], [VEREADORES_RESUMO],
        [ESTADO_FINANCEIRO], [EMENDA], [DIARIO_OFICIAL]
Saída: JSON estruturado (secoes[], fatos[], flags[]).

Fallback: QC legado por keywords se o modelo não emitir JSON (teto 60).
"""

from __future__ import annotations

import logging

from src.analysts import register_analyst
from src.analysts.base import AnalystBase, Briefing, qc_estruturado

log = logging.getLogger(__name__)

_SCHEMA = """{
  "secoes": [
    "**1. PREFEITOS ALIADOS BENEFICIADOS**\\n- Município X (partido Y): R$ ... (fonte: ...)\\n- ...",
    "**2. LIGAÇÕES SENADO/GOVERNADORES**\\n- ...",
    "**3. VEREADORES DO REDUTO**\\n- ...",
    "**4. MOVIMENTAÇÕES NO DOU**\\n- ...",
    "**5. ANÁLISE DA REDE**\\n- ..."
  ],
  "fatos": [
    {"categoria": "prefeito_aliado", "valor": "R$ 1.500.000,00", "fonte_chunk_id": "CONEXAO_POLITICA"},
    {"categoria": "senador_mesmo_partido", "valor": "NOME (PARTIDO)", "fonte_chunk_id": "SENADOR"}
  ],
  "flags": ["APADRINHAMENTO" | "CONCENTRACAO" | "REDE_AMPLA" | "SEM_CONEXOES"]
}"""


@register_analyst
class AnalistaRedePolitica(AnalystBase):
    analyst_id = "rede_politica"
    section_title = "REDE POLÍTICA E APADRINHAMENTO (CROSS-ESFERAS)"
    required_chunks = [
        "[CONEXAO_POLITICA]",
        "[PREFEITO]",
        "[SENADOR]",
        "[VEREADORES_RESUMO]",
        "[ESTADO_FINANCEIRO]",
        "[EMENDA]",
        "[DIARIO_OFICIAL]",
    ]
    min_chunks = 3

    system_prompt = (
        "Você é um analista de inteligência política especializado em mapear "
        "redes de poder entre esferas (federal, estadual e municipal). Cruze "
        "dados de prefeitos, senadores, governadores, vereadores e emendas para "
        "identificar conexões e apadrinhamento. Baseie-se exclusivamente nos "
        "dados fornecidos. Responda APENAS com JSON válido."
    )

    def build_prompt(
        self,
        context: list[str],
        nome: str,
        briefing: Briefing | None = None,
    ) -> str:
        # Data-first (2026-08-10, golden set): usar SEMPRE os chunks crus. O
        # briefing sintetizado induz confabulação no modelo 3B (ADOLFO VIANA
        # inventou "Senador João (PSDB/BA): R$ 200.000,00" — fato sem fonte).
        # Os chunks crus trazem as conexões reais (conexao_politica, prefeito,
        # senador, vereador) com valores literais.
        ctx = self._format_context(context)
        origem = "DADOS CRUZ (CONEXÕES + PREFEITOS + SENADORES + VEREADORES)"

        return f"""Mapeie a rede política do deputado federal {nome} cruzando TODAS as esferas de poder.

=== {origem} ===
{ctx}
========================================

INSTRUÇÕES:
1. **PREFEITOS ALIADOS BENEFICIADOS**: Identifique prefeituras (e seus partidos) que recebem emendas do deputado. Destaque quando o prefeito for do mesmo partido, coligação ou família (apadrinhamento).
2. **LIGAÇÕES SENADO/GOVERNADORES**: Senadores ou governadores do mesmo partido/coligação do deputado, especialmente da mesma UF.
3. **VEREADORES DO REDUTO**: Vereadores do mesmo partido nos municípios que recebem emendas (base eleitoral municipal).
4. **MOVIMENTAÇÕES NO DOU**: Publicações no Diário Oficial envolvendo o deputado ou beneficiários das emendas dele.
5. **ANÁLISE DA REDE**: Sintetize o desenho da rede (amplitude, concentração, partido dominante).
6. **FIDELIDADE NUMÉRICA (CRÍTICO)**: NUNCA invente valores R$. Cite SOMENTE valores que apareçam literalmente nos dados. Se um dado não estiver disponível, escreva "não informado".

RESPONDA APENAS COM JSON VÁLIDO, neste schema exato (sem texto fora do JSON):
{_SCHEMA}
"""

    def quality_check(self, output: str) -> tuple[bool, float]:
        qc_pass, qc_score = qc_estruturado(
            output,
            getattr(self, "_last_chunks", []),
            campos_obrigatorios=["secoes", "fatos"],
            min_secoes=3,
        )
        if qc_pass or qc_score > 0:
            return qc_pass, qc_score

        # Fallback legado (markdown)
        upper = output.upper()
        tem_rede = any(
            w in upper
            for w in [
                "PREFEIT",
                "SENADOR",
                "GOVERNADOR",
                "VEREADOR",
                "REDE",
                "CONEX",
                "APADRINHAMENTO",
            ]
        )
        palavras = len(output.split())
        if tem_rede and palavras >= 60:
            return True, 60.0
        elif tem_rede:
            return True, 45.0
        return False, 10.0
