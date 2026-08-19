"""
Testes unitários para o ReasoningEngine (otimizações cognitivas do Cognee).
"""

from src.mcp.reasoning_engine import ReasoningEngine


def test_reasoning_engine_pre_cognify_synthesis():
    engine = ReasoningEngine()
    input_text = """
    Linha 1: porta 8080 em uso pelo LocalAI
    Linha 2: porta 8080 em uso pelo LocalAI
    Linha 3: porta 5432 em uso pelo Postgres
    """
    synthesized = engine.pre_cognify_synthesis(input_text, domain="infrastructure")
    assert "### [Cognified System Knowledge - Domain: infrastructure]" in synthesized
    assert synthesized.count("porta 8080 em uso pelo LocalAI") == 1
    assert "porta 5432 em uso pelo Postgres" in synthesized


def test_reasoning_engine_validate_ontology():
    engine = ReasoningEngine()
    valid_ttl = """
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    :Service a owl:Class .
    """
    res = engine.validate_ontology_consistency(valid_ttl)
    assert res["valid"] is True
    assert res["witness"] == "Formal consistency verified"

    invalid_ttl = "service name is LocalAI"
    res_invalid = engine.validate_ontology_consistency(invalid_ttl)
    assert res_invalid["valid"] is False
    assert len(res_invalid["issues"]) > 0


def test_reasoning_engine_route_cognee_query():
    engine = ReasoningEngine()
    route_complex = engine.route_cognee_query("Qual a relação e dependência entre o LocalAI e o Cognee?")
    assert route_complex["search_type"] == "GRAPH_COMPLETION"
    assert route_complex["target_instance"] == "cloud_tenant"

    route_simple = engine.route_cognee_query("Qual a porta do Postgres?")
    assert route_simple["search_type"] == "CHUNKS"
    assert route_simple["target_instance"] == "workspace_bare_metal"


def test_reasoning_engine_devil_advocate():
    engine = ReasoningEngine()
    bad_proposal = "Vamos rodar dois modelos simultaneos na GPU para acelerar"
    res_bad = engine.devil_advocate_adr(bad_proposal)
    assert res_bad["approved"] is False
    assert any("VIOLAÇÃO DE VRAM" in flag for flag in res_bad["flags"])

    good_proposal = "Vamos utilizar PagedAttention no vLLM com modelo único residente"
    res_good = engine.devil_advocate_adr(good_proposal)
    assert res_good["approved"] is True


def test_reasoning_engine_hindsight_postmortem():
    engine = ReasoningEngine()
    log = "Error: Context size has been exceeded in GRAPH_COMPLETION call"
    postmortem = engine.hindsight_postmortem(log)
    assert "Estouro de capacidade de VRAM" in postmortem["root_cause"]
    assert "EMBEDDING_BATCH_SIZE=5" in postmortem["actionable_rule"]


def test_should_persist_memory_discards_domain_data():
    engine = ReasoningEngine()
    res = engine.should_persist_memory("CPF de 123.456.789-00 registrado no benefício")
    assert res["destination"] == "discard"
    assert res["requires_review"] is True

    res_beneficiario = engine.should_persist_memory("Beneficiário: Maria da Silva, município X")
    assert res_beneficiario["destination"] == "discard"


def test_should_persist_memory_discards_secrets():
    engine = ReasoningEngine()
    res = engine.should_persist_memory("A configuração usa API_KEY=sk-abc123 no serviço remoto")
    assert res["destination"] == "discard"
    assert res["requires_review"] is True


def test_should_persist_memory_routes_transient_noise_to_session():
    engine = ReasoningEngine()
    res = engine.should_persist_memory("stdout: build ok")
    assert res["destination"] == "session"
    assert res["requires_review"] is False


def test_should_persist_memory_routes_stable_decisions_to_cognee():
    engine = ReasoningEngine()
    res = engine.should_persist_memory(
        "Decisão: migrar embeddings para LocalAI local por causa raiz de custo do gateway Zen.",
        source="ADR-042",
    )
    assert res["destination"] == "cognee"


def test_should_persist_memory_short_decision_still_routes_to_cognee():
    """Regressão 2026-08-17 (docs/decision_reviews.md): o filtro de texto curto
    (<80 chars) rodava antes do filtro de marcador estável, então uma decisão
    concisa (o estilo normal de entrada de decision_reviews.md) caía em
    'session' em vez de 'cognee' só por ser curta."""
    engine = ReasoningEngine()
    texto = "Decisão: usar INTEGER para municipio_ibge_id, não KEYWORD."
    assert len(texto) < 80
    res = engine.should_persist_memory(texto)
    assert res["destination"] == "cognee"
    assert res["requires_review"] is False


def test_should_persist_memory_routes_reference_docs_to_qdrant():
    engine = ReasoningEngine()
    res = engine.should_persist_memory(
        "## Endpoint: POST /api/v1/remember\nParâmetros: dataset_name, ontology_key\nExemplo: curl ..."
    )
    assert res["destination"] == "qdrant"


def test_should_persist_memory_default_is_low_confidence_and_flagged():
    engine = ReasoningEngine()
    res = engine.should_persist_memory(
        "O serviço de reasoning.services concede graph-of-thought mas não decision-matrix no plano trial."
    )
    assert res["destination"] == "cognee"
    assert res["confidence"] < 0.5
    assert res["requires_review"] is True


def test_should_persist_memory_empty_fact_is_discarded():
    engine = ReasoningEngine()
    res = engine.should_persist_memory("   ")
    assert res["destination"] == "discard"
    assert res["requires_review"] is False
