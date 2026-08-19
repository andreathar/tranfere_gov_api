"""Testes de invariante para QUERY_CHUNK_FILTER / QUERIES_TEMATICAS (rag_persona.py).

Regressão da revisão de processo 2026-08-17 (docs/decision_reviews.md): o dict
QUERY_CHUNK_FILTER e a lista QUERIES_TEMATICAS eram duas estruturas paralelas
mantidas por posição — 7 dos 15 índices ficaram desalinhados (cada query
temática filtrava por um tipo de chunk semanticamente diferente do que ela
própria buscava, ex: query sobre "risco judicial" filtrava COMPRAS_MUNICIPIO).
Isso já tinha acontecido antes de forma diferente (fix 2026-07-31: 7 tipos de
chunk nunca alcançados por nenhuma query) sem nenhum teste protegendo contra
recorrência.

O fix estrutural (rag_persona.py) unificou as duas listas paralelas numa única
_QUERIES_TEMATICAS_E_FILTROS — QUERIES_TEMATICAS e QUERY_CHUNK_FILTER agora só
são derivados dela, então a classe "editei um lado e esqueci do outro" fica
impossível por construção. Os testes abaixo cobrem o que ainda pode dar
errado: um tipo de chunk indexado que nenhuma query alcança, e um erro de
digitação na hora de escrever o PAR query+filtro (a derivação em si não pega
isso — só uma checagem semântica pega).
"""

from src.enrichers.rag_persona import QUERIES_TEMATICAS, QUERY_CHUNK_FILTER
from src.enrichers.rag_qdrant_indexer import CHUNK_EXTRACTORS


def test_todos_os_chunk_types_indexados_sao_alcancaveis() -> None:
    """Cada tipo de chunk realmente indexado (CHUNK_EXTRACTORS, fonte canônica)
    deve aparecer em pelo menos uma entrada de QUERY_CHUNK_FILTER — senão fica
    fora do contexto do dossiê mesmo quando existe no Qdrant (bug 2026-07-31)."""
    tipos_indexados = {tipo.upper() for tipo in CHUNK_EXTRACTORS}
    tipos_no_filtro: set[str] = set()
    for tipos in QUERY_CHUNK_FILTER.values():
        tipos_no_filtro.update(tipos)

    faltando = tipos_indexados - tipos_no_filtro
    assert not faltando, (
        f"Tipos de chunk indexados sem nenhuma query que os alcance: {sorted(faltando)}"
    )


def test_query_chunk_filter_cobre_todos_os_indices_de_queries_tematicas() -> None:
    """Toda query em QUERIES_TEMATICAS deve ter uma entrada correspondente em
    QUERY_CHUNK_FILTER (mesmo índice) — um índice sem entrada faz a busca
    ficar irrestrita silenciosamente, sem sinalização. Garantido por
    construção agora (derivação de uma única lista), mas mantido como rede de
    segurança caso a derivação mude no futuro."""
    assert len(QUERIES_TEMATICAS) == len(QUERY_CHUNK_FILTER)
    for idx in range(len(QUERIES_TEMATICAS)):
        assert idx in QUERY_CHUNK_FILTER, (
            f"QUERIES_TEMATICAS[{idx}] não tem entrada correspondente em "
            f"QUERY_CHUNK_FILTER — busca ficaria irrestrita (chunk_types=None)."
        )


def test_query_chunk_filter_alinhamento_semantico() -> None:
    """Checa a correspondência SEMÂNTICA entre cada query e seu filtro —
    diferente de comparar contra uma cópia hardcoded (que não pegaria um erro
    de digitação no próprio par), aqui cada âncora garante que uma
    palavra-chave da query realmente aparece no tipo de chunk que ela filtra.
    Cobre exatamente os 7 pares que estavam trocados antes do fix de 2026-08-17.
    """
    ancoras: list[tuple[str, str]] = [
        ("voto", "VOTO"),
        ("proposicoes legislativas", "PROPOSICAO"),
        ("emendas parlamentares pix", "EMENDA"),
        ("emendas discricionarias", "EMENDA_DISCRICIONARIA"),
        ("resumo consolidado", "PARLAMENTAR_RESUMO"),
        ("financeiros municipais", "MUNICIPIO_FINANCEIRO"),
        ("governo estadual", "ESTADO_FINANCEIRO"),
        ("demograficos ibge", "DEMOGRAFIA_MUNICIPIO"),
        ("saude e educacao", "INDICADORES_SOCIAIS"),
        ("repasses fnde", "FNDE_REPASSES"),
        ("conexao politica local", "CONEXAO_POLITICA"),
        ("risco judicial", "RISCO_JUDICIAL"),
        ("compras publicas", "COMPRAS_MUNICIPIO"),
        ("discursos de plenario", "DISCURSO_PLENARIO"),
    ]
    for palavra_chave, tipo_esperado in ancoras:
        idx = next(
            i
            for i, q in enumerate(QUERIES_TEMATICAS)
            if palavra_chave in q.lower()
        )
        tipos = QUERY_CHUNK_FILTER[idx]
        assert tipo_esperado in tipos, (
            f"Query {idx} ('{palavra_chave}') filtra {tipos}, esperava conter "
            f"'{tipo_esperado}' — desalinhamento semântico query <-> filtro."
        )
