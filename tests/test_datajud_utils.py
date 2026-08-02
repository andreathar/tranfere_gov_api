"""Testes do parser de respostas DataJud (src/datajud_utils.py).

Garante que a resposta STRING da tool `datajud_buscar_processos` do mcp-brasil
(markdown/mensagem) seja convertida em (total_processos, dados_estruturados) —
regressao do falso-zero que zerava o chunk `risco_judicial` no Qdrant.
"""

from __future__ import annotations

import pytest

from src.datajud_utils import parse_datajud_response

MD_TABLE = """Processos encontrados no TJSP (3 resultados):

| Número | Classe | Assunto | Órgão Julgador | Ajuizamento |
| --- | --- | --- | --- | --- |
| 0001234-56.2024.8.26.0100 | Execução de Título | Cobrança | 1ª Vara Cível | 2024-01-15 |
| 0009876-54.2023.8.26.0100 | Procedimento Comum | Indenização | 2ª Vara Cível | 2023-08-22 |
| 0005555-55.2022.8.26.0100 | — | — | — | — |"""


def test_markdown_table_parse():
    total, dados = parse_datajud_response(MD_TABLE)
    assert total == 3
    procs = dados["processos"]
    assert len(procs) == 3
    # chaves lidas pelo indexador Qdrant (_extract_risco_judicial)
    assert procs[0]["classe"] == "Execução de Título"
    assert procs[0]["assunto"] == "Cobrança"
    assert procs[0]["dataDistribuicao"] == "2024-01-15"
    # linha com valores vazios ("—") nao pode virar chunk fantasma
    assert procs[2]["classe"] == "—"  # valor cru preservado, mas linha existe


def test_nenhum_processo_legitimo():
    total, dados = parse_datajud_response("Nenhum processo encontrado para '123' no TJSP.")
    assert total == 0
    assert "message" in dados


def test_unknown_tool_nao_e_sucesso():
    total, dados = parse_datajud_response("Unknown tool: 'datajud_buscar_processos'")
    assert total == 0
    assert "Unknown tool" in dados["message"]


def test_json_list_backward_compat():
    total, dados = parse_datajud_response('[{"classe": "A"}, {"classe": "B"}]')
    assert total == 2
    assert len(dados["processos"]) == 2


def test_json_dict_estruturado():
    total, dados = parse_datajud_response('{"processos": [{"classe": "A"}]}')
    assert total == 1
    assert len(dados["processos"]) == 1


def test_vazio_e_none():
    assert parse_datajud_response(None) == (0, {})
    assert parse_datajud_response("") == (0, {})


@pytest.mark.parametrize(
    "resposta",
    [
        "Rate limited. Try again later.",
        "Erro interno do servidor.",
        "{}",
    ],
)
def test_outras_strings_sem_total_falso(resposta):
    total, dados = parse_datajud_response(resposta)
    assert total == 0
    # "{}" vira dict vazio (sem message); demais carregam mensagem de erro
    assert not dados or "message" in dados
