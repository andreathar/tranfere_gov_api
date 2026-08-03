"""
Tests for src.redator_transferegov — Redator Oficial de Documentos.

Tests pure formatting/validation functions and document generators.
Uses mocks for DB-dependent functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.redator_transferegov import (
    FECHOS,
    MESES,
    PRONOMES_TRATAMENTO,
    TIPOS_DOCUMENTO,
    consultar_pronome_tratamento,
    formatar_data_extenso,
    gerar_despacho,
    gerar_nota_tecnica,
    gerar_numeracao,
    gerar_oficio,
    gerar_parecer,
    obter_fecho,
    validar_documento,
)

# ---------------------------------------------------------------------------
# formatar_data_extenso
# ---------------------------------------------------------------------------


class TestFormatarDataExtenso:
    """Tests for formatar_data_extenso — data por extenso no padrão oficial."""

    @patch("src.redator_transferegov.datetime")
    def test_default_city(self, mock_dt):
        mock_dt.now.return_value.day = 15
        mock_dt.now.return_value.month = 7
        mock_dt.now.return_value.year = 2026
        result = formatar_data_extenso()
        assert "Brasília, 15 de julho de 2026." in result

    @patch("src.redator_transferegov.datetime")
    def test_first_day_uses_ordinal(self, mock_dt):
        mock_dt.now.return_value.day = 1
        mock_dt.now.return_value.month = 1
        mock_dt.now.return_value.year = 2026
        result = formatar_data_extenso()
        assert "1º" in result

    @patch("src.redator_transferegov.datetime")
    def test_custom_city(self, mock_dt):
        mock_dt.now.return_value.day = 25
        mock_dt.now.return_value.month = 12
        mock_dt.now.return_value.year = 2026
        result = formatar_data_extenso(cidade="Recife")
        assert "Recife, 25 de dezembro de 2026." in result

    @patch("src.redator_transferegov.datetime")
    def test_ends_with_period(self, mock_dt):
        mock_dt.now.return_value.day = 10
        mock_dt.now.return_value.month = 3
        mock_dt.now.return_value.year = 2026
        result = formatar_data_extenso()
        assert result.endswith(".")

    @patch("src.redator_transferegov.datetime")
    def test_month_lowercase(self, mock_dt):
        mock_dt.now.return_value.day = 5
        mock_dt.now.return_value.month = 8
        mock_dt.now.return_value.year = 2026
        result = formatar_data_extenso()
        # Month should be lowercase per Manual de Redação
        assert "agosto" in result
        assert "Agosto" not in result

    @patch("src.redator_transferegov.datetime")
    def test_all_months(self, mock_dt):
        """Verify all 12 month names are in MESES dict."""
        assert len(MESES) == 12
        for m in range(1, 13):
            mock_dt.now.return_value.month = m
            mock_dt.now.return_value.day = 1
            mock_dt.now.return_value.year = 2026
            result = formatar_data_extenso()
            assert MESES[m] in result


# ---------------------------------------------------------------------------
# gerar_numeracao
# ---------------------------------------------------------------------------


class TestGerarNumeracao:
    """Tests for gerar_numeracao — numeração oficial de documentos."""

    def test_basic_numeracao(self):
        result = gerar_numeracao("oficio", 142, setor="SAA/SE/MT")
        assert "Nº" in result
        assert "142" in result
        assert "SAA/SE/MT" in result

    def test_memorando_converted_to_oficio(self):
        result = gerar_numeracao("memorando", 5, setor="GAB")
        assert "OFÍCIO" in result
        assert "memorando" not in result.lower()

    def test_aviso_converted_to_oficio(self):
        result = gerar_numeracao("aviso", 10, ano=2026)
        assert "OFÍCIO" in result

    def test_without_setor(self):
        result = gerar_numeracao("oficio", 1)
        assert result == "OFÍCIO Nº 1/2026" or result == "OFÍCIO Nº 1/2026"

    def test_default_ano_is_current(self):
        """Without ano, should use current year."""
        result = gerar_numeracao("parecer", 42)
        assert str(result).startswith("Parecer Nº 42/")

    def test_custom_ano(self):
        result = gerar_numeracao("oficio", 100, ano=2024, setor="ADM")
        assert "2024" in result

    def test_nota_tecnica_numeracao(self):
        result = gerar_numeracao("nota_tecnica", 1, setor="ASSESSORIA")
        assert "NOTA TÉCNICA" in result

    def test_portaria_numeracao(self):
        result = gerar_numeracao("portaria", 50, ano=2025)
        assert "PORTARIA" in result
        assert "50" in result


# ---------------------------------------------------------------------------
# consultar_pronome_tratamento
# ---------------------------------------------------------------------------


class TestConsultarPronomeTratamento:
    """Tests for consultar_pronome_tratamento — pronomes de tratamento."""

    def test_presidente_republica(self):
        info = consultar_pronome_tratamento("presidente da república")
        assert "Excelentíssimo" in info["vocativo"]
        assert info["vocativo"].startswith("Excelentíssimo")

    def test_governador(self):
        info = consultar_pronome_tratamento("governador")
        assert info["vocativo"] == "Senhor Governador,"
        assert info["enderecamento"] == "Ao Senhor"

    def test_prefeito(self):
        info = consultar_pronome_tratamento("prefeito")
        assert "Senhor Prefeito" in info["vocativo"]

    def test_deputado_federal(self):
        info = consultar_pronome_tratamento("deputado federal")
        assert "Senhor Deputado" in info["vocativo"]
        assert "Excelência" in info["enderecamento"]

    def test_senador(self):
        info = consultar_pronome_tratamento("senador")
        assert "Senhor Senador" in info["vocativo"]

    def test_ministro(self):
        info = consultar_pronome_tratamento("ministro")
        assert "Senhor Ministro" in info["vocativo"]

    def test_case_insensitive(self):
        info_upper = consultar_pronome_tratamento("PRESIDENTE DA REPÚBLICA")
        info_lower = consultar_pronome_tratamento("presidente da república")
        assert info_upper["vocativo"] == info_lower["vocativo"]

    def test_partial_match_fallback(self):
        info = consultar_pronome_tratamento("secretário adjunto")
        assert "Secretário" in info["vocativo"]

    def test_unknown_cargo_returns_generic(self):
        info = consultar_pronome_tratamento("cargo inexistente 123")
        assert "Senhor(a)" in info["vocativo"]

    def test_all_pronomes_have_vocativo(self):
        """Verify every registered pronome has vocativo and enderecamento."""
        for cargo, dados in PRONOMES_TRATAMENTO.items():
            assert "vocativo" in dados, f"{cargo} missing vocativo"
            assert "enderecamento" in dados, f"{cargo} missing enderecamento"

    def test_strip_handles_whitespace(self):
        info = consultar_pronome_tratamento("  Governador  ")
        assert "Senhor Governador" in info["vocativo"]

    def test_deputado_and_deputado_federal_distinct(self):
        dep = consultar_pronome_tratamento("deputado")
        dep_fed = consultar_pronome_tratamento("deputado federal")
        # Both should resolve correctly
        assert "Deputado" in dep["vocativo"]
        assert "Deputado" in dep_fed["vocativo"]


# ---------------------------------------------------------------------------
# obter_fecho
# ---------------------------------------------------------------------------


class TestObterFecho:
    """Tests for obter_fecho — fechos de documentos oficiais."""

    def test_superior_returns_respeitosamente(self):
        assert obter_fecho("superior") == "Respeitosamente,"

    def test_igual_returns_atenciosamente(self):
        assert obter_fecho("igual") == "Atenciosamente,"

    def test_default_is_igual(self):
        assert obter_fecho() == "Atenciosamente,"

    def test_unknown_level_falls_back_to_igual(self):
        assert obter_fecho("desconhecido") == "Atenciosamente,"

    def test_all_fechos_have_comma(self):
        for nivel, fecho in FECHOS.items():
            assert fecho.endswith(","), f"Fecho for '{nivel}' must end with comma"

    def test_only_two_fechos(self):
        assert len(FECHOS) == 2


# ---------------------------------------------------------------------------
# validar_documento
# ---------------------------------------------------------------------------


class TestValidarDocumento:
    """Tests for validar_documento — validação de conformidade MRPR 3ª ed."""

    def test_valid_texto_returns_empty(self):
        texto = "Senhor Governador,\n\n" "Brasília, 15 de julho de 2026.\n\n" "Atenciosamente,\n"
        problemas = validar_documento(texto, "oficio")
        assert problemas == []

    def test_numeric_date_detected(self):
        problemas = validar_documento("15/07/2026", "oficio")
        assert len(problemas) >= 1
        assert any("Data" in p for p in problemas)

    def test_pronome_abolido_dignissimo(self):
        problemas = validar_documento("Digníssimo Senhor", "oficio")
        assert any("Digníssimo" in p for p in problemas)

    def test_pronome_abolido_ilmo(self):
        problemas = validar_documento("Ilmo. Senhor", "oficio")
        assert any("Ilmo." in p for p in problemas)

    def test_pronome_abolido_ilustrissimo(self):
        problemas = validar_documento("Ilustríssimo Senhor", "oficio")
        assert any("Ilustríssimo" in p for p in problemas)

    def test_memorando_detected(self):
        problemas = validar_documento("MEMORANDO Nº 1/2026", "oficio")
        assert any("MEMORANDO" in p for p in problemas)

    def test_aviso_detected(self):
        problemas = validar_documento("AVISO Nº 1/2026", "oficio")
        assert any("AVISO" in p for p in problemas)

    def test_excessive_gerundio(self):
        texto = "estando fazendo andando vendendo partindo correndo"
        problemas = validar_documento(texto, "oficio")
        assert any("gerúndio" in p for p in problemas)

    def test_single_gerundio_ok(self):
        problemas = validar_documento("estando", "oficio")
        assert problemas == [] or all("gerúndio" not in p for p in problemas)

    def test_multiple_issues_returned(self):
        texto = "15/07/2026\nDigníssimo Senhor\nMEMORANDO"
        problemas = validar_documento(texto, "oficio")
        assert len(problemas) >= 3


# ---------------------------------------------------------------------------
# gerar_oficio
# ---------------------------------------------------------------------------


class TestGerarOficio:
    """Tests for gerar_oficio — geração de ofício oficial."""

    def test_contains_vocativo(self):
        texto = gerar_oficio(
            destinatario="Governador do Estado",
            cargo_destinatario="governador",
            assunto="Relatório",
            corpo="Segue em anexo o relatório.",
        )
        assert "Senhor Governador" in texto

    def test_contains_fecho_superior(self):
        texto = gerar_oficio(
            destinatario="Ministro da Saúde",
            cargo_destinatario="ministro",
            assunto="Solicitação",
            corpo="Solicito providências.",
        )
        assert "Respeitosamente" in texto

    def test_contains_corpo(self):
        corpo = "Encaminho o relatório para análise."
        texto = gerar_oficio(
            destinatario="Secretário",
            cargo_destinatario="secretário",
            assunto="Relatório",
            corpo=corpo,
        )
        assert corpo in texto

    def test_with_numero(self):
        texto = gerar_oficio(
            destinatario="Chefe de Gabinete",
            cargo_destinatario="secretário",
            assunto="Comunicado",
            corpo="Comunico...",
            numero=42,
        )
        assert "OFÍCIO" in texto
        assert "42" in texto

    def test_without_numero_no_prefix(self):
        texto = gerar_oficio(
            destinatario="Diretor",
            cargo_destinatario="diretor",
            assunto="Informe",
            corpo="Informo que...",
        )
        # Without numero, no OFÍCIO Nº line
        assert "OFÍCIO" not in texto

    def test_contains_date(self):
        texto = gerar_oficio(
            destinatario="Prefeito",
            cargo_destinatario="prefeito",
            assunto="Comunicado",
            corpo="Corpo do ofício.",
        )
        assert "Brasília" in texto

    def test_multiline_corpo(self):
        corpo = "Linha 1.\n\nLinha 2."
        texto = gerar_oficio(
            destinatario="Secretário",
            cargo_destinatario="secretário",
            assunto="Assunto",
            corpo=corpo,
        )
        assert "Linha 1." in texto
        assert "Linha 2." in texto

    def test_custom_orgao(self):
        texto = gerar_oficio(
            destinatario="Ministro",
            cargo_destinatario="ministro",
            assunto="Assunto",
            corpo="Corpo.",
            orgao_remetente="Ministério do Planejamento",
        )
        assert "Ministério do Planejamento" in texto


# ---------------------------------------------------------------------------
# gerar_parecer
# ---------------------------------------------------------------------------


class TestGerarParecer:
    """Tests for gerar_parecer — geração de parecer técnico/jurídico."""

    def test_contains_processo(self):
        texto = gerar_parecer(processo="001/2026", consulta="Análise de emendas")
        assert "001/2026" in texto

    def test_contains_consulta(self):
        texto = gerar_parecer(processo="001/2026", consulta="Análise técnica")
        assert "Análise técnica" in texto

    def test_contains_ementa_section(self):
        texto = gerar_parecer(processo="001/2026", consulta="Teste")
        assert "EMENTA" in texto

    def test_contains_relatorio_section(self):
        texto = gerar_parecer(processo="001/2026", consulta="Teste")
        assert "DO RELATÓRIO" in texto

    def test_contains_fundamentacao_section(self):
        texto = gerar_parecer(processo="001/2026", consulta="Teste")
        assert "DA FUNDAMENTAÇÃO" in texto

    def test_contains_conclusao_section(self):
        texto = gerar_parecer(processo="001/2026", consulta="Teste")
        assert "DA CONCLUSÃO" in texto

    def test_autoridade_no_final(self):
        texto = gerar_parecer(
            processo="001/2026",
            consulta="Teste",
            autoridade="Assessor Técnico",
        )
        assert "Assessor Técnico" in texto

    def test_custom_area(self):
        texto = gerar_parecer(
            processo="001/2026",
            consulta="Teste",
            area="jurídico",
        )
        assert "JURÍDICO" in texto  # area is uppercased


# ---------------------------------------------------------------------------
# gerar_despacho
# ---------------------------------------------------------------------------


class TestGerarDespacho:
    """Tests for gerar_despacho — geração de despacho administrativo."""

    def test_contains_assunto(self):
        texto = gerar_despacho(assunto="Encaminhamento", texto="Encaminho os documentos.")
        assert "Encaminhamento" in texto

    def test_contains_texto(self):
        texto = gerar_despacho(assunto="Encaminhamento", texto="Encaminho os documentos.")
        assert "Encaminho os documentos" in texto

    def test_contains_data(self):
        texto = gerar_despacho(assunto="Assunto", texto="Texto do despacho.")
        assert "Brasília" in texto

    def test_autoridade_no_final(self):
        texto = gerar_despacho(
            assunto="Assunto",
            texto="Texto.",
            autoridade="Secretário de Planejamento",
        )
        assert "Secretário de Planejamento" in texto

    def test_orgao_no_final(self):
        texto = gerar_despacho(
            assunto="Assunto",
            texto="Texto.",
            orgao="Secretaria de Planejamento",
        )
        assert "Secretaria de Planejamento" in texto

    def test_no_fecho_obrigatorio(self):
        """Despacho does not require a fecho."""
        texto = gerar_despacho(assunto="Assunto", texto="Texto.")
        # Should not contain either fecho
        assert "Respeitosamente" not in texto
        assert "Atenciosamente" not in texto

    def test_custom_cidade(self):
        texto = gerar_despacho(
            assunto="Assunto",
            texto="Texto.",
            cidade="Salvador",
        )
        assert "Salvador" in texto


# ---------------------------------------------------------------------------
# gerar_nota_tecnica (with mocked DB)
# ---------------------------------------------------------------------------


class TestGerarNotaTecnica:
    """Tests for gerar_nota_tecnica with mocked DB queries."""

    @patch("src.redator_transferegov.resumo_geral")
    @patch("src.redator_transferegov.resumo_impedidos")
    @patch("src.redator_transferegov.buscar_planos_parlamentar")
    def test_basic_nota_tecnica(
        self,
        mock_buscar_planos,
        mock_resumo_impedidos,
        mock_resumo_geral,
    ):
        mock_resumo_geral.return_value = {
            "total": 1000,
            "parlamentares": 50,
            "beneficiarios": 200,
            "valor_total": 50000000.0,
            "aprovados": 300,
            "em_execucao": 400,
            "concluidos": 100,
            "impedidos": 100,
            "reprovados": 50,
            "cancelados": 50,
        }
        mock_resumo_impedidos.return_value = MagicMock()
        mock_resumo_impedidos.return_value.empty = True
        mock_buscar_planos.return_value = MagicMock()
        mock_buscar_planos.return_value.empty = True

        texto = gerar_nota_tecnica(parlamentar=None, ano=2026)
        assert "NOTA TÉCNICA" in texto
        assert "INTRODUÇÃO" in texto
        assert "ANÁLISE" in texto
        assert "CONCLUSÃO" in texto
        assert "1.000" in texto or "1000" in texto
        assert "50" in texto

    @patch("src.redator_transferegov.resumo_geral")
    @patch("src.redator_transferegov.resumo_impedidos")
    @patch("src.redator_transferegov.buscar_planos_parlamentar")
    def test_nota_tecnica_with_parlamentar(
        self,
        mock_buscar_planos,
        mock_resumo_impedidos,
        mock_resumo_geral,
    ):
        mock_resumo_geral.return_value = {
            "total": 500,
            "parlamentares": 30,
            "beneficiarios": 100,
            "valor_total": 25000000.0,
            "aprovados": 150,
            "em_execucao": 200,
            "concluidos": 50,
            "impedidos": 50,
            "reprovados": 25,
            "cancelados": 25,
        }
        mock_resumo_impedidos.return_value = MagicMock()
        mock_resumo_impedidos.return_value.empty = True
        mock_buscar_planos.return_value = MagicMock()
        mock_buscar_planos.return_value.empty = True

        texto = gerar_nota_tecnica(parlamentar="AFONSO FLORENCE", ano=2026)
        assert "AFONSO FLORENCE" in texto.upper()
        assert "NOTA TÉCNICA" in texto

    @patch("src.redator_transferegov.resumo_geral")
    @patch("src.redator_transferegov.resumo_impedidos")
    @patch("src.redator_transferegov.query_df")
    def test_nota_tecnica_with_planos(
        self,
        mock_query_df,
        mock_resumo_impedidos,
        mock_resumo_geral,
    ):
        mock_resumo_geral.return_value = {
            "total": 500,
            "parlamentares": 30,
            "beneficiarios": 100,
            "valor_total": 25000000.0,
            "aprovados": 150,
            "em_execucao": 200,
            "concluidos": 50,
            "impedidos": 50,
            "reprovados": 25,
            "cancelados": 25,
        }
        mock_resumo_impedidos.return_value = MagicMock()
        mock_resumo_impedidos.return_value.empty = True

        import pandas as pd

        planos_df = pd.DataFrame(
            [
                {
                    "plano_acao_codigo": "2026000001",
                    "objeto_descricao": "Cemitérios",
                    "beneficiario_nome": "Município X",
                    "uf": "AL",
                    "plano_acao_situacao": "IMPEDIDO",
                    "valor_total": 150000.0,
                    "emenda_codigo": "11228",
                    "motivo_impedimento": "Restrição Técnica",
                }
            ]
        )
        mock_query_df.return_value = planos_df

        texto = gerar_nota_tecnica(parlamentar="DEPUTADO TESTE", ano=2026)
        assert "2026000001" in texto
        assert "Cemitérios" in texto
        assert "IMPEDIDO" in texto
        assert "Restrição Técnica" in texto

    @patch("src.redator_transferegov.resumo_geral")
    @patch("src.redator_transferegov.resumo_impedidos")
    def test_nota_tecnica_empty_resumo(
        self,
        mock_resumo_impedidos,
        mock_resumo_geral,
    ):
        mock_resumo_geral.return_value = {}
        mock_resumo_impedidos.return_value = MagicMock()
        mock_resumo_impedidos.return_value.empty = True

        # Should still generate without crashing when resumo is empty
        texto = gerar_nota_tecnica()
        assert "NOTA TÉCNICA" in texto
        assert "CONCLUSÃO" in texto


# ---------------------------------------------------------------------------
# TIPOS_DOCUMENTO consistency
# ---------------------------------------------------------------------------


class TestTiposDocumento:
    """Verify document type constants."""

    def test_tipos_contains_core_types(self):
        for tipo in ("oficio", "despacho", "portaria", "parecer", "nota_tecnica", "ata"):
            assert tipo in TIPOS_DOCUMENTO

    def test_tipos_have_brazilian_names(self):
        assert TIPOS_DOCUMENTO["oficio"] == "Ofício"
        assert TIPOS_DOCUMENTO["nota_tecnica"] == "Nota Técnica"


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_nota_tecnica_command(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv", ["prog", "nota-tecnica", "--parlamentar", "TESTE", "--ano", "2026"]
        )
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.comando == "nota-tecnica"
        assert args.parlamentar == "TESTE"
        assert args.ano == 2026

    def test_oficio_command(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "oficio",
                "--dest",
                "Governador",
                "--cargo",
                "Governador do Estado",
                "--assunto",
                "Relatório",
                "--corpo",
                "Segue o relatório.",
            ],
        )
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.comando == "oficio"
        assert args.dest == "Governador"
        assert args.cargo == "Governador do Estado"

    def test_parecer_command(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "parecer",
                "--processo",
                "001/2026",
                "--consulta",
                "Análise jurídica",
            ],
        )
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.comando == "parecer"
        assert args.processo == "001/2026"

    def test_despacho_command(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "despacho",
                "--assunto",
                "Encaminhamento",
                "--texto",
                "Encaminho os documentos.",
            ],
        )
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.comando == "despacho"
        assert args.assunto == "Encaminhamento"

    def test_listar_tipos(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "listar-tipos"])
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.comando == "listar-tipos"

    def test_validar_command(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "validar",
                "--arquivo",
                "/tmp/teste.txt",
                "--tipo",
                "oficio",
            ],
        )
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.comando == "validar"
        assert args.arquivo == "/tmp/teste.txt"
        assert args.tipo == "oficio"

    def test_data_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--data"])
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.data is True

    def test_pronomes_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--pronomes", "governador"])
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.pronomes == "governador"

    def test_numeracao_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--numeracao", "oficio", "142", "SAA/SE/MT"])
        from src.redator_transferegov import parse_args

        args = parse_args()
        assert args.numeracao == ["oficio", "142", "SAA/SE/MT"]
