"""
Testes dos novos endpoints (Senadores, Financeiro, Discursos, Alertas,
Discricionárias, Votações recentes, Indicadores municipais).

Usa mocking de db_service — sem dependência de PostgreSQL nem APIs externas.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("TRANSPARENCIA_API_KEY", "test-key")

from src.api.app import app  # noqa: E402

client = TestClient(app)


# ===========================================================================
# SENADORES — /api/v1/senadores/
# ===========================================================================


class TestSenadoresRoutes:
    def test_search_senadores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import senadores

        monkeypatch.setattr(
            senadores.db_service,
            "search_senadores",
            lambda q: [
                {
                    "senador_codigo": 5672,
                    "nome_parlamentar": "Alan Rick",
                    "sigla_partido": "REPUBLICANOS",
                    "uf": "AC",
                }
            ],
        )
        resp = client.get("/api/v1/senadores/search?q=rick")
        assert resp.status_code == 200
        assert resp.json()[0]["nome_parlamentar"] == "Alan Rick"

    def test_search_min_length(self) -> None:
        """Busca com < 2 caracteres → 422 (Query min_length)."""
        resp = client.get("/api/v1/senadores/search?q=a")
        assert resp.status_code == 422

    def test_ranking_senadores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import senadores

        monkeypatch.setattr(
            senadores.db_service,
            "get_ranking_senadores",
            lambda limit=30, partido=None, uf=None: [
                {"senador_codigo": 5982, "atividade_total": 0}
            ],
        )
        resp = client.get("/api/v1/senadores/ranking?limit=10&partido=MDB")
        assert resp.status_code == 200
        assert resp.json()[0]["senador_codigo"] == 5982

    def test_senadores_por_partido(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import senadores

        monkeypatch.setattr(
            senadores.db_service,
            "get_senadores_por_partido",
            lambda: [{"sigla_partido": "MDB", "total": 11}],
        )
        resp = client.get("/api/v1/senadores/por-partido")
        assert resp.status_code == 200
        assert resp.json()[0]["total"] == 11

    def test_perfil_senador_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import senadores

        monkeypatch.setattr(senadores.db_service, "get_perfil_senador", lambda _: None)
        resp = client.get("/api/v1/senadores/99999/perfil")
        assert resp.status_code == 404

    def test_perfil_senador_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import senadores

        monkeypatch.setattr(
            senadores.db_service,
            "get_perfil_senador",
            lambda _: {
                "senador_codigo": 1,
                "nome_parlamentar": "Senador X",
                "situacao": "EM EXERCÍCIO",
            },
        )
        resp = client.get("/api/v1/senadores/1/perfil")
        assert resp.status_code == 200
        assert resp.json()["situacao"] == "EM EXERCÍCIO"


# ===========================================================================
# FINANCEIRO — /api/v1/financeiro/
# ===========================================================================


class TestFinanceiroRoutes:
    def test_estados(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import financeiro

        monkeypatch.setattr(
            financeiro.db_service,
            "get_financeiro_estados",
            lambda exercicio=None: [{"uf": "SP", "exercicio": 2025, "despesas_totais": 1.0}],
        )
        resp = client.get("/api/v1/financeiro/estados")
        assert resp.status_code == 200
        assert resp.json()[0]["uf"] == "SP"

    def test_estado_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import financeiro

        monkeypatch.setattr(financeiro.db_service, "get_financeiro_estado", lambda _: None)
        resp = client.get("/api/v1/financeiro/estado/ZZ")
        assert resp.status_code == 404

    def test_municipios_uf_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import financeiro

        captured: dict = {}

        def fake(**kwargs):
            captured.update(kwargs)
            return [{"municipio_id": 3501608, "nome": "Americana"}]

        monkeypatch.setattr(financeiro.db_service, "get_financeiro_municipios", fake)
        resp = client.get("/api/v1/financeiro/municipios?uf=sp&order_by=populacao")
        assert resp.status_code == 200
        assert captured["uf"] == "sp"  # normalização fica no db_service
        assert captured["order_by"] == "populacao"

    def test_municipio_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import financeiro

        monkeypatch.setattr(financeiro.db_service, "get_financeiro_municipio", lambda _: None)
        resp = client.get("/api/v1/financeiro/municipio/0")
        assert resp.status_code == 404

    def test_comparativo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import financeiro

        monkeypatch.setattr(
            financeiro.db_service,
            "get_comparativo_emendas_financeiro",
            lambda uf=None: [{"uf": "AC", "valor_emendas": 887078446.09}],
        )
        resp = client.get("/api/v1/financeiro/comparativo?uf=AC")
        assert resp.status_code == 200
        assert resp.json()[0]["valor_emendas"] > 0


# ===========================================================================
# DEPUTADO — discursos, alertas, discricionárias
# ===========================================================================


class TestDeputadoNovosRecursos:
    def test_discursos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "get_discursos_deputado",
            lambda deputado_id, limit=50, tipo=None: [
                {
                    "id": 6171,
                    "data_hora_inicio": "2026-07-14T18:20:00",
                    "tipo_discurso": "COMO LÍDER",
                    "sumario": "...",
                }
            ],
        )
        resp = client.get("/api/v1/deputados/204407/discursos?limit=5")
        assert resp.status_code == 200
        assert resp.json()[0]["tipo_discurso"] == "COMO LÍDER"

    def test_alertas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "get_alertas_deputado",
            lambda deputado_id: [{"alerta_id": 38, "nivel_relevancia": 1, "notificado": False}],
        )
        resp = client.get("/api/v1/deputados/73579/alertas")
        assert resp.status_code == 200
        assert resp.json()[0]["alerta_id"] == 38

    def test_emendas_discricionarias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import deputados

        monkeypatch.setattr(
            deputados.db_service,
            "get_emendas_discricionarias_deputado",
            lambda deputado_id, ano=None, limit=100: [
                {"codigo_emenda": "202639840001", "ano": 2026, "valor_total": 5031503.0}
            ],
        )
        resp = client.get("/api/v1/deputados/204407/emendas-discricionarias?ano=2026")
        assert resp.status_code == 200
        assert resp.json()[0]["valor_total"] == 5031503.0


# ===========================================================================
# ANALYTICS — votações recentes
# ===========================================================================


class TestVotacoesRecentes:
    def test_votacoes_recentes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import analytics

        monkeypatch.setattr(
            analytics.db_service,
            "get_votacoes_recentes",
            lambda ano=None, limit=20: [
                {
                    "votacao_id": "2638483-34",
                    "data_registro": "2026-07-14",
                    "descricao": "Rejeitada",
                    "aprovacao": False,
                }
            ],
        )
        resp = client.get("/api/v1/analytics/votacoes-recentes?limit=5")
        assert resp.status_code == 200
        assert resp.json()[0]["votacao_id"] == "2638483-34"


# ===========================================================================
# MUNICÍPIOS — indicadores locais
# ===========================================================================


class TestMunicipiosIndicadores:
    def test_indicadores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import municipios

        monkeypatch.setattr(
            municipios.db_service,
            "get_indicadores_municipio",
            lambda _: {
                "municipio_id": 3501608,
                "nome": "Americana",
                "total_estabelecimentos": 34,
                "ubs": 20,
            },
        )
        resp = client.get("/api/v1/municipios/3501608/indicadores")
        assert resp.status_code == 200
        assert resp.json()["ubs"] == 20

    def test_indicadores_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import municipios

        monkeypatch.setattr(municipios.db_service, "get_indicadores_municipio", lambda _: None)
        resp = client.get("/api/v1/municipios/0/indicadores")
        assert resp.status_code == 404

    def test_financeiro_municipio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.api.routes import municipios

        monkeypatch.setattr(
            municipios.db_service,
            "get_financeiro_municipio",
            lambda _: {
                "municipio_id": 3501608,
                "nome": "Americana",
                "despesas_totais": 1592595003.39,
            },
        )
        resp = client.get("/api/v1/municipios/3501608/financeiro")
        assert resp.status_code == 200
        assert resp.json()["despesas_totais"] == 1592595003.39


# ===========================================================================
# PERFORMANCE — GZip e cache de estáticos
# ===========================================================================


class TestPerformanceHeaders:
    def test_gzip_compressao(self) -> None:
        """Respostas JSON grandes são comprimidas com gzip."""
        resp = client.get("/api/v1/financeiro/estados", headers={"Accept-Encoding": "gzip"})
        assert resp.status_code == 200
        assert resp.headers.get("content-encoding") == "gzip"

    def test_static_cache_immutable(self) -> None:
        """Estáticos servidos com Cache-Control imutável (cache-busting via ?v=)."""
        resp = client.get("/static/style.css")
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "public, max-age=31536000, immutable"
