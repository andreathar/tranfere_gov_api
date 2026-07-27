"""
Rotas REST de Verbas FNDE (FastAPI).

Endpoints para consulta de repasses do FNDE (FUNDEB, PNAE, PNLD, PNATE)
por município e estado.
"""

from fastapi import APIRouter, HTTPException, Query

from src.api.services import db_service

router = APIRouter()


@router.get("/resumo")
async def get_resumo_fnde(uf: str | None = None):
    """Retorna resumo FNDE por estado, opcionalmente filtrado por UF."""
    return db_service.get_fnde_resumo_estado(uf=uf)


@router.get("/municipios")
async def get_fnde_municipios(
    municipio_id: int | None = None,
    uf: str | None = None,
    limit: int = Query(default=50, le=500),
):
    """Retorna resumo FNDE por município, com filtros opcionais."""
    return db_service.get_fnde_resumo_municipio(municipio_id=municipio_id, uf=uf, limit=limit)


@router.get("/municipio/{municipio_id}")
async def get_fnde_por_municipio(
    municipio_id: int,
    programa: str | None = None,
):
    """Retorna programas FNDE para um município específico."""
    result = db_service.get_fnde_programas_municipio(municipio_id=municipio_id, programa=programa)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Nenhum dado FNDE encontrado para este município",
        )
    return result


@router.get("/programas")
async def get_programas_disponiveis():
    """Retorna lista de programas FNDE disponíveis no banco."""
    return db_service.get_fnde_programas_disponiveis()


@router.get("/search")
async def search_fnde(q: str, limit: int = Query(default=20, le=100)):
    """Busca municípios com dados FNDE por nome ou UF."""
    return db_service.search_fnde_municipios(query=q, limit=limit)
