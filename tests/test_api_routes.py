"""
Testes de integração para os endpoints REST da API (FastAPI + TestClient).

Testa os 9 routers registrados em src/api/app.py usando mocking
de db_service, camara_service, analytics_service e mcp_service
para evitar dependência com PostgreSQL ou APIs externas.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Garantir CORS permissivo antes de importar o app
# ---------------------------------------------------------------------------
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("TRANSPARENCIA_API_KEY", "test-key")

from src.api.app import app  # noqa: E402

client = TestClient(app)

# ===========================================================================
# DEPUTADOS — /api/v1/deputados/
# ===========================================================================


class TestDeputadosRoutes:
    """10 endpoints no router deputados.py (mix sync/async)."""

    def test_search_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/search?q= — retorna lista do DB."""
        from src.api.routes import deputados

        mock_data = [
            {
                "deputado_id": 1,
                "nome": "Deputado Teste",
                "nome_urna": "Dep. Teste",
                "sigla_partido": "PARTIDO",
                "uf": "SP",
                "url_foto": "https://foto.jpg",
            }
        ]
        monkeypatch.setattr(deputados.db_service, "search_deputados", lambda q: mock_data)

        resp = client.get("/api/v1/deputados/search?q=teste")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["nome"] == "Deputado Teste"

    def test_search_fallback_to_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quando DB retorna < 5 resultados, enriquece com API Câmara."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "search_deputados", lambda q: [])
        mock_api = AsyncMock(
            return_value=[
                {
                    "id": 100,
                    "nome": "API Dep",
                    "nomeEleitoral": "API Dep",
                    "siglaPartido": "PDT",
                    "siglaUf": "RJ",
                    "urlFoto": "https://foto2.jpg",
                }
            ]
        )
        monkeypatch.setattr(deputados.camara_service, "search_deputados_api", mock_api)

        resp = client.get("/api/v1/deputados/search?q=api")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["deputado_id"] == 100

    def test_search_fallback_fails_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Quando API Câmara falha, retorna os poucos resultados do DB sem quebrar."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "search_deputados",
            lambda q: [
                {
                    "deputado_id": 1,
                    "nome": "Unico",
                    "nome_urna": "Unico",
                    "sigla_partido": "X",
                    "uf": "SP",
                    "url_foto": "",
                }
            ],
        )
        monkeypatch.setattr(
            deputados.camara_service,
            "search_deputados_api",
            AsyncMock(side_effect=Exception("API offline")),
        )

        resp = client.get("/api/v1/deputados/search?q=unico")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_perfil_found_in_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/perfil — retorna perfil do DB."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "get_perfil_deputado",
            lambda _: {
                "deputado_id": 204560,
                "nome": "Dep Teste",
                "sigla_partido": "PARTIDO",
                "uf": "SP",
            },
        )

        resp = client.get("/api/v1/deputados/204560/perfil")
        assert resp.status_code == 200
        assert resp.json()["deputado_id"] == 204560

    def test_perfil_not_in_db_fallback_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Perfil não encontrado no DB → busca na API Câmara."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "get_perfil_deputado", lambda _: None)
        monkeypatch.setattr(
            deputados.camara_service,
            "buscar_deputado",
            AsyncMock(
                return_value={
                    "id": 999,
                    "nomeCivil": "Dep Via API",
                    "ultimoStatus": {
                        "nomeEleitoral": "Dep Via API",
                        "siglaPartido": "PSB",
                        "siglaUf": "MG",
                        "urlFoto": "https://foto.com",
                        "situacao": "Exercício",
                        "gabinete": {
                            "sala": "1",
                            "predio": "4",
                            "telefone": "1111",
                            "email": "a@b.com",
                        },
                        "condicaoEleitoral": "Titular",
                    },
                    "escolaridade": "Superior",
                    "dataNascimento": "1980-01-01",
                }
            ),
        )

        resp = client.get("/api/v1/deputados/999/perfil")
        assert resp.status_code == 200
        assert resp.json()["nome"] == "Dep Via API"

    def test_perfil_not_found_anywhere(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Perfil não encontrado nem no DB nem na API → 404."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "get_perfil_deputado", lambda _: None)
        monkeypatch.setattr(
            deputados.camara_service, "buscar_deputado", AsyncMock(return_value=None)
        )

        resp = client.get("/api/v1/deputados/99999/perfil")
        assert resp.status_code == 404

    def test_emendas_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/emendas — retorna lista."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "get_parlamentar_id", lambda _: None)
        monkeypatch.setattr(deputados.db_service, "get_nome_by_id", lambda _: "Dep Teste")
        monkeypatch.setattr(
            deputados.db_service,
            "get_emendas_deputado",
            lambda _: [{"emenda_codigo": "E001", "valor_total": 50000.0}],
        )

        resp = client.get("/api/v1/deputados/204560/emendas")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_emendas_deputado_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Deputado inexistente → 404."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "get_nome_by_id", lambda _: None)
        monkeypatch.setattr(
            deputados.camara_service, "buscar_deputado", AsyncMock(return_value=None)
        )

        resp = client.get("/api/v1/deputados/99999/emendas")
        assert resp.status_code == 404

    def test_emendas_resumo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/emendas/resumo — KPIs."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "get_parlamentar_id", lambda _: None)
        monkeypatch.setattr(deputados.db_service, "get_nome_by_id", lambda _: "Dep Teste")
        monkeypatch.setattr(
            deputados.db_service,
            "get_resumo_emendas",
            lambda _: {"total_planos": 10, "valor_total": 500000.0, "taxa_sucesso": 80.0},
        )

        resp = client.get("/api/v1/deputados/204560/emendas/resumo")
        assert resp.status_code == 200
        assert resp.json()["total_planos"] == 10

    def test_despesas_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/despesas — retorna lista da API Câmara."""
        from src.api.routes import deputados

        mock_despesas = AsyncMock(
            return_value=[
                {"ano": 2024, "valorLiquido": 5000.0, "tipoDespesa": "Passagem"},
            ]
        )
        monkeypatch.setattr(deputados.camara_service, "listar_despesas", mock_despesas)

        resp = client.get("/api/v1/deputados/204560/despesas?ano=2024")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_despesas_api_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Despesas com API offline → 502."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.camara_service,
            "listar_despesas",
            AsyncMock(side_effect=Exception("API Câmara fora")),
        )

        resp = client.get("/api/v1/deputados/1/despesas")
        assert resp.status_code == 502

    def test_comissoes_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/comissoes."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.camara_service,
            "listar_orgaos",
            AsyncMock(return_value=[{"id": 1, "sigla": "CCJ", "nome": "Comissão de Justiça"}]),
        )

        resp = client.get("/api/v1/deputados/204560/comissoes")
        assert resp.status_code == 200

    def test_votacoes_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/votacoes — delega ao db_service."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "get_votacoes_deputado",
            lambda _id, **kwargs: [{"votacao_id": "V001", "tipo_voto": "Sim"}],
        )

        resp = client.get("/api/v1/deputados/204560/votacoes?limit=10")
        assert resp.status_code == 200

    def test_proposicoes_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/proposicoes."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.camara_service,
            "listar_proposicoes",
            AsyncMock(return_value=[{"id": 123, "siglaTipo": "PL", "numero": 456}]),
        )

        resp = client.get("/api/v1/deputados/204560/proposicoes")
        assert resp.status_code == 200

    def test_dossie_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/dossie."""
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "get_dossie_deputado",
            lambda _: {
                "analise_gerada": "Dossiê completo",
                "data_analise": "2024-01-01",
                "fontes_usadas": ["voto", "emenda"],
            },
        )

        resp = client.get("/api/v1/deputados/204560/dossie")
        assert resp.status_code == 200
        assert resp.json()["analise_gerada"] == "Dossiê completo"

    def test_dossie_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dossiê não encontrado → 404."""
        from src.api.routes import deputados

        monkeypatch.setattr(deputados.db_service, "get_dossie_deputado", lambda _: None)

        resp = client.get("/api/v1/deputados/99999/dossie")
        assert resp.status_code == 404

    def test_full_report_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/v1/deputados/{id}/full_report — MCP lote.

        A rota faz import local ``from src.api.services.mcp_service import executar_lote``
        dentro do corpo da funcao, portanto patcheamos direto no modulo.
        """
        import src.api.services.mcp_service as mcp_svc

        mock_mcp = AsyncMock(return_value={"resultados": ["ok"]})
        monkeypatch.setattr(mcp_svc, "executar_lote", mock_mcp)

        resp = client.get("/api/v1/deputados/204560/full_report?ano=2024")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# ===========================================================================
