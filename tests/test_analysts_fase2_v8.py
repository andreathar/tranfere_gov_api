"""Testes da Fase 2 do refactor multi-analista (v8).

Cobre: fusão votacao, analista rede_politica, QC estruturado determinístico,
fidelidade R$ unificada e truncamento seletivo do preparer.
"""

from __future__ import annotations

import json

from src.analysts.base import (
    parse_structured_output,
    qc_estruturado,
    render_secoes_markdown,
    taxa_invencao_rs,
)
from src.analysts.preparer import _truncar_chunks_seletivo

# ---------------------------------------------------------------------------
# parse_structured_output
# ---------------------------------------------------------------------------


class TestParseStructuredOutput:
    def test_json_direto(self):
        saida = '{"secoes": ["a"], "fatos": []}'
        assert parse_structured_output(saida) == {"secoes": ["a"], "fatos": []}

    def test_bloco_json_markdown(self):
        saida = 'Texto antes\n```json\n{"secoes": ["a"], "fatos": []}\n```\ndepois'
        dados = parse_structured_output(saida)
        assert dados == {"secoes": ["a"], "fatos": []}

    def test_bloco_balanceado_sem_markdown(self):
        saida = 'lorem ipsum {"secoes": ["x"], "fatos": [{"categoria": "c"}]} tail'
        dados = parse_structured_output(saida)
        assert dados == {"secoes": ["x"], "fatos": [{"categoria": "c"}]}

    def test_invalido_retorna_none(self):
        assert parse_structured_output("apenas texto") is None
        assert parse_structured_output("") is None
        assert parse_structured_output("{json quebrado") is None

    def test_lista_raiz_ignorada(self):
        assert parse_structured_output("[1, 2, 3]") is None


# ---------------------------------------------------------------------------
# qc_estruturado
# ---------------------------------------------------------------------------


class TestQcEstruturado:
    CHUNKS = ["[EMENDA] COARI R$ 13.034.456,00 arrecadação R$ 163.487.712,39"]

    def test_json_valido_aprovado(self):
        saida = json.dumps(
            {
                "secoes": ["**1. CONCENTRAÇÃO**: ALERTA", "**2. RISCO**: NORMAL"],
                "fatos": [
                    {"categoria": "emenda", "valor": "R$ 13.034.456,00", "fonte_chunk_id": "EMENDA"}
                ],
                "flags": ["ALERTA"],
            },
            ensure_ascii=False,
        )
        aprovado, score = qc_estruturado(
            saida, self.CHUNKS, campos_obrigatorios=["secoes", "fatos"], min_secoes=2
        )
        assert aprovado
        assert score >= 50.0

    def test_json_invalido_reprovado(self):
        aprovado, score = qc_estruturado(
            "markdown sem json", self.CHUNKS, campos_obrigatorios=["secoes", "fatos"]
        )
        assert not aprovado
        assert score == 0.0

    def test_campos_faltando_reprovado(self):
        saida = '{"secoes": ["a"]}'  # sem fatos
        aprovado, score = qc_estruturado(
            saida, self.CHUNKS, campos_obrigatorios=["secoes", "fatos"]
        )
        assert not aprovado
        assert score == 10.0

    def test_fonte_chunk_invalida_penaliza(self):
        saida = json.dumps(
            {
                "secoes": ["a"],
                "fatos": [
                    {"categoria": "x", "valor": "R$ 13.034.456,00", "fonte_chunk_id": "INEXISTENTE"}
                ],
            }
        )
        _aprovado, score = qc_estruturado(
            saida, self.CHUNKS, campos_obrigatorios=["secoes", "fatos"]
        )
        assert score < 100.0

    def test_valor_inventado_penaliza(self):
        saida = json.dumps(
            {
                "secoes": ["a"],
                "fatos": [
                    {"categoria": "x", "valor": "R$ 999.999.999,99", "fonte_chunk_id": "EMENDA"}
                ],
            }
        )
        aprovado, _score = qc_estruturado(
            saida, self.CHUNKS, campos_obrigatorios=["secoes", "fatos"]
        )
        assert not aprovado


