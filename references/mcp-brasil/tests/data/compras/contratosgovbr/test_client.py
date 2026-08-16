"""Tests for the Contratos.gov.br HTTP client."""

import httpx
import pytest
import respx

from mcp_brasil.data.compras.contratosgovbr import client
from mcp_brasil.data.compras.contratosgovbr.constants import (
    CONTRATO_POR_ID_URL,
    CONTRATO_POR_UG_URL,
    CONTRATO_SUBRESOURCE_URL,
    ORGAOS_URL,
    UNIDADES_URL,
)

SAMPLE_CONTRATO = {
    "id": 12345,
    "receita_despesa": "D",
    "numero": "001/2023",
    "orgao_codigo": "26000",
    "orgao_nome": "Ministério da Educação",
    "unidade_codigo": "110161",
    "unidade_nome": "Coordenação-Geral de Logística",
    "fornecedor_tipo": "CNPJ",
    "fonecedor_cnpj_cpf_idgener": "12345678000199",
    "fornecedor_nome": "Empresa XYZ Ltda",
    "tipo": "Contrato",
    "categoria": "Serviço",
    "processo": "00001.000001/2023-01",
    "objeto": "Prestação de serviços de limpeza",
    "fundamento_legal": "Lei 14.133/2021",
    "modalidade": "Pregão Eletrônico",
    "data_assinatura": "2023-01-15",
    "data_publicacao": "2023-01-16",
    "vigencia_inicio": "2023-02-01",
    "vigencia_fim": "2024-01-31",
    "valor_inicial": "1.200.000,00",
    "valor_global": "1.200.000,00",
    "valor_parcela": "100.000,00",
    "valor_acumulado": "600.000,00",
    "situacao": "Ativo",
}

# Nested format (from /api/contrato/ug/{id})
SAMPLE_CONTRATO_NESTED = {
    "id": 12345,
    "receita_despesa": "D",
    "numero": "001/2023",
    "contratante": {
        "orgao": {
            "codigo": "26000",
            "nome": "Ministério da Educação",
            "unidade_gestora": {
                "codigo": "110161",
                "nome": "Coordenação-Geral de Logística",
            },
        }
    },
    "fornecedor": {
        "tipo": "CNPJ",
        "cnpj_cpf_idgener": "12345678000199",
        "nome": "Empresa XYZ Ltda",
    },
    "tipo": "Contrato",
    "categoria": "Serviço",
    "processo": "00001.000001/2023-01",
    "objeto": "Prestação de serviços de limpeza",
    "modalidade": "Pregão Eletrônico",
    "data_assinatura": "2023-01-15",
    "vigencia_inicio": "2023-02-01",
    "vigencia_fim": "2024-01-31",
    "valor_global": "1.200.000,00",
    "situacao": "Ativo",
}


