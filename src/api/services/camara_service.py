import time
from typing import Any

import httpx

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
CACHE_TTL = 3600
cache: dict[str, tuple[float, Any]] = {}


def get_from_cache(key: str) -> Any | None:
    if key in cache:
        timestamp, value = cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return value
        else:
            del cache[key]
    return None


def set_in_cache(key: str, value: Any):
    cache[key] = (time.time(), value)


async def _get_json(
    client: httpx.AsyncClient, endpoint: str, params: dict[str, Any] | None = None
) -> Any:
    url = f"{BASE_URL}{endpoint}"
    cache_key = f"{url}?{str(params)}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json().get("dados", response.json())
    set_in_cache(cache_key, data)
    return data


async def buscar_deputado(deputado_id: int) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await _get_json(client, f"/deputados/{deputado_id}")  # type: ignore[no-any-return]


async def search_deputados_api(nome: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        return await _get_json(client, "/deputados", params={"nome": nome})  # type: ignore[no-any-return]


async def listar_despesas(deputado_id: int, ano: int | None = None) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resultados: list[dict[str, Any]] = []
        pagina = 1
        params: dict[str, Any] = {"pagina": pagina, "itens": 100}
        if ano:
            params["ano"] = ano

        while len(resultados) < 500:
            params["pagina"] = pagina
            dados = await _get_json(client, f"/deputados/{deputado_id}/despesas", params=params)
            if not dados:
                break
            resultados.extend(dados)
            if len(dados) < 100:
                break
            pagina += 1

        return resultados[:500]


async def listar_orgaos(deputado_id: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        return await _get_json(client, f"/deputados/{deputado_id}/orgaos")  # type: ignore[no-any-return]


async def listar_votacoes(deputado_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """Busca votações de um deputado a partir do banco local (tabela votos_camara).

    A API da Câmara não possui endpoint /deputados/{id}/votacoes,
    portanto usamos a tabela local preenchida pelo enricher votacoes_camara.
    """
    from src.api.services.db_service import get_votacoes_deputado

    return get_votacoes_deputado(deputado_id, limit=limit)  # type: ignore[return-value]


async def listar_proposicoes(deputado_id: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        params: dict[str, Any] = {
            "idDeputadoAutor": deputado_id,
            "ordenarPor": "id",
            "ordem": "DESC",
        }
        return await _get_json(client, "/proposicoes", params=params)  # type: ignore[no-any-return]
