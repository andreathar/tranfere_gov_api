"""Tests for the TCE-RJ HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.tce_rj import client
from mcp_brasil.data.tce_rj.constants import (
    COMPRAS_DIRETAS_ESTADO_URL,
    COMPRAS_DIRETAS_MUNICIPIO_URL,
    CONCESSOES_PUBLICAS_URL,
    CONTRATOS_MUNICIPIO_URL,
    LICITACOES_URL,
    OBRAS_PARALISADAS_URL,
    PENALIDADES_MUNICIPIO_URL,
    PRESTACAO_CONTAS_MUNICIPIO_URL,
)

# ---------------------------------------------------------------------------
# buscar_licitacoes
# ---------------------------------------------------------------------------


class TestBuscarLicitacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_licitacoes(self) -> None:
        respx.get(LICITACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "Licitacoes": [
                        {
                            "Ente": "NITEROI",
                            "Unidade": "Prefeitura",
                            "Ano": 2024,
                            "Modalidade": "Pregão Eletrônico",
                            "ProcessoLicitatorio": "001/2024",
                            "NumeroEdital": "PE-001/2024",
                            "Objeto": "Aquisição de material de escritório",
                            "ValorEstimado": 150000.0,
                            "DataHomologacao": "2024-03-15",
                        }
                    ],
                    "Count": 1,
                },
            )
        )
        result = await client.buscar_licitacoes(ano=2024, municipio="NITEROI")
        assert result.total == 1
        assert len(result.licitacoes) == 1
        assert result.licitacoes[0].ente == "NITEROI"
        assert result.licitacoes[0].valor_estimado == 150000.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_list_response(self) -> None:
        respx.get(LICITACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"Ente": "NITEROI", "Objeto": "Serviço de limpeza"},
                ],
            )
        )
        result = await client.buscar_licitacoes()
        assert result.total == 1
        assert result.licitacoes[0].objeto == "Serviço de limpeza"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(LICITACOES_URL).mock(
            return_value=httpx.Response(200, json={"Licitacoes": [], "Count": 0})
        )
        result = await client.buscar_licitacoes()
        assert result.licitacoes == []
        assert result.total == 0


# ---------------------------------------------------------------------------
# buscar_contratos_municipio
# ---------------------------------------------------------------------------


class TestBuscarContratosMunicipio:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contratos(self) -> None:
        respx.get(CONTRATOS_MUNICIPIO_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "Contratos": [
                        {
                            "Ente": "NITEROI",
                            "NumeroContrato": "CT-001/2024",
                            "AnoContrato": 2024,
                            "Contratado": "EMPRESA X LTDA",
                            "Objeto": "Manutenção predial",
                            "TipoContrato": "Serviço",
                            "ValorContrato": 500000.0,
                        }
                    ],
                    "Count": 1,
                },
            )
        )
        result = await client.buscar_contratos_municipio(municipio="NITEROI")
        assert result.total == 1
        assert result.contratos[0].contratado == "EMPRESA X LTDA"
        assert result.contratos[0].valor_contrato == 500000.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(CONTRATOS_MUNICIPIO_URL).mock(
            return_value=httpx.Response(200, json={"Contratos": [], "Count": 0})
        )
        result = await client.buscar_contratos_municipio()
        assert result.contratos == []


# ---------------------------------------------------------------------------
# buscar_compras_diretas_municipio
# ---------------------------------------------------------------------------


class TestBuscarComprasDiretasMunicipio:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_compras(self) -> None:
        respx.get(COMPRAS_DIRETAS_MUNICIPIO_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "Compras": [
                        {
                            "Processo": "DL-001/2024",
                            "AnoProcesso": "2024",
                            "Municipio": "NITEROI",
                            "Objeto": "Compra emergencial de medicamentos",
                            "EnquadramentoLegal": "Art. 24, IV",
                            "Fornecedor": "FARMACIA Y LTDA",
                            "ValorTotalCompra": 25000.0,
                        }
                    ],
                },
            )
        )
        result = await client.buscar_compras_diretas_municipio(ano=2024)
        assert len(result) == 1
        assert result[0].fornecedor_vencedor == "FARMACIA Y LTDA"
        assert result[0].valor_processo == 25000.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_list_response(self) -> None:
        respx.get(COMPRAS_DIRETAS_MUNICIPIO_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_compras_diretas_municipio()
        assert result == []


# ---------------------------------------------------------------------------
# buscar_compras_diretas_estado
# ---------------------------------------------------------------------------


class TestBuscarComprasDiretasEstado:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_compras_estado(self) -> None:
        respx.get(COMPRAS_DIRETAS_ESTADO_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "Processo": "EST-001/2024",
                        "Unidade": "SEEDUC",
                        "Objeto": "Material didático",
                        "Afastamento": "Dispensa de licitação",
                        "FornecedorVencedor": "EDITORA Z",
                        "ValorProcesso": 80000.0,
                    }
                ],
            )
        )
        result = await client.buscar_compras_diretas_estado()
        assert len(result) == 1
        assert result[0].fornecedor_vencedor == "EDITORA Z"
        assert result[0].unidade == "SEEDUC"


# ---------------------------------------------------------------------------
# buscar_obras_paralisadas
# ---------------------------------------------------------------------------


class TestBuscarObrasParalisadas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_obras(self) -> None:
        respx.get(OBRAS_PARALISADAS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "Ente": "NITEROI",
                        "TipoEnte": "Municipal",
                        "Nome": "Construção de escola",
                        "FuncaoGoverno": "Educação",
                        "NomeContratada": "CONSTRUTORA ABC LTDA",
                        "ValorTotalContrato": 2000000.0,
                        "TempoParalizacao": "18 meses",
                        "MotivoParalisacao": "Abandono pela contratada",
                        "StatusContrato": "Paralisado",
                    }
                ],
            )
        )
        result = await client.buscar_obras_paralisadas()
        assert len(result) == 1
        assert result[0].nome_contratada == "CONSTRUTORA ABC LTDA"
        assert result[0].valor_total_contrato == 2000000.0
        assert result[0].tempo_paralisacao == "18 meses"

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_dict_response(self) -> None:
        respx.get(OBRAS_PARALISADAS_URL).mock(return_value=httpx.Response(200, json={"Obras": []}))
        result = await client.buscar_obras_paralisadas()
        assert result == []


# ---------------------------------------------------------------------------
# buscar_penalidades
# ---------------------------------------------------------------------------


class TestBuscarPenalidades:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_penalidades(self) -> None:
        respx.get(PENALIDADES_MUNICIPIO_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "Processo": "TC-001/2023",
                        "AnoCondenacao": 2023,
                        "ValorPenalidade": 50000.0,
                        "Condenacao": "Multa",
                        "Ente": "NITEROI",
                        "NomeOrgao": "Prefeitura Municipal",
                        "GrupoNatureza": "Irregularidade grave",
                    }
                ],
            )
        )
        result = await client.buscar_penalidades(tipo="multa")
        assert len(result) == 1
        assert result[0].valor_penalidade == 50000.0
        assert result[0].condenacao == "Multa"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PENALIDADES_MUNICIPIO_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_penalidades()
        assert result == []


# ---------------------------------------------------------------------------
# buscar_prestacao_contas
# ---------------------------------------------------------------------------


class TestBuscarPrestacaoContas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contas(self) -> None:
        respx.get(PRESTACAO_CONTAS_MUNICIPIO_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "Municipio": "NITEROI",
                        "Regiao": "Metropolitana",
                        "Ano": 2023,
                        "Indicador": "Favorável",
                        "Processo": "PC-001/2024",
                        "Responsavel": "João da Silva",
                    }
                ],
            )
        )
        result = await client.buscar_prestacao_contas()
        assert len(result) == 1
        assert result[0].municipio == "NITEROI"
        assert result[0].indicador == "Favorável"


# ---------------------------------------------------------------------------
# buscar_concessoes
# ---------------------------------------------------------------------------


class TestBuscarConcessoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_concessoes(self) -> None:
        respx.get(CONCESSOES_PUBLICAS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "Municipio": "NITEROI",
                        "Concessoes": [
                            {
                                "Ente": "NITEROI",
                                "Numero": "CON-001/2020",
                                "Objeto": "Transporte coletivo",
                                "NomeRazaoSocial": "TRANSPORTE X S.A.",
                                "Natureza": "Concessão comum",
                                "SituacaoConcessao": "Vigente",
                                "ValorTotalOutorga": 10000000.0,
                            }
                        ],
                    }
                ],
            )
        )
        result = await client.buscar_concessoes()
        assert len(result) == 1
        assert result[0].municipio == "NITEROI"
        assert len(result[0].concessoes) == 1
        assert result[0].concessoes[0].nome_razao_social == "TRANSPORTE X S.A."

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_concessoes(self) -> None:
        respx.get(CONCESSOES_PUBLICAS_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_concessoes()
        assert result == []
