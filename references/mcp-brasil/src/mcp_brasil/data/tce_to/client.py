"""HTTP client for the TCE-TO e-Contas API.

IMPORTANT: The API requires `Accept: application/json` header.
Without it, it returns PHP debug output (print_r format).

Endpoints:
    - /pessoas?nome=X&pagina=N&tamanho=N → buscar_pessoas
    - /processo/{numero}/{ano}            → consultar_processo
    - /pautas?ordem=DESC&tamanho=N        → listar_pautas
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PAUTAS_URL, PESSOAS_URL, PROCESSO_URL
from .schemas import Pauta, Pessoa, Processo, ProcessoResumo


def _parse_processos(procs: list[dict[str, Any]]) -> list[ProcessoResumo]:
    """Parse a list of process dicts into ProcessoResumo models."""
    return [
        ProcessoResumo(
            numero_ano=p.get("numero_ano"),
            assunto=p.get("assunto"),
            classe_assunto=p.get("classe_assunto"),
            entidade_origem=p.get("entidade_origem"),
            entidade_origem_municipio=p.get("entidade_origem_municipio"),
            data_entrada=p.get("data_entrada"),
            departamento_atual=p.get("departamento_atual"),
        )
        for p in procs
    ]


async def buscar_pessoas(
    *,
    nome: str | None = None,
    codigo: str | None = None,
    pagina: int = 1,
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> list[Pessoa]:
    """Search persons with processes at TCE-TO.

    At least one filter (nome or codigo) is required by the API.

    Args:
        nome: Person name (partial search).
        codigo: CPF (partial search).
        pagina: Page number (1-based).
        tamanho: Results per page.
    """
    params: dict[str, Any] = {
        "pagina": pagina,
        "tamanho": min(tamanho, MAX_PAGE_SIZE),
    }
    if nome:
        params["nome"] = nome
    if codigo:
        params["codigo"] = codigo

    data: list[dict[str, Any]] = await http_get(PESSOAS_URL, params=params)
    return [
        Pessoa(
            id=item.get("id"),
            nome=item.get("nome"),
            codigo=item.get("codigo"),
            processos=_parse_processos(item.get("processos", [])),
        )
        for item in data
    ]


async def consultar_processo(*, numero: int, ano: int) -> Processo | None:
    """Fetch details for a specific process.

    Args:
        numero: Process number.
        ano: Process year.

    Returns:
        Process details or None if not found.
    """
    url = f"{PROCESSO_URL}/{numero}/{ano}"
    data: dict[str, Any] = await http_get(url)

    if "error_message" in data:
        return None

    return Processo(
        numero_ano=data.get("numero_ano"),
        assunto=data.get("assunto"),
        classe_assunto=data.get("classe_assunto"),
        entidade_origem=data.get("entidade_origem"),
        entidade_origem_municipio=data.get("entidade_origem_municipio"),
        entidade_origem_cnpj=data.get("entidade_origem_cnpj"),
        data_entrada=data.get("data_entrada"),
        departamento_atual=data.get("departamento_atual"),
        complemento=data.get("complemento"),
        distribuicao=data.get("distribuicao"),
        eletronico=data.get("eletronico"),
        sigiloso=data.get("sigiloso"),
    )


async def listar_pautas(
    *,
    ordem: str = "DESC",
    tamanho: int = DEFAULT_PAGE_SIZE,
) -> list[Pauta]:
    """Fetch session agendas from TCE-TO.

    Note: The pagina parameter is broken server-side (ignored).
    Only ordem and tamanho work.

    Args:
        ordem: Sort order (ASC or DESC).
        tamanho: Number of results to return.
    """
    params: dict[str, Any] = {
        "ordem": ordem,
        "tamanho": min(tamanho, MAX_PAGE_SIZE),
    }
    data: dict[str, Any] = await http_get(PAUTAS_URL, params=params)
    items: list[dict[str, Any]] = data.get("pautas", [])

    return [
        Pauta(
            data=item.get("data"),
            hora=item.get("hora"),
            tipo=item.get("tipo"),
            origem=item.get("origem"),
            url=item.get("url"),
        )
        for item in items
    ]
