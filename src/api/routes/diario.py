from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict
import logging

from src.api.services import mcp_service

log = logging.getLogger(__name__)

router = APIRouter()

@router.get("/buscar", response_model=Dict[str, Any])
async def buscar_diario(
    q: str = Query(..., description="Termo de busca (nome do deputado, município, CNPJ ou lei)"),
    escopo: str = Query("ambos", description="Escopo da busca: 'federal', 'municipal' ou 'ambos'")
):
    """
    Busca matérias publicadas no Diário Oficial da União (DOU) e diários municipais via Querido Diário.
    """
    try:
        result = await mcp_service._mcp_client.call_tool(
            "diario_oficial_buscar_diario_unificado",
            {"texto": q, "escopo": escopo}
        )
        return {"status": "success", "data": result}
    except Exception as e:
        log.error(f"Erro ao buscar no Diário Oficial para {q}: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao consultar Diário Oficial: {str(e)}")
