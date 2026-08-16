"""Tests for the TCE-CE HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.tce_ce import client
from mcp_brasil.data.tce_ce.constants import (
    CONTRATOS_URL,
    EMPENHOS_URL,
    LICITACOES_URL,
    MUNICIPIOS_URL,
)

# ---------------------------------------------------------------------------
# listar_municipios
# ---------------------------------------------------------------------------


class TestListarMunicipios:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_municipios(self) -> None:
        respx.get(MUNICIPIOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"codigo_municipio": "057", "nome_municipio": "FORTALEZA"},
                        {"codigo_municipio": "150", "nome_municipio": "SOBRAL"},
                    ]
                },
            )
        )
        result = await client.listar_municipios()
        assert len(result) == 2
        assert result[0].codigo_municipio == "057"
        assert result[0].nome_municipio == "FORTALEZA"
        assert result[1].codigo_municipio == "150"

    @pytest.mark.asyncio
    @respx.mock
    async def test_nested_data_response(self) -> None:
        """API sometimes wraps data in nested data.data."""
        respx.get(MUNICIPIOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "data": [
                            {"codigo_municipio": "057", "nome_municipio": "FORTALEZA"},
                        ]
                    }
                },
            )
        )
        result = await client.listar_municipios()
        assert len(result) == 1
        assert result[0].codigo_municipio == "057"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(MUNICIPIOS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        result = await client.listar_municipios()
        assert result == []


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
                    "data": [
                        {
                            "codigo_municipio": "057",
                            "numero_licitacao": "2024/001",
                            "data_realizacao_autuacao_licitacao": "2024-03-15",
                            "modalidade_licitacao": "Pregão Eletrônico",
                            "descricao1_objeto_licitacao": "Aquisição de ",
                            "descricao2_objeto_licitacao": "material escolar",
                            "valor_orcado_estimado": 150000.0,
                            "data_homologacao": "2024-04-01",
                            "nome_responsavel_homologacao": "João Silva",
                            "modalidade_processo_administrativo": "PAD 001",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_licitacoes(
            codigo_municipio="057",
            data_realizacao="2024-01-01_2024-12-31",
        )
        assert len(result) == 1
        lic = result[0]
        assert lic.numero_licitacao == "2024/001"
        assert lic.modalidade_licitacao == "Pregão Eletrônico"
        assert lic.objeto == "Aquisição de material escolar"
        assert lic.valor_orcado_estimado == 150000.0
        assert lic.data_homologacao == "2024-04-01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_concatenates_descriptions(self) -> None:
        respx.get(LICITACOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "codigo_municipio": "057",
                            "descricao1_objeto_licitacao": "Parte 1 ",
                            "descricao2_objeto_licitacao": "Parte 2",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_licitacoes(
            codigo_municipio="057", data_realizacao="2024-01-01"
        )
        assert result[0].objeto == "Parte 1 Parte 2"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(LICITACOES_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        result = await client.buscar_licitacoes(
            codigo_municipio="057", data_realizacao="2024-01-01"
        )
        assert result == []


# ---------------------------------------------------------------------------
# buscar_contratos
# ---------------------------------------------------------------------------


class TestBuscarContratos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_paginated_contratos(self) -> None:
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "total": 42,
                        "data": [
                            {
                                "codigo_municipio": "057",
                                "numero_contrato": "CT-2024/001",
                                "data_contrato": "2024-02-15",
                                "tipo_contrato": "Compras",
                                "modalidade_contrato": "Pregão",
                                "descricao_objeto_contrato": "Fornecimento de merenda",
                                "valor_total_contrato": 500000.0,
                                "data_inicio_vigencia_contrato": "2024-03-01",
                                "data_fim_vigencia_contrato": "2024-12-31",
                            }
                        ],
                    }
                },
            )
        )
        result = await client.buscar_contratos(
            codigo_municipio="057",
            data_contrato="2024-01-01_2024-12-31",
        )
        assert result.total == 42
        assert len(result.contratos) == 1
        c = result.contratos[0]
        assert c.numero_contrato == "CT-2024/001"
        assert c.valor_total_contrato == 500000.0
        assert c.data_fim_vigencia == "2024-12-31"

    @pytest.mark.asyncio
    @respx.mock
    async def test_flat_list_response(self) -> None:
        """When API returns a flat list instead of paginated object."""
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "codigo_municipio": "057",
                            "numero_contrato": "CT-2024/002",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_contratos(codigo_municipio="057", data_contrato="2024-01-01")
        assert result.total == 1
        assert result.contratos[0].numero_contrato == "CT-2024/002"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_paginated_response(self) -> None:
        respx.get(CONTRATOS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"total": 0, "data": []}})
        )
        result = await client.buscar_contratos(codigo_municipio="057", data_contrato="2024-01-01")
        assert result.total == 0
        assert result.contratos == []


# ---------------------------------------------------------------------------
# buscar_empenhos
# ---------------------------------------------------------------------------


class TestBuscarEmpenhos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_paginated_empenhos(self) -> None:
        respx.get(EMPENHOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "total": 100,
                        "data": [
                            {
                                "codigo_municipio": 57,
                                "numero_empenho": "2024NE000123",
                                "data_emissao_empenho": "2024-01-15",
                                "valor_empenho": 25000.0,
                                "nome_negociante": "EMPRESA ABC LTDA",
                                "numero_documento_negociante": "12345678000199",
                                "historico1_empenho": "Pagamento referente ",
                                "historico2_empenho": "ao contrato CT-001",
                                "codigo_orgao": "02",
                                "codigo_funcao": "12",
                            }
                        ],
                    }
                },
            )
        )
        result = await client.buscar_empenhos(
            codigo_municipio=57,
            data_referencia=202401,
            codigo_orgao="02",
        )
        assert result.total == 100
        assert len(result.empenhos) == 1
        e = result.empenhos[0]
        assert e.numero_empenho == "2024NE000123"
        assert e.valor_empenho == 25000.0
        assert e.nome_negociante == "EMPRESA ABC LTDA"
        assert e.historico == "Pagamento referente ao contrato CT-001"

    @pytest.mark.asyncio
    @respx.mock
    async def test_concatenates_historico(self) -> None:
        respx.get(EMPENHOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "total": 1,
                        "data": [
                            {
                                "codigo_municipio": 57,
                                "historico1_empenho": "Parte A ",
                                "historico2_empenho": "Parte B",
                            }
                        ],
                    }
                },
            )
        )
        result = await client.buscar_empenhos(
            codigo_municipio=57, data_referencia=202401, codigo_orgao="02"
        )
        assert result.empenhos[0].historico == "Parte A Parte B"

    @pytest.mark.asyncio
    @respx.mock
    async def test_flat_list_response(self) -> None:
        respx.get(EMPENHOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "codigo_municipio": 57,
                            "numero_empenho": "2024NE000456",
                        }
                    ]
                },
            )
        )
        result = await client.buscar_empenhos(
            codigo_municipio=57, data_referencia=202401, codigo_orgao="02"
        )
        assert result.total == 1
        assert result.empenhos[0].numero_empenho == "2024NE000456"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(EMPENHOS_URL).mock(
            return_value=httpx.Response(200, json={"data": {"total": 0, "data": []}})
        )
        result = await client.buscar_empenhos(
            codigo_municipio=57, data_referencia=202401, codigo_orgao="02"
        )
        assert result.total == 0
        assert result.empenhos == []
