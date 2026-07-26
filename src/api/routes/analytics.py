import logging
from typing import Any

from fastapi import APIRouter

from src.api.services import analytics_service

log = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])


@router.get("/party-efficiency")
async def party_efficiency():
    """Retorna dados agregados de emendas por partido e situação."""
    data = await analytics_service.get_party_efficiency()
    return {"status": "success", "data": data}


@router.get("/socioeconomic")
async def socioeconomic():
    """Retorna dados agregados de emendas vs. dados IBGE dos municípios."""
    data = await analytics_service.get_socioeconomic_data()
    return {"status": "success", "data": data}


@router.get("/deputy-roi", response_model=dict[str, Any])
async def deputy_roi():
    """Retorna comparativo de Despesas da Cota vs. Valor de Emendas do parlamentar."""
    data = await analytics_service.get_deputy_roi()
    return {"status": "success", "data": data}


@router.get("/top-municipios", response_model=dict[str, Any])
async def top_municipios():
    """Returns the top municipalities by total emenda value."""
    data = await analytics_service.get_top_municipios()
    return {"status": "success", "data": data}
