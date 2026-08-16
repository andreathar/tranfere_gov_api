"""Tests for the Redator Oficial tool functions."""

from datetime import datetime

import pytest

from mcp_brasil.agentes.redator import tools


class TestFormatarDataExtenso:
    @pytest.mark.asyncio
    async def test_default_brasilia(self) -> None:
        result = await tools.formatar_data_extenso()
        now = datetime.now()
        assert "Brasília," in result
        assert str(now.year) in result
        assert result.endswith(".")

    @pytest.mark.asyncio
    async def test_no_uf_in_date(self) -> None:
        """3ª edição: data sem sigla da UF."""
        result = await tools.formatar_data_extenso()
        assert "/DF" not in result

    @pytest.mark.asyncio
    async def test_custom_city(self) -> None:
        result = await tools.formatar_data_extenso(cidade="Teresina", estado="PI")
        assert "Teresina," in result
        assert "/PI" not in result

    @pytest.mark.asyncio
    async def test_contains_month(self) -> None:
        result = await tools.formatar_data_extenso()
        from mcp_brasil.agentes.redator.constants import MESES

        now = datetime.now()
        assert MESES[now.month] in result


class TestGerarNumeracao:
    @pytest.mark.asyncio
    async def test_memorando_converts_to_oficio(self) -> None:
        """3ª edição: memorando abolido, converte para OFÍCIO."""
        result = await tools.gerar_numeracao("memorando", 42, 2026, "COORD-TI")
        assert result == "OFÍCIO Nº 42/2026/COORD-TI"

    @pytest.mark.asyncio
    async def test_oficio_without_setor(self) -> None:
        result = await tools.gerar_numeracao("oficio", 10, 2026)
        assert result == "OFÍCIO Nº 10/2026"

    @pytest.mark.asyncio
    async def test_portaria(self) -> None:
        result = await tools.gerar_numeracao("portaria", 123, 2026)
        assert result == "PORTARIA Nº 123/2026"

    @pytest.mark.asyncio
    async def test_default_year(self) -> None:
        result = await tools.gerar_numeracao("despacho", 1)
        now = datetime.now()
        assert str(now.year) in result

    @pytest.mark.asyncio
    async def test_unknown_type(self) -> None:
        result = await tools.gerar_numeracao("resolucao", 5, 2026)
        assert result == "Resolucao Nº 5/2026"


class TestConsultarPronomeTratamento:
    @pytest.mark.asyncio
    async def test_exact_match(self) -> None:
        result = await tools.consultar_pronome_tratamento("Governador")
        assert "Vossa Excelência" in result
        assert "Governador" in result
        assert "Endereçamento" in result

    @pytest.mark.asyncio
    async def test_chefes_de_poder_excelentissimo(self) -> None:
        """3ª edição: Excelentíssimo apenas para os 3 Chefes de Poder."""
        result = await tools.consultar_pronome_tratamento("Presidente da República")
        assert "Excelentíssimo" in result

    @pytest.mark.asyncio
    async def test_demais_sem_excelentissimo(self) -> None:
        """3ª edição: demais usam 'Senhor + Cargo', não 'Excelentíssimo'."""
        result = await tools.consultar_pronome_tratamento("Governador")
        assert "Excelentíssimo" not in result
        assert "Senhor Governador" in result

    @pytest.mark.asyncio
    async def test_partial_match(self) -> None:
        result = await tools.consultar_pronome_tratamento("Senador da República")
        assert "Vossa Excelência" in result
        assert "similar a" in result

    @pytest.mark.asyncio
    async def test_default_senhoria(self) -> None:
        result = await tools.consultar_pronome_tratamento("Analista")
        assert "Vossa Senhoria" in result

    @pytest.mark.asyncio
    async def test_reitor(self) -> None:
        result = await tools.consultar_pronome_tratamento("Reitor")
        assert "Magnificência" in result


class TestValidarDocumento:
    @pytest.mark.asyncio
    async def test_valid_document(self) -> None:
        texto = (
            "OFÍCIO Nº 1/2026/GAB\n\n"
            "Brasília, 22 de março de 2026.\n\n"
            "Senhor Diretor,\n\n"
            "Informo que o processo foi concluído.\n\n"
            "Atenciosamente,\n\n"
            "Fulano de Tal"
        )
        result = await tools.validar_documento(texto, "oficio")
        assert "Nenhum problema" in result

    @pytest.mark.asyncio
    async def test_missing_date(self) -> None:
        texto = "Senhor Diretor,\n\nInformo.\n\nAtenciosamente,"
        result = await tools.validar_documento(texto, "oficio")
        assert "Sem data" in result

    @pytest.mark.asyncio
    async def test_missing_fecho(self) -> None:
        texto = "Brasília, 22 de março de 2026.\n\nInformo."
        result = await tools.validar_documento(texto, "oficio")
        assert "Sem fecho" in result

    @pytest.mark.asyncio
    async def test_portaria_no_fecho_required(self) -> None:
        texto = "PORTARIA Nº 1/2026\n\n22 de março de 2026.\n\nRESOLVE:"
        result = await tools.validar_documento(texto, "portaria")
        assert "Sem fecho" not in result

    @pytest.mark.asyncio
    async def test_abolished_terms_detected(self) -> None:
        """3ª edição: Digníssimo e Ilustríssimo abolidos."""
        texto = "Brasília, 22 de março de 2026.\n\nIlustríssimo Senhor Diretor,\n\nAtenciosamente,"
        result = await tools.validar_documento(texto, "oficio")
        assert "abolido" in result.lower()

    @pytest.mark.asyncio
    async def test_expressions_to_avoid(self) -> None:
        """3ª edição: evitar expressões como 'Tenho a honra'."""
        texto = "Brasília, 22 de março de 2026.\n\nTenho a honra de informar.\n\nAtenciosamente,"
        result = await tools.validar_documento(texto, "oficio")
        assert "tenho a honra" in result.lower()

    @pytest.mark.asyncio
    async def test_excessive_gerundio(self) -> None:
        texto = (
            "Brasília, 22 de março de 2026.\n\n"
            "Considerando estando tendo fazendo gerando produzindo\n\n"
            "Atenciosamente,"
        )
        result = await tools.validar_documento(texto, "oficio")
        assert "gerúndios" in result


class TestListarTiposDocumento:
    @pytest.mark.asyncio
    async def test_lists_all_types(self) -> None:
        result = await tools.listar_tipos_documento()
        assert "oficio" in result
        assert "despacho" in result
        assert "portaria" in result
        assert "parecer" in result
        assert "nota_tecnica" in result
        assert "ata" in result

    @pytest.mark.asyncio
    async def test_notes_memorando_abolished(self) -> None:
        """3ª edição: menciona que memorando e aviso foram abolidos."""
        result = await tools.listar_tipos_documento()
        assert "abolidos" in result.lower()
