"""Tests for the TCE-RN HTTP client."""

import pytest
import respx
from httpx import Response

from mcp_brasil.data.tce_rn import client
from mcp_brasil.data.tce_rn.constants import (
    CONTRATOS_PATH,
    DESPESA_PATH,
    JURISDICIONADOS_PATH,
    LICITACOES_PATH,
    RECEITA_PATH,
)


class TestListarJurisdicionados:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_jurisdicionados(self) -> None:
        respx.get(JURISDICIONADOS_PATH).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "identificadorUnidade": 1,
                        "codigoOrgao": "PMNATAL",
                        "nomeOrgao": "PREFEITURA MUNICIPAL DE NATAL",
                        "cnpj": "08241747000143",
                    },
                ],
            )
        )
        result = await client.listar_jurisdicionados()
        assert len(result) == 1
        assert result[0].nome_orgao == "PREFEITURA MUNICIPAL DE NATAL"
        assert result[0].identificador_unidade == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(JURISDICIONADOS_PATH).mock(return_value=Response(200, json=[]))
        result = await client.listar_jurisdicionados()
        assert result == []


class TestBuscarDespesas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_despesas(self) -> None:
        url = f"{DESPESA_PATH}/2024/6/1"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "descricaoCategoriaEconomica": "Despesas correntes",
                        "descricaoGrupoDespesa": "Pessoal",
                        "descricaoElementoDespesa": "Vencimentos e Salários",
                        "valorDotacaoInicial": 1000000.0,
                        "valorDotacaoAtualizada": 1100000.0,
                        "valorEmpenhoAtePeriodo": 900000.0,
                        "valorLiquidacaoAtePeriodo": 850000.0,
                        "valorPagoAtePeriodo": 800000.0,
                    }
                ],
            )
        )
        result = await client.buscar_despesas(ano=2024, bimestre=6, id_unidade=1)
        assert len(result) == 1
        assert result[0].descricao_elemento_despesa == "Vencimentos e Salários"
        assert result[0].valor_pago_ate_periodo == 800000.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        url = f"{DESPESA_PATH}/2024/1/999"
        respx.get(url).mock(return_value=Response(200, json=[]))
        result = await client.buscar_despesas(ano=2024, bimestre=1, id_unidade=999)
        assert result == []


class TestBuscarReceitas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_receitas(self) -> None:
        url = f"{RECEITA_PATH}/2024/6/1"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "descricaoReceita": "Impostos sobre o Patrimônio",
                        "codNaturezaReceita": "1.1.1.2",
                        "valorPrevistoInicial": 500000.0,
                        "valorPrevistoAtualizado": 520000.0,
                        "valorRealizadoNoExecicio": 480000.0,
                    }
                ],
            )
        )
        result = await client.buscar_receitas(ano=2024, bimestre=6, id_unidade=1)
        assert len(result) == 1
        assert result[0].descricao_receita == "Impostos sobre o Patrimônio"
        assert result[0].valor_realizado_no_exercicio == 480000.0


class TestBuscarLicitacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_licitacoes(self) -> None:
        url = f"{LICITACOES_PATH}/1/2024-01-01/2024-12-31"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "numeroLicitacao": "001",
                        "anoLicitacao": "2024",
                        "modalidade": "Pregao Eletronico",
                        "tipoObjeto": "Compra - Material",
                        "descricaoObjeto": "Material de escritório",
                        "valorTotalOrcado": 50000.0,
                        "situacaoProcedimentoLicitacao": "HOMOLOGADA",
                        "nomeJurisdicionado": "PREFEITURA DE NATAL",
                    }
                ],
            )
        )
        result = await client.buscar_licitacoes(
            id_unidade=1, data_inicio="2024-01-01", data_fim="2024-12-31"
        )
        assert len(result) == 1
        assert result[0].modalidade == "Pregao Eletronico"
        assert result[0].valor_total_orcado == 50000.0
        assert result[0].situacao == "HOMOLOGADA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        url = f"{LICITACOES_PATH}/999/2024-01-01/2024-01-31"
        respx.get(url).mock(return_value=Response(200, json=[]))
        result = await client.buscar_licitacoes(
            id_unidade=999, data_inicio="2024-01-01", data_fim="2024-01-31"
        )
        assert result == []


class TestBuscarContratos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contratos(self) -> None:
        url = f"{CONTRATOS_PATH}/1/false"
        respx.get(url).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "numeroContrato": "CT-001",
                        "anoContrato": 2024,
                        "objetoContrato": "Fornecimento de material",
                        "valorContrato": 150000.0,
                        "nomeContratado": "EMPRESA XYZ LTDA",
                        "cpfcnpjContratado": "12345678000199",
                        "dataInicioVigencia": "2024-01-15",
                        "dataTerminoVigencia": "2025-01-15",
                    }
                ],
            )
        )
        result = await client.buscar_contratos(id_unidade=1)
        assert len(result) == 1
        assert result[0].numero_contrato == "CT-001"
        assert result[0].valor_contrato == 150000.0
        assert result[0].nome_contratado == "EMPRESA XYZ LTDA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_with_hierarquia(self) -> None:
        url = f"{CONTRATOS_PATH}/1/true"
        respx.get(url).mock(return_value=Response(200, json=[]))
        result = await client.buscar_contratos(id_unidade=1, considerar_hierarquia=True)
        assert result == []
