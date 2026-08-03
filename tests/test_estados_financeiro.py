"""Testes do enricher de dados financeiros estaduais (SICONFI esfera estadual).

Cobre o parser DCA/RREO estadual — especialmente a regra de NAO somar as
colunas mensais/previsao do RREO (falso-inflado) e o match por nome exato do
DCA (evita "Outras Receitas Correntes" / intra-orcamentarias).
"""

from src.enrichers.estados_financeiro import (
    UF_IBGE,
    _conta_exata,
    _ItemDCA,
    parse_dca_estadual_itens,
    parse_rreo_estadual_itens,
)


def _item(conta: str, coluna: str, valor: float) -> _ItemDCA:
    return {"conta": conta, "coluna": coluna, "valor": valor}  # type: ignore[return-value]


class TestConvencoes:
    def test_uf_ibge_tem_27_entes(self):
        assert len(UF_IBGE) == 27
        assert UF_IBGE["SP"] == 35
        assert UF_IBGE["DF"] == 53
        assert UF_IBGE["RO"] == 11

    def test_conta_exata(self):
        assert _conta_exata("1.0.0.0.00.0.0 - Receitas Correntes", "Receitas Correntes")
        assert _conta_exata("Receitas Correntes", "Receitas Correntes")
        # Nao pode casar com "Outras/Demais" nem com intra-orcamentarias
        assert not _conta_exata("1.9.0.0.00.0.0 - Outras Receitas Correntes", "Receitas Correntes")
        assert not _conta_exata("7.0.0.0.00.0.0 - Receitas Correntes", "Receitas Correntes")
        assert not _conta_exata(
            "8.9.0.0.00.0.0 - Outras Receitas de Capital", "Receitas de Capital"
        )
        assert _conta_exata("2.0.0.0.00.0.0 - Receitas de Capital", "Receitas de Capital")


class TestParseDCAEstadual:
    def test_pega_coluna_certa_e_ignora_deducoes(self):
        itens = [
            _item("1.0.0.0.00.0.0 - Receitas Correntes", "Receitas Brutas Realizadas", 100.0),
            _item(
                "1.0.0.0.00.0.0 - Receitas Correntes", "Deduções - FUNDEB", 90.0
            ),  # NAO pode ser usado
            _item("2.0.0.0.00.0.0 - Receitas de Capital", "Receitas Brutas Realizadas", 20.0),
            _item("3.0.00.00.00 - Despesas Correntes", "Despesas Empenhadas", 80.0),
            _item("Despesas Exceto Intraorçamentárias", "Despesas Empenhadas", 95.0),
            _item("Despesas Intraorçamentárias", "Despesas Empenhadas", 5.0),
            _item("TOTAL DAS RECEITAS (III) = (I + II)", "Receitas Brutas Realizadas", 120.0),
        ]
        dados = parse_dca_estadual_itens(itens)
        assert dados["receitas_correntes"] == 100.0
        assert dados["receitas_capital"] == 20.0
        assert dados["despesas_correntes"] == 80.0
        assert dados["despesas_orcamentarias"] == 100.0  # 95 + 5
        assert dados["despesas_totais"] == 100.0
        assert dados["receitas_orcamentarias"] == 120.0
        assert dados["resultado_orcamentario"] == 20.0  # 120 - 100

    def test_saldo_patrimonial_vira_patrimonio_liquido(self):
        itens = [_item("Saldo Patrimonial", "31/12/2024", -850.0)]
        dados = parse_dca_estadual_itens(itens)
        assert dados["patrimonio_liquido"] == -850.0


class TestParseRREOEstadual:
    def test_nao_soma_colunas_mensais_e_previsao(self):
        """A API retorna a mesma conta em 14 colunas; so vale o total anual."""
        itens = [
            _item("ICMS", "<MR-1>", 17.0),
            _item("ICMS", "<MR-2>", 18.0),
            _item("ICMS", "<MR>", 20.0),
            _item("ICMS", "PREVISÃO ATUALIZADA 2024", 223.0),
            _item("ICMS", "TOTAL (ÚLTIMOS 12 MESES)", 223.8),
        ]
        dados = parse_rreo_estadual_itens(itens)
        assert dados["arrec_icms"] == 223.8  # nao 17+18+20+223+223.8

    def test_fallback_soma_mensais_quando_sem_total(self):
        itens = [
            _item("IPVA", "<MR-1>", 10.0),
            _item("IPVA", "<MR-2>", 12.0),
        ]
        dados = parse_rreo_estadual_itens(itens)
        assert dados["arrec_ipva"] == 22.0

    def test_conta_estadual_fpe(self):
        itens = [_item("Cota-Parte do FPE", "TOTAL (ÚLTIMOS 12 MESES)", 1.9)]
        dados = parse_rreo_estadual_itens(itens)
        assert dados["arrec_cota_fpe"] == 1.9
        assert dados["arrec_rcl"] is None
