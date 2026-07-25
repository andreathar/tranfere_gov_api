from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict
import logging

from src.api.services import mcp_service

log = logging.getLogger(__name__)

router = APIRouter()

@router.get("/fornecedor", response_model=Dict[str, Any])
async def consultar_fornecedor(
    cnpj: str = Query(..., description="CNPJ do fornecedor ou órgão contratante")
):
    """
    Consulta dados do fornecedor ou órgão no Portal Nacional de Contratações Públicas (PNCP).
    """
    try:
        # Tenta consultar como fornecedor
        res_fornecedor = await mcp_service._mcp_client.call_tool(
            "compras_pncp_consultar_fornecedor",
            {"cnpj": cnpj}
        )
        return {"status": "success", "data": res_fornecedor}
    except Exception as e:
        log.error("Erro ao consultar PNCP para %s: %s", cnpj, e)
        raise HTTPException(status_code=500, detail=f"Falha ao consultar PNCP: {str(e)}")

@router.get("/bps", response_model=Dict[str, Any])
async def buscar_precos_medicamentos(
    termo: str = Query("insulina", description="Termo de busca na descrição do medicamento no BPS")
):
    """
    Consulta preços praticados em compras públicas registradas no Banco de Preços em Saúde (BPS).
    """
    try:
        result = await mcp_service._mcp_client.call_tool(
            "bps_buscar_medicamento_bps",
            {"descricao": termo, "limite": 20}
        )
        return {"status": "success", "data": result}
    except Exception as e:
        log.error("Erro ao consultar BPS para %s: %s", termo, e)
        raise HTTPException(status_code=500, detail=f"Falha ao consultar Banco de Preços em Saúde: {str(e)}")
