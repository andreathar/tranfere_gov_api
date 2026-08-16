"""Tests for the Senado HTTP client.

Focus on nested parsing, _ensure_list, and _deep_get helpers.
"""

import httpx
import pytest
import respx

from mcp_brasil.data.senado import client
from mcp_brasil.data.senado.constants import (
    BLOCOS_URL,
    COMISSAO_URL,
    COMISSOES_URL,
    EMENDAS_URL,
    LEGISLATURA_URL,
    LIDERANCAS_URL,
    MATERIA_URL,
    MATERIAS_URL,
    RELATORIAS_URL,
    SENADORES_LISTA_URL,
    SENADORES_URL,
    VOTACOES_URL,
)

# ---------------------------------------------------------------------------
# Helpers: _deep_get, _ensure_list
# ---------------------------------------------------------------------------


class TestDeepGet:
    def test_nested_dict(self) -> None:
        data = {"a": {"b": {"c": 42}}}
        assert client._deep_get(data, "a", "b", "c") == 42

    def test_missing_key(self) -> None:
        data = {"a": {"b": 1}}
        assert client._deep_get(data, "a", "x") is None

    def test_non_dict(self) -> None:
        assert client._deep_get("string", "a") is None

    def test_none_value(self) -> None:
        assert client._deep_get(None, "a") is None

    def test_empty_keys(self) -> None:
        assert client._deep_get({"a": 1}) == {"a": 1}


class TestEnsureList:
    def test_list_passthrough(self) -> None:
        assert client._ensure_list([1, 2]) == [1, 2]

    def test_dict_wraps(self) -> None:
        assert client._ensure_list({"a": 1}) == [{"a": 1}]

    def test_none_returns_empty(self) -> None:
        assert client._ensure_list(None) == []

    def test_other_returns_empty(self) -> None:
        assert client._ensure_list("string") == []


# ---------------------------------------------------------------------------
# listar_senadores
# ---------------------------------------------------------------------------


class TestListarSenadores:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_senators(self) -> None:
        respx.get(SENADORES_LISTA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaParlamentarEmExercicio": {
                        "Parlamentares": {
                            "Parlamentar": [
                                {
                                    "IdentificacaoParlamentar": {
                                        "CodigoParlamentar": "5012",
                                        "NomeParlamentar": "Senador Teste",
                                        "SiglaPartidoParlamentar": "PT",
                                        "UfParlamentar": "SP",
                                        "UrlFotoParlamentar": "https://foto.example.com/5012.jpg",
                                    },
                                    "EmExercicio": "Sim",
                                }
                            ]
                        }
                    }
                },
            )
        )
        result = await client.listar_senadores()
        assert len(result) == 1
        assert result[0].nome == "Senador Teste"
        assert result[0].partido == "PT"
        assert result[0].em_exercicio is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_single_senator_dict(self) -> None:
        """When API returns single result as dict instead of list."""
        respx.get(SENADORES_LISTA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaParlamentarEmExercicio": {
                        "Parlamentares": {
                            "Parlamentar": {
                                "IdentificacaoParlamentar": {
                                    "CodigoParlamentar": "5012",
                                    "NomeParlamentar": "Único Senador",
                                    "SiglaPartidoParlamentar": "PL",
                                    "UfParlamentar": "RJ",
                                }
                            }
                        }
                    }
                },
            )
        )
        result = await client.listar_senadores()
        assert len(result) == 1
        assert result[0].nome == "Único Senador"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(SENADORES_LISTA_URL).mock(
            return_value=httpx.Response(
                200, json={"ListaParlamentarEmExercicio": {"Parlamentares": {}}}
            )
        )
        result = await client.listar_senadores()
        assert result == []


# ---------------------------------------------------------------------------
# obter_senador
# ---------------------------------------------------------------------------


