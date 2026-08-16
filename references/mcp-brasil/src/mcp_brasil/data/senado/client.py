"""HTTP client for the Senado Federal API.

All functions return typed Pydantic models. No LLM formatting here (ADR-001).

API docs: https://legis.senado.leg.br/dadosabertos/docs

The Senado API wraps results in deeply nested structures. We use:
- ``_deep_get(data, *keys)`` to navigate nested dicts safely
- ``_ensure_list(val)`` to handle dict→list coercion (single result quirk)
- ``JSON_HEADERS`` to request JSON via Accept header

Endpoints:
    - /senador/lista/atual              → listar_senadores
    - /senador/{codigo}                 → obter_senador
    - /senador/lista/atual?nome=        → buscar_senador_por_nome (filtered)
    - /senador/{codigo}/votacoes        → votacoes_senador
    - /materia/pesquisa/lista           → buscar_materias
    - /materia/{codigo}                 → obter_materia
    - /materia/movimentacoes/{codigo}   → tramitacao_materia
    - /materia/textos/{codigo}          → textos_materia
    - /materia/votacoes/{codigo}        → votos_materia
    - /votacao?ano={ano}                → listar_votacoes
    - /votacao?ano={ano} (filtered)     → votacoes_recentes
    - /comissao/lista/colegiados        → listar_comissoes
    - /comissao/{codigo}                → obter_comissao
    - /comissao/{codigo}/membros        → membros_comissao
    - /agenda/lista/comissoes/{data}    → reunioes_comissao
    - /plenario/agenda/mes/{ano}/{mes}  → agenda_plenario
    - /agenda/lista/comissoes/{data}    → agenda_comissoes
    - /legislatura                      → legislatura_atual
    - /processo/emenda                   → emendas_materia
    - /composicao/lista/blocos           → listar_blocos
    - /composicao/lideranca              → listar_liderancas
    - /processo/relatoria                → relatorias_senador
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_brasil._shared.http_client import http_get
from mcp_brasil._shared.rate_limiter import RateLimiter

from .constants import (
    AGENDA_COMISSOES_URL,
    AGENDA_URL,
    BLOCOS_URL,
    COMISSAO_URL,
    COMISSOES_URL,
    EMENDAS_URL,
    JSON_HEADERS,
    LEGISLATURA_URL,
    LIDERANCAS_URL,
    MATERIA_URL,
    MATERIAS_URL,
    RELATORIAS_URL,
    SENADORES_LISTA_URL,
    SENADORES_URL,
    TIPOS_MATERIA,
    VOTACOES_URL,
)
from .schemas import (
    BlocoParlamentar,
    ComissaoDetalhe,
    ComissaoResumo,
    Emenda,
    LegislaturaInfo,
    Lideranca,
    MateriaDetalhe,
    MateriaResumo,
    MembroComissao,
    Relatoria,
    ReuniaoComissao,
    SenadorDetalhe,
    SenadorResumo,
    SessaoPlenario,
    Tramitacao,
    VotacaoDetalhe,
    VotacaoResumo,
    VotoNominal,
)

logger = logging.getLogger(__name__)

# Conservative limit — Senado API does not document rate limits
_rate_limiter = RateLimiter(max_requests=60, period=60.0)


# --- Helpers ----------------------------------------------------------------


def _deep_get(data: Any, *keys: str) -> Any:
    """Navigate nested dicts safely. Returns None if any key is missing."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _ensure_list(val: Any) -> list[Any]:
    """Ensure value is a list. Senado API returns dict when there's only 1 result."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return [val]
    return []


async def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET request with JSON Accept header for Senado API."""
    async with _rate_limiter:
        return await http_get(url, params=params, headers=JSON_HEADERS)


# --- Parsing helpers --------------------------------------------------------


def _parse_senador_resumo(raw: dict[str, Any]) -> SenadorResumo:
    ident = raw.get("IdentificacaoParlamentar") or {}
    partido = _deep_get(ident, "SiglaPartidoParlamentar")
    uf = _deep_get(ident, "UfParlamentar")
    return SenadorResumo(
        codigo=_deep_get(ident, "CodigoParlamentar"),
        nome=_deep_get(ident, "NomeParlamentar"),
        nome_completo=_deep_get(ident, "NomeCompletoParlamentar"),
        partido=partido,
        uf=uf,
        foto=_deep_get(ident, "UrlFotoParlamentar"),
        em_exercicio=raw.get("EmExercicio") == "Sim" if raw.get("EmExercicio") else None,
    )


