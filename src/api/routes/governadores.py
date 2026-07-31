"""
Rotas REST de Governadores Estaduais (FastAPI).

Endpoints para busca, perfil, atuação política, financeiro SICONFI
e cruzamento com emendas Pix das bancadas estaduais.
"""

from fastapi import APIRouter, HTTPException

from src.api.services import db_service

router = APIRouter()


@router.get("/")
async def list_governadores(partido: str | None = None, regiao: str | None = None):
    """Lista todos os governadores eleitos em 2022, com filtros opcionais por partido e região."""
    return db_service.get_all_governadores(partido=partido, regiao=regiao)


@router.get("/ranking/emendas")
async def get_ranking_emendas(limit: int = 27):
    """Ranking de governadores por volume de emendas Pix captadas na UF."""
    return db_service.get_ranking_governadores_emendas(limit=limit)


@router.get("/ranking/alinhamento")
async def get_ranking_alinhamento(limit: int = 27):
    """Ranking de governadores por alinhamento partidário com bancada federal da UF."""
    return db_service.get_ranking_alinhamento_governador(limit=limit)


@router.get("/triangulo-politico")
async def get_triangulo_politico(uf: str | None = None, limit: int = 100):
    """
    Retorna dados do triângulo político (deputado × prefeito × governador)
    por UF. Útil para mapear relações de apoio, oposição e fisiologismo.
    """
    return db_service.get_triangulo_politico(uf=uf, limit=limit)


@router.get("/{uf}/perfil")
async def get_perfil_governador(uf: str):
    """Perfil completo do governador: dados eleitorais, financeiro SICONFI e bancada aliada."""
    perfil = db_service.get_perfil_governador(uf.upper())
    if not perfil:
        raise HTTPException(
            status_code=404, detail=f"Governador não encontrado para UF: {uf.upper()}"
        )
    return perfil


@router.get("/{uf}/bancada")
async def get_bancada_uf(uf: str, limit: int = 100):
    """Retorna todos os deputados federais da bancada da UF e seu alinhamento com o governador."""
    return db_service.get_bancada_deputados_uf(uf.upper(), limit=limit)


@router.get("/{uf}/emendas")
async def get_emendas_estado(uf: str, ano: int | None = None, limit: int = 200):
    """Retorna emendas Pix destinadas à UF, agrupadas por deputado e município beneficiado."""
    return db_service.get_emendas_estado(uf.upper(), ano=ano, limit=limit)


@router.get("/{uf}/financeiro")
async def get_financeiro_estado(uf: str):
    """Retorna dados financeiros SICONFI do estado: receitas, despesas e arrecadação."""
    return db_service.get_financeiro_estado(uf.upper())


@router.get("/{uf}/municipios")
async def get_municipios_estado(uf: str, limit: int = 100):
    """Lista os municípios do estado com prefeitos, emendas captadas e indicadores IBGE."""
    return db_service.get_municipios_por_estado(uf.upper(), limit=limit)