# ---------------------------------------------------------------------------
# render_secoes_markdown (compat do dossier final)
# ---------------------------------------------------------------------------


class TestRenderSecoes:
    def test_estruturado_extrai_secoes(self):
        saida = json.dumps({"secoes": ["**1. A**", "**2. B**"], "fatos": []})
        assert render_secoes_markdown(saida) == "**1. A**\n\n**2. B**"

    def test_markdown_puro_passthrough(self):
        saida = "### TITULO\n\nconteúdo"
        assert render_secoes_markdown(saida) == saida


# ---------------------------------------------------------------------------
# Fidelidade R$ unificada
# ---------------------------------------------------------------------------


class TestFidelidadeUnificada:
    CHUNK = "[EMENDA] Valor total: R$ 1.234,56 para COARI"

    def test_valor_fiel(self):
        assert taxa_invencao_rs("A emenda foi de R$ 1.234,56", self.CHUNK) == 0.0

    def test_valor_inventado(self):
        assert taxa_invencao_rs("A emenda foi de R$ 9.999,99", self.CHUNK) == 1.0

    def test_sem_valores_retorna_zero(self):
        assert taxa_invencao_rs("Sem números aqui", self.CHUNK) == 0.0

    def test_analista_com_briefing_compartilhado_nao_falha_por_valor_do_briefing(self):
        """Regressão do bug v8: analista cita valor que só existe no briefing
        compartilhado (preparado com contexto completo) e o QC acusava
        invenção porque validava apenas contra os chunks filtrados.
        O fix inclui briefing.text/fact_table no _last_chunks do QC.
        """
        from src.analysts.base import AnalystBase

        # Chunks filtrados com valor R$ presente, mas NÃO o citado no briefing
        chunks_filtrados = ["[VOTO] SIM no PL 1234 (R$ 999,00)"]
        briefing_text = "Emenda para COARI no valor de R$ 13.034.456,00"
        saida = "Destinou R$ 13.034.456,00 para COARI via emenda."

        class _Stub(AnalystBase):
            analyst_id = "stub"
            section_title = "STUB"

            def build_prompt(self, context, nome, briefing=None):
                return ""

            def quality_check(self, output):
                return True, 100.0

        # Simula o que run() faz (base.py:517-525): _last_chunks = chunks +
        # briefing quando compartilhado e is_useful
        inst = _Stub()
        inst._last_chunks = list(chunks_filtrados) + [briefing_text]
        taxa = taxa_invencao_rs(saida, "\n".join(inst._last_chunks))
        assert taxa == 0.0

        # Sem o briefing no contexto, o mesmo valor seria acusado de invenção
        taxa_sem_briefing = taxa_invencao_rs(saida, "\n".join(chunks_filtrados))
        assert taxa_sem_briefing > 0.0


# ---------------------------------------------------------------------------
# Truncamento seletivo do preparer
# ---------------------------------------------------------------------------


class TestTruncarSeletivo:
    CHUNKS = [
        "[EMENDA] a",
        "[EMENDA] b",
        "[VOTO] c",
        "[DISCURSO_PLENARIO] d",
        "[PERFIL] e",
        "[CONEXAO_POLITICA] f",
        "[PROPOSICAO] g",
    ]

    def test_sem_truncamento(self):
        assert _truncar_chunks_seletivo(self.CHUNKS, 99) == self.CHUNKS

    def test_prioriza_tipos_ricos(self):
        out = _truncar_chunks_seletivo(self.CHUNKS, 4)
        assert len(out) == 4
        assert out[0] == "[EMENDA] a"  # primeiro do tipo mais rico
        tipos = {c.split("]")[0] for c in out}
        assert "[EMENDA" in tipos
        assert "[VOTO" in tipos
        assert "[PROPOSICAO" in tipos

    def test_mesmo_tipo_so_um_por_tipo(self):
        chunks = ["[EMENDA] a", "[EMENDA] b", "[EMENDA] c"]
        out = _truncar_chunks_seletivo(chunks, 2)
        assert len(out) == 2
        assert out[0] == "[EMENDA] a"

    def test_completa_na_ordem_original(self):
        out = _truncar_chunks_seletivo(self.CHUNKS, 3)
        assert out[0] == "[EMENDA] a"
        assert out[1] == "[VOTO] c"
        # Prioridade: PROPOSICAO vem antes de DISCURSO_PLENARIO na lista
        assert out[2] == "[PROPOSICAO] g"