# PREFEITOS — /api/v1/prefeitos/
# ===========================================================================


class TestPrefeitosRoutes:
    """6 endpoints sync (db_service)."""

    def test_search_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(
            prefeitos.db_service,
            "search_prefeitos",
            lambda q: [{"municipio_id": 1, "municipio_nome": "Maceió", "uf": "AL"}],
        )
        resp = client.get("/api/v1/prefeitos/search?q=maceio")
        assert resp.status_code == 200
        assert resp.json()[0]["municipio_nome"] == "Maceió"

    def test_ranking_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(
            prefeitos.db_service,
            "get_ranking_prefeitos",
            lambda **kw: [{"municipio_nome": "A", "valor_total_emendas": 1e6}],
        )
        resp = client.get("/api/v1/prefeitos/ranking?limit=5")
        assert resp.status_code == 200

    def test_perfil_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(
            prefeitos.db_service,
            "get_perfil_prefeito",
            lambda _: {"municipio_id": 1, "prefeito_nome": "Prefeito Teste"},
        )
        resp = client.get("/api/v1/prefeitos/1/perfil")
        assert resp.status_code == 200
        assert resp.json()["prefeito_nome"] == "Prefeito Teste"

    def test_perfil_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(prefeitos.db_service, "get_perfil_prefeito", lambda _: None)
        resp = client.get("/api/v1/prefeitos/99999/perfil")
        assert resp.status_code == 404

    def test_emendas_municipio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(
            prefeitos.db_service,
            "get_emendas_municipio",
            lambda _id, **kw: {"anos_disponiveis": [2024], "total_planos": 5, "emendas": []},
        )
        resp = client.get("/api/v1/prefeitos/1/emendas")
        assert resp.status_code == 200
        assert resp.json()["total_planos"] == 5

    def test_licitacoes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(
            prefeitos.db_service,
            "get_licitacoes_prefeitura",
            lambda _id, **kw: [{"id": 1, "descricao": "Compra de insumos"}],
        )
        resp = client.get("/api/v1/prefeitos/1/licitacoes")
        assert resp.status_code == 200

    def test_licitacoes_ganhadores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import prefeitos

        monkeypatch.setattr(
            prefeitos.db_service,
            "get_ganhadores_licitacoes_prefeitura",
            lambda _id, **kw: [{"razao_social": "Empresa X", "total_licitacoes_ganhas": 3}],
        )
        resp = client.get("/api/v1/prefeitos/1/licitacoes/ganhadores")
        assert resp.status_code == 200