def _parse_senador_detalhe(raw: dict[str, Any]) -> SenadorDetalhe:
    dados = _deep_get(raw, "Parlamentar", "IdentificacaoParlamentar") or {}
    mandato = _deep_get(raw, "Parlamentar", "UltimoMandato") or {}
    return SenadorDetalhe(
        codigo=dados.get("CodigoParlamentar"),
        nome=dados.get("NomeParlamentar"),
        nome_completo=dados.get("NomeCompletoParlamentar"),
        partido=dados.get("SiglaPartidoParlamentar"),
        uf=dados.get("UfParlamentar"),
        email=dados.get("EmailParlamentar"),
        foto=dados.get("UrlFotoParlamentar"),
        telefone=dados.get("TelefoneParlamentar"),
        mandato_inicio=_deep_get(mandato, "PrimeiroExercicio", "DataInicio"),
        mandato_fim=_deep_get(mandato, "SegundoExercicio", "DataFim"),
    )


def _parse_materia_resumo(raw: dict[str, Any]) -> MateriaResumo:
    return MateriaResumo(
        codigo=raw.get("CodigoMateria"),
        sigla_tipo=raw.get("SiglaTipoMateria") or raw.get("DescricaoSubtipoMateria"),
        numero=raw.get("NumeroMateria"),
        ano=raw.get("AnoMateria"),
        ementa=raw.get("EmentaMateria") or raw.get("DadosBasicosMateria", {}).get("EmentaMateria"),
        data_apresentacao=raw.get("DataApresentacao"),
        autor=raw.get("NomeAutor"),
        situacao=raw.get("DescricaoSituacao")
        or _deep_get(raw, "SituacaoAtual", "Autuacoes", "Situacao", "DescricaoSituacao"),
    )


def _parse_materia_detalhe(raw: dict[str, Any]) -> MateriaDetalhe:
    materia = _deep_get(raw, "DetalheMateria", "Materia") or raw
    dados = materia.get("DadosBasicosMateria") or {}
    situacao = _deep_get(materia, "SituacaoAtual", "Autuacoes", "Situacao") or {}
    autor_raw = _deep_get(materia, "Autoria", "Autor") or []
    autor_list = _ensure_list(autor_raw)
    autor_nome = autor_list[0].get("NomeAutor") if autor_list else None
    return MateriaDetalhe(
        codigo=dados.get("CodigoMateria"),
        sigla_tipo=dados.get("SiglaSubtipoMateria"),
        numero=dados.get("NumeroMateria"),
        ano=dados.get("AnoMateria"),
        ementa=dados.get("EmentaMateria"),
        ementa_completa=dados.get("ExplicacaoEmentaMateria"),
        data_apresentacao=dados.get("DataApresentacao"),
        autor=autor_nome,
        situacao=situacao.get("DescricaoSituacao") if isinstance(situacao, dict) else None,
        casa_origem=dados.get("NomeCasaOrigem"),
    )


def _parse_tramitacao(raw: dict[str, Any]) -> Tramitacao:
    return Tramitacao(
        data=raw.get("DataTramitacao") or raw.get("DataRecebimento"),
        descricao=raw.get("DescricaoTramitacao") or raw.get("TextoTramitacao"),
        local=raw.get("DestinoSigla") or _deep_get(raw, "Destino", "SiglaLocal"),
        situacao=raw.get("SituacaoTramitacao") or raw.get("DescricaoSituacao"),
    )


def _str(val: Any) -> str | None:
    """Convert to str if not None (new API returns int codes)."""
    return str(val) if val is not None else None


def _parse_votacao_resumo(raw: dict[str, Any]) -> VotacaoResumo:
    # Handles both old PascalCase and new camelCase API formats
    return VotacaoResumo(
        codigo=_str(
            raw.get("codigoSessaoVotacao")
            or raw.get("CodigoSessaoVotacao")
            or raw.get("CodigoVotacao")
        ),
        data=raw.get("dataSessao") or raw.get("DataSessao") or raw.get("DataVotacao"),
        descricao=(
            raw.get("descricaoVotacao") or raw.get("DescricaoVotacao") or raw.get("Descricao")
        ),
        resultado=raw.get("resultadoVotacao") or raw.get("Resultado"),
    )


