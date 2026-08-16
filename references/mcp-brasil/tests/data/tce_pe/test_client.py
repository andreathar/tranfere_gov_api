"""Tests for the TCE-PE HTTP client."""

import json

import httpx
import pytest
import respx

from mcp_brasil.data.tce_pe import client
from mcp_brasil.data.tce_pe.constants import API_BASE, RESPONSE_ENCODING


def _mock_response(entity: str, items: list[dict], status: str = "OK") -> bytes:
    """Build a TCE-PE style response encoded in ISO-8859-1."""
    data = {
        "resposta": {
            "status": status,
            "entidade": entity,
            "tamanhoResultado": len(items),
            "limiteResultado": 100000,
            "conteudo": items,
        }
    }
    return json.dumps(data, ensure_ascii=False).encode(RESPONSE_ENCODING)


# ---------------------------------------------------------------------------
# buscar_unidades
# ---------------------------------------------------------------------------


class TestBuscarUnidades:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_unidades(self) -> None:
        respx.get(f"{API_BASE}/UnidadesJurisdicionadas!json").mock(
            return_value=httpx.Response(
                200,
                content=_mock_response(
                    "UnidadesJurisdicionadas",
                    [
                        {
                            "Codigo": "123",
                            "Nome": "PREFEITURA DO RECIFE",
                            "Natureza": "prefeitura",
                            "Municipio": "Recife",
                            "CodigoMunicipio": "2611",
                        },
                    ],
                ),
            )
        )
        result = await client.buscar_unidades(natureza="prefeitura")
        assert len(result) == 1
        assert result[0].codigo == "123"
        assert result[0].nome == "PREFEITURA DO RECIFE"
        assert result[0].municipio == "Recife"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{API_BASE}/UnidadesJurisdicionadas!json").mock(
            return_value=httpx.Response(200, content=_mock_response("UnidadesJurisdicionadas", []))
        )
        result = await client.buscar_unidades()
        assert result == []


# ---------------------------------------------------------------------------
# buscar_licitacoes
# ---------------------------------------------------------------------------


class TestBuscarLicitacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_licitacoes(self) -> None:
        respx.get(f"{API_BASE}/LicitacaoUG!json").mock(
            return_value=httpx.Response(
                200,
                content=_mock_response(
                    "LicitacaoUG",
                    [
                        {
                            "NUMEROLICITACAO": "001/2024",
                            "ANOLICITACAO": 2024,
                            "MODALIDADE": "Pregão Eletrônico",
                            "OBJETO": "Aquisição de material",
                            "VALORESTIMADO": 150000.0,
                            "SITUACAO": "Homologada",
                            "MUNICIPIO": "Recife",
                            "NOMEUNIDADEGESTORA": "PREFEITURA DO RECIFE",
                            "ID_UNIDADE_GESTORA": 123,
                        }
                    ],
                ),
            )
        )
        result = await client.buscar_licitacoes(ano=2024, municipio="Recife")
        assert len(result) == 1
        lic = result[0]
        assert lic.numero_licitacao == "001/2024"
        assert lic.modalidade == "Pregão Eletrônico"
        assert lic.valor_estimado == 150000.0
        assert lic.situacao == "Homologada"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{API_BASE}/LicitacaoUG!json").mock(
            return_value=httpx.Response(200, content=_mock_response("LicitacaoUG", []))
        )
        result = await client.buscar_licitacoes(ano=2024)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_contratos
# ---------------------------------------------------------------------------


class TestBuscarContratos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_contratos(self) -> None:
        respx.get(f"{API_BASE}/Contratos!json").mock(
            return_value=httpx.Response(
                200,
                content=_mock_response(
                    "Contratos",
                    [
                        {
                            "NUMEROCONTRATO": "CT-001/2024",
                            "ANOREFERENCIA": 2024,
                            "OBJETO": "Fornecimento de merenda",
                            "VALORCONTRATO": 500000.0,
                            "FORNECEDOR": "EMPRESA ABC",
                            "CPFCNPJ": "12345678000199",
                            "MUNICIPIO": "Recife",
                            "NOMEUNIDADEGESTORA": "PREFEITURA",
                            "ID_UNIDADE_GESTORA": 123,
                        }
                    ],
                ),
            )
        )
        result = await client.buscar_contratos(ano=2024)
        assert len(result) == 1
        assert result[0].numero_contrato == "CT-001/2024"
        assert result[0].valor_contrato == 500000.0
        assert result[0].fornecedor == "EMPRESA ABC"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{API_BASE}/Contratos!json").mock(
            return_value=httpx.Response(200, content=_mock_response("Contratos", []))
        )
        result = await client.buscar_contratos(ano=2024)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_despesas
