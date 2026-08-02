"""datajud_utils: parse de respostas da ferramenta DataJud (mcp-brasil).

A tool `datajud_buscar_processos` do mcp-brasil retorna STRING — tabela
markdown com os processos, mensagem de "Nenhum processo encontrado" ou erro —
NUNCA JSON. Versoes antigas do enricher faziam `json.loads(res)` que falhava
silenciosamente, gravando `total_processos = 0` e a resposta crua em
`processos_detalhes`, o que zerava o chunk type `risco_judicial` no Qdrant.

Este modulo converte qualquer formato de resposta em
`(total_processos, dados_estruturados)` para gravacao em
`beneficiario_processos`, com o formato lido pelo indexador Qdrant
(`_extract_risco_judicial` espera `{"processos": [{classe, assunto, ...}]}`).
"""

from __future__ import annotations

import json
import re
from typing import Any

# Colunas da tabela markdown retornada pela tool (ordem fixa em mcp-brasil):
# | Número | Classe | Assunto | Órgão Julgador | Ajuizamento |
_MD_HEADERS = ("Número", "Classe", "Assunto", "Órgão Julgador", "Ajuizamento")

# Chaves que o indexador Qdrant (_extract_risco_judicial) le nos itens
_ROW_KEYS = (
    "numero",
    "classe",
    "assunto",
    "orgao_julgador",
    "dataDistribuicao",  # lida pelo indexador (dataDistribuicao/dataistribuicao/data)
)


def parse_datajud_response(res: Any) -> tuple[int, dict[str, Any]]:
    """Converte resposta da tool DataJud em `(total_processos, dados)`.

    Formatos aceitos:
    - `None`/vazio                          -> (0, {})
    - JSON list                             -> (len, {"processos": [...]})
    - JSON dict (ex.: erro estruturado)     -> (0, dict)
    - "Nenhum processo encontrado ..."      -> (0, {"message": res})  # legitimo
    - Tabela markdown "(N resultados)"      -> (N, {"processos": [...]})
    - Outra string (erro/rate limit)        -> (0, {"message": res})
    """
    if not res:
        return 0, {}

    if isinstance(res, (list, dict)):
        data: Any = res
    elif isinstance(res, str):
        stripped = res.strip()
        if stripped.startswith(("{", "[")):
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                return 0, {"message": res}
        elif "Nenhum processo encontrado" in stripped:
            # Resposta legitima de zero processos — nao e erro
            return 0, {"message": stripped}
        elif "resultados" in stripped and "|" in stripped:
            return _parse_markdown_table(stripped)
        else:
            return 0, {"message": stripped}
    else:
        return 0, {"message": str(res)}

    if isinstance(data, list):
        return len(data), {"processos": data, "fonte": "datajud-mcp"}
    if isinstance(data, dict):
        # dict pode ja vir estruturado (ex.: {"processos": [...]})
        procs = data.get("processos") or data.get("data") or []
        total = len(procs) if isinstance(procs, list) else 0
        return total, data
    return 0, {"message": str(data)}


def _parse_markdown_table(text: str) -> tuple[int, dict[str, Any]]:
    """Converte a tabela markdown do DataJud em lista estruturada de processos.

    Exemplo de entrada:
        Processos encontrados no TJSP (3 resultados):

        | Número | Classe | Assunto | Órgão Julgador | Ajuizamento |
        | --- | --- | --- | --- | --- |
        | 0001234-56.2024.8.26.0100 | Execução de Título | Cobrança | ... | 2024-01-15 |
    """
    m = re.search(r"\((\d+)\s+resultados?\)", text)
    declared = int(m.group(1)) if m else 0

    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Pula linha do header e linha separadora (---)
        if any(h in cells for h in _MD_HEADERS):
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        if len(cells) < len(_MD_HEADERS):
            continue
        numero, classe, assunto, orgao, ajuiz = cells[:5]
        if not any((numero, classe, assunto, orgao, ajuiz)):
            continue
        rows.append(
            {
                "numero": numero,
                "classe": classe,
                "assunto": assunto,
                "orgao_julgador": orgao,
                "dataDistribuicao": ajuiz,
                "data_ajuizamento": ajuiz,  # alias legivel
            }
        )

    total = declared if declared > 0 else len(rows)
    return total, {"processos": rows, "fonte": "datajud-mcp", "total": total}