def _parse_votacao_detalhe(raw: dict[str, Any]) -> VotacaoDetalhe:
    # Old API (PascalCase, deeply nested) — /materia/votacoes/{id}
    materia = raw.get("Materia") or raw.get("IdentificacaoMateria") or {}
    sessao = raw.get("SessaoPlenaria") or {}
    votos_raw = _ensure_list(_deep_get(raw, "Votos", "VotoParlamentar"))
    # New API (camelCase, flat) — /votacao
    sim = _safe_int(raw.get("totalVotosSim") or raw.get("TotalVotosSim"))
    nao = _safe_int(raw.get("totalVotosNao") or raw.get("TotalVotosNao"))
    abstencao = _safe_int(raw.get("totalVotosAbstencao") or raw.get("TotalVotosAbstencao"))
    if sim is None and votos_raw:
        sim = sum(1 for v in votos_raw if v.get("SiglaVoto") == "Sim")
        nao = sum(1 for v in votos_raw if v.get("SiglaVoto") == "Não")
        abstencao = sum(1 for v in votos_raw if v.get("SiglaVoto") == "Abstenção")
    return VotacaoDetalhe(
        codigo=_str(
            raw.get("codigoSessaoVotacao")
            or raw.get("CodigoSessaoVotacao")
            or raw.get("CodigoVotacao")
        ),
        data=(
            raw.get("dataSessao")
            or sessao.get("DataSessao")
            or raw.get("DataSessao")
            or raw.get("DataVotacao")
        ),
        descricao=raw.get("descricaoVotacao") or raw.get("DescricaoVotacao"),
        resultado=(
            raw.get("resultadoVotacao") or raw.get("DescricaoResultado") or raw.get("Resultado")
        ),
        materia_codigo=_str(raw.get("codigoMateria") or materia.get("CodigoMateria")),
        materia_descricao=raw.get("identificacao") or materia.get("DescricaoIdentificacaoMateria"),
        sim=sim,
        nao=nao,
        abstencao=abstencao,
    )