class TestObterSenador:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_senator_detail(self) -> None:
        respx.get(f"{SENADORES_URL}/5012").mock(
            return_value=httpx.Response(
                200,
                json={
                    "DetalheParlamentar": {
                        "Parlamentar": {
                            "IdentificacaoParlamentar": {
                                "CodigoParlamentar": "5012",
                                "NomeParlamentar": "Senador Detalhe",
                                "NomeCompletoParlamentar": "Senador Detalhe da Silva",
                                "SiglaPartidoParlamentar": "MDB",
                                "UfParlamentar": "MG",
                                "EmailParlamentar": "senador@senado.leg.br",
                            },
                            "UltimoMandato": {
                                "PrimeiroExercicio": {"DataInicio": "2023-02-01"},
                                "SegundoExercicio": {"DataFim": "2031-01-31"},
                            },
                        }
                    }
                },
            )
        )
        result = await client.obter_senador("5012")
        assert result is not None
        assert result.nome == "Senador Detalhe"
        assert result.email == "senador@senado.leg.br"
        assert result.mandato_inicio == "2023-02-01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_not_found(self) -> None:
        respx.get(f"{SENADORES_URL}/99999").mock(return_value=httpx.Response(200, json={}))
        result = await client.obter_senador("99999")
        assert result is None


# ---------------------------------------------------------------------------
# buscar_senador_por_nome
# ---------------------------------------------------------------------------


class TestBuscarSenadorPorNome:
    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_by_name(self) -> None:
        respx.get(SENADORES_LISTA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaParlamentarEmExercicio": {
                        "Parlamentares": {
                            "Parlamentar": [
                                {
                                    "IdentificacaoParlamentar": {
                                        "CodigoParlamentar": "1",
                                        "NomeParlamentar": "Maria Silva",
                                        "SiglaPartidoParlamentar": "PT",
                                        "UfParlamentar": "SP",
                                    }
                                },
                                {
                                    "IdentificacaoParlamentar": {
                                        "CodigoParlamentar": "2",
                                        "NomeParlamentar": "João Santos",
                                        "SiglaPartidoParlamentar": "PL",
                                        "UfParlamentar": "RJ",
                                    }
                                },
                            ]
                        }
                    }
                },
            )
        )
        result = await client.buscar_senador_por_nome("Maria")
        assert len(result) == 1
        assert result[0].nome == "Maria Silva"


# ---------------------------------------------------------------------------
# buscar_materias
# ---------------------------------------------------------------------------


class TestBuscarMaterias:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_materias(self) -> None:
        respx.get(MATERIAS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "PesquisaBasicaMateria": {
                        "Materias": {
                            "Materia": [
                                {
                                    "CodigoMateria": "150001",
                                    "SiglaTipoMateria": "PEC",
                                    "NumeroMateria": "45",
                                    "AnoMateria": "2024",
                                    "EmentaMateria": "Altera a Constituição",
                                    "DataApresentacao": "2024-03-15",
                                    "NomeAutor": "Sen. Fulano",
                                }
                            ]
                        }
                    }
                },
            )
        )
        result = await client.buscar_materias(sigla_tipo="PEC")
        assert len(result) == 1
        assert result[0].sigla_tipo == "PEC"
        assert result[0].numero == "45"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty(self) -> None:
        respx.get(MATERIAS_URL).mock(
            return_value=httpx.Response(200, json={"PesquisaBasicaMateria": {"Materias": {}}})
        )
        result = await client.buscar_materias()
        assert result == []


# ---------------------------------------------------------------------------
# obter_materia
# ---------------------------------------------------------------------------


class TestObterMateria:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_materia_detail(self) -> None:
        respx.get(f"{MATERIA_URL}/150001").mock(
            return_value=httpx.Response(
                200,
                json={
                    "DetalheMateria": {
                        "Materia": {
                            "DadosBasicosMateria": {
                                "CodigoMateria": "150001",
                                "SiglaSubtipoMateria": "PEC",
                                "NumeroMateria": "45",
                                "AnoMateria": "2024",
                                "EmentaMateria": "Altera a Constituição",
                                "NomeCasaOrigem": "Senado Federal",
                            },
                            "Autoria": {"Autor": [{"NomeAutor": "Sen. Fulano"}]},
                        }
                    }
                },
            )
        )
        result = await client.obter_materia("150001")
        assert result is not None
        assert result.sigla_tipo == "PEC"
        assert result.autor == "Sen. Fulano"
        assert result.casa_origem == "Senado Federal"


# ---------------------------------------------------------------------------
# tramitacao_materia
# ---------------------------------------------------------------------------


