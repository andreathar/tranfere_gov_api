"""
Preparador de contexto para analistas — sintetiza chunks brutos em briefing
estruturado usando modelo rápido (qwen2.5-1.5b).

Fluxo:
  30 chunks brutos (~5000 chars) → PromptPreparer (qwen, 88.9 tok/s)
    → Briefing (~800 chars) + Fact Table (~400 chars) + Insights
    → Validador de fidelidade numérica (R$ do briefing existem nos chunks?)
    → Analista principal (gemma-4 / llama-3.1-8b) gera análise final

Fase 3 (2026-08-14) — reasoning em estágios:
  O prompt agora exige um protocolo em 6 estágios na MESMA resposta:
  INVENTÁRIO (fixa TODOS os números antes de escrever) → AGRUPAMENTO →
  BRIEFING (escrito SOMENTE a partir do inventário) → FACT TABLE (fonte
  obrigatória) → VERIFICAÇÃO (auto-check máquina-legível OK/FALTA_FONTE/
  CONFLITO) → KEY INSIGHTS. Se a validação de fidelidade falhar, um repair
  pass corrige cirurgicamente os valores sem fonte antes do fallback cru.

Benefícios:
  - Reduz tokens do modelo principal em 5-10x
  - Preserva exatidão numérica (validação pós-geração)
  - Extrai contradições e padrões automaticamente
  - Prepara o terreno para análise — modelo principal só analisa, não "lê"

Uso:
    from src.analysts.preparer import PromptPreparer, Briefing
    preparer = PromptPreparer()
    briefing = preparer.prepare(chunks, persona, "SECTION", "Nome")
    if briefing and briefing.validation_pass:
        print(briefing.text)
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from config.settings import PREPARER_MODEL

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Modelo usado para preparação (síntese de chunks em briefing).
# ALTERADO 2026-07-31 (2x): qwen2.5-1.5b dava timeout (13.9 tok/s); gemma-4-e2b
# era thinking (max_tokens baixo = content vazio). zero-gemma4-e4b-openzero:
# reasoning model validado a 21.9 tok/s (gpu_layers=40), preserva R$ com
# fidelidade — melhor para síntese de dados. Pode ser sobrescrito via PREPARER_MODEL env var.

# Máximo de chunks enviados ao preparador por chamada.
# ALTERADO 2026-08-10 (Fase 1 refactor): 8 -> 14 com truncamento SELETIVO por tipo
# (antes cortava "do meio" e perdia os chunks mais ricos). O briefing é agora
# ÚNICO por dossiê (1 chamada em vez de 7).
PREPARER_MAX_CHUNKS = 14

# Tamanho máximo do prompt enviado ao preparador em caracteres
PREPARER_MAX_PROMPT_CHARS = 14000

# Máximo de tentativas de repair pass (Fase 3, 2026-08-14): quando a validação
# de fidelidade R$ falha, o preparer tenta corrigir cirurgicamente os valores
# sem fonte ANTES de cair no fallback cru (chunks crus).
PREPARER_MAX_REPAIR_ATTEMPTS = 2

# Prioridade de tipos de chunk para o truncamento seletivo (mais ricos primeiro).
# EMENDA carrega totais R$ exatos; VOTO carrega alinhamento; PROPOSICAO e
# DISCURSO dão o contexto temático; CONEXAO_POLITICA e demais completam a rede.
PREPARER_CHUNK_PRIORITY: list[str] = [
    "[EMENDA]",
    "[EMENDA_DETALHE]",
    "[EMENDA_DISCRICIONARIA]",
    "[VOTO]",
    "[PROPOSICAO]",
    "[DISCURSO_PLENARIO]",
    "[CONEXAO_POLITICA]",
    "[DIARIO_OFICIAL]",
    "[RISCO_JUDICIAL]",
    "[COMPRAS_MUNICIPIO]",
    "[BENEFICIARIO]",
    "[MUNICIPIO_FINANCEIRO]",
    "[INDICADORES_SOCIAIS]",
    "[INDICADORES_MUNICIPAL]",
    "[DEMOGRAFIA_MUNICIPIO]",
    "[FNDE_REPASSES]",
    "[VEREADORES_RESUMO]",
    "[PREFEITO]",
    "[SENADOR]",
    "[ESTADO_FINANCEIRO]",
    "[PERFIL]",
    "[PARLAMENTAR_RESUMO]",
    "[PERSONA_EXISTENTE]",
    "[PARLAMENTAR_ALERTAS]",
]


def _truncar_chunks_seletivo(chunks: list[str], max_chunks: int) -> list[str]:
    """Mantém até max_chunks preservando 1 chunk de cada tipo prioritário.

    Estratégia: primeira passada mantém o primeiro chunk de cada tipo na ordem
    de prioridade; se ainda couber, completa com os demais na ordem original.
    """
    if len(chunks) <= max_chunks:
        return list(chunks)

    mantidos: list[str] = []
    vistos: set[str] = set()
    for prefix in PREPARER_CHUNK_PRIORITY:
        if len(mantidos) >= max_chunks:
            break
        for c in chunks:
            if c.startswith(prefix) and prefix not in vistos:
                mantidos.append(c)
                vistos.add(prefix)
                break

    # Completar com o restante na ordem original
    for c in chunks:
        if len(mantidos) >= max_chunks:
            break
        if c not in mantidos:
            mantidos.append(c)

    return mantidos

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class Briefing:
    """Briefing estruturado produzido pelo PromptPreparer.

    Attributes:
        text: Síntese narrativa dos fatos mais relevantes (2-4 parágrafos).
        fact_table: Tabela de fatos com valores verificados (pipe-separated).
        insights: Lista de contradições, anomalias ou padrões detectados.
        validation_pass: True se todos os R$ do briefing existem nos chunks fonte.
        raw_fallback: True se o preparador falhou e este é fallback simples.
        chunks_pre_count: Quantidade original de chunks recebidos.
    """

    text: str = ""
    fact_table: str = ""
    insights: list[str] = field(default_factory=list)
    validation_pass: bool = False
    raw_fallback: bool = False
    chunks_pre_count: int = 0
    # Fase 3 (2026-08-14): reasoning em estágios — estágios visíveis do
    # protocolo INVENTÁRIO → AGRUPAMENTO → BRIEFING → FACT TABLE → VERIFICAÇÃO.
    inventario: str = ""
    agrupamento: str = ""
    verificacao: str = ""
    # Fase 3: repair pass — correção cirúrgica aplicada após falha de validação.
    repair_used: bool = False
    repair_attempts: int = 0

    @property
    def is_useful(self) -> bool:
        """Retorna True se o briefing tem conteúdo utilizável e passou validação."""
        return (
            bool(self.text or self.fact_table)
            and not self.raw_fallback
            and self.validation_pass
        )

    @property
    def total_chars(self) -> int:
        return len(self.text) + len(self.fact_table)


# ---------------------------------------------------------------------------
# PromptPreparer
# ---------------------------------------------------------------------------


class PromptPreparer:
    """Sintetiza chunks brutos em briefing estruturado usando modelo rápido.

    Preserva exatidão numérica através de validação pós-geração:
    todo R$ mencionado no briefing é conferido contra os chunks fonte.
    Se >20% dos R$ forem falsos, usa fallback (formatação simples dos chunks).
    """

    def __init__(self, model: str | None = None):
        self.model = model or PREPARER_MODEL
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from src.localai_client import LocalAIClient

            self._client = LocalAIClient(model=self.model)
        return self._client

    # -----------------------------------------------------------------------
    # Prompts
    # -----------------------------------------------------------------------

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Você é um preparador de dados especializado em análise política e "
            "orçamentária. Sua função é condensar dados brutos em briefings "
            "estruturados, preservando EXATAMENTE todos os valores numéricos "
            "(R$, %, datas, IDs, totais). NUNCA invente ou modifique números. "
            "Se um dado estiver ausente, escreva 'N/D'. "
            "Seja conciso — priorize o que é mais relevante para a análise "
            "solicitada. Ignore informações redundantes."
        )

    def _build_prep_prompt(
        self,
        chunks: list[str],
        analyst_persona: str,
        section_title: str,
        nome: str,
        _depth: int = 0,
    ) -> str:
        """Monta o prompt para o modelo preparador."""
        # Truncar chunks se necessário (SELETIVO por tipo — Fase 1 refactor)
        if len(chunks) > PREPARER_MAX_CHUNKS:
            log.info(
                f"Preparer: truncando {len(chunks)} -> {PREPARER_MAX_CHUNKS} "
                f"chunks para '{section_title}' (seletivo por tipo)"
            )
            chunks = _truncar_chunks_seletivo(chunks, PREPARER_MAX_CHUNKS)

        context_str = "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(chunks))

        prompt = f"""Você está preparando dados para a seção "{section_title}" do dossiê do deputado {nome}.

