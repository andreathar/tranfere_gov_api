import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.services import mcp_service

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/buscar", response_model=dict[str, Any])
async def buscar_diario(
    q: str = Query(..., description="Termo de busca (nome do deputado, município, CNPJ ou lei)"),
    escopo: str = Query("ambos", description="Escopo da busca: 'federal', 'municipal' ou 'ambos'"),
):
    """
    Busca matérias publicadas no Diário Oficial da União (DOU) e diários municipais via Querido Diário.
    """
    try:
        result = await mcp_service._mcp_client.call_tool(
            "diario_oficial_buscar_diario_unificado", {"texto": q, "escopo": escopo}
        )
        return {"status": "success", "data": result}
    except Exception as e:
        log.error("Erro ao buscar no Diário Oficial para %s: %s", q, e)
        raise HTTPException(
            status_code=500, detail=f"Falha ao consultar Diário Oficial: {e}"
        ) from e


@router.post("/buscar-perfil", response_model=dict[str, Any])
async def buscar_diario_perfil(payload: dict):
    """Busca citações de um político no Diário Oficial (DOU + Querido Diário).

    Body: {q: str, escopo: str, uf_municipio?: str, data_inicio?: str, data_fim?: str}
    """
    q = payload.get("q", "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Campo 'q' é obrigatório")

    escopo = payload.get("escopo", "ambos")
    uf = payload.get("uf_municipio")
    data_inicio = payload.get("data_inicio")
    data_fim = payload.get("data_fim")

    try:
        result = await mcp_service.buscar_diario_perfil(
            nome=q,
            escopo=escopo,
            uf_municipio=uf,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        return {"status": "success", "data": result}
    except Exception as e:
        log.error("Erro ao buscar diário para perfil '%s': %s", q, e)
        raise HTTPException(status_code=500, detail=f"Falha: {e}") from e
