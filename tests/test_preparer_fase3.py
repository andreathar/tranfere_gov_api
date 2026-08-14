"""Testes da Fase 3 (2026-08-14): reasoning em estágios e repair pass.

Cobre:
- Parse do protocolo em estágios (INVENTÁRIO → AGRUPAMENTO → BRIEFING →
  FACT TABLE → VERIFICAÇÃO → KEY INSIGHTS), com tolerância a acentos.
- Compatibilidade retroativa com o formato antigo (sem inventário/verificação).
- Extração de valores sem fonte (base.valores_rs_sem_fonte) e problemas
  auto-reportados na VERIFICAÇÃO.
- Repair pass: quando a 1a resposta reprova a fidelidade R$, o preparer
  corrige cirurgicamente em vez de cair direto no fallback cru.
"""

from src.analysts.base import valores_rs_sem_fonte
from src.analysts.preparer import Briefing, PromptPreparer

CHUNKS = [
    "[EMENDA] Total de Emendas PIX: R$ 28.788.030,99 conforme [PARLAMENTAR_RESUMO].",
    "[EMENDA] Emenda ao Município A: R$ 1.500.000,00 (Objeto: Saúde).",
    "[VOTO] Votação do PL 123/2024: Sim (Tema: Educação).",
]

RESPOSTA_ESTAGIOS = """---INVENTÁRIO---
| Total de Emendas PIX | R$ 28.788.030,99 | R$ | emendas | fonte=[EMENDA] |
| Emenda Município A | R$ 1.500.000,00 | R$ | emendas | fonte=[EMENDA] |
| PL 123/2024 | Sim | voto | alinhamento | fonte=[VOTO] |

---AGRUPAMENTO---
Emendas: Total R$ 28.788.030,99; Município A R$ 1.500.000,00.
Votações: PL 123/2024 Sim.

---BRIEFING---
O deputado destinou R$ 28.788.030,99 em emendas PIX e R$ 1.500.000,00 ao
Município A (Saúde). Votou Sim no PL 123/2024 (Educação).

---FACT TABLE---
| Total de Emendas PIX | Deputado | R$ 28.788.030,99 | [PARLAMENTAR_RESUMO] |
| Emendas | Município A | R$ 1.500.000,00 | Objeto: Saúde; fonte=[EMENDA] |
| Votação | PL 123/2024 | Sim | Tema: Educação; fonte=[VOTO] |

---VERIFICAÇÃO---
| R$ 28.788.030,99 | OK |
| R$ 1.500.000,00 | OK |
| Sim | OK |

---KEY INSIGHTS---
- Concentração de emendas no Município A
- Alinhamento com o governo no PL 123/2024
"""


def test_parse_estagios_extrai_inventario_agrupamento_verificacao():
    prep = PromptPreparer()
    b = prep._parse_response(RESPOSTA_ESTAGIOS, CHUNKS)

    assert b.inventario
    assert "28.788.030,99" in b.inventario
    assert "fonte=[EMENDA]" in b.inventario
    assert b.agrupamento
    assert "Emendas" in b.agrupamento
    assert b.verificacao
    assert "OK" in b.verificacao
    assert b.text and "28.788.030,99" in b.text
    assert b.fact_table and "| Total de Emendas PIX" in b.fact_table
    assert b.insights == [
        "Concentração de emendas no Município A",
        "Alinhamento com o governo no PL 123/2024",
    ]


def test_parse_backward_compat_formato_antigo():
    """Formato antigo (sem inventário/verificação) continua parseando."""
    prep = PromptPreparer()
    antigo = """---BRIEFING---
Síntese do período.

---FACT TABLE---
| Categoria | Entidade | Valor | Detalhe |
| Total | Deputado | R$ 1.000,00 | Conforme [EMENDA] |

---KEY INSIGHTS---
- Insight 1
"""
    b = prep._parse_response(antigo, CHUNKS)
    assert b.text == "Síntese do período."
    assert "R$ 1.000,00" in b.fact_table
    assert b.insights == ["Insight 1"]
    assert b.inventario == ""
    assert b.agrupamento == ""
    assert b.verificacao == ""


def test_parse_verificacao_sem_acento_e_problemas():
    """Modelo pode emitir VERIFICACAO sem acento; problemas são extraídos."""
    prep = PromptPreparer()
    resp = """---VERIFICACAO---
| R$ 1.000,00 | FALTA_FONTE |
| R$ 2.000,00 | CONFLITO |
| R$ 3.000,00 | OK |
"""
    b = prep._parse_response(resp, CHUNKS)
    assert "FALTA_FONTE" in b.verificacao
    problemas = prep._problemas_verificacao(b)
    assert problemas == ["R$ 1.000,00", "R$ 2.000,00"]


def test_problemas_verificacao_vazio():
    prep = PromptPreparer()
    assert prep._problemas_verificacao(Briefing()) == []
    assert prep._problemas_verificacao(
        Briefing(verificacao="| R$ 5,00 | OK |\n| R$ 6,00 | OK |")
    ) == []


