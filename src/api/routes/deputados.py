import datetime
import logging

from fastapi import APIRouter, HTTPException

from src.api.services import camara_service, db_service

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search")
async def search_deputados(q: str):
    db_results = db_service.search_deputados(q)
    if len(db_results) < 5:
        try:
            api_results = await camara_service.search_deputados_api(q)
            existing_ids = {d["deputado_id"] for d in db_results}
            for api_dep in api_results:
                if api_dep["id"] not in existing_ids:
                    db_results.append(
                        {
                            "deputado_id": api_dep["id"],
                            "nome": api_dep["nome"],
                            "nome_urna": api_dep.get("nomeEleitoral", api_dep["nome"]),
                            "sigla_partido": api_dep["siglaPartido"],
                            "uf": api_dep["siglaUf"],
                            "url_foto": api_dep["urlFoto"],
                        }
                    )
        except Exception as e:
            log.warning("Fallback to local DB for search '%s': %s", q, e)
    return db_results


@router.get("/{deputado_id}/perfil")
async def get_perfil(deputado_id: int):
    perfil = db_service.get_perfil_deputado(deputado_id)
    if not perfil:
        try:
            api_perfil = await camara_service.buscar_deputado(deputado_id)
            if not api_perfil:
                raise HTTPException(status_code=404, detail="Deputado não encontrado")

            ultimo_status = api_perfil.get("ultimoStatus", {})
            gabinete = ultimo_status.get("gabinete", {})

            return {
                "nome_urna": ultimo_status.get("nomeEleitoral") or api_perfil.get("nomeCivil"),
                "nome": api_perfil.get("nomeCivil"),
                "url_foto": ultimo_status.get("urlFoto"),
                "sigla_partido": ultimo_status.get("siglaPartido"),
                "uf": ultimo_status.get("siglaUf"),
                "situacao": ultimo_status.get("situacao"),
                "gabinete_numero": gabinete.get("sala"),
                "gabinete_predio": gabinete.get("predio"),
                "gabinete_telefone": gabinete.get("telefone"),
                "gabinete_email": gabinete.get("email"),
                "ultimo_status": ultimo_status.get("condicaoEleitoral"),
                "escolaridade": api_perfil.get("escolaridade"),
                "data_nascimento": api_perfil.get("dataNascimento"),
            }
        except HTTPException:
            raise
        except Exception as e:
            log.warning("Câmara API fallback for perfil %d: %s", deputado_id, e)
            raise HTTPException(status_code=502, detail="Erro na API da Câmara") from e
    return perfil


@router.get("/{deputado_id}/emendas")
async def get_emendas(deputado_id: int):
    nome = db_service.get_nome_by_id(deputado_id)
    if not nome:
        try:
            api_perfil = await camara_service.buscar_deputado(deputado_id)
            nome = api_perfil.get("nomeEleitoral") or api_perfil.get("nomeCivil")
        except Exception as e:
            log.warning("Câmara API fallback for emendas %d: %s", deputado_id, e)
            raise HTTPException(status_code=404, detail="Deputado não encontrado") from e
    if not nome:
        raise HTTPException(status_code=404, detail="Deputado não encontrado")
    return db_service.get_emendas_deputado(nome)


@router.get("/{deputado_id}/emendas/resumo")
async def get_resumo_emendas(deputado_id: int):
    nome = db_service.get_nome_by_id(deputado_id)
    if not nome:
        try:
            api_perfil = await camara_service.buscar_deputado(deputado_id)
            nome = api_perfil.get("nomeEleitoral") or api_perfil.get("nomeCivil")
        except Exception as e:
            log.warning("Câmara API fallback for resumo %d: %s", deputado_id, e)
            raise HTTPException(status_code=404, detail="Deputado não encontrado") from e
    if not nome:
        raise HTTPException(status_code=404, detail="Deputado não encontrado")
    return db_service.get_resumo_emendas(nome)


@router.get("/{deputado_id}/despesas")
async def get_despesas(deputado_id: int, ano: int | None = None):
    try:
        return await camara_service.listar_despesas(deputado_id, ano)
    except Exception as e:
        log.error("Erro ao buscar despesas do deputado %d: %s", deputado_id, e)
        raise HTTPException(status_code=502, detail="Erro na API da Câmara") from e


@router.get("/{deputado_id}/comissoes")
async def get_comissoes(deputado_id: int):
    try:
        return await camara_service.listar_orgaos(deputado_id)
    except Exception as e:
        log.error("Erro ao buscar comissões do deputado %d: %s", deputado_id, e)
        raise HTTPException(status_code=502, detail="Erro na API da Câmara") from e


@router.get("/{deputado_id}/votacoes")
async def get_votacoes(deputado_id: int, limit: int = 50):
    try:
        return await camara_service.listar_votacoes(deputado_id, limit)
    except Exception as e:
        log.error("Erro ao buscar votações do deputado %d: %s", deputado_id, e)
        raise HTTPException(status_code=502, detail="Erro na API da Câmara") from e


@router.get("/{deputado_id}/proposicoes")
async def get_proposicoes(deputado_id: int):
    try:
        return await camara_service.listar_proposicoes(deputado_id)
    except Exception as e:
        log.error("Erro ao buscar proposições do deputado %d: %s", deputado_id, e)
        raise HTTPException(status_code=502, detail="Erro na API da Câmara") from e


@router.get("/{deputado_id}/full_report")
async def get_full_report(deputado_id: int, ano: int = datetime.date.today().year):
    """
    Fetches the deputy's profile, expenses, votes, and propositions in parallel
    using the mcp-brasil executar_lote smart feature.
    """
    from src.api.services.mcp_service import executar_lote

    consultas = [
        {"tool": "camara_despesas_deputado", "args": {"deputado_id": deputado_id, "ano": ano}},
        # {"tool": "camara_votacoes_deputado", "args": {"deputado_id": deputado_id}}, # (Tool name might be different, let's just fetch despesas for 2 years)
        {"tool": "camara_despesas_deputado", "args": {"deputado_id": deputado_id, "ano": ano - 1}},
    ]

    try:
        result = await executar_lote(consultas)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar lote: {str(e)}") from e