def _safe_int(val: Any) -> int | None:
    """Safely convert a value to int."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _parse_voto(raw: dict[str, Any]) -> VotoNominal:
    # Old API (PascalCase, nested IdentificacaoParlamentar)
    ident = raw.get("IdentificacaoParlamentar") or {}
    return VotoNominal(
        senador_codigo=_str(raw.get("codigoParlamentar") or ident.get("CodigoParlamentar")),
        senador_nome=raw.get("nomeParlamentar") or ident.get("NomeParlamentar"),
        partido=raw.get("siglaPartidoParlamentar") or ident.get("SiglaPartidoParlamentar"),
        uf=raw.get("siglaUFParlamentar") or ident.get("UfParlamentar"),
        voto=(raw.get("siglaVotoParlamentar") or raw.get("SiglaVoto") or raw.get("DescricaoVoto")),
    )


def _parse_comissao_resumo(raw: dict[str, Any]) -> ComissaoResumo:
    return ComissaoResumo(
        codigo=raw.get("CodigoColegiado"),
        sigla=raw.get("SiglaColegiado"),
        nome=raw.get("NomeColegiado"),
        tipo=raw.get("SiglaTipoColegiado"),
    )


def _parse_comissao_detalhe(raw: dict[str, Any]) -> ComissaoDetalhe:
    colegiado = _deep_get(raw, "DetalheComissao", "Colegiado") or raw
    return ComissaoDetalhe(
        codigo=colegiado.get("CodigoColegiado"),
        sigla=colegiado.get("SiglaColegiado"),
        nome=colegiado.get("NomeColegiado"),
        tipo=colegiado.get("SiglaTipoColegiado"),
        finalidade=colegiado.get("Finalidade"),
        data_criacao=colegiado.get("DataCriacao"),
        data_extincao=colegiado.get("DataExtincao"),
    )


def _parse_membro(raw: dict[str, Any]) -> MembroComissao:
    ident = raw.get("IdentificacaoParlamentar") or {}
    return MembroComissao(
        codigo_senador=ident.get("CodigoParlamentar"),
        nome=ident.get("NomeParlamentar"),
        partido=ident.get("SiglaPartidoParlamentar"),
        uf=ident.get("UfParlamentar"),
        cargo=raw.get("DescricaoParticipacao"),
    )


def _parse_reuniao(raw: dict[str, Any]) -> ReuniaoComissao:
    comissoes = raw.get("Comissoes") or {}
    comissao = comissoes.get("Comissao") or {}
    if isinstance(comissao, list):
        comissao = comissao[0] if comissao else {}
    return ReuniaoComissao(
        data=raw.get("DataReuniao") or raw.get("Data"),
        tipo=raw.get("TipoReuniao") or raw.get("Tipo"),
        comissao=comissao.get("SiglaColegiado") if isinstance(comissao, dict) else None,
        pauta=raw.get("Pauta") or raw.get("DescricaoPauta"),
        local=raw.get("Local"),
    )


def _parse_sessao(raw: dict[str, Any]) -> SessaoPlenario:
    return SessaoPlenario(
        data=raw.get("DataSessao") or raw.get("Data"),
        tipo=raw.get("TipoSessao") or raw.get("Tipo"),
        numero=raw.get("NumeroSessao") or raw.get("Numero"),
        situacao=raw.get("SituacaoSessao") or raw.get("Situacao"),
    )


def _parse_legislatura(raw: dict[str, Any]) -> LegislaturaInfo:
    return LegislaturaInfo(
        numero=_safe_int(raw.get("NumeroLegislatura")),
        data_inicio=raw.get("DataInicio"),
        data_fim=raw.get("DataFim"),
    )


# --- Public API functions ---------------------------------------------------

# Senadores (4)


async def listar_senadores(em_exercicio: bool = True) -> list[SenadorResumo]:
    """Lista senadores atuais."""
    data = await _get(SENADORES_LISTA_URL)
    parlamentares = _deep_get(data, "ListaParlamentarEmExercicio", "Parlamentares", "Parlamentar")
    return [_parse_senador_resumo(p) for p in _ensure_list(parlamentares)]


async def obter_senador(codigo: str) -> SenadorDetalhe | None:
    """Obtém detalhes de um senador pelo código."""
    data = await _get(f"{SENADORES_URL}/{codigo}")
    parlamentar = _deep_get(data, "DetalheParlamentar")
    if not parlamentar:
        return None
    return _parse_senador_detalhe(parlamentar)


async def buscar_senador_por_nome(nome: str) -> list[SenadorResumo]:
    """Busca senadores pelo nome."""
    data = await _get(SENADORES_LISTA_URL)
    parlamentares = _deep_get(data, "ListaParlamentarEmExercicio", "Parlamentares", "Parlamentar")
    todos = [_parse_senador_resumo(p) for p in _ensure_list(parlamentares)]
    nome_lower = nome.lower()
    return [s for s in todos if s.nome and nome_lower in s.nome.lower()]


async def votacoes_senador(codigo: str) -> list[VotacaoResumo]:
    """Lista votações em que um senador participou."""
    data = await _get(f"{SENADORES_URL}/{codigo}/votacoes")
    votacoes = _deep_get(data, "VotacaoParlamentar", "Parlamentar", "Votacoes", "Votacao")
    return [_parse_votacao_resumo(v) for v in _ensure_list(votacoes)]


# Matérias (5)


async def buscar_materias(
    sigla_tipo: str | None = None,
    numero: str | None = None,
    ano: str | None = None,
    keywords: str | None = None,
    tramitando: bool = False,
) -> list[MateriaResumo]:
    """Busca matérias legislativas com filtros."""
    params: dict[str, Any] = {}
    if sigla_tipo:
        params["sigla"] = sigla_tipo
    if numero:
        params["numero"] = numero
    if ano:
        params["ano"] = ano
    if keywords:
        params["palavraChave"] = keywords
    if tramitando:
        params["tramitando"] = "S"
    data = await _get(MATERIAS_URL, params)
    materias = _deep_get(data, "PesquisaBasicaMateria", "Materias", "Materia")
    return [_parse_materia_resumo(m) for m in _ensure_list(materias)]


async def obter_materia(codigo: str) -> MateriaDetalhe | None:
    """Obtém detalhes de uma matéria pelo código."""
    data = await _get(f"{MATERIA_URL}/{codigo}")
    if not data:
        return None
    return _parse_materia_detalhe(data)


async def tramitacao_materia(codigo: str) -> list[Tramitacao]:
    """Obtém tramitações de uma matéria."""
    data = await _get(f"{MATERIA_URL}/movimentacoes/{codigo}")
    tramitacoes = _deep_get(data, "MovimentacaoMateria", "Materia", "Autuacoes", "Autuacao")
    if not tramitacoes:
        tramitacoes = _deep_get(
            data, "MovimentacaoMateria", "Materia", "Tramitacoes", "Tramitacao"
        )
    return [_parse_tramitacao(t) for t in _ensure_list(tramitacoes)]


async def textos_materia(codigo: str) -> list[dict[str, str | None]]:
    """Obtém textos/documentos de uma matéria (retorna lista de URLs)."""
    data = await _get(f"{MATERIA_URL}/textos/{codigo}")
    textos = _deep_get(data, "TextoMateria", "Materia", "Textos", "Texto")
    results: list[dict[str, str | None]] = []
    for t in _ensure_list(textos):
        results.append(
            {
                "tipo": t.get("DescricaoTipoTexto"),
                "data": t.get("DataTexto"),
                "url": t.get("UrlTexto"),
            }
        )
    return results


async def votos_materia(codigo: str) -> list[VotacaoDetalhe]:
    """Obtém votações de uma matéria específica."""
    data = await _get(f"{MATERIA_URL}/votacoes/{codigo}")
    votacoes = _deep_get(data, "VotacaoMateria", "Materia", "Votacoes", "Votacao")
    return [_parse_votacao_detalhe(v) for v in _ensure_list(votacoes)]


# Votações (3)


async def listar_votacoes(ano: str) -> list[VotacaoResumo]:
    """Lista votações do plenário em um ano."""
    data = await _get(VOTACOES_URL, params={"ano": ano})
    items = _ensure_list(data)
    return [_parse_votacao_resumo(v) for v in items]


async def obter_votacao(codigo_sessao: str) -> VotacaoDetalhe | None:
    """Obtém detalhes de uma votação incluindo votos."""
    # New API has no individual detail endpoint; filter from list
    data = await _get(VOTACOES_URL, params={"codigoSessaoVotacao": codigo_sessao})
    items = _ensure_list(data)
    if not items:
        return None
    return _parse_votacao_detalhe(items[0])


async def votacoes_recentes(data_str: str) -> list[VotacaoResumo]:
    """Lista votações por data (formato AAAAMMDD ou AAAA-MM-DD)."""
    ano = data_str[:4]
    data = await _get(VOTACOES_URL, params={"ano": ano})
    items = _ensure_list(data)
    # Filter by date prefix client-side
    results = []
    normalized = data_str.replace("-", "")
    for item in items:
        ds = (item.get("dataSessao") or "").replace("-", "").replace("T", "")[:8]
        if ds.startswith(normalized):
            results.append(_parse_votacao_resumo(item))
    return results


# Comissões (4)


async def listar_comissoes() -> list[ComissaoResumo]:
    """Lista comissões do Senado."""
    data = await _get(COMISSOES_URL)
    comissoes = _deep_get(data, "ListaColegiados", "Colegiados", "Colegiado")
    return [_parse_comissao_resumo(c) for c in _ensure_list(comissoes)]


async def obter_comissao(codigo: str) -> ComissaoDetalhe | None:
    """Obtém detalhes de uma comissão."""
    data = await _get(f"{COMISSAO_URL}/{codigo}")
    if not data:
        return None
    return _parse_comissao_detalhe(data)


async def membros_comissao(codigo: str) -> list[MembroComissao]:
    """Lista membros de uma comissão."""
    data = await _get(f"{COMISSAO_URL}/{codigo}/membros")
    membros = _deep_get(data, "ComposicaoComissao", "Comissao", "Membros", "Membro")
    return [_parse_membro(m) for m in _ensure_list(membros)]


async def reunioes_comissao(codigo: str) -> list[ReuniaoComissao]:
    """Lista reuniões de uma comissão."""
    data = await _get(f"{COMISSAO_URL}/{codigo}/reunioes")
    reunioes = _deep_get(data, "ReuniaoComissao", "Reunioes", "Reuniao")
    return [_parse_reuniao(r) for r in _ensure_list(reunioes)]


# Agenda (2)


async def agenda_plenario(ano: str, mes: str) -> list[SessaoPlenario]:
    """Lista sessões plenárias de um mês."""
    data = await _get(f"{AGENDA_URL}/{ano}/{mes}")
    sessoes = _deep_get(data, "AgendaPlenario", "Sessoes", "Sessao")
    return [_parse_sessao(s) for s in _ensure_list(sessoes)]


async def agenda_comissoes(data_str: str) -> list[ReuniaoComissao]:
    """Lista reuniões de comissões em uma data (formato AAAAMMDD)."""
    data = await _get(f"{AGENDA_COMISSOES_URL}/{data_str}")
    reunioes = _deep_get(data, "AgendaComissoes", "Reunioes", "Reuniao")
    return [_parse_reuniao(r) for r in _ensure_list(reunioes)]


# Auxiliares (2)


async def legislatura_atual() -> LegislaturaInfo | None:
    """Obtém informações da legislatura atual."""
    data = await _get(LEGISLATURA_URL)
    legs = _deep_get(data, "ListaLegislatura", "Legislaturas", "Legislatura")
    leg_list = _ensure_list(legs)
    if leg_list:
        return _parse_legislatura(leg_list[0])
    return None


async def tipos_materia_api() -> dict[str, str]:
    """Retorna tipos de matéria do Senado (dados estáticos)."""
    return dict(TIPOS_MATERIA)


# Dados Abertos Extras (4)


def _parse_emenda(raw: dict[str, Any]) -> Emenda:
    # New API: flat camelCase
    decisoes = _ensure_list(raw.get("decisoes"))
    primeira_decisao = decisoes[0] if decisoes else {}
    return Emenda(
        codigo=_str(raw.get("codigoEmenda")),
        numero=_str(raw.get("numeroEmenda")),
        identificacao=raw.get("identificacaoEmenda"),
        tipo=raw.get("tipoEmenda"),
        data_apresentacao=raw.get("dataApresentacao"),
        autor=raw.get("nomeAutor"),
        colegiado=raw.get("siglaColegiado"),
        decisao=primeira_decisao.get("descricaoDecisao") if primeira_decisao else None,
        data_decisao=primeira_decisao.get("dataDecisao") if primeira_decisao else None,
        url_documento=raw.get("urlDocumento"),
    )


def _parse_bloco(raw: dict[str, Any]) -> BlocoParlamentar:
    # Old API: nested PascalCase
    partidos_raw = _ensure_list(_deep_get(raw, "Partidos", "Partido"))
    partidos = [p.get("SiglaPartido") for p in partidos_raw if p.get("SiglaPartido")]
    return BlocoParlamentar(
        codigo=raw.get("CodigoBloco"),
        nome=raw.get("NomeBloco"),
        apelido=raw.get("NomeApelido"),
        data_criacao=raw.get("DataCriacao"),
        partidos=partidos or None,
    )


def _parse_lideranca(raw: dict[str, Any]) -> Lideranca:
    # New API: flat camelCase
    return Lideranca(
        codigo_parlamentar=_str(raw.get("codigoParlamentar")),
        nome_parlamentar=raw.get("nomeParlamentar"),
        partido=raw.get("siglaPartido"),
        tipo_lideranca=raw.get("tipoLideranca"),
        unidade_lideranca=raw.get("unidadeLideranca"),
        data_designacao=raw.get("dataDesignacao"),
    )


def _parse_relatoria(raw: dict[str, Any]) -> Relatoria:
    # New API: flat camelCase; truncate datetime to date-only
    data_designacao = raw.get("dataDesignacao")
    if data_designacao and len(data_designacao) > 10:
        data_designacao = data_designacao[:10]
    tramitando = raw.get("tramitando")
    return Relatoria(
        codigo_materia=_str(raw.get("codigoMateria")),
        identificacao=raw.get("identificacaoMateria"),
        ementa=raw.get("ementaMateria"),
        autor=raw.get("nomeAutorMateria"),
        tipo_relator=raw.get("descricaoTipoRelator"),
        data_designacao=data_designacao,
        colegiado=raw.get("siglaColegiado"),
        tramitando=tramitando == "Sim" if isinstance(tramitando, str) else None,
    )


async def emendas_materia(codigo: str) -> list[Emenda]:
    """Lista emendas a uma matéria legislativa."""
    data = await _get(EMENDAS_URL, params={"codigoMateria": codigo})
    return [_parse_emenda(e) for e in _ensure_list(data)]


async def listar_blocos() -> list[BlocoParlamentar]:
    """Lista blocos parlamentares do Senado."""
    data = await _get(BLOCOS_URL)
    blocos = _deep_get(data, "ListaBlocoParlamentar", "Blocos", "Bloco")
    return [_parse_bloco(b) for b in _ensure_list(blocos)]


async def listar_liderancas() -> list[Lideranca]:
    """Lista lideranças do Senado Federal."""
    data = await _get(LIDERANCAS_URL, params={"casa": "SF"})
    return [_parse_lideranca(lid) for lid in _ensure_list(data)]


async def relatorias_senador(codigo: str) -> list[Relatoria]:
    """Lista matérias de relatoria de um senador."""
    data = await _get(RELATORIAS_URL, params={"codigoParlamentar": codigo})
    return [_parse_relatoria(r) for r in _ensure_list(data)]