# ===========================================================================
# VEREADORES — /api/v1/vereadores/
# ===========================================================================


class TestVereadoresRoutes:
    """6 endpoints sync (db_service)."""

    def test_search_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(
            vereadores.db_service,
            "search_vereadores",
            lambda q: [{"sq_candidato": "1", "nome_completo": "Ver. Teste", "partido": "PT"}],
        )
        resp = client.get("/api/v1/vereadores/search?q=teste")
        assert resp.status_code == 200

    def test_ranking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(
            vereadores.db_service,
            "get_ranking_vereadores",
            lambda **kw: [{"nome_completo": "Ver. A", "votos": 5000}],
        )
        resp = client.get("/api/v1/vereadores/ranking?limit=10&uf=SP")
        assert resp.status_code == 200

    def test_resumo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(
            vereadores.db_service,
            "get_resumo_vereadores",
            lambda: {"total_eleitos": 50000, "total_municipios": 5000},
        )
        resp = client.get("/api/v1/vereadores/resumo")
        assert resp.status_code == 200
        assert resp.json()["total_eleitos"] == 50000

    def test_por_partido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(
            vereadores.db_service,
            "get_vereadores_por_partido",
            lambda **kw: [{"partido": "PT", "total_eleitos": 1000}],
        )
        resp = client.get("/api/v1/vereadores/por-partido?uf=SP")
        assert resp.status_code == 200

    def test_por_municipio_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(
            vereadores.db_service,
            "get_vereadores_por_municipio",
            lambda _id: [{"nome_completo": "Ver. Mun"}],
        )
        resp = client.get("/api/v1/vereadores/municipio/2700300")
        assert resp.status_code == 200

    def test_por_municipio_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(vereadores.db_service, "get_vereadores_por_municipio", lambda _id: [])
        resp = client.get("/api/v1/vereadores/municipio/99999")
        assert resp.status_code == 404

    def test_por_uf(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import vereadores

        monkeypatch.setattr(
            vereadores.db_service,
            "get_vereadores_por_uf",
            lambda uf: [{"nome_completo": "Ver. SP"}],
        )
        resp = client.get("/api/v1/vereadores/uf/SP")
        assert resp.status_code == 200


# ===========================================================================
# ANALYTICS — /api/v1/analytics/
# ===========================================================================


class TestAnalyticsRoutes:
    """4 endpoints async (analytics_service)."""

    def test_party_efficiency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import analytics

        monkeypatch.setattr(
            analytics.analytics_service,
            "get_party_efficiency",
            AsyncMock(return_value=[{"partido": "PT", "taxa_sucesso": 75.0}]),
        )
        resp = client.get("/api/v1/analytics/party-efficiency")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_socioeconomic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import analytics

        monkeypatch.setattr(
            analytics.analytics_service,
            "get_socioeconomic_data",
            AsyncMock(return_value=[{"municipio": "Maceió", "idhm": 0.7}]),
        )
        resp = client.get("/api/v1/analytics/socioeconomic")
        assert resp.status_code == 200

    def test_deputy_roi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import analytics

        monkeypatch.setattr(
            analytics.analytics_service,
            "get_deputy_roi",
            AsyncMock(return_value=[{"deputado": "Teste", "roi": 2.5}]),
        )
        resp = client.get("/api/v1/analytics/deputy-roi")
        assert resp.status_code == 200

    def test_top_municipios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import analytics

        monkeypatch.setattr(
            analytics.analytics_service,
            "get_top_municipios",
            AsyncMock(return_value=[{"municipio": "Maceió", "valor_total": 1e7}]),
        )
        resp = client.get("/api/v1/analytics/top-municipios")
        assert resp.status_code == 200


# ===========================================================================
# AUDITORIA — /api/v1/auditoria/
# ===========================================================================


class TestAuditoriaRoutes:
    """3 endpoints (mcp_service + db_service)."""

    def test_saude_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import auditoria

        monkeypatch.setattr(
            auditoria.mcp_service,
            "get_saude_resumo",
            AsyncMock(return_value={"farmacia_popular": {"unidades": 5}}),
        )
        resp = client.get("/api/v1/auditoria/saude/2700300")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_saude_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import auditoria

        monkeypatch.setattr(
            auditoria.mcp_service,
            "get_saude_resumo",
            AsyncMock(side_effect=Exception("MCP erro")),
        )
        resp = client.get("/api/v1/auditoria/saude/000")
        assert resp.status_code == 500

    def test_tcu_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import auditoria

        monkeypatch.setattr(
            auditoria.mcp_service,
            "executar_lote",
            AsyncMock(return_value=[{"inidoneo": False}]),
        )
        resp = client.get("/api/v1/auditoria/tcu?cnpj=12345678000190")
        assert resp.status_code == 200

    def test_tcu_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import auditoria

        monkeypatch.setattr(
            auditoria.mcp_service,
            "executar_lote",
            AsyncMock(side_effect=Exception("Falha MCP")),
        )
        resp = client.get("/api/v1/auditoria/tcu?cnpj=00000000000000")
        assert resp.status_code == 500


# ===========================================================================
# COMPRAS — /api/v1/compras/
# ===========================================================================


class TestComprasRoutes:
    """2 endpoints (mcp_service)."""

    def test_fornecedor_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import compras

        monkeypatch.setattr(
            compras.mcp_service._mcp_client,
            "call_tool",
            AsyncMock(return_value={"fornecedor": "Empresa X"}),
        )
        resp = client.get("/api/v1/compras/fornecedor?cnpj=12345678000190")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_fornecedor_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import compras

        monkeypatch.setattr(
            compras.mcp_service._mcp_client,
            "call_tool",
            AsyncMock(side_effect=Exception("PNCP erro")),
        )
        resp = client.get("/api/v1/compras/fornecedor?cnpj=00000000000000")
        assert resp.status_code == 500

    def test_bps_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import compras

        monkeypatch.setattr(
            compras.mcp_service._mcp_client,
            "call_tool",
            AsyncMock(return_value={"precos": []}),
        )
        resp = client.get("/api/v1/compras/bps?termo=insulina")
        assert resp.status_code == 200


# ===========================================================================
# DIARIO OFICIAL — /api/v1/diario/
# ===========================================================================


class TestDiarioRoutes:
    """2 endpoints (mcp_service)."""

    def test_buscar_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import diario

        monkeypatch.setattr(
            diario.mcp_service._mcp_client,
            "call_tool",
            AsyncMock(return_value={"materias": [{"titulo": "Portaria X"}]}),
        )
        resp = client.get("/api/v1/diario/buscar?q=portaria&escopo=federal")
        assert resp.status_code == 200

    def test_buscar_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import diario

        monkeypatch.setattr(
            diario.mcp_service._mcp_client,
            "call_tool",
            AsyncMock(side_effect=Exception("DOU erro")),
        )
        resp = client.get("/api/v1/diario/buscar?q=xxx&escopo=ambos")
        assert resp.status_code == 500

    def test_buscar_perfil_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import diario

        monkeypatch.setattr(
            diario.mcp_service,
            "buscar_diario_perfil",
            AsyncMock(return_value={"citacoes": []}),
        )
        resp = client.post(
            "/api/v1/diario/buscar-perfil",
            json={"q": "Deputado Teste", "escopo": "ambos"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_buscar_perfil_missing_q(self) -> None:
        """POST sem 'q' → 400."""
        resp = client.post("/api/v1/diario/buscar-perfil", json={"escopo": "federal"})
        assert resp.status_code == 400


# ===========================================================================
# FNDE — /api/v1/fnde/
# ===========================================================================


class TestFndeRoutes:
    """5 endpoints sync (db_service)."""

    def test_resumo_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "get_fnde_resumo_estado",
            lambda **kw: [{"uf": "AL", "total_beneficiados": 50000}],
        )
        resp = client.get("/api/v1/fnde/resumo?uf=AL")
        assert resp.status_code == 200

    def test_resumo_sem_filtro(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "get_fnde_resumo_estado",
            lambda **kw: [{"uf": "AL"}, {"uf": "SP"}],
        )
        resp = client.get("/api/v1/fnde/resumo")
        assert resp.status_code == 200

    def test_municipios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "get_fnde_resumo_municipio",
            lambda **kw: [{"municipio_id": 1, "total_beneficiados": 1000}],
        )
        resp = client.get("/api/v1/fnde/municipios?uf=AL&limit=10")
        assert resp.status_code == 200

    def test_municipio_por_id_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "get_fnde_programas_municipio",
            lambda **kw: [{"programa": "FUNDEB", "ano": 2024}],
        )
        resp = client.get("/api/v1/fnde/municipio/2700300")
        assert resp.status_code == 200

    def test_municipio_por_id_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "get_fnde_programas_municipio",
            lambda **kw: [],
        )
        resp = client.get("/api/v1/fnde/municipio/99999")
        assert resp.status_code == 404

    def test_programas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "get_fnde_programas_disponiveis",
            lambda: [{"programa": "FUNDEB", "total_registros": 100}],
        )
        resp = client.get("/api/v1/fnde/programas")
        assert resp.status_code == 200

    def test_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import fnde

        monkeypatch.setattr(
            fnde.db_service,
            "search_fnde_municipios",
            lambda **kw: [{"municipio_id": 1, "nome": "Maceió"}],
        )
        resp = client.get("/api/v1/fnde/search?q=maceio")
        assert resp.status_code == 200