def test_valores_rs_sem_fonte():
    output = "Total: R$ 28.788.030,99 e R$ 999,99"
    chunks_text = "R$ 28.788.030,99 e R$ 1.500.000,00"
    sem = valores_rs_sem_fonte(output, chunks_text)
    assert 999.99 in sem
    assert 28788030.99 not in sem


def test_taxa_invencao_delega_para_valores_sem_fonte():
    from src.analysts.base import taxa_invencao_rs

    # 1 de 2 valores sem fonte -> taxa 0.5 (mesma semântica de antes)
    output = "A: R$ 28.788.030,99 e B: R$ 999,99"
    chunks_text = "R$ 28.788.030,99 e R$ 1.500.000,00"
    assert taxa_invencao_rs(output, chunks_text) == 0.5
    # Todos com fonte -> 0
    assert taxa_invencao_rs("R$ 28.788.030,99", chunks_text) == 0.0


def test_valores_sem_fonte_rs_briefing():
    prep = PromptPreparer()
    b = Briefing(
        text="Total de R$ 999,99.",
        fact_table="| X | Y | R$ 999,99 | [EMENDA] |",
    )
    sem = prep._valores_sem_fonte_rs(b, CHUNKS)
    assert 999.99 in sem


def test_build_repair_prompt_inclui_valores_sem_fonte():
    prep = PromptPreparer()
    b = Briefing(
        text="Total de R$ 999,99.",
        fact_table="| X | Y | R$ 999,99 | [EMENDA] |",
    )
    prompt = prep._build_repair_prompt(b, CHUNKS, "persona", "SEC", "Nome")
    assert "CORRIGINDO" in prompt
    assert "999,99" in prompt
    assert "R$ 28.788.030,99" in prompt  # chunk de referência presente


class _FakeClient:
    """Client fake: responde em sequência e conta chamadas."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.calls = 0

    def chat(self, prompt, system, max_tokens):
        self.calls += 1
        if not self.respostas:
            return ""
        return self.respostas.pop(0)


RESPOSTA_RUIM = """---BRIEFING---
Total de R$ 9.999.999,99 em emendas.

---FACT TABLE---
| Total | Deputado | R$ 9.999.999,99 | [EMENDA] |

---KEY INSIGHTS---
- x
"""

RESPOSTA_BOA = """---BRIEFING---
Total de R$ 28.788.030,99 em emendas e R$ 1.500.000,00 ao Município A.

---FACT TABLE---
| Total | Deputado | R$ 28.788.030,99 | [EMENDA] |
| Emendas | Município A | R$ 1.500.000,00 | [EMENDA] |

---KEY INSIGHTS---
- x
"""


def _preparer_mockado(monkeypatch, respostas):
    fake = _FakeClient(respostas)
    prep = PromptPreparer()
    monkeypatch.setattr(prep, "_get_client", lambda: fake)
    monkeypatch.setattr(prep, "_model_scope", lambda: None)
    return prep, fake


def test_prepare_repair_pass_corrige(monkeypatch):
    """1a resposta reprova a fidelidade; o repair corrige e valida."""
    chunks = [
        "[EMENDA] Total: R$ 28.788.030,99. Município A: R$ 1.500.000,00.",
    ]
    prep, fake = _preparer_mockado(monkeypatch, [RESPOSTA_RUIM, RESPOSTA_BOA])

    b = prep.prepare(chunks, "persona", "SEC", "Nome")

    assert b.validation_pass is True
    assert b.repair_used is True
    assert b.repair_attempts >= 1
    assert "28.788.030,99" in b.text
    assert "9.999.999,99" not in b.text
    assert fake.calls == 2


def test_prepare_sem_repair_quando_valida_direto(monkeypatch):
    """Se a 1a resposta já valida, não faz chamada extra de repair."""
    chunks = [
        "[EMENDA] Total: R$ 28.788.030,99. Município A: R$ 1.500.000,00.",
    ]
    prep, fake = _preparer_mockado(monkeypatch, [RESPOSTA_BOA])

    b = prep.prepare(chunks, "persona", "SEC", "Nome")

    assert b.validation_pass is True
    assert b.repair_used is False
    assert b.repair_attempts == 0
    assert fake.calls == 1


def test_prepare_repair_esgota_e_cai_fallback(monkeypatch):
    """Se o repair não corrigir e depois retornar vazio, cai no fallback cru."""
    chunks = ["[EMENDA] Total: R$ 28.788.030,99."]
    # 1a ruim (invalida) -> repair 1 ruim (invalida) -> repair 2 vazio (fallback)
    prep, fake = _preparer_mockado(monkeypatch, [RESPOSTA_RUIM, RESPOSTA_RUIM, ""])

    b = prep.prepare(chunks, "persona", "SEC", "Nome")

    assert b.raw_fallback is True
    assert b.repair_used is True
    assert fake.calls == 3
