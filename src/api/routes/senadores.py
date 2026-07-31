"""
Rotas REST de Senadores (FastAPI).

Endpoints para busca, ranking por atividade legislativa e perfil
dos 81 senadores em exercício (tabela senadores_dados — API Senado).
"""

from fastapi import APIRouter, HTTPException, Query

from src.api.services import db_service

router = APIRouter()


@router.get("/search")
async def search_senadores(q: str = Query(..., min_length=2)):
    """Busca senadores por nome de urna ou nome completo."""
    return db_service.search_senadores(q)


@router.get("/ranking")
async def ranking_senadores(
    limit: int = 30,
    partido: str | None = None,
    uf: str | None = None,
):
    """Ranking de senadores por atividade legislativa (votações + relatorias)."""
    return db_service.get_ranking_senadores(limit=limit, partido=partido, uf=uf)


@router.get("/por-partido")
async def senadores_por_partido():
    """Contagem de senadores por partido."""
    return db_service.get_senadores_por_partido()


@router.get("/{senador_codigo}/perfil")
async def perfil_senador(senador_codigo: int):
    """Perfil completo do senador."""
    perfil = db_service.get_perfil_senador(senador_codigo)
    if not perfil:
        raise HTTPException(status_code=404, detail="Senador não encontrado")
    return perfil
