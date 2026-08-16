"""Tests for the Contratos.gov.br tool functions."""

from unittest.mock import AsyncMock

import pytest

from mcp_brasil.data.compras.contratosgovbr import tools
from mcp_brasil.data.compras.contratosgovbr.schemas import (
    ContratoResumo,
    Empenho,
    Fatura,
    HistoricoContrato,
    ItemContrato,
    Terceirizado,
)


def _make_ctx() -> AsyncMock:
    ctx = AsyncMock()
    ctx.info = AsyncMock()
    ctx.report_progress = AsyncMock()
    return ctx


SAMPLE_CONTRATO = ContratoResumo(
    id=12345,
    numero="001/2023",
    orgao_codigo="26000",
    orgao_nome="Ministério da Educação",
    unidade_codigo="110161",
    unidade_nome="Coordenação-Geral de Logística",
    fornecedor_nome="Empresa XYZ Ltda",
    fornecedor_cnpj_cpf="12345678000199",
    tipo="Contrato",
    categoria="Serviço",
    objeto="Prestação de serviços de limpeza",
    modalidade="Pregão Eletrônico",
    valor_global="1.200.000,00",
    vigencia_inicio="2023-02-01",
    vigencia_fim="2024-01-31",
    situacao="Ativo",
)


class TestListarContratosUnidade:
    @pytest.mark.asyncio
    async def test_returns_formatted_contratos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_contratos_ug",
            AsyncMock(return_value=[SAMPLE_CONTRATO]),
        )
        result = await tools.listar_contratos_unidade(110161, _make_ctx())
        assert "1 contratos ativos" in result
        assert "Empresa XYZ Ltda" in result
        assert "1.200.000,00" in result
        assert "Ativo" in result

    @pytest.mark.asyncio
    async def test_empty_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_contratos_ug",
            AsyncMock(return_value=[]),
        )
        result = await tools.listar_contratos_unidade(999999, _make_ctx())
        assert "Nenhum contrato" in result


class TestConsultarContratoId:
    @pytest.mark.asyncio
    async def test_returns_formatted_contrato(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.consultar_contrato",
            AsyncMock(return_value=SAMPLE_CONTRATO),
        )
        result = await tools.consultar_contrato_id(12345, _make_ctx())
        assert "Ministério da Educação" in result
        assert "Empresa XYZ Ltda" in result
        assert "Pregão Eletrônico" in result

    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.consultar_contrato",
            AsyncMock(return_value=None),
        )
        result = await tools.consultar_contrato_id(999, _make_ctx())
        assert "não encontrado" in result


class TestConsultarEmpenhosContrato:
    @pytest.mark.asyncio
    async def test_returns_formatted_empenhos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        empenho = Empenho(
            id=1,
            numero="2023NE000123",
            credor="Empresa XYZ",
            empenhado="100.000,00",
            liquidado="50.000,00",
            pago="50.000,00",
        )
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_empenhos",
            AsyncMock(return_value=[empenho]),
        )
        result = await tools.consultar_empenhos_contrato(12345, _make_ctx())
        assert "2023NE000123" in result
        assert "100.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_empenhos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_empenhos",
            AsyncMock(return_value=[]),
        )
        result = await tools.consultar_empenhos_contrato(999, _make_ctx())
        assert "Nenhum empenho" in result


class TestConsultarFaturasContrato:
    @pytest.mark.asyncio
    async def test_returns_formatted_faturas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fatura = Fatura(
            id=1,
            numero="NF-001",
            emissao="2023-03-01",
            valor="100.000,00",
            valorliquido="95.000,00",
            situacao="Paga",
        )
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_faturas",
            AsyncMock(return_value=[fatura]),
        )
        result = await tools.consultar_faturas_contrato(12345, _make_ctx())
        assert "NF-001" in result
        assert "Paga" in result


class TestConsultarHistoricoContrato:
    @pytest.mark.asyncio
    async def test_returns_formatted_historico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hist = HistoricoContrato(
            id=1,
            tipo="Termo Aditivo",
            numero="01/2023",
            valor_global="1.500.000,00",
            situacao_contrato="Ativo",
        )
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_historico",
            AsyncMock(return_value=[hist]),
        )
        result = await tools.consultar_historico_contrato(12345, _make_ctx())
        assert "Termo Aditivo" in result
        assert "1.500.000,00" in result


class TestConsultarItensContrato:
    @pytest.mark.asyncio
    async def test_returns_formatted_itens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        item = ItemContrato(
            tipo_item="Serviço",
            codigo_item="SRV001",
            descricao_item="Limpeza predial",
            unidade="m2",
            quantidade="500",
            valor_unitario="25,00",
            valor_total="12.500,00",
        )
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_itens",
            AsyncMock(return_value=[item]),
        )
        result = await tools.consultar_itens_contrato(12345, _make_ctx())
        assert "Limpeza predial" in result
        assert "12.500,00" in result


class TestConsultarTerceirizadosContrato:
    @pytest.mark.asyncio
    async def test_returns_formatted_terceirizados(self, monkeypatch: pytest.MonkeyPatch) -> None:
        terc = Terceirizado(
            id=1,
            funcao="Auxiliar de limpeza",
            jornada="44h",
            salario="1.500,00",
            custo="3.200,00",
            situacao="Ativo",
        )
        monkeypatch.setattr(
            "mcp_brasil.data.compras.contratosgovbr.tools.client.listar_terceirizados",
            AsyncMock(return_value=[terc]),
        )
        result = await tools.consultar_terceirizados_contrato(12345, _make_ctx())
        assert "Auxiliar de limpeza" in result
        assert "3.200,00" in result
