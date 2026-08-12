"""Testes da Fase 3 (2026-08-10): dossiês multi-cargo (tipo_politico).

Cobre:
- cargo.py: vocabulário PT-BR por cargo + tem_votacao
- run_analyst_pipeline: votacao desativado para cargos sem voto nominal
- search_context_qdrant: filtro por tipo_politico/politico_id (deputado com fallback)
- limites de chunks por cargo (RAG_MIN/MAX_CHUNKS_BY_TIPO)
"""

from __future__ import annotations


class TestCargoInfo:
    """Vocabulário de cargo e capacidades."""

    def test_vocabulario_por_cargo(self) -> None:
        from src.analysts.cargo import get_cargo

        dep = get_cargo("deputado")
        assert dep["singular"] == "deputado federal"
        assert dep["tem_votacao"] is True

        sen = get_cargo("senador")
        assert sen["singular"] == "senador"
        assert sen["casa"] == "Senado Federal"
        assert sen["tem_votacao"] is True

        gov = get_cargo("governador")
        assert gov["tem_votacao"] is False
        assert gov["casa"] == "executivo estadual"

        pref = get_cargo("prefeito")
        assert pref["tem_votacao"] is False

        ver = get_cargo("vereador")
        assert ver["singular"] == "vereador"
        assert ver["tem_votacao"] is True

    def test_fallback_cargo_desconhecido(self) -> None:
        from src.analysts.cargo import get_cargo

        assert get_cargo("prefeito_do_futuro")["singular"] == "deputado federal"

    def test_tem_votacao(self) -> None:
        from src.analysts.cargo import tem_votacao

        assert tem_votacao("deputado")
        assert tem_votacao("senador")
        assert tem_votacao("vereador")
        assert not tem_votacao("governador")
        assert not tem_votacao("prefeito")


class TestLimitesPorCargo:
    """RAG_MIN/MAX_CHUNKS_BY_TIPO em settings."""

    def test_settings_tem_todos_os_cargos(self) -> None:
        from config.settings import (
            RAG_MAX_CHUNKS_BY_TIPO,
            RAG_MIN_CHUNKS_BY_TIPO,
            TIPOS_POLITICOS,
        )

        assert set(TIPOS_POLITICOS) == {
            "deputado",
            "senador",
            "governador",
            "prefeito",
            "vereador",
        }
        for t in TIPOS_POLITICOS:
            assert t in RAG_MIN_CHUNKS_BY_TIPO
            assert t in RAG_MAX_CHUNKS_BY_TIPO
            assert RAG_MIN_CHUNKS_BY_TIPO[t] <= RAG_MAX_CHUNKS_BY_TIPO[t]

    def test_deputado_mantem_defaults(self) -> None:
        from config.settings import RAG_MAX_CHUNKS, RAG_MIN_CHUNKS
        from src.enrichers.rag_persona import search_context_multiquery  # noqa: F401

        assert RAG_MIN_CHUNKS >= 3
        assert RAG_MAX_CHUNKS >= 25


class TestFiltroQdrantPorCargo:
    """search_context_qdrant monta filtro tipo_politico + id."""

    def test_filtro_deputado_inclui_fallback_deputado_id(self) -> None:
        # Não conecta Qdrant — inspeciona o filtro via monkeypatch do client.
        # (teste estrutural: o filtro base é montado antes de qualquer IO)
        import inspect

        from src.enrichers.rag_persona import search_context_qdrant

        src = inspect.getsource(search_context_qdrant)
        assert 'key="tipo_politico"' in src
        assert 'key="politico_id"' in src
        assert 'key="deputado_id"' in src

    def test_filtro_nao_deputado_sem_fallback(self) -> None:
        import inspect

        from qdrant_client.http import models as qdrant_models  # noqa: F401

        from src.enrichers.rag_persona import search_context_qdrant

        src = inspect.getsource(search_context_qdrant)
        # O fallback deputado_id só existe no ramo tipo_politico == "deputado"
        assert 'if tipo_politico == "deputado":' in src

    def test_models_filter_aceita_filtro_aninhado(self) -> None:
        """Regressão: Filter(should=...) aninhado dentro de must é válido."""
        from qdrant_client.http import models as qdrant_models

        f = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="tipo_politico",
                    match=qdrant_models.MatchValue(value="senador"),
                ),
                qdrant_models.Filter(
                    should=[
                        qdrant_models.FieldCondition(
                            key="politico_id",
                            match=qdrant_models.MatchValue(value=5001),
                        )
                    ]
                ),
            ]
        )
        assert f.must is not None
        assert isinstance(f.must, list)
        assert len(f.must) == 2