PERFIL DO ANALISTA QUE RECEBERÁ ESTE BRIEFING:
{analyst_persona}

DADOS BRUTOS ({len(chunks)} chunks):
{context_str}

RACIOCÍNIO EM ESTÁGIOS — Fase 3 (2026-08-14): produza TODOS os estágios
abaixo, na ordem, em UMA única resposta. Os estágios 1 e 2 são seu raciocínio
visível: fixam os fatos ANTES de qualquer escrita. Os estágios 3-6 são o que
os analistas consomem.

ESTÁGIO 1 — INVENTÁRIO (fixe TODOS os números AQUI primeiro):
Liste cada fato relevante em uma linha, no formato pipe:
| entidade | valor | unidade (R$/%/data/ID/Sim-Não) | tema | fonte=[TIPO_DO_CHUNK] |
Inclua TODOS os valores monetários (R$), percentuais, datas e IDs relevantes à
seção "{section_title}", EXATAMENTE como aparecem. Cada número usado nos
estágios seguintes DEVE constar aqui. Se um dado estiver ausente, escreva 'N/D'.
Nunca invente.

ESTÁGIO 2 — AGRUPAMENTO (sem números novos):
Agrupe as linhas do inventário por tema relevante ao analista e à seção
"{section_title}". Destaque contradições, anomalias ou padrões.