# ---------------------------------------------------------------------------
# Registry v8
# ---------------------------------------------------------------------------


class TestRegistryV8:
    def test_analistas_registrados(self):
        from src.analysts import ANALYST_REGISTRY

        ids = set(ANALYST_REGISTRY.keys())
        assert "votacao" in ids
        assert "rede_politica" in ids
        assert "classificador" not in ids
        assert "alinhamento" not in ids

    def test_router_mapeia_novos(self):
        from src.analysts.router import CHUNK_TYPE_TO_ANALYST

        assert "[VOTO]" in CHUNK_TYPE_TO_ANALYST["votacao"]
        assert "[CONEXAO_POLITICA]" in CHUNK_TYPE_TO_ANALYST["rede_politica"]
        assert "[SENADOR]" in CHUNK_TYPE_TO_ANALYST["rede_politica"]

    def test_tematicas_prioriza_resumo_area(self):
        from src.analysts.router import filter_chunks_by_analyst

        chunks = [
            "[EMENDA] COARI R$ 1.000,00",
            "[EMENDA] Distribuição por área das emendas PIX de FULANO: Pavimentação: R$ 900,00",
            "[EMENDA] OUTROS R$ 100,00",
        ]
        out = filter_chunks_by_analyst(chunks, "tematicas")
        assert "Distribuição por área" in out[0]

    def test_pesos_v8_somam_um(self):
        from src.analysts import calculate_global_score

        # Acessa PESOS via inspeção do docstring é frágil; valida apenas que
        # pesos de analistas removidos não existem mais no cálculo.
        from src.analysts.base import AnalystResult

        def _fake_result(analyst_id: str, score: float) -> AnalystResult:
            return AnalystResult(
                analyst_id=analyst_id,
                section_title="t",
                content="x",
                quality_score=score,
                quality_ok=True,
                duration=0.1,
                chunks_used=[],
            )

        r = _fake_result("votacao", 100.0)
        score, ok = calculate_global_score([r])
        assert score == 100.0
        assert ok

        r2 = _fake_result("classificador", 100.0)  # removido -> peso default 0.10
        score2, _ = calculate_global_score([r2])
        assert score2 == 100.0

    def test_assemble_dossier_renderiza_json_como_markdown(self):
        """O dossier final não pode vazar JSON bruto: seções estruturadas
        (secoes[]) viram markdown via render_secoes_markdown."""
        from src.analysts import assemble_dossier
        from src.analysts.base import AnalystResult

        r = AnalystResult(
            analyst_id="votacao",
            section_title="CLASSIFICAÇÃO POLÍTICA + ALINHAMENTO E DISSENSO",
            content=json.dumps(
                {
                    "secoes": ["**CLASSIFICAÇÃO**: GOVERNO", "**DISSENSO**: nenhum"],
                    "fatos": [{"categoria": "alinhamento", "valor": "70%", "fonte_chunk_id": "VOTO"}],
                    "flags": ["ALINHADO"],
                },
                ensure_ascii=False,
            ),
            quality_ok=True,
            quality_score=100.0,
        )
        dossier = assemble_dossier([r])
        assert "**CLASSIFICAÇÃO**: GOVERNO" in dossier
        assert '"secoes"' not in dossier
        assert '"fatos"' not in dossier
