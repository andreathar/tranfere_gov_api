"""Fixtures compartilhadas para todos os testes da suite TransfereGov."""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Amostras de dados reais (anônimos) para uso nos testes
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_cnpj() -> str:
    """CNPJ válido (11 dígitos, sem pontuação) para testes de validação."""
    return "12345678000190"


@pytest.fixture
def sample_cnpj_formatado() -> str:
    """CNPJ com pontuação para testar limpeza."""
    return "12.345.678/0001-90"


@pytest.fixture
def sample_cnpj_invalido() -> str:
    """CNPJ que retorna 404 na BrasilAPI."""
    return "00000000000000"


@pytest.fixture
def sample_plano_acao() -> dict[str, Any]:
    """Registro mínimo de plano de ação para testes."""
    return {
        "planoAcaoId": 12345,
        "planoAcaoCodigo": "202600012345",
        "planoAcaoSituacao": "EM_EXECUCAO",
        "objetoId": 301,
        "objetoDescricao": "Cemitérios",
        "programaId": 25,
        "beneficiarioId": 9858,
        "beneficiarioNome": "Município de Teste",
        "beneficiarioCnpj": "12345678000190",
        "uf": "AL",
        "valorCusteio": 50000.0,
        "valorInvestimento": 100000.0,
        "valorTotal": 150000.0,
    }


@pytest.fixture
def sample_deputado_response() -> dict[str, Any]:
    """Resposta simulada da API da Câmara para /deputarios/{id}."""
    return {
        "dados": {
            "id": 204560,
            "nomeCivil": "Deputado Teste",
            "siglaPartido": "PARTIDO",
            "siglaUf": "SP",
            "ultimoStatus": {
                "nomeEleitoral": "Dep. Teste",
                "siglaPartido": "PARTIDO",
                "siglaUf": "SP",
                "urlFoto": "https://www.camara.leg.br/foto.jpg",
                "situacao": "Exercício",
                "gabinete": {
                    "sala": "123",
                    "predio": "4",
                    "telefone": "3215-1234",
                    "email": "dep.teste@camara.leg.br",
                },
                "condicaoEleitoral": "Titular",
            },
        }
    }


@pytest.fixture
def sample_ibge_municipio() -> list[dict[str, Any]]:
    """Resposta simulada da API IBGE para /localidades/estados/AL/municipios."""
    return [
        {
            "id": 2700300,
            "nome": "Maceió",
            "microrregiao": {
                "nome": "Maceió",
                "mesorregiao": {
                    "nome": "Leste Alagoano",
                    "UF": {
                        "sigla": "AL",
                        "nome": "Alagoas",
                        "regiao": {"nome": "Nordeste"},
                    },
                },
            },
        },
        {
            "id": 2704302,
            "nome": "Rio Largo",
            "microrregiao": {
                "nome": "Maceió",
                "mesorregiao": {
                    "nome": "Leste Alagoano",
                    "UF": {
                        "sigla": "AL",
                        "nome": "Alagoas",
                        "regiao": {"nome": "Nordeste"},
                    },
                },
            },
        },
    ]


@pytest.fixture
def sample_validacao_cnpj_response() -> dict[str, Any]:
    """Resposta simulada da BrasilAPI para CNPJ válido."""
    return {
        "razao_social": "Empresa Teste Ltda",
        "nome_fantasia": "Empresa Teste",
        "situacao_cadastral": "Ativa",
        "data_situacao_cadastral": "2020-01-15",
        "porte": "ME",
        "natureza_juridica": "206-2 - Sociedade Empresária Limitada",
        "cep": "01001-000",
        "telefone": "1130000000",
        "email": "contato@empresateste.com.br",
    }


# ---------------------------------------------------------------------------
# Mock de resposta HTTP (compatível com unittest.mock / respx)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_response_200() -> int:
    """Código HTTP 200."""
    return 200


@pytest.fixture
def mock_response_404() -> int:
    """Código HTTP 404."""
    return 404