class TestTramitacaoMateria:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_tramitacoes(self) -> None:
        respx.get(f"{MATERIA_URL}/movimentacoes/150001").mock(
            return_value=httpx.Response(
                200,
                json={
                    "MovimentacaoMateria": {
                        "Materia": {
                            "Autuacoes": {
                                "Autuacao": [
                                    {
                                        "DataTramitacao": "2024-03-15",
                                        "DescricaoTramitacao": "Recebida no Senado",
                                        "DestinoSigla": "CCJ",
                                        "SituacaoTramitacao": "Tramitando",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        )
        result = await client.tramitacao_materia("150001")
        assert len(result) == 1
        assert result[0].local == "CCJ"


# ---------------------------------------------------------------------------
# votos_materia
# ---------------------------------------------------------------------------


class TestVotosMateria:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_votacoes(self) -> None:
        respx.get(f"{MATERIA_URL}/votacoes/150001").mock(
            return_value=httpx.Response(
                200,
                json={
                    "VotacaoMateria": {
                        "Materia": {
                            "Votacoes": {
                                "Votacao": [
                                    {
                                        "CodigoSessaoVotacao": "VOT-001",
                                        "DataSessao": "2024-06-01",
                                        "DescricaoVotacao": "Votação em turno único",
                                        "Resultado": "Aprovada",
                                        "TotalVotosSim": "50",
                                        "TotalVotosNao": "20",
                                        "TotalVotosAbstencao": "3",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        )
        result = await client.votos_materia("150001")
        assert len(result) == 1
        assert result[0].resultado == "Aprovada"
        assert result[0].sim == 50
        assert result[0].nao == 20


# ---------------------------------------------------------------------------
# listar_votacoes
# ---------------------------------------------------------------------------


class TestListarVotacoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_votacoes(self) -> None:
        respx.get(VOTACOES_URL, params={"ano": "2024"}).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigoSessaoVotacao": 6900,
                        "dataSessao": "2024-03-15T00:00:00",
                        "descricaoVotacao": "PEC da reforma",
                        "resultadoVotacao": "A",
                    }
                ],
            )
        )
        result = await client.listar_votacoes("2024")
        assert len(result) == 1
        assert result[0].codigo == "6900"


# ---------------------------------------------------------------------------
# listar_comissoes
# ---------------------------------------------------------------------------


class TestListarComissoes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_comissoes(self) -> None:
        respx.get(COMISSOES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaColegiados": {
                        "Colegiados": {
                            "Colegiado": [
                                {
                                    "CodigoColegiado": "40",
                                    "SiglaColegiado": "CCJ",
                                    "NomeColegiado": "Comissão de Constituição e Justiça",
                                    "SiglaTipoColegiado": "Permanente",
                                }
                            ]
                        }
                    }
                },
            )
        )
        result = await client.listar_comissoes()
        assert len(result) == 1
        assert result[0].sigla == "CCJ"


# ---------------------------------------------------------------------------
# membros_comissao
# ---------------------------------------------------------------------------


class TestMembrosComissao:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_members(self) -> None:
        respx.get(f"{COMISSAO_URL}/40/membros").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ComposicaoComissao": {
                        "Comissao": {
                            "Membros": {
                                "Membro": [
                                    {
                                        "IdentificacaoParlamentar": {
                                            "CodigoParlamentar": "5012",
                                            "NomeParlamentar": "Senador Membro",
                                            "SiglaPartidoParlamentar": "PT",
                                            "UfParlamentar": "SP",
                                        },
                                        "DescricaoParticipacao": "Presidente",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        )
        result = await client.membros_comissao("40")
        assert len(result) == 1
        assert result[0].nome == "Senador Membro"
        assert result[0].cargo == "Presidente"


# ---------------------------------------------------------------------------
# legislatura_atual
# ---------------------------------------------------------------------------


class TestLegislaturaAtual:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_first_legislatura(self) -> None:
        respx.get(LEGISLATURA_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaLegislatura": {
                        "Legislaturas": {
                            "Legislatura": [
                                {
                                    "NumeroLegislatura": "57",
                                    "DataInicio": "2023-02-01",
                                    "DataFim": "2027-01-31",
                                }
                            ]
                        }
                    }
                },
            )
        )
        result = await client.legislatura_atual()
        assert result is not None
        assert result.numero == 57

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty(self) -> None:
        respx.get(LEGISLATURA_URL).mock(return_value=httpx.Response(200, json={}))
        result = await client.legislatura_atual()
        assert result is None


# ---------------------------------------------------------------------------
# Parser edge cases
# ---------------------------------------------------------------------------


class TestParserEdgeCases:
    def test_senador_resumo_empty(self) -> None:
        result = client._parse_senador_resumo({})
        assert result.nome is None
        assert result.partido is None

    def test_senador_detalhe_empty(self) -> None:
        result = client._parse_senador_detalhe({})
        assert result.nome is None

    def test_materia_resumo_empty(self) -> None:
        result = client._parse_materia_resumo({})
        assert result.sigla_tipo is None

    def test_materia_detalhe_empty(self) -> None:
        result = client._parse_materia_detalhe({})
        assert result.sigla_tipo is None
        assert result.autor is None

    def test_tramitacao_empty(self) -> None:
        result = client._parse_tramitacao({})
        assert result.data is None

    def test_votacao_resumo_empty(self) -> None:
        result = client._parse_votacao_resumo({})
        assert result.codigo is None

    def test_votacao_detalhe_empty(self) -> None:
        result = client._parse_votacao_detalhe({})
        assert result.sim is None

    def test_voto_empty(self) -> None:
        result = client._parse_voto({})
        assert result.senador_nome is None

    def test_comissao_resumo_empty(self) -> None:
        result = client._parse_comissao_resumo({})
        assert result.sigla is None

    def test_comissao_detalhe_empty(self) -> None:
        result = client._parse_comissao_detalhe({})
        assert result.sigla is None

    def test_membro_empty(self) -> None:
        result = client._parse_membro({})
        assert result.nome is None

    def test_reuniao_empty(self) -> None:
        result = client._parse_reuniao({})
        assert result.data is None
        assert result.comissao is None

    def test_sessao_empty(self) -> None:
        result = client._parse_sessao({})
        assert result.data is None

    def test_legislatura_empty(self) -> None:
        result = client._parse_legislatura({})
        assert result.numero is None

    def test_safe_int_none(self) -> None:
        assert client._safe_int(None) is None

    def test_safe_int_string(self) -> None:
        assert client._safe_int("42") == 42

    def test_safe_int_invalid(self) -> None:
        assert client._safe_int("abc") is None

    def test_materia_detalhe_single_autor(self) -> None:
        """When Autor is a dict instead of list (single author)."""
        raw = {
            "DetalheMateria": {
                "Materia": {
                    "DadosBasicosMateria": {},
                    "Autoria": {
                        "Autor": {"NomeAutor": "Único Autor"},
                    },
                }
            }
        }
        result = client._parse_materia_detalhe(raw)
        assert result.autor == "Único Autor"

    def test_emenda_empty(self) -> None:
        result = client._parse_emenda({})
        assert result.codigo is None
        assert result.decisao is None

    def test_bloco_empty(self) -> None:
        result = client._parse_bloco({})
        assert result.nome is None
        assert result.partidos is None

    def test_lideranca_empty(self) -> None:
        result = client._parse_lideranca({})
        assert result.nome_parlamentar is None

    def test_relatoria_empty(self) -> None:
        result = client._parse_relatoria({})
        assert result.codigo_materia is None
        assert result.tramitando is None


# ---------------------------------------------------------------------------
# emendas_materia
# ---------------------------------------------------------------------------


class TestEmendasMateria:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_emendas(self) -> None:
        respx.get(EMENDAS_URL, params={"codigoMateria": "150001"}).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigoEmenda": 8001,
                        "numeroEmenda": 1,
                        "identificacaoEmenda": "EMD 1/2024",
                        "tipoEmenda": "Substitutiva",
                        "dataApresentacao": "2024-05-10",
                        "nomeAutor": "Sen. Teste",
                        "siglaColegiado": "CCJ",
                        "decisoes": [
                            {"descricaoDecisao": "Aprovada", "dataDecisao": "2024-06-01"}
                        ],
                    }
                ],
            )
        )
        result = await client.emendas_materia("150001")
        assert len(result) == 1
        assert result[0].codigo == "8001"
        assert result[0].autor == "Sen. Teste"
        assert result[0].decisao == "Aprovada"
        assert result[0].data_decisao == "2024-06-01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(EMENDAS_URL, params={"codigoMateria": "999"}).mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await client.emendas_materia("999")
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_emenda_without_decisoes(self) -> None:
        respx.get(EMENDAS_URL, params={"codigoMateria": "150001"}).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigoEmenda": 8002,
                        "nomeAutor": "Sen. Outro",
                    }
                ],
            )
        )
        result = await client.emendas_materia("150001")
        assert len(result) == 1
        assert result[0].decisao is None


