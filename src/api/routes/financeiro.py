"""
Rotas REST de Financeiro SICONFI (FastAPI).

Endpoints para dados financeiros de estados e municípios (DCA + RREO):
receitas, despesas, resultado primário e arrecadação própria (ICMS,
IPVA, ITCD, FPE, FUNDEB, IPTU, ISS, FPM).
"""

from fastapi import APIRouter, HTTPException, Query

from src.api.services import db_service

router = APIRouter()


@router.get("/estados")
async def financeiro_estados(exercicio: int | None = None):
    """Resumo financeiro das 27 UFs (esfera estadual, DCA + RREO A03)."""
    return db_service.get_financeiro_estados(exercicio=exercicio)


@router.get("/estado/{uf}")
async def financeiro_estado(uf: str):
    """Detalhe financeiro de um estado (tabela estadual ou soma municipal)."""
    dados = db_service.get_financeiro_estado(uf.upper())
    if not dados:
        raise HTTPException(
            status_code=404, detail=f"Sem dados financeiros para UF: {uf.upper()}"
        )
    return dados


@router.get("/municipios")
async def financeiro_municipios(
    uf: str | None = None,
    exercicio: int | None = None,
    order_by: str = Query("despesas_totais", description="Coluna de ordenação"),
    limit: int = 100,
):
    """Ranking de municípios por receita/despesa/arrecadação (JOIN IBGE)."""
    return db_service.get_financeiro_municipios(
        uf=uf, exercicio=exercicio, order_by=order_by, limit=limit
    )


@router.get("/municipio/{municipio_id}")
async def financeiro_municipio(municipio_id: int):
    """Financeiro + indicadores IBGE de um município (exercício mais recente)."""
    dados = db_service.get_financeiro_municipio(municipio_id)
    if not dados:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return dados


@router.get("/comparativo")
async def comparativo(uf: str | None = None):
    """Emendas Pix recebidas × arrecadação própria (ICMS/IPTU/ISS/FPM) por UF."""
    return db_service.get_comparativo_emendas_financeiro(uf=uf)
