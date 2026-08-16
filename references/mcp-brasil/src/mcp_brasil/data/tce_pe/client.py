"""HTTP client for the TCE-PE API.

The TCE-PE API uses a non-standard URL pattern:
    {API_BASE}/{Entity}!json?{params}

It returns ISO-8859-1 encoded responses with this structure:
    {"resposta": {"status": "OK", "entidade": "...",
     "tamanhoResultado": N, "limiteResultado": 100000,
     "conteudo": [...]}}

Endpoints:
    - /UnidadesJurisdicionadas → buscar_unidades
    - /LicitacaoUG            → buscar_licitacoes
    - /Contratos              → buscar_contratos
    - /DespesasMunicipais     → buscar_despesas
    - /Fornecedores           → buscar_fornecedores
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from mcp_brasil.exceptions import HttpClientError
from mcp_brasil.settings import HTTP_TIMEOUT, USER_AGENT

from .constants import (
    API_BASE,
    CONTRATOS_ENTITY,
    DESPESAS_ENTITY,
    FORNECEDORES_ENTITY,
    LICITACOES_ENTITY,
    RESPONSE_ENCODING,
    UNIDADES_ENTITY,
)
from .schemas import Contrato, Despesa, Fornecedor, Licitacao, UnidadeJurisdicionada

logger = logging.getLogger(__name__)


async def _fetch(entity: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Fetch data from TCE-PE API handling ISO-8859-1 encoding.

    Args:
        entity: Entity name (e.g. "Fornecedores", "LicitacaoUG").
        params: Query parameters.

    Returns:
        List of items from the 'conteudo' field.

    Raises:
        HttpClientError: On request failure or unexpected response.
    """
    url = f"{API_BASE}/{entity}!json"
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(HTTP_TIMEOUT),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HttpClientError(f"HTTP {exc.response.status_code} from {url}") from exc
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise HttpClientError(f"Request to {url} failed: {exc}") from exc

    # Decode with ISO-8859-1
    text = response.content.decode(RESPONSE_ENCODING)
    data = json.loads(text)

    resposta = data.get("resposta", {})
    if resposta.get("status") != "OK":
        raise HttpClientError(f"TCE-PE API error for {entity}: {resposta.get('status')}")

    items: list[dict[str, Any]] = resposta.get("conteudo", [])
    return items


async def buscar_unidades(
    *,
    natureza: str = "prefeitura",
    municipio: str | None = None,
) -> list[UnidadeJurisdicionada]:
    """Busca unidades jurisdicionadas do TCE-PE.

    Args:
        natureza: Tipo de unidade (prefeitura, câmara, etc.).
        municipio: Filtrar por município.
    """
    params: dict[str, Any] = {"NATUREZA": natureza}
    if municipio:
        params["MUNICIPIO"] = municipio

    items = await _fetch(UNIDADES_ENTITY, params)
    return [
        UnidadeJurisdicionada(
            codigo=str(item.get("Codigo", "")),
            nome=item.get("Nome"),
            natureza=item.get("Natureza"),
            municipio=item.get("Municipio"),
            codigo_municipio=item.get("CodigoMunicipio"),
        )
        for item in items
    ]


async def buscar_licitacoes(
    *,
    ano: int,
    municipio: str | None = None,
    modalidade: str | None = None,
) -> list[Licitacao]:
    """Busca licitações registradas no TCE-PE.

    Args:
        ano: Ano da licitação (obrigatório).
        municipio: Filtrar por município.
        modalidade: Filtrar por modalidade.
    """
    params: dict[str, Any] = {"ANOLICITACAO": ano}
    if municipio:
        params["MUNICIPIO"] = municipio
    if modalidade:
        params["MODALIDADE"] = modalidade

    items = await _fetch(LICITACOES_ENTITY, params)
    return [
        Licitacao(
            numero_licitacao=item.get("NUMEROLICITACAO"),
            ano_licitacao=item.get("ANOLICITACAO"),
            modalidade=item.get("MODALIDADE"),
            objeto=item.get("OBJETO"),
            valor_estimado=item.get("VALORESTIMADO"),
            situacao=item.get("SITUACAO"),
            municipio=item.get("MUNICIPIO"),
            unidade_gestora=item.get("NOMEUNIDADEGESTORA"),
            id_unidade_gestora=item.get("ID_UNIDADE_GESTORA"),
        )
        for item in items
    ]


