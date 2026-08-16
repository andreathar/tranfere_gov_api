"""Tests for the Saúde HTTP client."""

from unittest.mock import patch

import httpx
import pytest
import respx

from mcp_brasil.data.saude import client
from mcp_brasil.data.saude.constants import (
    ESTABELECIMENTOS_URL,
    INFODENGUE_API_BASE,
    INFOGRIPE_ALERTA_URL,
    LEITOS_URL,
    TIPOS_URL,
)
from mcp_brasil.exceptions import HttpClientError

# ---------------------------------------------------------------------------
# buscar_estabelecimentos
# ---------------------------------------------------------------------------


class TestBuscarEstabelecimentos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_establishments(self) -> None:
        respx.get(ESTABELECIMENTOS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigo_cnes": "1234567",
                        "nome_fantasia": "UBS Central",
                        "nome_razao_social": "Unidade Básica de Saúde Central",
                        "natureza_organizacao_entidade": "Administração Pública",
                        "tipo_gestao": "Municipal",
                        "codigo_tipo_unidade": "01",
                        "descricao_turno_atendimento": "Central de Regulação",
                        "codigo_municipio": "355030",
                        "codigo_uf": "35",
                        "endereco_estabelecimento": "Rua ABC, 123",
                    }
                ],
            )
        )
        result = await client.buscar_estabelecimentos(codigo_municipio="355030")
        assert len(result) == 1
        assert result[0].codigo_cnes == "1234567"
        assert result[0].nome_fantasia == "UBS Central"
        assert result[0].codigo_municipio == "355030"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(ESTABELECIMENTOS_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_estabelecimentos()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_query_params(self) -> None:
        route = respx.get(ESTABELECIMENTOS_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_estabelecimentos(
            codigo_municipio="355030", codigo_uf="35", status=1, limit=10, offset=5
        )
        req_url = str(route.calls[0].request.url)
        assert "codigo_municipio=355030" in req_url
        assert "codigo_uf=35" in req_url
        assert "status=1" in req_url
        assert "limit=10" in req_url
        assert "offset=5" in req_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_limit_capped_at_max(self) -> None:
        route = respx.get(ESTABELECIMENTOS_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_estabelecimentos(limit=999)
        req_url = str(route.calls[0].request.url)
        assert "limit=20" in req_url


# ---------------------------------------------------------------------------
# listar_tipos_estabelecimento
# ---------------------------------------------------------------------------


class TestListarTiposEstabelecimento:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_types(self) -> None:
        respx.get(TIPOS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigo_tipo_unidade": "01",
                        "descricao_tipo_unidade": "Central de Regulação",
                    },
                    {
                        "codigo_tipo_unidade": "02",
                        "descricao_tipo_unidade": "Hospital Geral",
                    },
                ],
            )
        )
        result = await client.listar_tipos_estabelecimento()
        assert len(result) == 2
        assert result[0].codigo == "01"
        assert result[0].descricao == "Central de Regulação"
        assert result[1].codigo == "02"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(TIPOS_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.listar_tipos_estabelecimento()
        assert result == []


# ---------------------------------------------------------------------------
# consultar_leitos
# ---------------------------------------------------------------------------


class TestConsultarLeitos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_beds(self) -> None:
        respx.get(LEITOS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "nome_do_hospital": "Hospital Central",
                        "descricao_do_tipo_da_unidade": "Cirúrgico",
                        "descricao_da_natureza_juridica_do_hosptial": "Cirurgia Geral",
                        "quantidade_total_de_leitos_do_hosptial": 20,
                        "quantidade_total_de_leitos_sus_do_hosptial": 15,
                    }
                ],
            )
        )
        result = await client.consultar_leitos()
        assert len(result) == 1
        assert result[0].tipo_leito == "Cirúrgico"
        assert result[0].existente == 20
        assert result[0].sus == 15

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(LEITOS_URL).mock(return_value=httpx.Response(200, json=[]))
        result = await client.consultar_leitos()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_query_params(self) -> None:
        route = respx.get(LEITOS_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.consultar_leitos(limit=50, offset=10)
        req_url = str(route.calls[0].request.url)
        assert "limit=50" in req_url
        assert "offset=10" in req_url


# ---------------------------------------------------------------------------
# Parse functions
# ---------------------------------------------------------------------------


class TestParseEstabelecimento:
    def test_handles_missing_fields(self) -> None:
        result = client._parse_estabelecimento({})
        assert result.codigo_cnes == ""
        assert result.nome_fantasia is None

    def test_converts_numeric_codes_to_str(self) -> None:
        result = client._parse_estabelecimento(
            {"codigo_cnes": 1234567, "codigo_municipio": 355030, "codigo_uf": 35}
        )
        assert result.codigo_cnes == "1234567"
        assert result.codigo_municipio == "355030"
        assert result.codigo_uf == "35"


class TestParseTipo:
    def test_handles_missing_fields(self) -> None:
        result = client._parse_tipo({})
        assert result.codigo == ""
        assert result.descricao is None


class TestParseLeito:
    def test_handles_missing_fields(self) -> None:
        result = client._parse_leito({})
        assert result.codigo_cnes == ""
        assert result.existente is None
        assert result.sus is None


# ---------------------------------------------------------------------------
# buscar_estabelecimento_por_cnes
# ---------------------------------------------------------------------------


class TestBuscarEstabelecimentoPorCnes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_detail(self) -> None:
        respx.get(f"{ESTABELECIMENTOS_URL}/1234567").mock(
            return_value=httpx.Response(
                200,
                json={
                    "codigo_cnes": "1234567",
                    "nome_fantasia": "Hospital São Paulo",
                    "nome_razao_social": "Hospital São Paulo Ltda",
                    "natureza_organizacao_entidade": "Administração Pública",
                    "tipo_gestao": "Estadual",
                    "codigo_tipo_unidade": "05",
                    "descricao_turno_atendimento": "Hospital Geral",
                    "codigo_municipio": "355030",
                    "codigo_uf": "35",
                    "endereco_estabelecimento": "Rua Napoleão de Barros, 715",
                    "bairro_estabelecimento": "Vila Clementino",
                    "codigo_cep_estabelecimento": "04024-002",
                    "numero_telefone_estabelecimento": "(11) 5576-4000",
                    "latitude_estabelecimento_decimo_grau": -23.5989,
                    "longitude_estabelecimento_decimo_grau": -46.6423,
                    "numero_cnpj": "12.345.678/0001-90",
                    "data_atualizacao": "2024-01-15",
                },
            )
        )
        result = await client.buscar_estabelecimento_por_cnes("1234567")
        assert result is not None
        assert result.codigo_cnes == "1234567"
        assert result.nome_fantasia == "Hospital São Paulo"
        assert result.telefone == "(11) 5576-4000"
        assert result.latitude == -23.5989

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_none_for_empty(self) -> None:
        respx.get(f"{ESTABELECIMENTOS_URL}/0000000").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await client.buscar_estabelecimento_por_cnes("0000000")
        assert result is None


# ---------------------------------------------------------------------------
# buscar_estabelecimentos_por_tipo
# ---------------------------------------------------------------------------


class TestBuscarEstabelecimentosPorTipo:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_tipo_param(self) -> None:
        route = respx.get(ESTABELECIMENTOS_URL).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_estabelecimentos_por_tipo(
            codigo_tipo="73",
            codigo_municipio="355030",
        )
        req_url = str(route.calls[0].request.url)
        assert "codigo_tipo_unidade=73" in req_url
        assert "codigo_municipio=355030" in req_url
        assert "status=1" in req_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_list(self) -> None:
        respx.get(ESTABELECIMENTOS_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigo_cnes": "9876543",
                        "nome_fantasia": "UPA 24h",
                        "codigo_tipo_unidade": "73",
                        "descricao_turno_atendimento": "Pronto Atendimento",
                        "codigo_municipio": "220040",
                        "codigo_uf": "22",
                    }
                ],
            )
        )
        result = await client.buscar_estabelecimentos_por_tipo(codigo_tipo="73")
        assert len(result) == 1
        assert result[0].codigo_cnes == "9876543"
        assert result[0].descricao_tipo == "Pronto Atendimento"


