"""Tests for the IBGE tool functions.

Tools are tested by mocking client functions (never HTTP).
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.ibge import tools
from mcp_brasil.data.ibge.schemas import (
    AgregadoValor,
    CnaeSecao,
    CnaeSubclasse,
    Estado,
    MalhaMetadados,
    Municipio,
    NomeConsulta,
    NomeFrequencia,
    RankingEntry,
    RankingResult,
    Regiao,
)

CLIENT_MODULE = "mcp_brasil.data.ibge.client"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# listar_estados
# ---------------------------------------------------------------------------


class TestListarEstados:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Estado(
                id=35,
                sigla="SP",
                nome="São Paulo",
                regiao=Regiao(id=3, sigla="SE", nome="Sudeste"),
            ),
            Estado(
                id=22,
                sigla="PI",
                nome="Piauí",
                regiao=Regiao(id=2, sigla="NE", nome="Nordeste"),
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_estados", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.listar_estados(ctx)
        assert "SP" in result
        assert "São Paulo" in result
        assert "Sudeste" in result
        assert "PI" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.listar_estados", new_callable=AsyncMock, return_value=[]):
            result = await tools.listar_estados(ctx)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# buscar_municipios
# ---------------------------------------------------------------------------


class TestBuscarMunicipios:
    @pytest.mark.asyncio
    async def test_formats_list(self) -> None:
        mock_data = [
            Municipio(id=2211001, nome="Teresina"),
            Municipio(id=2207702, nome="Parnaíba"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_municipios", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.buscar_municipios("PI", ctx)
        assert "Teresina" in result
        assert "2211001" in result
        assert "2 encontrados" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.listar_municipios", new_callable=AsyncMock, return_value=[]):
            result = await tools.buscar_municipios("XX", ctx)
        assert "0 encontrados" in result


# ---------------------------------------------------------------------------
# listar_regioes
# ---------------------------------------------------------------------------


class TestListarRegioes:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Regiao(id=1, sigla="N", nome="Norte"),
            Regiao(id=2, sigla="NE", nome="Nordeste"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_regioes", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.listar_regioes(ctx)
        assert "Norte" in result
        assert "Nordeste" in result


# ---------------------------------------------------------------------------
# consultar_nome
# ---------------------------------------------------------------------------


class TestConsultarNome:
    @pytest.mark.asyncio
    async def test_formats_frequency(self) -> None:
        mock_data = [
            NomeConsulta(
                nome="JOÃO",
                sexo=None,
                localidade="BR",
                res=[
                    NomeFrequencia(periodo="[1930,1940[", frequencia=60155),
                    NomeFrequencia(periodo="[1940,1950[", frequencia=141772),
                ],
            )
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_nome", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.consultar_nome("João", ctx)
        assert "JOÃO" in result
        assert "60.155" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.consultar_nome", new_callable=AsyncMock, return_value=[]):
            result = await tools.consultar_nome("Xyzabc", ctx)
        assert "não encontrado" in result

    @pytest.mark.asyncio
    async def test_with_sexo(self) -> None:
        mock_data = [
            NomeConsulta(
                nome="MARIA",
                sexo="F",
                localidade="BR",
                res=[NomeFrequencia(periodo="[1930,1940[", frequencia=100000)],
            )
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_nome", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.consultar_nome("Maria", ctx)
        assert "Sexo: F" in result


# ---------------------------------------------------------------------------
# ranking_nomes
# ---------------------------------------------------------------------------


class TestRankingNomes:
    @pytest.mark.asyncio
    async def test_formats_ranking(self) -> None:
        mock_data = [
            RankingResult(
                localidade="BR",
                sexo=None,
                res=[
                    RankingEntry(nome="MARIA", frequencia=11734129, ranking=1),
                    RankingEntry(nome="JOSÉ", frequencia=5754529, ranking=2),
                ],
            )
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.ranking_nomes", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.ranking_nomes(ctx)
        assert "MARIA" in result
        assert "JOSÉ" in result
        assert "11.734.129" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.ranking_nomes", new_callable=AsyncMock, return_value=[]):
            result = await tools.ranking_nomes(ctx)
        assert "Nenhum resultado" in result


# ---------------------------------------------------------------------------
# consultar_agregado
# ---------------------------------------------------------------------------


class TestConsultarAgregado:
    @pytest.mark.asyncio
    async def test_with_indicador(self) -> None:
        mock_data = [
            AgregadoValor(localidade_id="35", localidade_nome="São Paulo", valor="44411238"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_agregado", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.consultar_agregado(ctx, indicador="populacao")
        assert "São Paulo" in result
        assert "44411238" in result
        assert "População" in result

    @pytest.mark.asyncio
    async def test_without_params(self) -> None:
        ctx = _mock_ctx()
        result = await tools.consultar_agregado(ctx)
        assert "Informe" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.consultar_agregado", new_callable=AsyncMock, return_value=[]):
            result = await tools.consultar_agregado(ctx, indicador="populacao")
        assert "Nenhum dado" in result

    @pytest.mark.asyncio
    async def test_with_custom_ids(self) -> None:
        mock_data = [
            AgregadoValor(localidade_id="1", localidade_nome="Brasil", valor="999"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_agregado", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.consultar_agregado(ctx, agregado_id=1234, variavel_id=5678)
        assert "Brasil" in result


# ---------------------------------------------------------------------------
# listar_pesquisas
# ---------------------------------------------------------------------------


class TestListarPesquisas:
    @pytest.mark.asyncio
    async def test_formats_list(self) -> None:
        mock_data = [
            {
                "id": "CA",
                "nome": "Censo Agropecuário",
                "agregados": [{"id": "123", "nome": "Produção"}],
            },
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_pesquisas", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.listar_pesquisas(ctx)
        assert "Censo Agropecuário" in result
        assert "Produção" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(f"{CLIENT_MODULE}.listar_pesquisas", new_callable=AsyncMock, return_value=[]):
            result = await tools.listar_pesquisas(ctx)
        assert "Nenhuma pesquisa" in result


# ---------------------------------------------------------------------------
# obter_malha
# ---------------------------------------------------------------------------


class TestObterMalha:
    @pytest.mark.asyncio
    async def test_formats_metadata(self) -> None:
        mock_data = MalhaMetadados(
            id="35",
            nivel_geografico="Estado",
            centroide_lat=-22.19,
            centroide_lon=-48.79,
            area_km2=248219.481,
            bbox_min_lon=-53.11,
            bbox_min_lat=-25.31,
            bbox_max_lon=-44.16,
            bbox_max_lat=-19.78,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_malha_metadados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.obter_malha("35", ctx)
        assert "Estado" in result
        assert "-22,1900" in result or "-22.1900" in result
        assert "248.219,48" in result
        assert "GeoJSON" in result

    @pytest.mark.asyncio
    async def test_without_area(self) -> None:
        mock_data = MalhaMetadados(
            id="35",
            nivel_geografico="Estado",
            centroide_lat=-22.19,
            centroide_lon=-48.79,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_malha_metadados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.obter_malha("35", ctx)
        assert "Área" not in result


# ---------------------------------------------------------------------------
# buscar_cnae
# ---------------------------------------------------------------------------


class TestBuscarCnae:
    @pytest.mark.asyncio
    async def test_list_sections(self) -> None:
        mock_data = [
            CnaeSecao(id="A", descricao="AGRICULTURA"),
            CnaeSecao(id="J", descricao="INFORMAÇÃO E COMUNICAÇÃO"),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_cnae_secoes", new_callable=AsyncMock, return_value=mock_data
        ):
            result = await tools.buscar_cnae(ctx)
        assert "Seções CNAE" in result
        assert "Agricultura" in result

    @pytest.mark.asyncio
    async def test_subclass_with_hierarchy(self) -> None:
        mock_data = CnaeSubclasse(
            id="6201-5/01",
            descricao="DESENVOLVIMENTO DE PROGRAMAS SOB ENCOMENDA",
            classe_id="6201-5",
            classe_descricao="DESENVOLVIMENTO DE PROGRAMAS",
            grupo_id="62.0",
            grupo_descricao="SERVIÇOS DE TI",
            divisao_id="62",
            divisao_descricao="ATIVIDADES DE TI",
            secao_id="J",
            secao_descricao="INFORMAÇÃO E COMUNICAÇÃO",
            atividades=["Desenvolvimento de software", "Programação"],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_cnae_subclasse",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_cnae(ctx, codigo="6201501")
        assert "6201-5/01" in result
        assert "Hierarquia" in result
        assert "Seção J" in result
        assert "Atividades" in result
        assert "Desenvolvimento De Software" in result

    @pytest.mark.asyncio
    async def test_subclass_with_many_activities(self) -> None:
        mock_data = CnaeSubclasse(
            id="9999-9/99",
            descricao="TESTE",
            atividades=[f"Atividade {i}" for i in range(20)],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_cnae_subclasse",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_cnae(ctx, codigo="9999999")
        assert "... e mais 5 atividades" in result
