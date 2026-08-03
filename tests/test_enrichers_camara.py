"""Tests for src.enrichers.camara — perfil de deputados via API da Câmara."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

from src.enrichers.camara import buscar_deputado

# ---------------------------------------------------------------------------
# buscar_deputado — consulta à API da Câmara dos Deputados
# ---------------------------------------------------------------------------


class TestBuscarDeputado:
    """Testes para a função buscar_deputado com mock de HTTP."""

    @patch("src.enrichers.camara.requests.get")
    def test_deputado_encontrado(self, mock_get: Mock, sample_deputado_response: dict[str, Any]):
        """Deputado encontrado deve retornar dados detalhados."""
        mock_search = Mock(status_code=200)
        mock_search.json.return_value = {"dados": [{"id": 204560, "nome": "Deputado Teste"}]}
        mock_detail = Mock(status_code=200)
        mock_detail.json.return_value = sample_deputado_response

        mock_get.side_effect = [mock_search, mock_detail]

        result: Any = buscar_deputado("Deputado Teste")

        assert result is not None
        assert result["id"] == 204560
        assert result["ultimoStatus"]["siglaPartido"] == "PARTIDO"
        assert result["ultimoStatus"]["siglaUf"] == "SP"

    @patch("src.enrichers.camara.requests.get")
    def test_deputado_nao_encontrado(self, mock_get: Mock):
        """Nenhum deputado encontrado deve retornar None."""
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"dados": []}

        mock_get.return_value = mock_response

        result = buscar_deputado("Nome Inexistente")

        assert result is None

    @patch("src.enrichers.camara.requests.get")
    def test_erro_api(self, mock_get: Mock):
        """Erro na API (500) deve retornar None sem exceção."""
        mock_response = Mock(status_code=500)
        mock_get.return_value = mock_response

        result = buscar_deputado("Deputado Teste")

        assert result is None

    @patch("src.enrichers.camara.requests.get")
    def test_exception_network_capturada(self, mock_get: Mock):
        """Exceção de rede deve ser capturada, função retorna None."""
        mock_get.side_effect = TimeoutError("timeout")

        result = buscar_deputado("Deputado Teste")

        assert result is None

    @patch("src.enrichers.camara.requests.get")
    def test_busca_por_nome_sem_acento(self, mock_get: Mock):
        """Nome com acento deve ser normalizado na busca."""
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"dados": []}

        mock_get.return_value = mock_response

        buscar_deputado("João da Silva")

        call_kwargs = mock_get.call_args[1]
        assert "params" in call_kwargs
        assert call_kwargs["params"]["nome"] == "joao da silva"