# ---------------------------------------------------------------------------


class TestBuscarDespesas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_despesas(self) -> None:
        respx.get(f"{API_BASE}/DespesasMunicipais!json").mock(
            return_value=httpx.Response(
                200,
                content=_mock_response(
                    "DespesasMunicipais",
                    [
                        {
                            "NUMEROEMPENHO": "2024NE001",
                            "ANOREFERENCIA": 2024,
                            "MESREFERENCIA": 1,
                            "FORNECEDOR": "EMPRESA XYZ",
                            "CPF_CNPJ": "98765432000100",
                            "HISTORICO": "Pagamento de serviços",
                            "VALOREMPENHADO": 25000.0,
                            "VALORLIQUIDADO": 20000.0,
                            "VALORPAGO": 18000.0,
                            "FUNCAO": "Educação",
                            "ELEMENTODESPESA": "Material de consumo",
                            "NOMEUNIDADEGESTORA": "PREFEITURA",
                            "CODIGO_MUNICIPIO": "2611",
                        }
                    ],
                ),
            )
        )
        result = await client.buscar_despesas(ano=2024, mes=1)
        assert len(result) == 1
        d = result[0]
        assert d.numero_empenho == "2024NE001"
        assert d.valor_empenhado == 25000.0
        assert d.valor_pago == 18000.0
        assert d.funcao == "Educação"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{API_BASE}/DespesasMunicipais!json").mock(
            return_value=httpx.Response(200, content=_mock_response("DespesasMunicipais", []))
        )
        result = await client.buscar_despesas(ano=2024)
        assert result == []


# ---------------------------------------------------------------------------
# buscar_fornecedores
# ---------------------------------------------------------------------------


class TestBuscarFornecedores:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_fornecedores(self) -> None:
        respx.get(f"{API_BASE}/Fornecedores!json").mock(
            return_value=httpx.Response(
                200,
                content=_mock_response(
                    "Fornecedores",
                    [
                        {
                            "CPFCNPJ": "06990590000123",
                            "NOME": "GOOGLE BRASIL INTERNET LTDA.",
                            "TipoCredor": 2,
                        },
                    ],
                ),
            )
        )
        result = await client.buscar_fornecedores(nome="GOOGLE")
        assert len(result) == 1
        assert result[0].nome == "GOOGLE BRASIL INTERNET LTDA."
        assert result[0].cpf_cnpj == "06990590000123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(f"{API_BASE}/Fornecedores!json").mock(
            return_value=httpx.Response(200, content=_mock_response("Fornecedores", []))
        )
        result = await client.buscar_fornecedores(nome="INEXISTENTE")
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_iso_8859_encoding(self) -> None:
        """Verify proper handling of ISO-8859-1 encoded characters."""
        respx.get(f"{API_BASE}/Fornecedores!json").mock(
            return_value=httpx.Response(
                200,
                content=_mock_response(
                    "Fornecedores",
                    [{"CPFCNPJ": "111", "NOME": "JOSÉ DA SILVA", "TipoCredor": 1}],
                ),
            )
        )
        result = await client.buscar_fornecedores(nome="JOSÉ")
        assert result[0].nome == "JOSÉ DA SILVA"


# ---------------------------------------------------------------------------
# _fetch error handling
# ---------------------------------------------------------------------------


class TestFetchErrors:
    @pytest.mark.asyncio
    @respx.mock
    async def test_api_error_status(self) -> None:
        data = {
            "resposta": {
                "status": "ERRO",
                "entidade": "Fornecedores",
                "tamanhoResultado": 0,
                "limiteResultado": 100000,
                "conteudo": [],
            }
        }
        content = json.dumps(data).encode(RESPONSE_ENCODING)
        respx.get(f"{API_BASE}/Fornecedores!json").mock(
            return_value=httpx.Response(200, content=content)
        )
        with pytest.raises(Exception, match="TCE-PE API error"):
            await client.buscar_fornecedores(nome="test")
