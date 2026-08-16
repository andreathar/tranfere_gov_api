"""HTTP client for the TCE-RJ API.

Endpoints:
    - /licitacoes                              → buscar_licitacoes
    - /contratos_municipio                     → buscar_contratos_municipio
    - /compras_diretas_municipio               → buscar_compras_diretas_municipio
    - /compras_diretas_estado                  → buscar_compras_diretas_estado
    - /obras_paralisadas                       → buscar_obras_paralisadas
    - /penalidades_ressarcimento_municipio     → buscar_penalidades
    - /prestacao_contas_municipio              → buscar_prestacao_contas
    - /concessoes_publicas                     → buscar_concessoes
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    COMPRAS_DIRETAS_ESTADO_URL,
    COMPRAS_DIRETAS_MUNICIPIO_URL,
    CONCESSOES_PUBLICAS_URL,
    CONTRATOS_MUNICIPIO_URL,
    DEFAULT_LIMITE,
    LICITACOES_URL,
    OBRAS_PARALISADAS_URL,
    PENALIDADES_MUNICIPIO_URL,
    PRESTACAO_CONTAS_MUNICIPIO_URL,
)
from .schemas import (
    CompraDireta,
    Concessao,
    ConcessaoMunicipio,
    ContratoMunicipio,
    ContratoMunicipioResultado,
    Licitacao,
    LicitacaoResultado,
    ObraParalisada,
    Penalidade,
    PrestacaoContas,
)


async def buscar_licitacoes(
    *,
    ano: int | None = None,
    municipio: str | None = None,
    inicio: int = 0,
    limite: int = DEFAULT_LIMITE,
) -> LicitacaoResultado:
    """Busca licitações municipais no RJ."""
    params: dict[str, Any] = {"inicio": inicio, "limite": limite}
    if ano:
        params["ano"] = ano
    if municipio:
        params["municipio"] = municipio
    data: dict[str, Any] | list[Any] = await http_get(LICITACOES_URL, params=params)
    if isinstance(data, dict):
        items = data.get("Licitacoes", [])
        total = data.get("Count", len(items))
    else:
        items = data
        total = len(items)
    licitacoes = [
        Licitacao(
            ente=item.get("Ente"),
            unidade=item.get("Unidade"),
            ano=item.get("Ano"),
            modalidade=item.get("Modalidade"),
            tipo=item.get("Tipo"),
            processo_licitatorio=item.get("ProcessoLicitatorio"),
            numero_edital=item.get("NumeroEdital"),
            objeto=item.get("Objeto"),
            valor_estimado=item.get("ValorEstimado"),
            data_publicacao_oficial=item.get("DataPublicacaoOficial"),
            data_homologacao=item.get("DataHomologacao"),
        )
        for item in items
    ]
    return LicitacaoResultado(licitacoes=licitacoes, total=total)


async def buscar_contratos_municipio(
    *,
    ano: int | None = None,
    municipio: str | None = None,
    inicio: int = 0,
    limite: int = DEFAULT_LIMITE,
) -> ContratoMunicipioResultado:
    """Busca contratos municipais no RJ."""
    params: dict[str, Any] = {"inicio": inicio, "limite": limite}
    if ano:
        params["ano"] = ano
    if municipio:
        params["municipio"] = municipio
    data: dict[str, Any] | list[Any] = await http_get(CONTRATOS_MUNICIPIO_URL, params=params)
    if isinstance(data, dict):
        items = data.get("Contratos", [])
        total = data.get("Count", len(items))
    else:
        items = data
        total = len(items)
    contratos = [
        ContratoMunicipio(
            ente=item.get("Ente"),
            numero_contrato=item.get("NumeroContrato"),
            ano_contrato=item.get("AnoContrato"),
            contratado=item.get("Contratado"),
            cpf_cnpj_contratado=item.get("CNPJCPFContratado"),
            objeto=item.get("Objeto"),
            tipo_contrato=item.get("TipoContrato"),
            valor_contrato=item.get("ValorContrato"),
            data_assinatura_contrato=item.get("DataAssinaturaContrato"),
            data_vencimento_contrato=item.get("DataVencimentoContrato"),
        )
        for item in items
    ]
    return ContratoMunicipioResultado(contratos=contratos, total=total)


async def buscar_compras_diretas_municipio(
    *,
    ano: int | None = None,
    municipio: str | None = None,
    inicio: int = 0,
    limite: int = DEFAULT_LIMITE,
) -> list[CompraDireta]:
    """Busca compras diretas municipais (dispensas e inexigibilidades)."""
    params: dict[str, Any] = {"inicio": inicio, "limite": limite}
    if ano:
        params["ano"] = ano
    if municipio:
        params["municipio"] = municipio
    data: dict[str, Any] | list[Any] = await http_get(COMPRAS_DIRETAS_MUNICIPIO_URL, params=params)
    items = data.get("Compras", data) if isinstance(data, dict) else data
    return [
        CompraDireta(
            processo=item.get("Processo"),
            ano_processo=item.get("AnoProcesso"),
            unidade=item.get("Unidade") or item.get("Municipio"),
            objeto=item.get("Objeto"),
            afastamento=item.get("EnquadramentoLegal") or item.get("Afastamento"),
            fornecedor_vencedor=item.get("Fornecedor") or item.get("CPFCNPJFornecedor"),
            valor_processo=item.get("ValorTotalCompra") or item.get("ValorProcesso"),
            data_aprovacao=item.get("DataProcesso"),
            enquadramento_legal=item.get("Fundamentacao"),
        )
        for item in items
    ]


async def buscar_compras_diretas_estado(
    *,
    inicio: int = 0,
    limite: int = DEFAULT_LIMITE,
) -> list[CompraDireta]:
    """Busca compras diretas do Estado do RJ."""
    params: dict[str, Any] = {"inicio": inicio, "limite": limite}
    data: list[dict[str, Any]] = await http_get(COMPRAS_DIRETAS_ESTADO_URL, params=params)
    return [
        CompraDireta(
            processo=item.get("Processo"),
            ano_processo=item.get("AnoProcesso"),
            unidade=item.get("Unidade"),
            objeto=item.get("Objeto"),
            afastamento=item.get("Afastamento"),
            fornecedor_vencedor=item.get("FornecedorVencedor"),
            valor_processo=item.get("ValorProcesso"),
            data_aprovacao=item.get("DataAprovacao"),
            enquadramento_legal=item.get("EnquadramentoLegal"),
        )
        for item in data
    ]


async def buscar_obras_paralisadas() -> list[ObraParalisada]:
    """Busca obras públicas paralisadas (estado e municípios)."""
    data: dict[str, Any] | list[Any] = await http_get(OBRAS_PARALISADAS_URL)
    items = data.get("Obras", data) if isinstance(data, dict) else data
    return [
        ObraParalisada(
            ente=item.get("Ente"),
            tipo_ente=item.get("TipoEnte"),
            nome=item.get("Nome"),
            funcao_governo=item.get("FuncaoGoverno"),
            numero_contrato=item.get("NumeroContrato"),
            nome_contratada=item.get("NomeContratada"),
            cnpj_contratada=item.get("CNPJContratada"),
            valor_total_contrato=item.get("ValorTotalContrato"),
            valor_pago_obra=item.get("ValorPagoObra"),
            tempo_paralisacao=item.get("TempoParalizacao"),
            motivo_paralisacao=item.get("MotivoParalisacao"),
            data_paralisacao=item.get("DataParalisacao"),
            data_inicio_obra=item.get("DataInicioObra"),
            status_contrato=item.get("StatusContrato"),
            classificacao_obra=item.get("ClassificacaoObra"),
        )
        for item in items
    ]


async def buscar_penalidades(
    *,
    tipo: str | None = None,
) -> list[Penalidade]:
    """Busca penalidades e ressarcimentos municipais."""
    params: dict[str, Any] = {}
    if tipo:
        params["tipo"] = tipo
    data: list[dict[str, Any]] = await http_get(PENALIDADES_MUNICIPIO_URL, params=params)
    return [
        Penalidade(
            processo=item.get("Processo"),
            ano_condenacao=item.get("AnoCondenacao"),
            valor_penalidade=item.get("ValorPenalidade"),
            condenacao=item.get("Condenacao"),
            ente=item.get("Ente"),
            nome_orgao=item.get("NomeOrgao"),
            tipo_ente=item.get("TipoEnte"),
            grupo_natureza=item.get("GrupoNatureza"),
            data_sessao=item.get("DataSessao"),
        )
        for item in data
    ]


async def buscar_prestacao_contas() -> list[PrestacaoContas]:
    """Busca prestação de contas dos municípios."""
    data: list[dict[str, Any]] = await http_get(PRESTACAO_CONTAS_MUNICIPIO_URL)
    return [
        PrestacaoContas(
            municipio=item.get("Municipio"),
            regiao=item.get("Regiao"),
            ano=item.get("Ano"),
            indicador=item.get("Indicador"),
            processo=item.get("Processo"),
            responsavel=item.get("Responsavel"),
        )
        for item in data
    ]


async def buscar_concessoes() -> list[ConcessaoMunicipio]:
    """Busca concessões públicas municipais."""
    data: list[dict[str, Any]] = await http_get(CONCESSOES_PUBLICAS_URL)
    result: list[ConcessaoMunicipio] = []
    for mun in data:
        concessoes = [
            Concessao(
                ente=c.get("Ente"),
                unidade=c.get("Unidade"),
                numero=c.get("Numero"),
                objeto=c.get("Objeto"),
                data_assinatura=c.get("DataAssinatura"),
                data_execucao_final=c.get("DataExecucaoFinal"),
                situacao_concessao=c.get("SituacaoConcessao"),
                natureza=c.get("Natureza"),
                segmento_servico=c.get("SegmentoServicoConcedido"),
                nome_razao_social=c.get("NomeRazaoSocial"),
                valor_total_outorga=c.get("ValorTotalOutorga"),
            )
            for c in mun.get("Concessoes", [])
        ]
        result.append(
            ConcessaoMunicipio(
                municipio=mun.get("Municipio", ""),
                concessoes=concessoes,
            )
        )
    return result
