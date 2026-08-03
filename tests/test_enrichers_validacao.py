"""Tests for src.enrichers.validação — validação de CNPJ via BrasilAPI."""

from __future__ import annotations

from unittest.mock import patch

from src.enrichers.validacao import validar_cnpj

# ---------------------------------------------------------------------------
# validar_cnpj — consulta à BrasilAPI
# ---------------------------------------------------------------------------


class TestValidarCnpj:
    """Testes para a função validar_cnpj com mock de HTTP."""

    BRAISLAPI_BASE = "https://brasilapi.com.br/api/cnpj/v1"

    @patch("src.enrichers.validacao.requests.get")
    def test_cnpj_valido(self, mock_get, sample_validacao_cnpj_response):
        """CNPJ válido deve retornar dados completos com valido=True."""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = sample_validacao_cnpj_response

        result = validar_cnpj("12345678000190")

        assert result["valido"] is True
        assert result["razao_social"] == "Empresa Teste Ltda"
        assert result["nome_fantasia"] == "Empresa Teste"
        assert result["situacao_cadastral"] == "Ativa"
        assert result["porte"] == "ME"
        assert result["erro"] is None

    @patch("src.enrichers.validacao.requests.get")
    def test_cnpj_nao_encontrado(self, mock_get):
        """CNPJ não encontrado (404) deve retornar valido=False e erro descritivo."""
        mock_response = mock_get.return_value
        mock_response.status_code = 404

        result = validar_cnpj("00000000000000")

        assert result["valido"] is False
        assert result["erro"] == "CNPJ não encontrado"

    @patch("src.enrichers.validacao.requests.get")
    def test_erro_http(self, mock_get):
        """Erro HTTP inesperado deve retornar valido=False com código."""
        mock_response = mock_get.return_value
        mock_response.status_code = 429  # Too Many Requests

        result = validar_cnpj("12345678000190")

        assert result["valido"] is False
        assert "HTTP 429" in result["erro"]

    @patch("src.enrichers.validacao.requests.get")
    def test_exception_network(self, mock_get):
        """Exceção de rede deve ser capturada e retornar erro truncado."""
        mock_get.side_effect = TimeoutError("Connection timed out after 15 seconds")

        result = validar_cnpj("12345678000190")

        assert result["valido"] is False
        assert result["erro"] == "Connection timed out after 15 seconds"

    @patch("src.enrichers.validacao.requests.get")
    def test_cnpj_cleanup(self, mock_get):
        """CNPJ com pontuação deve ser limpo antes da consulta."""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "razao_social": "Empresa Teste Ltda",
            "situacao_cadastral": "Ativa",
        }

        validar_cnpj("12.345.678/0001-90")

        # Verificar que a URL chamada tem o CNPJ limpo
        # 12.345.678/0001-90 → 12345678000190 (14 dígitos)
        expected_url_correct = f"{self.BRAISLAPI_BASE}/12345678000190"
        mock_get.assert_called_once_with(expected_url_correct, timeout=15)

    @patch("src.enrichers.validacao.requests.get")
    def test_cnpj_sem_pontuacao(self, mock_get):
        """CNPJ já limpo não deve ser alterado."""
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {"razao_social": "Teste"}

        validar_cnpj("12345678000190")

        expected_url = f"{self.BRAISLAPI_BASE}/12345678000190"
        mock_get.assert_called_once_with(expected_url, timeout=15)

    @patch("src.enrichers.validacao.requests.get")
    def test_exception_erro_truncado(self, mock_get):
        """Erro com mensagem longa deve ser truncado em 200 caracteres."""
        msg_long = "x" * 500
        mock_get.side_effect = ConnectionError(msg_long)

        result = validar_cnpj("12345678000190")

        assert len(result["erro"]) <= 200
        assert result["erro"] == "x" * 200