# ---------------------------------------------------------------------------
# listar_blocos
# ---------------------------------------------------------------------------


class TestListarBlocos:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_blocos(self) -> None:
        respx.get(BLOCOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaBlocoParlamentar": {
                        "Blocos": {
                            "Bloco": [
                                {
                                    "CodigoBloco": "100",
                                    "NomeBloco": "Bloco da Maioria",
                                    "NomeApelido": "Maioria",
                                    "DataCriacao": "2023-02-01",
                                    "Partidos": {
                                        "Partido": [
                                            {"SiglaPartido": "PL"},
                                            {"SiglaPartido": "PP"},
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                },
            )
        )
        result = await client.listar_blocos()
        assert len(result) == 1
        assert result[0].nome == "Bloco da Maioria"
        assert result[0].partidos == ["PL", "PP"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(BLOCOS_URL).mock(
            return_value=httpx.Response(200, json={"ListaBlocoParlamentar": {"Blocos": {}}})
        )
        result = await client.listar_blocos()
        assert result == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_single_bloco_dict(self) -> None:
        """When API returns single bloco as dict."""
        respx.get(BLOCOS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ListaBlocoParlamentar": {
                        "Blocos": {
                            "Bloco": {
                                "CodigoBloco": "200",
                                "NomeBloco": "Único Bloco",
                            }
                        }
                    }
                },
            )
        )
        result = await client.listar_blocos()
        assert len(result) == 1
        assert result[0].nome == "Único Bloco"


# ---------------------------------------------------------------------------
# listar_liderancas
# ---------------------------------------------------------------------------


class TestListarLiderancas:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_liderancas(self) -> None:
        respx.get(LIDERANCAS_URL, params={"casa": "SF"}).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigoParlamentar": 5012,
                        "nomeParlamentar": "Sen. Líder",
                        "siglaPartido": "PT",
                        "tipoLideranca": "Líder",
                        "unidadeLideranca": "Partido",
                        "dataDesignacao": "2023-02-15",
                    }
                ],
            )
        )
        result = await client.listar_liderancas()
        assert len(result) == 1
        assert result[0].nome_parlamentar == "Sen. Líder"
        assert result[0].tipo_lideranca == "Líder"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(LIDERANCAS_URL, params={"casa": "SF"}).mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await client.listar_liderancas()
        assert result == []


# ---------------------------------------------------------------------------
# relatorias_senador
# ---------------------------------------------------------------------------


class TestRelatoriasSenador:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_parsed_relatorias(self) -> None:
        respx.get(RELATORIAS_URL, params={"codigoParlamentar": "5012"}).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "codigoMateria": 150001,
                        "identificacaoMateria": "PEC 45/2024",
                        "ementaMateria": "Altera a Constituição",
                        "nomeAutorMateria": "Sen. Fulano",
                        "descricaoTipoRelator": "Relator",
                        "dataDesignacao": "2024-03-15T00:00:00",
                        "siglaColegiado": "CCJ",
                        "tramitando": "Sim",
                    }
                ],
            )
        )
        result = await client.relatorias_senador("5012")
        assert len(result) == 1
        assert result[0].codigo_materia == "150001"
        assert result[0].identificacao == "PEC 45/2024"
        assert result[0].data_designacao == "2024-03-15"
        assert result[0].tramitando is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self) -> None:
        respx.get(RELATORIAS_URL, params={"codigoParlamentar": "999"}).mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await client.relatorias_senador("999")
        assert result == []
