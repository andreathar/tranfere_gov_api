"""Tests for src.enrichers.ibge — dados municipais via API do IBGE."""

from __future__ import annotations

from unittest.mock import patch

from src.enrichers.ibge import buscar_municipios_ibge

# ---------------------------------------------------------------------------
# buscar_municipios_ibge — consulta à API do IBGE
# ---------------------------------------------------------------------------


class TestBuscarMunicipiosIbge:
    """Testes para a função buscar_municipios_ibge com mock de HTTP."""

    @patch("src.enrichers.ibge.requests.get")
    def test_uf_encontrada(self, mock_get, sample_ibge_municipio):
        """UF com municípios deve retornar lista."""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = sample_ibge_municipio

        result = buscar_municipios_ibge("AL")

        assert len(result) == 2
        assert result[0]["nome"] == "Maceió"
        assert result[0]["id"] == 2700300
        assert result[1]["nome"] == "Rio Largo"

    @patch("src.enrichers.ibge.requests.get")
    def test_uf_sem_municipios(self, mock_get):
        """UF sem dados deve retornar lista vazia."""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = []

        result = buscar_municipios_ibge("XX")

        assert result == []

    @patch("src.enrichers.ibge.requests.get")
    def test_erro_http(self, mock_get):
        """Erro HTTP deve retornar lista vazia."""
        mock_response = mock_get.return_value
        mock_response.status_code = 500

        result = buscar_municipios_ibge("SP")

        assert result == []

    @patch("src.enrichers.ibge.requests.get")
    def test_exception_rede(self, mock_get):
        """Exceção de rede deve retornar lista vazia."""
        mock_get.side_effect = TimeoutError("timeout")

        result = buscar_municipios_ibge("RJ")

        assert result == []

    @patch("src.enrichers.ibge.requests.get")
    def test_url_correta(self, mock_get):
        """URL deve ser montada corretamente com a UF."""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = []

        buscar_municipios_ibge("SP")

        mock_get.assert_called_once_with(
            "https://servicodados.ibge.gov.br/api/v1/localidades/estados/SP/municipios",
            timeout=15,
        )
