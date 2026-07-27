"""
Rotas REST de Vereadores em Exercício (FastAPI).

Endpoints para busca, ranking, resumo e listagem de vereadores
eleitos nas eleições municipais (TSE).
"""

from fastapi import APIRouter, HTTPException

from src.api.services import db_service

router = APIRouter()


@router.get("/search")
async def search_vereadores(q: str):
    """Busca vereadores eleitos por nome, município, partido ou UF."""
    return db_service.search_vereadores(q)


@router.get("/ranking")
async def get_ranking(
    limit: int = 30,
    partido: str | None = None,
    uf: str | None = None,
):
    """Ranking de vereadores por votos, com filtros opcionais por partido e UF."""
    return db_service.get_ranking_vereadores(limit=limit, partido=partido, uf=uf)


@router.get("/resumo")
async def get_resumo():
    """Retorna KPIs agregados dos vereadores eleitos."""
    return db_service.get_resumo_vereadores()


@router.get("/por-partido")
async def get_por_partido(uf: str | None = None):
    """Retorna contagem de vereadores eleitos por partido."""
    return db_service.get_vereadores_por_partido(uf=uf)


@router.get("/municipio/{municipio_id}")
async def get_por_municipio(municipio_id: int):
    """Retorna todos os vereadores eleitos de um município."""
    result = db_service.get_vereadores_por_municipio(municipio_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Nenhum vereador eleito encontrado para este município",
        )
    return result


@router.get("/uf/{uf}")
async def get_por_uf(uf: str):
    """Retorna todos os vereadores eleitos de uma UF."""
    return db_service.get_vereadores_por_uf(uf)
