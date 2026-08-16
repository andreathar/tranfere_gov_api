"""HTTP client for the TCE-PI Portal da Cidadania API.

Base: https://sistemas.tce.pi.gov.br/api/portaldacidadania
Auth: none
Format: JSON arrays/objects
"""

from __future__ import annotations

from mcp_brasil._shared.http_client import http_get

from .constants import (
    CREDORES_URL,
    DESPESAS_TOTAL_URL,
    DESPESAS_URL,
    ORGAOS_URL,
    PREFEITURAS_URL,
    RECEITAS_TOTAL_URL,
    RECEITAS_URL,
)
from .schemas import (
    Credor,
    DespesaAnual,
    DespesaFuncao,
    Gestor,
    Orgao,
    Prefeitura,
    ReceitaAnual,
    ReceitaDetalhe,
)


async def listar_prefeituras() -> list[Prefeitura]:
    """List all 224 municipalities of Piauí."""
    data = await http_get(PREFEITURAS_URL)
    return [Prefeitura(**item) for item in data]


async def buscar_prefeitura(nome: str) -> list[Prefeitura]:
    """Search municipalities by name (partial match)."""
    url = f"{PREFEITURAS_URL}/{nome}"
    data = await http_get(url)
    if isinstance(data, dict):
        return [Prefeitura(**data)]
    return [Prefeitura(**item) for item in data]


async def consultar_gestor(id_prefeitura: int) -> Gestor | None:
    """Get the current mayor of a municipality."""
    url = f"{PREFEITURAS_URL}/{id_prefeitura}/gestor"
    data = await http_get(url)
    if not data or (isinstance(data, dict) and "err" in data):
        return None
    return Gestor(**data)


async def consultar_despesas(id_unidade: int) -> list[DespesaAnual]:
    """Get annual expense history for a municipality."""
    url = f"{DESPESAS_URL}/{id_unidade}"
    data = await http_get(url)
    return [DespesaAnual(**item) for item in data]


async def consultar_despesas_total() -> list[DespesaAnual]:
    """Get annual expense totals for the entire state."""
    data = await http_get(DESPESAS_TOTAL_URL)
    return [DespesaAnual(**item) for item in data]


async def consultar_despesas_por_funcao(id_unidade: int, exercicio: int) -> list[DespesaFuncao]:
    """Get expense breakdown by government function."""
    url = f"{DESPESAS_URL}/{id_unidade}/{exercicio}/porFuncao"
    data = await http_get(url)
    return [DespesaFuncao(**item) for item in data]


async def consultar_receitas(id_unidade: int, exercicio: int) -> list[ReceitaDetalhe]:
    """Get detailed revenues for a municipality in a given year."""
    url = f"{RECEITAS_URL}/{id_unidade}/{exercicio}"
    data = await http_get(url)
    return [ReceitaDetalhe(**item) for item in data]


async def consultar_receitas_total() -> list[ReceitaAnual]:
    """Get annual revenue totals for the entire state."""
    data = await http_get(RECEITAS_TOTAL_URL)
    return [ReceitaAnual(**item) for item in data]


async def listar_orgaos(exercicio: int) -> list[Orgao]:
    """List state organs for a given year."""
    url = f"{ORGAOS_URL}/{exercicio}"
    data = await http_get(url)
    return [Orgao(**item) for item in data]


async def consultar_credores(id_unidade: int, exercicio: int) -> list[Credor]:
    """Get top 10 creditors for a municipality in a given year."""
    url = f"{CREDORES_URL}/{id_unidade}/{exercicio}"
    data = await http_get(url)
    return [Credor(**item) for item in data]
