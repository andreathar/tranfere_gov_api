import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.services import db_service, mcp_service

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/saude/{codigo_ibge}", response_model=dict[str, Any])
async def get_saude(codigo_ibge: str):
    """
    Returns health network infrastructure for a given IBGE code using mcp-brasil.
    """
    try:
        data = await mcp_service.get_saude_resumo(codigo_ibge)
        return {"status": "success", "data": data}
    except Exception as e:
        log.error("Error fetching saude data for %s: %s", codigo_ibge, e)
        raise HTTPException(status_code=500, detail="Failed to fetch saude data.") from e


@router.get("/justica", response_model=dict[str, Any])
async def search_justica(query: str = Query(..., description="CNPJ to search in DataJud")):
    """
    Searches judicial processes associated with a CNPJ using DataJud via mcp-brasil.
    Results are cached in the database for 30 days.
    """
    try:
        with db_service._get_connection() as conn, conn.cursor() as cur:
            # Check cache first
            cur.execute(
                "SELECT processos_detalhes, checked_at FROM beneficiario_processos WHERE cnpj = %s AND checked_at > NOW() - INTERVAL '30 days'",
                (query,),
            )
            row = cur.fetchone()

            if row:
                data = row["processos_detalhes"]
                if not data:
                    data = "Nenhum processo encontrado (cache local)."
                return {"status": "success", "data": data}

            # Cache miss, call API
            try:
                res = await mcp_service._mcp_client.call_tool(
                    "datajud_buscar_processos", {"query": query, "tamanho": 5}
                )

                import json

                try:
                    data = json.loads(res) if res else {}
                except Exception:
                    data = {"message": res} if res else {}

                total = len(data) if isinstance(data, list) else 0

                # Upsert into DB
                cur.execute(
                    """
                        INSERT INTO beneficiario_processos (cnpj, total_processos, processos_detalhes, erro, checked_at)
                        VALUES (%s, %s, %s, NULL, NOW())
                        ON CONFLICT (cnpj) DO UPDATE SET
                            total_processos = EXCLUDED.total_processos,
                            processos_detalhes = EXCLUDED.processos_detalhes,
                            erro = NULL,
                            checked_at = NOW();
                    """,
                    (query, total, json.dumps(data)),
                )
                conn.commit()
            except Exception as api_err:
                log.error("DataJud API error for %s: %s", query, api_err)
                data = {"message": f"Erro ao consultar DataJud: {api_err}"}

            return {"status": "success", "data": data}
    except Exception as e:
        log.error("Error fetching datajud for %s: %s", query, e)
        raise HTTPException(status_code=500, detail="Failed to search judicial processes.") from e


@router.get("/tcu", response_model=dict[str, Any])
async def check_tcu(
    cnpj: str = Query(..., description="CNPJ do beneficiário para verificar sanções TCU"),
):
    """
    Verifica sanções TCU para um CNPJ:
    - Empresas declaradas inidôneas (proibidas de licitar)
    - Certidão consolidada TCU + CNJ
    Usa executar_lote para paralelizar as consultas.
    """
    try:
        result = await mcp_service.executar_lote(
            [
                {"tool": "tcu_consultar_inidoneos", "args": {"cpf_cnpj": cnpj}},
                {"tool": "tcu_consultar_inabilitados", "args": {"cpf": cnpj}},
            ]
        )
        return {"status": "success", "data": result}
    except Exception as e:
        log.error("Error checking TCU for %s: %s", cnpj, e)
        raise HTTPException(status_code=500, detail="Falha ao consultar TCU.") from e
