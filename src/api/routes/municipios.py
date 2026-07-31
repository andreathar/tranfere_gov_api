"""
Rotas REST de Municípios (FastAPI).

Indicadores locais consolidados do município: financeiro SICONFI,
saúde (CNES), educação (INEP) e violência (ISP/Atlas), com JOIN IBGE.
"""

from fastapi import APIRouter, HTTPException

from src.api.services import db_service

router = APIRouter()


@router.get("/{municipio_id}/indicadores")
async def indicadores_municipio(municipio_id: int):
    """Indicadores locais: saúde, educação, violência, financeiro e IBGE."""
    dados = db_service.get_indicadores_municipio(municipio_id)
    if not dados:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return dados


@router.get("/{municipio_id}/financeiro")
async def financeiro_municipio(municipio_id: int):
    """Financeiro SICONFI + indicadores IBGE do município."""
    dados = db_service.get_financeiro_municipio(municipio_id)
    if not dados:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return dados