ESTÁGIO 3 — BRIEFING (escreva SOMENTE a partir do inventário):
Síntese narrativa em 2-4 parágrafos, organizada por tema, com números exatos.
Todo número usado deve constar no ESTÁGIO 1. Remova informação redundante.
Máximo 800 palavras.

ESTÁGIO 4 — FACT TABLE (fonte obrigatória por linha):
| Categoria | Entidade | Valor Financeiro/Quantitativo | Detalhe (fonte=[TIPO_DO_CHUNK]) |
ATENÇÃO MÁXIMA PARA NÚMEROS: nunca some ou agregue valores por conta própria.
Mantenha categorias e totais EXATAMENTE como fornecidos nos resumos (ex:
totais de emendas PIX ou de áreas). Ex:
| Total de Emendas PIX | Deputado | R$ 28.788.030,99 | Conforme [PARLAMENTAR_RESUMO] |
| Emendas | Município X | R$ 1.500.000,00 | Objeto: Saúde; fonte=[EMENDA] |
| Votação | PL 123/2024 | Sim | Tema: Educação; fonte=[VOTO] |

ESTÁGIO 5 — VERIFICAÇÃO (auto-check máquina-legível):
Re-liste cada R$/%/data usada nos estágios 3 e 4, uma por linha:
| valor | OK |          (consta no inventário)
| valor | FALTA_FONTE |  (não está no inventário)
| valor | CONFLITO |     (divergente do inventário)

ESTÁGIO 6 — KEY INSIGHTS:
Lista de 0-5 insights, contradições ou anomalias, um por linha com "- ".

FORMATO DE SAÍDA (estrito — use exatamente estes cabeçalhos):

---INVENTÁRIO---
[linhas pipe do Estágio 1]

---AGRUPAMENTO---
[temas agrupados do Estágio 2]

---BRIEFING---
[Síntese narrativa do Estágio 3]

---FACT TABLE---
[linhas pipe do Estágio 4]

---VERIFICAÇÃO---
[linhas | valor | status | do Estágio 5]

