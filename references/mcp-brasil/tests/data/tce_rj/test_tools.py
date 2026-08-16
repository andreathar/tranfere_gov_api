"""Tests for the TCE-RJ tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tce_rj import tools
from mcp_brasil.data.tce_rj.schemas import (
    CompraDireta,
    Concessao,
    ConcessaoMunicipio,
    ContratoMunicipio,
    ContratoMunicipioResultado,
    Licitacao,
    LicitacaoResultado,
    ObraParalisada,
    Penalidade,
    PrestacaoContas,
)

CLIENT_MODULE = "mcp_brasil.data.tce_rj.client"


def _mock_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_licitacoes
# ---------------------------------------------------------------------------


class TestBuscarLicitacoes:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = LicitacaoResultado(
            licitacoes=[
                Licitacao(
                    ente="NITEROI",
                    modalidade="Pregão Eletrônico",
                    numero_edital="PE-001/2024",
                    objeto="Material de escritório",
                    valor_estimado=150000.0,
                    data_homologacao="2024-03-15",
                ),
            ],
            total=1,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes(ctx)
        assert "PE-001/2024" in result
        assert "NITEROI" in result
        assert "Material de escritório" in result
        assert "R$ 150.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = LicitacaoResultado(licitacoes=[], total=0)
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_licitacoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_licitacoes(ctx)
        assert "Nenhuma licitação encontrada" in result


# ---------------------------------------------------------------------------
# buscar_contratos_municipio
# ---------------------------------------------------------------------------


class TestBuscarContratosMunicipio:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = ContratoMunicipioResultado(
            contratos=[
                ContratoMunicipio(
                    ente="NITEROI",
                    numero_contrato="CT-001/2024",
                    ano_contrato=2024,
                    contratado="EMPRESA X LTDA",
                    objeto="Manutenção predial",
                    tipo_contrato="Serviço",
                    valor_contrato=500000.0,
                ),
            ],
            total=1,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos_municipio",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_municipio(ctx)
        assert "CT-001/2024" in result
        assert "EMPRESA X LTDA" in result
        assert "R$ 500.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = ContratoMunicipioResultado(contratos=[], total=0)
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_contratos_municipio",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_contratos_municipio(ctx)
        assert "Nenhum contrato municipal encontrado" in result


# ---------------------------------------------------------------------------
# buscar_compras_diretas
# ---------------------------------------------------------------------------


class TestBuscarComprasDiretas:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            CompraDireta(
                processo="DL-001/2024",
                unidade="Prefeitura de Niterói",
                objeto="Compra emergencial de medicamentos",
                fornecedor_vencedor="FARMACIA Y LTDA",
                valor_processo=25000.0,
                afastamento="Art. 24, IV",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_compras_diretas_municipio",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_compras_diretas(ctx)
        assert "DL-001/2024" in result
        assert "FARMACIA Y LTDA" in result
        assert "R$ 25.000,00" in result
        assert "Art. 24, IV" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_compras_diretas_municipio",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_compras_diretas(ctx)
        assert "Nenhuma compra direta encontrada" in result


# ---------------------------------------------------------------------------
# buscar_obras_paralisadas
# ---------------------------------------------------------------------------


class TestBuscarObrasParalisadas:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            ObraParalisada(
                ente="NITEROI",
                tipo_ente="Municipal",
                nome="Construção de escola",
                funcao_governo="Educação",
                nome_contratada="CONSTRUTORA ABC LTDA",
                valor_total_contrato=2000000.0,
                tempo_paralisacao="18 meses",
                motivo_paralisacao="Abandono pela contratada",
                status_contrato="Paralisado",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_obras_paralisadas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_obras_paralisadas(ctx)
        assert "Construção de escola" in result
        assert "CONSTRUTORA ABC LTDA" in result
        assert "R$ 2.000.000,00" in result
        assert "18 meses" in result
        assert "Abandono" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_obras_paralisadas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_obras_paralisadas(ctx)
        assert "Nenhuma obra paralisada encontrada" in result


# ---------------------------------------------------------------------------
# buscar_penalidades
# ---------------------------------------------------------------------------


class TestBuscarPenalidades:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            Penalidade(
                processo="TC-001/2023",
                ano_condenacao=2023,
                valor_penalidade=50000.0,
                condenacao="Multa",
                ente="NITEROI",
                nome_orgao="Prefeitura Municipal",
                grupo_natureza="Irregularidade grave",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_penalidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_penalidades(ctx)
        assert "Multa" in result
        assert "NITEROI" in result
        assert "R$ 50.000,00" in result
        assert "TC-001/2023" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_penalidades",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_penalidades(ctx)
        assert "Nenhuma penalidade encontrada" in result


# ---------------------------------------------------------------------------
# buscar_prestacao_contas
# ---------------------------------------------------------------------------


class TestBuscarPrestacaoContas:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            PrestacaoContas(
                municipio="NITEROI",
                regiao="Metropolitana",
                ano=2023,
                indicador="Favorável",
                responsavel="João da Silva",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_prestacao_contas",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_prestacao_contas(ctx)
        assert "NITEROI" in result
        assert "2023" in result
        assert "Favorável" in result
        assert "João da Silva" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_prestacao_contas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_prestacao_contas(ctx)
        assert "Nenhuma prestação de contas encontrada" in result


# ---------------------------------------------------------------------------
# buscar_concessoes
# ---------------------------------------------------------------------------


class TestBuscarConcessoes:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = [
            ConcessaoMunicipio(
                municipio="NITEROI",
                concessoes=[
                    Concessao(
                        numero="CON-001/2020",
                        objeto="Transporte coletivo",
                        nome_razao_social="TRANSPORTE X S.A.",
                        natureza="Concessão comum",
                        situacao_concessao="Vigente",
                        valor_total_outorga=10000000.0,
                    ),
                ],
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_concessoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_concessoes(ctx)
        assert "CON-001/2020" in result
        assert "NITEROI" in result
        assert "TRANSPORTE X S.A." in result
        assert "R$ 10.000.000,00" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_concessoes",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_concessoes(ctx)
        assert "Nenhuma concessão encontrada" in result

    @pytest.mark.asyncio
    async def test_filters_by_municipio(self) -> None:
        mock_data = [
            ConcessaoMunicipio(
                municipio="NITEROI",
                concessoes=[Concessao(objeto="Transporte")],
            ),
            ConcessaoMunicipio(
                municipio="RIO DE JANEIRO",
                concessoes=[Concessao(objeto="Iluminação")],
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_concessoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_concessoes(ctx, municipio="NITEROI")
        assert "NITEROI" in result
        assert "Iluminação" not in result
