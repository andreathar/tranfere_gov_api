"""Testes para check_payload_index_health() (src/enrichers/rag_qdrant_indexer.py).

Regressão da revisão de processo 2026-08-17 (docs/decision_reviews.md): a coleção
Qdrant tinha um índice (municipio_ibge_id) criado com tipo KEYWORD enquanto os
dados reais eram INTEGER — o índice nunca casava com nenhum ponto (0 pontos
indexados apesar de 3.318+ pontos com o campo populado). politico_id/tipo_politico,
usados em toda busca desde a Fase 3 (multi-cargo), não tinham índice nenhum.
"""

from unittest.mock import MagicMock

from qdrant_client.http.models import CollectionInfo, PayloadIndexInfo, PayloadSchemaType

from src.enrichers.rag_qdrant_indexer import PAYLOAD_INDEXES, check_payload_index_health


def _fake_client(payload_schema: dict) -> MagicMock:
    info = MagicMock(spec=CollectionInfo)
    info.payload_schema = payload_schema
    client = MagicMock()
    client.get_collection.return_value = info
    return client


def test_saudavel_quando_todos_indices_presentes_com_tipo_certo() -> None:
    schema = {
        field: PayloadIndexInfo(data_type=tipo, params=None, points=10)
        for field, tipo in PAYLOAD_INDEXES
    }
    client = _fake_client(schema)
    assert check_payload_index_health(client) == []


def test_detecta_indice_ausente() -> None:
    schema = {
        field: PayloadIndexInfo(data_type=tipo, params=None, points=10)
        for field, tipo in PAYLOAD_INDEXES
        if field != "politico_id"
    }
    client = _fake_client(schema)
    problemas = check_payload_index_health(client)
    assert any("politico_id" in p and "sem índice" in p for p in problemas)


def test_detecta_mismatch_de_tipo() -> None:
    """Regressão exata do bug encontrado: municipio_ibge_id como KEYWORD, não INTEGER."""
    schema = {
        field: PayloadIndexInfo(data_type=tipo, params=None, points=10)
        for field, tipo in PAYLOAD_INDEXES
    }
    schema["municipio_ibge_id"] = PayloadIndexInfo(
        data_type=PayloadSchemaType.KEYWORD, params=None, points=0
    )
    client = _fake_client(schema)
    problemas = check_payload_index_health(client)
    assert any(
        "municipio_ibge_id" in p and "mismatch" in p.lower() for p in problemas
    )