async def buscar_contratos(
    *,
    ano: int,
    municipio: str | None = None,
    cpf_cnpj: str | None = None,
) -> list[Contrato]:
    """Busca contratos registrados no TCE-PE.

    Args:
        ano: Ano de referência (obrigatório).
        municipio: Filtrar por município.
        cpf_cnpj: Filtrar por CPF/CNPJ do fornecedor.
    """
    params: dict[str, Any] = {"ANOREFERENCIA": ano}
    if municipio:
        params["MUNICIPIO"] = municipio
    if cpf_cnpj:
        params["CPFCNPJ"] = cpf_cnpj

    items = await _fetch(CONTRATOS_ENTITY, params)
    return [
        Contrato(
            numero_contrato=item.get("NUMEROCONTRATO"),
            ano_referencia=item.get("ANOREFERENCIA"),
            objeto=item.get("OBJETO"),
            valor_contrato=item.get("VALORCONTRATO"),
            fornecedor=item.get("FORNECEDOR"),
            cpf_cnpj=item.get("CPFCNPJ"),
            municipio=item.get("MUNICIPIO"),
            unidade_gestora=item.get("NOMEUNIDADEGESTORA"),
            id_unidade_gestora=item.get("ID_UNIDADE_GESTORA"),
        )
        for item in items
    ]


async def buscar_despesas(
    *,
    ano: int,
    mes: int | None = None,
    municipio: str | None = None,
    codigo_municipio: str | None = None,
) -> list[Despesa]:
    """Busca despesas municipais registradas no TCE-PE.

    Args:
        ano: Ano de referência (obrigatório).
        mes: Mês de referência (1-12).
        municipio: Filtrar por nome do município.
        codigo_municipio: Filtrar por código SAGRES do município.
    """
    params: dict[str, Any] = {"ANOREFERENCIA": ano}
    if mes:
        params["MESREFERENCIA"] = mes
    if municipio:
        params["MUNICIPIO"] = municipio
    if codigo_municipio:
        params["CODIGO_MUNICIPIO"] = codigo_municipio

    items = await _fetch(DESPESAS_ENTITY, params)
    return [
        Despesa(
            numero_empenho=item.get("NUMEROEMPENHO"),
            ano_referencia=item.get("ANOREFERENCIA"),
            mes_referencia=item.get("MESREFERENCIA"),
            fornecedor=item.get("FORNECEDOR"),
            cpf_cnpj=item.get("CPF_CNPJ"),
            historico=item.get("HISTORICO"),
            valor_empenhado=item.get("VALOREMPENHADO"),
            valor_liquidado=item.get("VALORLIQUIDADO"),
            valor_pago=item.get("VALORPAGO"),
            funcao=item.get("FUNCAO"),
            elemento_despesa=item.get("ELEMENTODESPESA"),
            unidade_gestora=item.get("NOMEUNIDADEGESTORA"),
            codigo_municipio=item.get("CODIGO_MUNICIPIO"),
        )
        for item in items
    ]


async def buscar_fornecedores(
    *,
    nome: str | None = None,
    cpf_cnpj: str | None = None,
) -> list[Fornecedor]:
    """Busca fornecedores registrados no TCE-PE.

    Args:
        nome: Filtrar por nome (busca parcial).
        cpf_cnpj: Filtrar por CPF/CNPJ (busca parcial).
    """
    params: dict[str, Any] = {}
    if nome:
        params["NOME"] = nome
    if cpf_cnpj:
        params["CPFCNPJ"] = cpf_cnpj

    items = await _fetch(FORNECEDORES_ENTITY, params)
    return [
        Fornecedor(
            cpf_cnpj=item.get("CPFCNPJ"),
            nome=item.get("NOME"),
            tipo_credor=item.get("TipoCredor"),
        )
        for item in items
    ]
