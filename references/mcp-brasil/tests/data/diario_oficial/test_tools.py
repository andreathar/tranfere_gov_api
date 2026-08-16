"""Tests for the Diário Oficial tool functions.

Tools are tested by mocking client functions (never HTTP).
Context is mocked via MagicMock with async methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.diario_oficial import tools
from mcp_brasil.data.diario_oficial.schemas import (
    CidadeQueridoDiario,
    DiarioOficial,
    DiarioResultado,
    PublicacaoDOU,
    ResultadoDOU,
)

CLIENT_MODULE = "mcp_brasil.data.diario_oficial.client"
CLIENT_DOU_MODULE = "mcp_brasil.data.diario_oficial.client_dou"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# buscar_diarios
# ---------------------------------------------------------------------------


class TestBuscarDiarios:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = DiarioResultado(
            total_gazettes=2,
            gazettes=[
                DiarioOficial(
                    territory_id="3550308",
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    edition_number="1234",
                    is_extra_edition=False,
                    txt_url="https://example.com/gazette.txt",
                    excerpts=["Trecho com a palavra licitação encontrada no diário"],
                ),
                DiarioOficial(
                    territory_id="3304557",
                    territory_name="Rio de Janeiro",
                    state_code="RJ",
                    date="2024-01-14",
                    edition_number="5678",
                    is_extra_edition=True,
                    txt_url=None,
                    excerpts=[],
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_diarios("licitação", ctx)
        assert "São Paulo" in result
        assert "SP" in result
        assert "2024-01-15" in result
        assert "1234" in result
        assert "licitação" in result
        assert "Rio de Janeiro" in result
        assert "Edição Extra" in result
        assert "2 diários encontrados" in result

    @pytest.mark.asyncio
    async def test_strips_html_tags_from_excerpts(self) -> None:
        mock_data = DiarioResultado(
            total_gazettes=1,
            gazettes=[
                DiarioOficial(
                    territory_id="3550308",
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    excerpts=[
                        "Contrato <em>licitação</em> firmado entre <b>Empresa X</b> e prefeitura"
                    ],
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_diarios("licitação", ctx)
        assert "<em>" not in result
        assert "</em>" not in result
        assert "<b>" not in result
        assert "</b>" not in result
        assert "licitação" in result
        assert "Empresa X" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_diarios("inexistente", ctx)
        assert "Nenhum diário oficial encontrado" in result
        assert "inexistente" in result

    @pytest.mark.asyncio
    async def test_passes_territory_id_as_list(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            await tools.buscar_diarios("teste", ctx, territorio_id="3550308")
        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["territory_ids"] == ["3550308"]

    @pytest.mark.asyncio
    async def test_passes_sort_and_exact_params(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            await tools.buscar_diarios(
                "teste", ctx, busca_exata=False, ordenar_por="descending_date"
            )
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["is_exact_search"] is False
        assert call_kwargs["sort_by"] == "descending_date"


# ---------------------------------------------------------------------------
# buscar_diarios_regiao
# ---------------------------------------------------------------------------


class TestBuscarDiariosRegiao:
    @pytest.mark.asyncio
    async def test_filters_by_uf(self) -> None:
        mock_data = DiarioResultado(
            total_gazettes=1,
            gazettes=[
                DiarioOficial(
                    territory_id="3550308",
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    excerpts=["Resultado SP"],
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            result = await tools.buscar_diarios_regiao("teste", ctx, uf="SP")
        assert "São Paulo" in result
        call_kwargs = mock_client.call_args.kwargs
        assert "3550308" in call_kwargs["territory_ids"]

    @pytest.mark.asyncio
    async def test_capitais_apenas(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            await tools.buscar_diarios_regiao("teste", ctx, capitais_apenas=True)
        call_kwargs = mock_client.call_args.kwargs
        assert len(call_kwargs["territory_ids"]) == 20  # 20 capitais cobertas

    @pytest.mark.asyncio
    async def test_uf_not_found(self) -> None:
        ctx = _mock_ctx()
        result = await tools.buscar_diarios_regiao("teste", ctx, uf="XX")
        assert "Nenhuma capital coberta" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_diarios_regiao("inexistente", ctx, capitais_apenas=True)
        assert "Nenhum diário encontrado" in result


# ---------------------------------------------------------------------------
# buscar_cidades
# ---------------------------------------------------------------------------


class TestBuscarCidades:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            CidadeQueridoDiario(
                territory_id="3550308",
                territory_name="São Paulo",
                state_code="SP",
            ),
            CidadeQueridoDiario(
                territory_id="3549904",
                territory_name="São José dos Campos",
                state_code="SP",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_cidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.buscar_cidades("São", ctx)
        assert "3550308" in result
        assert "São Paulo" in result
        assert "SP" in result
        assert "São José dos Campos" in result
        assert "Código IBGE" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_cidades",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.buscar_cidades("Inexistente", ctx)
        assert "Nenhuma cidade encontrada" in result
        assert "Inexistente" in result


# ---------------------------------------------------------------------------
# listar_territorios
# ---------------------------------------------------------------------------


class TestListarTerritorios:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            CidadeQueridoDiario(
                territory_id="3550308",
                territory_name="São Paulo",
                state_code="SP",
            ),
            CidadeQueridoDiario(
                territory_id="2408102",
                territory_name="Natal",
                state_code="RN",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_cidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_territorios(ctx)
        assert "2 municípios" in result
        assert "São Paulo" in result
        assert "3550308" in result
        assert "Natal" in result
        assert "RN" in result
        assert "Código IBGE" in result

    @pytest.mark.asyncio
    async def test_pagination_hint_with_many(self) -> None:
        """When >100 cities, only first 100 are shown in table."""
        mock_data = [
            CidadeQueridoDiario(
                territory_id=str(i),
                territory_name=f"Cidade {i}",
                state_code="XX",
            )
            for i in range(150)
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.listar_cidades",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_territorios(ctx)
        assert "150 municípios" in result
        assert "Cidade 0" in result


# ---------------------------------------------------------------------------
# listar_diarios_recentes
# ---------------------------------------------------------------------------


class TestListarDiariosRecentes:
    @pytest.mark.asyncio
    async def test_formats_results(self) -> None:
        mock_data = DiarioResultado(
            total_gazettes=2,
            gazettes=[
                DiarioOficial(
                    territory_id="3550308",
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    edition_number="1234",
                    is_extra_edition=False,
                    txt_url="https://example.com/gazette.txt",
                ),
                DiarioOficial(
                    territory_id="3550308",
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-14",
                    edition_number="1233",
                    is_extra_edition=True,
                ),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_diarios_recentes(ctx, "3550308")
        assert "2024-01-15" in result
        assert "1234" in result
        assert "(Extra)" in result
        assert "2 diários recentes" in result

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.listar_diarios_recentes(ctx, "9999999")
        assert "Nenhum diário recente" in result

    @pytest.mark.asyncio
    async def test_passes_descending_date(self) -> None:
        mock_data = DiarioResultado(total_gazettes=0, gazettes=[])
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            await tools.listar_diarios_recentes(ctx, "3550308")
        call_kwargs = mock_client.call_args.kwargs
        assert call_kwargs["sort_by"] == "descending_date"


# ---------------------------------------------------------------------------
# buscar_diario_unificado
# ---------------------------------------------------------------------------


class TestBuscarDiarioUnificado:
    @pytest.mark.asyncio
    async def test_both_sources(self) -> None:
        mock_qd = DiarioResultado(
            total_gazettes=1,
            gazettes=[
                DiarioOficial(
                    territory_name="São Paulo",
                    state_code="SP",
                    date="2024-01-15",
                    excerpts=["Resultado municipal"],
                ),
            ],
        )
        mock_dou = ResultadoDOU(
            total=1,
            publicacoes=[
                PublicacaoDOU(
                    titulo="Portaria Federal",
                    orgao="Ministério X",
                    data_publicacao="2024-01-15",
                ),
            ],
        )
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_diarios",
                new_callable=AsyncMock,
                return_value=mock_qd,
            ),
            patch(
                f"{CLIENT_DOU_MODULE}.buscar_dou",
                new_callable=AsyncMock,
                return_value=mock_dou,
            ),
        ):
            result = await tools.buscar_diario_unificado("teste", ctx)
        assert "DOU Federal" in result
        assert "Diários Municipais" in result
        assert "Portaria Federal" in result
        assert "São Paulo" in result

    @pytest.mark.asyncio
    async def test_federal_only(self) -> None:
        mock_dou = ResultadoDOU(
            total=1,
            publicacoes=[
                PublicacaoDOU(titulo="Decreto 123", orgao="Gov Federal"),
            ],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_DOU_MODULE}.buscar_dou",
            new_callable=AsyncMock,
            return_value=mock_dou,
        ):
            result = await tools.buscar_diario_unificado("teste", ctx, escopo="federal")
        assert "DOU Federal" in result
        assert "Diários Municipais" not in result

    @pytest.mark.asyncio
    async def test_municipal_only(self) -> None:
        mock_qd = DiarioResultado(
            total_gazettes=1,
            gazettes=[DiarioOficial(territory_name="Natal", state_code="RN")],
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.buscar_diarios",
            new_callable=AsyncMock,
            return_value=mock_qd,
        ):
            result = await tools.buscar_diario_unificado("teste", ctx, escopo="municipal")
        assert "Diários Municipais" in result
        assert "DOU Federal" not in result

    @pytest.mark.asyncio
    async def test_empty_both(self) -> None:
        mock_qd = DiarioResultado(total_gazettes=0, gazettes=[])
        mock_dou = ResultadoDOU(total=0, publicacoes=[])
        ctx = _mock_ctx()
        with (
            patch(
                f"{CLIENT_MODULE}.buscar_diarios",
                new_callable=AsyncMock,
                return_value=mock_qd,
            ),
            patch(
                f"{CLIENT_DOU_MODULE}.buscar_dou",
                new_callable=AsyncMock,
                return_value=mock_dou,
            ),
        ):
            result = await tools.buscar_diario_unificado("inexistente", ctx)
        assert "Nenhum resultado no DOU" in result
        assert "Nenhum resultado nos diários municipais" in result