---KEY INSIGHTS---
[insights do Estágio 6]
"""

        # Truncar se exceder limite (para evitar estouro de contexto).
        # Fase 1: reaplica o truncamento seletivo (não corta mais "do meio").
        # Guarda de profundidade: nunca recursa além de 3 níveis (evita loop
        # quando um único chunk gigante ainda estoura o limite).
        if len(prompt) > PREPARER_MAX_PROMPT_CHARS and _depth < 3:
            reduzidos = _truncar_chunks_seletivo(chunks, max(1, len(chunks) - 2))
            log.warning(
                f"Preparer: prompt excede {PREPARER_MAX_PROMPT_CHARS} chars "
                f"({len(prompt)}), reaplicando truncamento seletivo. "
                f"{len(chunks)} -> {len(reduzidos)}"
            )
            return self._build_prep_prompt(
                reduzidos, analyst_persona, section_title, nome, _depth=_depth + 1
            )
        elif len(prompt) > PREPARER_MAX_PROMPT_CHARS:
            # Último recurso: corta o texto dos chunks preservando a cauda
            # (onde ficam os valores R$ e totais agregados)
            log.warning(
                f"Preparer: prompt ainda excede {PREPARER_MAX_PROMPT_CHARS} chars "
                f"({len(prompt)}), truncando texto dos chunks."
            )
            chunks_curtos = [
                (c[:800] + "\n[…]" + c[-400:]) if len(c) > 1200 else c for c in chunks
            ]
            return self._build_prep_prompt(
                chunks_curtos, analyst_persona, section_title, nome, _depth=3
            )

        return prompt

    # -----------------------------------------------------------------------
    # Parse
    # -----------------------------------------------------------------------

    def _parse_response(self, resposta: str, chunks: list[str]) -> Briefing:
        """Parseia resposta do modelo em Briefing.

        Fase 3 (2026-08-14): suporta o protocolo em estágios
        (INVENTÁRIO → AGRUPAMENTO → BRIEFING → FACT TABLE → VERIFICAÇÃO →
        KEY INSIGHTS). Mantém compatibilidade com o formato antigo (apenas
        BRIEFING/FACT TABLE/KEY INSIGHTS) — estágios ausentes viram "".
        Cabeçalhos são tolerantes a acentos (INVENTÁRIO/INVENTARIO,
        VERIFICAÇÃO/VERIFICACAO).
        """
        briefing = Briefing(chunks_pre_count=len(chunks))

        # Fase 3: estágios de reasoning — inventário/agrupamento/verificação
        m = re.search(
            r"---\s*INVENT[AÁ]RIO---\s*\n(.*?)(?=---\s*AGRUPAMENTO---|---\s*BRIEFING---|$)",
            resposta,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            briefing.inventario = m.group(1).strip()

        m = re.search(
            r"---\s*AGRUPAMENTO---\s*\n(.*?)(?=---\s*BRIEFING---|$)",
            resposta,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            briefing.agrupamento = m.group(1).strip()

        m = re.search(
            r"---\s*VERIFICA[CÇ][AÃ]?[CÇ]?[AÃ]?O---\s*\n(.*?)(?=---\s*KEY\s*INSIGHTS---|$)",
            resposta,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            briefing.verificacao = m.group(1).strip()

        # Extrair seção ---BRIEFING---
        m = re.search(
            r"---\s*BRIEFING---\s*\n(.*?)(?=---\s*FACT\s*TABLE---|---\s*KEY\s*INSIGHTS---|$)",
            resposta,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            briefing.text = m.group(1).strip()

        # Extrair seção ---FACT TABLE---
        m = re.search(
            r"---\s*FACT\s*TABLE---\s*\n(.*?)(?=---\s*VERIFICA[CÇ][AÃ]?[CÇ]?[AÃ]?O---|---\s*KEY\s*INSIGHTS---|$)",
            resposta,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            briefing.fact_table = m.group(1).strip()

        # Extrair seção ---KEY INSIGHTS---
        m = re.search(
            r"---\s*KEY\s*INSIGHTS---\s*\n(.*?)$",
            resposta,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            insights_text = m.group(1).strip()
            briefing.insights = [
                line.strip().lstrip("- ").strip()
                for line in insights_text.split("\n")
                if line.strip().startswith("-")
            ]

        # Se não extraiu briefing formatado, tenta formatos alternativos
        if not briefing.text and not briefing.fact_table:
            self._parse_alternativos(briefing, resposta)

        # Último recurso: usa resposta inteira
        if not briefing.text and not briefing.fact_table:
            briefing.text = resposta.strip()

        return briefing

    def _parse_alternativos(self, briefing: Briefing, resposta: str) -> None:
        """Tenta JSON, Markdown (##) ou rótulos (:) quando o formato --- não foi usado."""
        texto = resposta.strip()

        # (a) JSON: objeto único com briefing/fact_table/insights
        bloco_json = None
        try:
            inicio = texto.find("{")
            fim = texto.rfind("}")
            if inicio != -1 and fim > inicio:
                bloco_json = texto[inicio : fim + 1]
                dados = json.loads(bloco_json)
                if isinstance(dados, dict):
                    briefing.text = str(
                        dados.get("briefing") or dados.get("text") or dados.get("texto") or ""
                    ).strip()
                    ft = dados.get("fact_table") or dados.get("fatos")
                    briefing.fact_table = str(ft).strip() if ft else ""
                    ins = dados.get("insights") or dados.get("secoes")
                    if isinstance(ins, list):
                        briefing.insights = [str(x).strip() for x in ins if str(x).strip()]
        except (ValueError, TypeError, AttributeError):
            bloco_json = None
        if briefing.text or briefing.fact_table:
            return

        # (b) Markdown: seções ## BRIEFING / ## FACT TABLE / ## KEY INSIGHTS
        if re.search(r"^##\s*BRIEFING", texto, re.MULTILINE | re.IGNORECASE):
            _md = re.split(r"^##\s*FACT TABLE|^##\s*KEY INSIGHTS", texto, flags=re.MULTILINE | re.IGNORECASE)
            if _md:
                briefing.text = _md[0].split("## BRIEFING", 1)[-1].split("## briefing", 1)[-1].strip()
            m_ft = re.search(r"^##\s*FACT TABLE\s*\n(.*?)(?=^##|\Z)", texto, re.MULTILINE | re.IGNORECASE | re.DOTALL)
            if m_ft:
                briefing.fact_table = m_ft.group(1).strip()
            m_ins = re.search(r"^##\s*KEY INSIGHTS\s*\n(.*?)(?=^##|\Z)", texto, re.MULTILINE | re.IGNORECASE | re.DOTALL)
            if m_ins:
                briefing.insights = [
                    line.strip().lstrip("- ").strip()
                    for line in m_ins.group(1).split("\n")
                    if line.strip().startswith("-")
                ]
            if briefing.text or briefing.fact_table:
                return

        # (c) Rótulos: "BRIEFING:" / "Fact Table:" / "Key Insights:"
        m_b = re.search(r"BRIEFING:\s*(.*?)(?=Fact Table:|Key Insights:|\Z)", texto, re.DOTALL | re.IGNORECASE)
        if m_b:
            briefing.text = m_b.group(1).strip()
        m_ft = re.search(r"Fact Table:\s*(.*?)(?=Key Insights:|\Z)", texto, re.DOTALL | re.IGNORECASE)
        if m_ft:
            briefing.fact_table = m_ft.group(1).strip()
        m_ins = re.search(r"Key Insights:\s*(.*?)(?=\Z)", texto, re.DOTALL | re.IGNORECASE)
        if m_ins:
            briefing.insights = [
                line.strip().lstrip("- ").strip()
                for line in m_ins.group(1).split("\n")
                if line.strip().startswith("-")
            ]

    # -----------------------------------------------------------------------    # Helpers (Fase 3, 2026-08-14): reasoning em estágios e repair pass
    # -----------------------------------------------------------------------

    def _model_scope(self) -> Any:
        """Carrega o modelo via model_scope (refcount) se não for cloud proxy.

        Returns:
            Contexto do model_scope (liberar com _release_model) ou None para
            modelos cloud proxy (sem gerenciamento local de VRAM).
        """
        from config.settings import CLOUD_PROXY_MODEL_NAMES

        if self.model in CLOUD_PROXY_MODEL_NAMES:
            return None
        from src.localai_manager import manager as lm

        ctx = lm.model_scope(self.model)
        ctx.__enter__()
        return ctx

    @staticmethod
    def _release_model(lm_ctx: Any) -> None:
        """Libera o contexto do model_scope (já libera refcount)."""
        if lm_ctx is not None:
            try:
                lm_ctx.__exit__(None, None, None)
            except Exception:
                pass

    def _valores_sem_fonte_rs(
        self, briefing: Briefing, chunks: list[str]
    ) -> list[float]:
        """R$ do briefing sem correspondência nos chunks (Fase 3).

        Reusa a MESMA lógica da validação (base.valores_rs_sem_fonte) para que
        o repair pass corrija exatamente o que a validação reprova.
        """
        from src.analysts.base import valores_rs_sem_fonte

        texto_briefing = briefing.text + "\n" + briefing.fact_table
        return valores_rs_sem_fonte(texto_briefing, "\n".join(chunks))

    def _problemas_verificacao(self, briefing: Briefing) -> list[str]:
        """Extrai da seção VERIFICAÇÃO os valores marcados FALTA_FONTE/CONFLITO.

        Formato esperado das linhas (Estágio 5):
            | valor | OK |
            | valor | FALTA_FONTE |
            | valor | CONFLITO |
        """
        if not briefing.verificacao:
            return []
        problemas: list[str] = []
        for linha in briefing.verificacao.splitlines():
            if not linha.strip().startswith("|"):
                continue
            if not re.search(
                r"FALTA_FONTE|CONFLITO|SEM[_\s]*FONTE|N[AÃ]O.*FONTE",
                linha,
                re.IGNORECASE,
            ):
                continue
            partes = [p.strip() for p in linha.strip().strip("|").split("|")]
            if partes:
                problemas.append(partes[0])
        return problemas

    # -----------------------------------------------------------------------    # Validação de fidelidade numérica
    # -----------------------------------------------------------------------

    def _validate_fidelity(self, briefing: Briefing, chunks: list[str]) -> bool:
        """Verifica se todos os valores R$ do briefing existem nos chunks fonte.

        Estratégia:
         1. Extrai todos R$ do briefing (texto + fact_table).
         2. Valida contra os chunks usando o MESMO parser numérico de
            base.taxa_invencao_rs (tolerância 2% por valor — Fase 2 unificação:
            antes eram duas implementações divergentes que podiam discordar
            sobre o mesmo valor).
         3. Se a taxa de invenção >20% → reprova.

        Returns:
            True se passar na validação (ou não houver R$ para validar).
        """
        # Fase 2 (2026-08-10): validação unificada via base.taxa_invencao_rs
        # (parse numérico BR/US + tolerância 2% por valor).
        from src.analysts.base import taxa_invencao_rs

        texto_briefing = briefing.text + "\n" + briefing.fact_table
        from src.analysts.base import coletar_valores_rs

        if not coletar_valores_rs(texto_briefing):
            # Sem valores para validar = passa automaticamente
            briefing.validation_pass = True
            return True

        try:
            taxa = taxa_invencao_rs(texto_briefing, "\n".join(chunks))
        except Exception as exc:
            # Falha ao medir fidelidade: reprova (não pode validar R$)
            log.warning("taxa_invencao_rs falhou no _validate_fidelity: %s", exc)
            briefing.validation_pass = False
            return False

        if taxa > 0.2:
            log.warning(
                f"Valores R$ no briefing sem correspondência nos chunks: "
                f"{taxa:.0%} de invenção estimada"
            )
            briefing.validation_pass = False
            return False

        # Fase 3: cross-check da auto-verificação do modelo (Estágio 5). Não
        # altera a validação determinística, mas registra divergências para
        # observabilidade e serve de insumo ao repair pass.
        problemas = self._problemas_verificacao(briefing)
        if problemas:
            log.info(
                f"Preparer: VERIFICAÇÃO do modelo reportou {len(problemas)} "
                f"valores problemáticos: {problemas[:5]}"
            )

        briefing.validation_pass = True
        return True

    # -----------------------------------------------------------------------
    # Repair pass (Fase 3, 2026-08-14)
    # -----------------------------------------------------------------------

    def _build_repair_prompt(
        self,
        briefing: Briefing,
        chunks: list[str],
        analyst_persona: str,
        section_title: str,
        nome: str,
    ) -> str:
        """Monta prompt de repair cirúrgico.

        Informa ao modelo quais valores do briefing NÃO têm fonte nos chunks e
        pede apenas a correção desses valores, preservando o restante da
        síntese — em vez de descartar tudo para o fallback cru.
        """
        sem_fonte = self._valores_sem_fonte_rs(briefing, chunks)
        problemas = self._problemas_verificacao(briefing)

        if sem_fonte:
            valores_txt = "\n".join(
                f"- R$ {v:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
                for v in sem_fonte[:12]
            )
        elif problemas:
            valores_txt = "\n".join(f"- {p}" for p in problemas[:12])
        else:
            valores_txt = (
                "- (não foi possível isolar os valores — revise os números)"
            )

        chunks_txt = "\n".join(
            f"  [{i+1}] {c}" for i, c in enumerate(chunks[:10])
        )

        return f"""Você está CORRIGINDO um briefing da seção "{section_title}" do dossiê do deputado {nome}.

PERFIL DO ANALISTA QUE RECEBERÁ ESTE BRIEFING:
{analyst_persona}

DADOS BRUTOS ({len(chunks)} chunks) — estes são a ÚNICA fonte de verdade:
{chunks_txt}

BRIEFING ANTERIOR (contém valores SEM FONTE):
{briefing.text}

FACT TABLE ANTERIOR:
{briefing.fact_table}

VALORES SEM FONTE (corrija ou remova):
{valores_txt}

INSTRUÇÕES:
1. Reemita o briefing CORRIGIDO usando exatamente os cabeçalhos abaixo.
2. Corrija APENAS os valores sem fonte: ajuste para o valor exato dos chunks
   ou remova a afirmação. Preserve os demais fatos.
3. NUNCA some ou agregue valores por conta própria. Nunca invente números.
4. Máximo 600 palavras.

FORMATO DE SAÍDA (estrito):

---BRIEFING---
[síntese corrigida]

---FACT TABLE---
| Categoria | Entidade | Valor Financeiro/Quantitativo | Detalhe (fonte=[TIPO_DO_CHUNK]) |
[apenas linhas com fonte confiável nos chunks]

---KEY INSIGHTS---
- [insights, se houver]
"""

    def _repair_pass(
        self,
        briefing: Briefing,
        chunks: list[str],
        analyst_persona: str,
        section_title: str,
        nome: str,
    ) -> Briefing:
        """Tenta corrigir um briefing reprovado na validação de fidelidade.

        Em vez de cair direto no fallback cru, faz uma segunda chamada com
        prompt cirúrgico apontando os valores sem fonte. Se o repair também
        falhar, retorna fallback (raw_fallback=True).
        """
        briefing.repair_attempts += 1
        briefing.repair_used = True

        lm_ctx = None
        try:
            lm_ctx = self._model_scope()
        except Exception as e:
            log.warning(
                f"Preparer: repair não pôde carregar {self.model} para "
                f"'{section_title}': {e}"
            )
            fb = self._build_fallback(chunks)
            fb.repair_used = True
            fb.repair_attempts = briefing.repair_attempts
            return fb

        try:
            client = self._get_client()
            prompt = self._build_repair_prompt(
                briefing, chunks, analyst_persona, section_title, nome
            )
            resposta = client.chat(
                prompt=prompt, system=self._system_prompt(), max_tokens=1200
            )
        except Exception as e:
            log.warning(
                f"Preparer: repair pass falhou para '{section_title}': {e}"
            )
            fb = self._build_fallback(chunks)
            fb.repair_used = True
            fb.repair_attempts = briefing.repair_attempts
            return fb
        finally:
            self._release_model(lm_ctx)

        if not resposta or not resposta.strip():
            log.warning(f"Preparer: repair pass vazio para '{section_title}'")
            fb = self._build_fallback(chunks)
            fb.repair_used = True
            fb.repair_attempts = briefing.repair_attempts
            return fb

        novo = self._parse_response(resposta, chunks)
        novo.chunks_pre_count = len(chunks)
        novo.repair_used = True
        novo.repair_attempts = briefing.repair_attempts
        self._validate_fidelity(novo, chunks)

        log.info(
            f"Preparer: repair pass '{section_title}' "
            f"(tentativa {novo.repair_attempts}) — "
            f"validação: {'OK' if novo.validation_pass else 'AINDA FALHOU'}"
        )
        return novo

    # -----------------------------------------------------------------------
    # Fallback
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_fallback(chunks: list[str]) -> Briefing:
        """Cria briefing de fallback com formatação simples dos chunks crus.

        Agrupa chunks por tipo e formata como seções.
        """
        grouped: dict[str, list[str]] = defaultdict(list)
        for c in chunks:
            tipo = c.split("]")[0].lstrip("[").strip().upper() if "]" in c else "INFO"
            grouped[tipo].append(c)

        parts: list[str] = []
        for tipo, items in grouped.items():
            items_text = "\n".join(f"  - {item}" for item in items)
            parts.append(f"### {tipo}\n{items_text}")

        fallback_text = "\n\n".join(parts) if parts else "Sem dados disponíveis."

        return Briefing(
            text=fallback_text,
            validation_pass=False,
            raw_fallback=True,
            chunks_pre_count=len(chunks),
        )

    # -----------------------------------------------------------------------
    # Método principal
    # -----------------------------------------------------------------------

    def prepare(
        self,
        chunks: list[str],
        analyst_persona: str = "",
        section_title: str = "",
        nome: str = "",
    ) -> Briefing:
        """Prepara briefing a partir de chunks brutos.

        Args:
            chunks: Lista de chunks formatados "[TYPE] texto...".
            analyst_persona: System prompt do analista alvo.
            section_title: Título da seção (ex: "CLASSIFICAÇÃO POLÍTICA").
            nome: Nome do deputado.

        Returns:
            Briefing completo. Se o preparador falhar, retorna fallback
            com raw_fallback=True.
        """
        if not chunks:
            return Briefing(
                text="Sem dados disponíveis para esta seção.",
                validation_pass=False,
                chunks_pre_count=0,
            )

        prompt = self._build_prep_prompt(chunks, analyst_persona, section_title, nome)

        # Carregar modelo rápido via model_scope (refcount tracking)
        lm_ctx = None
        try:
            lm_ctx = self._model_scope()
        except Exception as e:
            # Não conseguiu carregar (ex: VRAM bloqueada por modelo em uso e
            # timeout em _wait_for_room). Não adianta chamar o chat sem o
            # modelo carregado — cai para fallback (chunks crus).
            log.warning(
                f"Preparer: não foi possível carregar {self.model} para "
                f"'{section_title}': {e}. Usando chunks crus."
            )
            return self._build_fallback(chunks)

        # Chamar LLM rápido
        try:
            client = self._get_client()
            # SEM warmup: havia um chat falso ("Responda apenas: OK.") por
            # analista para "absorver" o load do backend, mas isso gerava
            # requisições sem sentido a cada seção do dossiê. O prompt real
            # já tem timeout generoso (LOCALAI_MODEL_TIMEOUTS: 300s para
            # zero-gemma) que cobre load (60-90s) + reasoning + briefing.
            # Só a 1a chamada do processo paga o load; nas demais o backend
            # já está na GPU (model_scope mantém refcount e o LRU só descarrega
            # quando precisa de VRAM).
            resposta = client.chat(
                prompt=prompt, system=self._system_prompt(), max_tokens=1500
            )
        except Exception as e:
            log.warning(f"Preparer falhou para '{section_title}': {e}")
            return self._build_fallback(chunks)
        finally:
            self._release_model(lm_ctx)

        if not resposta or not resposta.strip():
            log.warning(f"Preparer retornou vazio para '{section_title}'")
            return self._build_fallback(chunks)

        # Parse resposta
        briefing = self._parse_response(resposta, chunks)
        briefing.chunks_pre_count = len(chunks)

        # Validar fidelidade numérica
        self._validate_fidelity(briefing, chunks)

        # Fase 3 (2026-08-14): repair pass — se a validação falhar, tenta
        # corrigir cirurgicamente os valores sem fonte antes do fallback cru.
        if not briefing.validation_pass and not briefing.raw_fallback:
            for _ in range(PREPARER_MAX_REPAIR_ATTEMPTS):
                if briefing.validation_pass or briefing.raw_fallback:
                    break
                briefing = self._repair_pass(
                    briefing, chunks, analyst_persona, section_title, nome
                )

        log.info(
            f"Preparer '{section_title}': {len(chunks)} chunks -> "
            f"{briefing.total_chars} chars briefing "
            f"(validação: {'OK' if briefing.validation_pass else 'FALHOU'}, "
            f"fallback: {briefing.raw_fallback}, "
            f"repair: {briefing.repair_attempts})"
        )

        return briefing
