"""Tests for the TCE-TO HTTP client."""

import pytest
import respx
from httpx import Response

from mcp_brasil.data.tce_to import client
from mcp_brasil.data.tce_to.constants import PAUTAS_URL, PESSOAS_URL, PROCESSO_URL


class TestBuscarPessoas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_pessoas(self) -> None:
        respx.get(PESSOAS_URL).mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 100,
                        "nome": "JOAO DA SILVA",
                        "codigo": "***.123.***-00",
                        "processos": [
                            {
                                "numero_ano": "1234/2024",
                                "assunto": "PRESTACAO DE CONTAS",
                                "classe_assunto": "CONTAS DE GOVERNO",
                                "entidade_origem": "PREFEITURA DE PALMAS",
                                "entidade_origem_municipio": "PALMAS",
                                "data_entrada": "15/03/2024 10:00:00",
                                "departamento_atual": "1A CAMARA",
                            }
                        ],
                    }
                ],
            )
        )
        result = await client.buscar_pessoas(nome="JOAO")
        assert len(result) == 1
        assert result[0].nome == "JOAO DA SILVA"
        assert result[0].processos is not None
        assert len(result[0].processos) == 1
        assert result[0].processos[0].numero_ano == "1234/2024"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(PESSOAS_URL).mock(return_value=Response(200, json=[]))
        result = await client.buscar_pessoas(nome="INEXISTENTE")
        assert result == []


class TestConsultarProcesso:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_processo(self) -> None:
        url = f"{PROCESSO_URL}/1234/2024"
        respx.get(url).mock(
            return_value=Response(
                200,
                json={
                    "numero_ano": "1234/2024",
                    "assunto": "PRESTACAO DE CONTAS",
                    "classe_assunto": "CONTAS DE GOVERNO",
                    "entidade_origem": "PREFEITURA DE PALMAS",
                    "entidade_origem_municipio": "PALMAS",
                    "entidade_origem_cnpj": "01234567000100",
                    "data_entrada": "15/03/2024 10:00:00",
                    "departamento_atual": "1A CAMARA",
                    "complemento": "Exercício 2023",
                    "distribuicao": "CORPO ESPECIAL",
                    "eletronico": "S",
                    "sigiloso": False,
                },
            )
        )
        result = await client.consultar_processo(numero=1234, ano=2024)
        assert result is not None
        assert result.numero_ano == "1234/2024"
        assert result.entidade_origem == "PREFEITURA DE PALMAS"
        assert result.sigiloso is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self) -> None:
        url = f"{PROCESSO_URL}/9999/2024"
        respx.get(url).mock(
            return_value=Response(200, json={"error_message": "Processo nao encontrado"})
        )
        result = await client.consultar_processo(numero=9999, ano=2024)
        assert result is None


class TestListarPautas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_pautas(self) -> None:
        respx.get(PAUTAS_URL).mock(
            return_value=Response(
                200,
                json={
                    "pautas": [
                        {
                            "data": "31/03/2026",
                            "hora": "14:30:00:000",
                            "tipo": "ORDINARIA/VIDEOCONFERENCIA",
                            "origem": "PRIMEIRA CAMARA",
                            "url": "https://example.com/pauta/1",
                        }
                    ]
                },
            )
        )
        result = await client.listar_pautas()
        assert len(result) == 1
        assert result[0].data == "31/03/2026"
        assert result[0].tipo == "ORDINARIA/VIDEOCONFERENCIA"
        assert result[0].origem == "PRIMEIRA CAMARA"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_pautas(self) -> None:
        respx.get(PAUTAS_URL).mock(return_value=Response(200, json={"pautas": []}))
        result = await client.listar_pautas()
        assert result == []
