from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict
import logging

from src.api.services import mcp_service
from src.api.services import db_service

log = logging.getLogger(__name__)

router = APIRouter()

@router.get("/saude/{codigo_ibge}", response_model=Dict[str, Any])
async def get_saude(codigo_ibge: str):
    """
    Returns health network infrastructure for a given IBGE code using mcp-brasil.
    """
    try:
        data = await mcp_service.get_saude_resumo(codigo_ibge)
        return {"status": "success", "data": data}
    except Exception as e:
        log.error(f"Error fetching saude data for {codigo_ibge}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch saude data.")

@router.get("/justica", response_model=Dict[str, Any])
async def search_justica(query: str = Query(..., description="CNPJ to search in DataJud")):
    """
    Searches judicial processes associated with a CNPJ using DataJud via mcp-brasil.
    Results are cached in the database for 30 days.
    """
    try:
        conn = db_service._get_connection()
        cur = conn.cursor()
        
        # Check cache first
        cur.execute("SELECT processos_detalhes, checked_at FROM beneficiario_processos WHERE cnpj = %s AND checked_at > NOW() - INTERVAL '30 days'", (query,))
        row = cur.fetchone()
        
        if row:
            data = row['processos_detalhes']
            cur.close()
            conn.close()
            if not data:
                data = "Nenhum processo encontrado (cache local)."
            return {"status": "success", "data": data}
            
        # Cache miss, call API
        try:
            res = await mcp_service._mcp_client.call_tool("datajud_buscar_processos", {"query": query, "tamanho": 5})
            
            import json
            try:
                data = json.loads(res) if res else {}
            except Exception:
                data = {"message": res} if res else {}
                
            total = len(data) if isinstance(data, list) else 0
            
            # Upsert into DB
            cur.execute("""
                INSERT INTO beneficiario_processos (cnpj, total_processos, processos_detalhes, erro, checked_at)
                VALUES (%s, %s, %s, NULL, NOW())
                ON CONFLICT (cnpj) DO UPDATE SET 
                    total_processos = EXCLUDED.total_processos,
                    processos_detalhes = EXCLUDED.processos_detalhes,
                    erro = NULL,
                    checked_at = NOW();
            """, (query, total, json.dumps(data)))
            conn.commit()
        except Exception as api_err:
            log.error(f"DataJud API error for {query}: {api_err}")
            data = {"message": f"Erro ao consultar DataJud: {api_err}"}
            
        cur.close()
        conn.close()
        return {"status": "success", "data": data}
    except Exception as e:
        log.error(f"Error fetching datajud for {query}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search judicial processes.")

@router.get("/tcu", response_model=Dict[str, Any])
async def check_tcu(cnpj: str = Query(..., description="CNPJ do beneficiário para verificar sanções TCU")):
    """
    Verifica sanções TCU para um CNPJ:
    - Empresas declaradas inidôneas (proibidas de licitar)
    - Certidão consolidada TCU + CNJ
    Usa executar_lote para paralelizar as consultas.
    """
    try:
        result = await mcp_service.executar_lote([
            {"tool": "tcu_consultar_inidoneos",    "args": {"cpf_cnpj": cnpj}},
            {"tool": "tcu_consultar_inabilitados", "args": {"cpf": cnpj}},
        ])
        return {"status": "success", "data": result}
    except Exception as e:
        log.error(f"Error checking TCU for {cnpj}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao consultar TCU.")

