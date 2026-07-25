"""
Rotas REST de Prefeitos & Gestão Municipal (FastAPI).

Endpoints para busca, perfil, ranking e emendas de prefeitos.
"""

from fastapi import APIRouter, HTTPException
from src.api.services import db_service

router = APIRouter()


@router.get("/search")
async def search_prefeitos(q: str):
    """Busca prefeitos por nome, município ou UF."""
    return db_service.search_prefeitos(q)


@router.get("/ranking")
async def get_ranking(limit: int = 20):
    """Retorna ranking de prefeituras por captação de emendas."""
    return db_service.get_ranking_prefeitos(limit=limit)


@router.get("/{municipio_id}/perfil")
async def get_perfil(municipio_id: int):
    """Retorna o perfil completo do prefeito e indicadores do município."""
    perfil = db_service.get_perfil_prefeito(municipio_id)
    if not perfil:
        raise HTTPException(status_code=404, detail="Prefeito/Município não encontrado")
    return perfil


@router.get("/{municipio_id}/emendas")
async def get_emendas(municipio_id: int, ano: int | None = None, limit: int = 100):
    """Retorna as emendas recebidas pelo município com os deputados autores, opcionalmente filtrado por ano."""
    return db_service.get_emendas_municipio(municipio_id, ano=ano, limit=limit)