# ---------------------------------------------------------------------------
# Parse detail function
# ---------------------------------------------------------------------------


class TestParseEstabelecimentoDetalhe:
    def test_handles_missing_fields(self) -> None:
        result = client._parse_estabelecimento_detalhe({})
        assert result.codigo_cnes == ""
        assert result.telefone is None
        assert result.latitude is None

    def test_parses_all_fields(self) -> None:
        result = client._parse_estabelecimento_detalhe(
            {
                "codigo_cnes": 1234567,
                "nome_fantasia": "Hospital X",
                "bairro_estabelecimento": "Centro",
                "codigo_cep_estabelecimento": "01000-000",
                "numero_telefone_estabelecimento": "1199999999",
                "latitude_estabelecimento_decimo_grau": -23.55,
                "longitude_estabelecimento_decimo_grau": -46.63,
                "numero_cnpj": "12345678000190",
                "data_atualizacao": "2024-06-01",
            }
        )
        assert result.codigo_cnes == "1234567"
        assert result.bairro == "Centro"
        assert result.latitude == -23.55


# ---------------------------------------------------------------------------
# Malformed API responses (type validation)
# ---------------------------------------------------------------------------


class TestMalformedResponses:
    """Test that client functions raise HttpClientError on unexpected response types."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_estabelecimentos_string_response(self) -> None:
        respx.get(ESTABELECIMENTOS_URL).mock(
            return_value=httpx.Response(200, json="Service Unavailable")
        )
        with pytest.raises(HttpClientError, match="expected list"):
            await client.buscar_estabelecimentos()

    @pytest.mark.asyncio
    @respx.mock
    async def test_estabelecimentos_dict_without_list_returns_empty(self) -> None:
        """Dict response without list-valued keys returns empty list (API wraps in dict)."""
        respx.get(ESTABELECIMENTOS_URL).mock(
            return_value=httpx.Response(200, json={"error": "not found"})
        )
        result = await client.buscar_estabelecimentos()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_leitos_string_response(self) -> None:
        respx.get(LEITOS_URL).mock(return_value=httpx.Response(200, json="404 Not Found"))
        with pytest.raises(HttpClientError, match="expected list"):
            await client.consultar_leitos()

    @pytest.mark.asyncio
    @respx.mock
    async def test_tipos_string_response(self) -> None:
        respx.get(TIPOS_URL).mock(return_value=httpx.Response(200, json="error"))
        with pytest.raises(HttpClientError, match="expected list"):
            await client.listar_tipos_estabelecimento()

    @pytest.mark.asyncio
    @respx.mock
    async def test_estabelecimento_por_cnes_string_response(self) -> None:
        respx.get(f"{ESTABELECIMENTOS_URL}/1234567").mock(
            return_value=httpx.Response(200, json="not found")
        )
        with pytest.raises(HttpClientError, match="expected dict"):
            await client.buscar_estabelecimento_por_cnes("1234567")


# ---------------------------------------------------------------------------
# buscar_municipio_geocodigo (in-memory)
# ---------------------------------------------------------------------------


class TestBuscarMunicipioGeocodigo:
    def test_finds_by_name(self) -> None:
        mock_data = [
            {"nome": "São Paulo", "uf": "SP", "geocodigo": "3550308"},
            {"nome": "São Pedro", "uf": "SP", "geocodigo": "3550407"},
            {"nome": "Rio de Janeiro", "uf": "RJ", "geocodigo": "3304557"},
        ]
        with patch.object(client, "_load_geocode_data", return_value=mock_data):
            result = client.buscar_municipio_geocodigo("São")
        assert len(result) == 2
        assert result[0].nome == "São Paulo"
        assert result[1].nome == "São Pedro"

    def test_filters_by_uf(self) -> None:
        mock_data = [
            {"nome": "Campinas", "uf": "SP", "geocodigo": "3509502"},
            {"nome": "Campinas do Sul", "uf": "RS", "geocodigo": "4303673"},
        ]
        with patch.object(client, "_load_geocode_data", return_value=mock_data):
            result = client.buscar_municipio_geocodigo("Campinas", uf="SP")
        assert len(result) == 1
        assert result[0].uf == "SP"

    def test_accent_insensitive(self) -> None:
        mock_data = [
            {"nome": "Maricá", "uf": "RJ", "geocodigo": "3302700"},
        ]
        with patch.object(client, "_load_geocode_data", return_value=mock_data):
            result = client.buscar_municipio_geocodigo("marica")
        assert len(result) == 1
        assert result[0].nome == "Maricá"

    def test_not_found(self) -> None:
        mock_data = [
            {"nome": "São Paulo", "uf": "SP", "geocodigo": "3550308"},
        ]
        with patch.object(client, "_load_geocode_data", return_value=mock_data):
            result = client.buscar_municipio_geocodigo("XYZ123")
        assert result == []

    def test_exact_match_first(self) -> None:
        """Exact name matches should come before partial matches."""
        mock_data = [
            {"nome": "Cruzeiro da Fortaleza", "uf": "MG", "geocodigo": "3120706"},
            {"nome": "Fortaleza", "uf": "CE", "geocodigo": "2304400"},
            {"nome": "Fortaleza de Minas", "uf": "MG", "geocodigo": "3126307"},
        ]
        with patch.object(client, "_load_geocode_data", return_value=mock_data):
            result = client.buscar_municipio_geocodigo("Fortaleza")
        assert len(result) == 3
        assert result[0].nome == "Fortaleza"
        assert result[0].geocodigo == "2304400"


# ---------------------------------------------------------------------------
# buscar_alertas_dengue
# ---------------------------------------------------------------------------


class TestBuscarAlertasDengue:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_alerts(self) -> None:
        respx.get(INFODENGUE_API_BASE).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "SE": 202410,
                        "data_iniSE": "2024-03-03",
                        "casos_est": 150.5,
                        "casos": 120,
                        "nivel": 2,
                        "p_inc100k": 5.6,
                        "Rt": 1.2,
                        "pop": 2700000.0,
                        "receptession_level": 0,
                        "transmission_evidence": 1,
                    }
                ],
            )
        )
        result = await client.buscar_alertas_dengue(
            geocodigo="2304400",
            doenca="dengue",
            ew_start=10,
            ew_end=10,
            ey_start=2024,
            ey_end=2024,
        )
        assert len(result) == 1
        assert result[0].semana_epidemiologica == 202410
        assert result[0].casos_estimados == 150.5
        assert result[0].casos_notificados == 120
        assert result[0].nivel == 2
        assert result[0].nivel_descricao == "Amarelo"
        assert result[0].rt == 1.2

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(INFODENGUE_API_BASE).mock(return_value=httpx.Response(200, json=[]))
        result = await client.buscar_alertas_dengue(geocodigo="2304400")
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_timestamp_data_iniSE(self) -> None:
        """API returns data_iniSE as timestamp in ms — should convert to date string."""
        respx.get(INFODENGUE_API_BASE).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "SE": 202510,
                        "data_iniSE": 1740873600000,  # 2025-03-02 UTC
                        "casos_est": 10.0,
                        "casos": 5,
                        "nivel": 1,
                    }
                ],
            )
        )
        result = await client.buscar_alertas_dengue(geocodigo="2304400")
        assert len(result) == 1
        assert result[0].data_inicio_se == "2025-03-02"

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_list_response(self) -> None:
        respx.get(INFODENGUE_API_BASE).mock(
            return_value=httpx.Response(200, json={"error": "not found"})
        )
        result = await client.buscar_alertas_dengue(geocodigo="0000000")
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_sends_query_params(self) -> None:
        route = respx.get(INFODENGUE_API_BASE).mock(return_value=httpx.Response(200, json=[]))
        await client.buscar_alertas_dengue(
            geocodigo="2304400",
            doenca="chikungunya",
            ew_start=5,
            ew_end=20,
            ey_start=2024,
            ey_end=2024,
        )
        req_url = str(route.calls[0].request.url)
        assert "geocode=2304400" in req_url
        assert "disease=chikungunya" in req_url
        assert "ew_start=5" in req_url
        assert "ew_end=20" in req_url
        assert "ey_start=2024" in req_url
        assert "ey_end=2024" in req_url
        assert "format=json" in req_url


# ---------------------------------------------------------------------------
# buscar_situacao_gripe
# ---------------------------------------------------------------------------


class TestBuscarSituacaoGripe:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_csv(self) -> None:
        csv_content = (
            "UF,epiweek,epiyear,situation_name,level,estimated_cases,notified_cases,"
            "ci_lower,ci_upper\n"
            "SP,10,2024,Atividade alta,alto,500.0,350,400.0,600.0\n"
            "RJ,10,2024,Atividade baixa,baixo,100.0,80,50.0,150.0\n"
        )
        respx.get(INFOGRIPE_ALERTA_URL).mock(return_value=httpx.Response(200, text=csv_content))
        result = await client.buscar_situacao_gripe()
        assert len(result) == 2
        assert result[0].uf == "SP"
        assert result[0].semana_epidemiologica == 10
        assert result[0].casos_estimados == 500.0
        assert result[1].uf == "RJ"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_csv(self) -> None:
        csv_content = "UF,epiweek,epiyear,situation_name,level\n"
        respx.get(INFOGRIPE_ALERTA_URL).mock(return_value=httpx.Response(200, text=csv_content))
        result = await client.buscar_situacao_gripe()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_raises(self) -> None:
        respx.get(INFOGRIPE_ALERTA_URL).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(HttpClientError, match="InfoGripe"):
            await client.buscar_situacao_gripe()


# ---------------------------------------------------------------------------
# listar_bases_datasus (in-memory)
# ---------------------------------------------------------------------------


class TestListarBasesDatasus:
    def test_returns_all_bases(self) -> None:
        result = client.listar_bases_datasus()
        assert len(result) == 9
        siglas = {b.sigla for b in result}
        assert "SIM" in siglas
        assert "SINAN" in siglas
        assert "CNES" in siglas

    def test_returns_base_datasus_models(self) -> None:
        result = client.listar_bases_datasus()
        for base in result:
            assert base.sigla
            assert base.nome
            assert base.descricao


# ---------------------------------------------------------------------------
# listar_doencas_notificaveis (in-memory)
# ---------------------------------------------------------------------------


class TestListarDoencasNotificaveis:
    def test_returns_all_diseases(self) -> None:
        result = client.listar_doencas_notificaveis()
        assert len(result) == 47

    def test_filters_by_category(self) -> None:
        result = client.listar_doencas_notificaveis(categoria="Arbovirose")
        assert len(result) >= 3
        for d in result:
            assert d.categoria == "Arbovirose"

    def test_filter_accent_insensitive(self) -> None:
        result = client.listar_doencas_notificaveis(categoria="Respiratoria")
        assert len(result) > 0
        for d in result:
            assert "Respiratória" in d.categoria

    def test_empty_category(self) -> None:
        result = client.listar_doencas_notificaveis(categoria="CategoriaInexistente")
        assert result == []


# ---------------------------------------------------------------------------
# Normalize helper
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_removes_accents(self) -> None:
        assert client._normalize("São Paulo") == "sao paulo"
        assert client._normalize("Maricá") == "marica"

    def test_lowercase(self) -> None:
        assert client._normalize("FORTALEZA") == "fortaleza"


# ---------------------------------------------------------------------------
# Safe parse helpers
# ---------------------------------------------------------------------------


class TestSafeParsers:
    def test_safe_int(self) -> None:
        assert client._safe_int("42") == 42
        assert client._safe_int("42.7") == 42
        assert client._safe_int(None) is None
        assert client._safe_int("abc") is None

    def test_safe_float(self) -> None:
        assert client._safe_float("3.14") == 3.14
        assert client._safe_float(None) is None
        assert client._safe_float("abc") is None