class TestListarOrgaos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_orgaos(self) -> None:
        respx.get(ORGAOS_URL).mock(
            return_value=httpx.Response(200, json=[{"codigo": "26000"}, {"codigo": "30000"}])
        )
        result = await client.listar_orgaos()
        assert len(result) == 2
        assert result[0]["codigo"] == "26000"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_orgaos(self) -> None:
        respx.get(ORGAOS_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.listar_orgaos()
        assert result == []


class TestListarUnidades:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_unidades(self) -> None:
        respx.get(UNIDADES_URL).mock(return_value=httpx.Response(200, json=[{"codigo": "110161"}]))
        result = await client.listar_unidades()
        assert len(result) == 1


class TestListarContratosUg:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contratos_nested_format(self) -> None:
        """UG listing returns nested contratante/fornecedor dicts."""
        respx.get(f"{CONTRATO_POR_UG_URL}/110161").mock(
            return_value=httpx.Response(200, json=[SAMPLE_CONTRATO_NESTED])
        )
        result = await client.listar_contratos_ug(110161)
        assert len(result) == 1
        c = result[0]
        assert c.id == 12345
        assert c.numero == "001/2023"
        assert c.orgao_nome == "Ministério da Educação"
        assert c.orgao_codigo == "26000"
        assert c.unidade_codigo == "110161"
        assert c.fornecedor_nome == "Empresa XYZ Ltda"
        assert c.fornecedor_cnpj_cpf == "12345678000199"
        assert c.objeto == "Prestação de serviços de limpeza"
        assert c.situacao == "Ativo"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_ug(self) -> None:
        respx.get(f"{CONTRATO_POR_UG_URL}/999999").mock(return_value=httpx.Response(200, json=[]))
        result = await client.listar_contratos_ug(999999)
        assert result == []


class TestConsultarContrato:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_contrato_from_list(self) -> None:
        """API /id/{id} returns a list; we take first item."""
        respx.get(f"{CONTRATO_POR_ID_URL}/12345").mock(
            return_value=httpx.Response(200, json=[SAMPLE_CONTRATO])
        )
        result = await client.consultar_contrato(12345)
        assert result is not None
        assert result.id == 12345
        assert result.orgao_nome == "Ministério da Educação"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_list(self) -> None:
        respx.get(f"{CONTRATO_POR_ID_URL}/999").mock(return_value=httpx.Response(200, json=[]))
        result = await client.consultar_contrato(999)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_dict(self) -> None:
        respx.get(f"{CONTRATO_POR_ID_URL}/999").mock(
            return_value=httpx.Response(200, json={"error": "Não encontrado"})
        )
        result = await client.consultar_contrato(999)
        assert result is None


class TestListarEmpenhos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_empenhos(self) -> None:
        respx.get(f"{CONTRATO_SUBRESOURCE_URL}/12345/empenhos").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "numero": "2023NE000123",
                        "credor": "Empresa XYZ",
                        "empenhado": "100.000,00",
                        "liquidado": "50.000,00",
                        "pago": "50.000,00",
                    }
                ],
            )
        )
        result = await client.listar_empenhos(12345)
        assert len(result) == 1
        assert result[0].numero == "2023NE000123"
        assert result[0].empenhado == "100.000,00"


class TestListarFaturas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_faturas(self) -> None:
        respx.get(f"{CONTRATO_SUBRESOURCE_URL}/12345/faturas").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "numero": "NF-001",
                        "emissao": "2023-03-01",
                        "vencimento": "2023-04-01",
                        "valor": "100.000,00",
                        "valorliquido": "95.000,00",
                        "situacao": "Paga",
                    }
                ],
            )
        )
        result = await client.listar_faturas(12345)
        assert len(result) == 1
        assert result[0].numero == "NF-001"
        assert result[0].situacao == "Paga"


class TestListarHistorico:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_historico(self) -> None:
        respx.get(f"{CONTRATO_SUBRESOURCE_URL}/12345/historico").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "tipo": "Termo Aditivo",
                        "numero": "01/2023",
                        "fornecedor": "Empresa XYZ",
                        "data_assinatura": "2023-12-15",
                        "vigencia_fim": "2025-01-31",
                        "valor_global": "1.500.000,00",
                        "situacao_contrato": "Ativo",
                    }
                ],
            )
        )
        result = await client.listar_historico(12345)
        assert len(result) == 1
        assert result[0].tipo == "Termo Aditivo"


class TestListarItens:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_itens(self) -> None:
        respx.get(f"{CONTRATO_SUBRESOURCE_URL}/12345/itens").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "tipo_item": "Serviço",
                        "codigo_item": "SRV001",
                        "descricao_item": "Limpeza predial",
                        "unidade": "m²",
                        "quantidade": "500",
                        "valor_unitario": "25,00",
                        "valor_total": "12.500,00",
                    }
                ],
            )
        )
        result = await client.listar_itens(12345)
        assert len(result) == 1
        assert result[0].descricao_item == "Limpeza predial"


class TestListarTerceirizados:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_terceirizados(self) -> None:
        respx.get(f"{CONTRATO_SUBRESOURCE_URL}/12345/terceirizados").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "funcao": "Auxiliar de limpeza",
                        "jornada": "44h",
                        "salario": "1.500,00",
                        "custo": "3.200,00",
                        "escolaridade": "Ensino Fundamental",
                        "situacao": "Ativo",
                    }
                ],
            )
        )
        result = await client.listar_terceirizados(12345)
        assert len(result) == 1
        assert result[0].funcao == "Auxiliar de limpeza"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_terceirizados(self) -> None:
        respx.get(f"{CONTRATO_SUBRESOURCE_URL}/12345/terceirizados").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await client.listar_terceirizados(12345)
        assert result == []