# ===========================================================================
# GOVERNADORES — /api/v1/governadores/
# ===========================================================================


class TestGovernadoresRoutes:
    """9 endpoints sync (db_service)."""

    def test_list_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_all_governadores",
            lambda **kw: [{"uf": "SP", "nome_governador": "Gov SP", "sigla_partido": "PSDB"}],
        )
        resp = client.get("/api/v1/governadores/")
        assert resp.status_code == 200

    def test_list_com_filtros(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_all_governadores",
            lambda **kw: [{"uf": "SP", "nome_governador": "Gov SP"}],
        )
        resp = client.get("/api/v1/governadores/?partido=PSDB&regiao=SE")
        assert resp.status_code == 200

    def test_ranking_emendas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_ranking_governadores_emendas",
            lambda **kw: [{"uf": "SP", "valor_total_emendas": 1e8}],
        )
        resp = client.get("/api/v1/governadores/ranking/emendas?limit=10")
        assert resp.status_code == 200

    def test_ranking_alinhamento(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_ranking_alinhamento_governador",
            lambda **kw: [{"uf": "SP", "pct_aliados": 85.0}],
        )
        resp = client.get("/api/v1/governadores/ranking/alinhamento")
        assert resp.status_code == 200

    def test_triangulo_politico(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_triangulo_politico",
            lambda **kw: [
                {"deputado_nome": "Dep A", "relacao_partidaria_prefeito": "mesmo partido"}
            ],
        )
        resp = client.get("/api/v1/governadores/triangulo-politico?uf=SP")
        assert resp.status_code == 200

    def test_perfil_governador_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_perfil_governador",
            lambda uf: {
                "uf": "SP",
                "nome_governador": "Gov SP",
                "top_municipios": [],
                "distribuicao_partidos_bancada": [],
            },
        )
        resp = client.get("/api/v1/governadores/SP/perfil")
        assert resp.status_code == 200
        assert resp.json()["nome_governador"] == "Gov SP"

    def test_perfil_governador_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(governadores.db_service, "get_perfil_governador", lambda uf: None)
        resp = client.get("/api/v1/governadores/XX/perfil")
        assert resp.status_code == 404

    def test_bancada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_bancada_deputados_uf",
            lambda uf, **kw: [{"deputado_id": 1, "nome": "Dep Federal"}],
        )
        resp = client.get("/api/v1/governadores/SP/bancada")
        assert resp.status_code == 200

    def test_emendas_estado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_emendas_estado",
            lambda uf, **kw: {
                "uf": "SP",
                "total_emendas": 100,
                "emendas": [],
                "por_parlamentar": [],
            },
        )
        resp = client.get("/api/v1/governadores/SP/emendas?ano=2024")
        assert resp.status_code == 200

    def test_financeiro(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_financeiro_estado",
            lambda uf: {"uf": "SP", "receitas_correntes": 1e9},
        )
        resp = client.get("/api/v1/governadores/SP/financeiro")
        assert resp.status_code == 200

    def test_municipios_estado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import governadores

        monkeypatch.setattr(
            governadores.db_service,
            "get_municipios_por_estado",
            lambda uf, **kw: [{"municipio_nome": "São Paulo", "valor_total_emendas": 1e7}],
        )
        resp = client.get("/api/v1/governadores/SP/municipios")
        assert resp.status_code == 200


# ===========================================================================
# ROOT — GET /
# ===========================================================================


class TestRootRoute:
    """Endpoint raiz sem fixtures (não depende de DB)."""

    def test_root_no_index(self) -> None:
        """GET / — retorna JSON (se sem index.html) ou HTML (se existir)."""
        from pathlib import Path

        index_path = (
            Path(__file__).resolve().parent.parent / "src" / "api" / "static" / "index.html"
        )
        resp = client.get("/")
        assert resp.status_code == 200
        if index_path.exists():
            assert "text/html" in resp.headers["content-type"]
        else:
            data = resp.json()
            assert "API TransfereGov rodando" in data["message"]

    def test_root_swagger(self) -> None:
        """GET /docs — OpenAPI UI."""
        resp = client.get("/docs")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_root_openapi_json(self) -> None:
        """GET /openapi.json — schema OpenAPI."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert (
            resp.json()["info"]["title"]
            == "TransfereGov — Painel de Inteligência Parlamentar & Municipal"
        )
