"""HTTP client for the Contratos.gov.br API.

Base URL: https://contratos.comprasnet.gov.br
Auth: None required for public endpoints (/api/contrato/)
Response format: JSON arrays or objects (no pagination wrapper)

Note: The API returns two different contract formats:
- /api/contrato/id/{id} — flat fields (orgao_codigo, orgao_nome, fornecedor_nome)
- /api/contrato/ug/{id} — nested dicts (contratante.orgao, fornecedor.nome)
The _parse_contrato function handles both formats.
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    CONTRATO_POR_ID_URL,
    CONTRATO_POR_UG_URL,
    CONTRATO_SUBRESOURCE_URL,
    ORGAOS_URL,
    UNIDADES_URL,
)
from .schemas import (
    ContratoResumo,
    Empenho,
    Fatura,
    HistoricoContrato,
    ItemContrato,
    Terceirizado,
)


def _parse_contrato(item: dict[str, Any]) -> ContratoResumo:
    """Parse contract from either flat (/id/) or nested (/ug/) format."""
    # Flat format (from /api/contrato/id/{id})
    orgao_codigo = item.get("orgao_codigo")
    orgao_nome = item.get("orgao_nome")
    unidade_codigo = item.get("unidade_codigo")
    unidade_nome = item.get("unidade_nome")
    fornecedor_tipo = item.get("fornecedor_tipo")
    fornecedor_cnpj_cpf = item.get("fonecedor_cnpj_cpf_idgener")
    fornecedor_nome = item.get("fornecedor_nome")
    fundamento_legal = item.get("fundamento_legal")

    # Nested format (from /api/contrato/ug/{id})
    contratante = item.get("contratante")
    if contratante and isinstance(contratante, dict):
        orgao = contratante.get("orgao", {})
        if orgao:
            orgao_codigo = orgao_codigo or orgao.get("codigo")
            orgao_nome = orgao_nome or orgao.get("nome")
            ug = orgao.get("unidade_gestora", {})
            if ug:
                unidade_codigo = unidade_codigo or ug.get("codigo")
                unidade_nome = unidade_nome or ug.get("nome")

    fornecedor = item.get("fornecedor")
    if fornecedor and isinstance(fornecedor, dict):
        fornecedor_tipo = fornecedor_tipo or fornecedor.get("tipo")
        fornecedor_cnpj_cpf = fornecedor_cnpj_cpf or fornecedor.get("cnpj_cpf_idgener")
        fornecedor_nome = fornecedor_nome or fornecedor.get("nome")

    return ContratoResumo(
        id=item.get("id"),
        receita_despesa=item.get("receita_despesa"),
        numero=item.get("numero"),
        orgao_codigo=orgao_codigo,
        orgao_nome=orgao_nome,
        unidade_codigo=unidade_codigo,
        unidade_nome=unidade_nome,
        fornecedor_tipo=fornecedor_tipo,
        fornecedor_cnpj_cpf=fornecedor_cnpj_cpf,
        fornecedor_nome=fornecedor_nome,
        tipo=item.get("tipo"),
        categoria=item.get("categoria"),
        processo=item.get("processo"),
        objeto=item.get("objeto"),
        fundamento_legal=fundamento_legal,
        modalidade=item.get("modalidade"),
        data_assinatura=item.get("data_assinatura"),
        data_publicacao=item.get("data_publicacao"),
        vigencia_inicio=item.get("vigencia_inicio"),
        vigencia_fim=item.get("vigencia_fim"),
        valor_inicial=item.get("valor_inicial"),
        valor_global=item.get("valor_global"),
        valor_parcela=item.get("valor_parcela"),
        valor_acumulado=item.get("valor_acumulado"),
        situacao=item.get("situacao"),
    )


async def listar_orgaos() -> list[dict[str, Any]]:
    """List all orgaos with active contracts."""
    data: list[dict[str, Any]] = await http_get(ORGAOS_URL)
    return data


async def listar_unidades() -> list[dict[str, Any]]:
    """List all unidades with active contracts."""
    data: list[dict[str, Any]] = await http_get(UNIDADES_URL)
    return data


async def listar_contratos_ug(unidade_codigo: int) -> list[ContratoResumo]:
    """List active contracts for a UG (Unidade Gestora)."""
    data: list[dict[str, Any]] = await http_get(f"{CONTRATO_POR_UG_URL}/{unidade_codigo}")
    return [_parse_contrato(i) for i in data] if isinstance(data, list) else []


async def consultar_contrato(contrato_id: int) -> ContratoResumo | None:
    """Get a single contract by ID. API returns a list; we take the first item."""
    data: Any = await http_get(f"{CONTRATO_POR_ID_URL}/{contrato_id}")
    # API returns a list even for single ID lookups
    if isinstance(data, list):
        if not data:
            return None
        return _parse_contrato(data[0])
    if isinstance(data, dict):
        if "error" in data:
            return None
        return _parse_contrato(data)
    return None


async def listar_empenhos(contrato_id: int) -> list[Empenho]:
    """List empenhos for a contract."""
    data: list[dict[str, Any]] = await http_get(
        f"{CONTRATO_SUBRESOURCE_URL}/{contrato_id}/empenhos"
    )
    if not isinstance(data, list):
        return []
    return [
        Empenho(
            id=i.get("id"),
            numero=i.get("numero"),
            credor=i.get("credor"),
            fonte_recurso=i.get("fonte_recurso"),
            programa_trabalho=i.get("programa_trabalho"),
            naturezadespesa=i.get("naturezadespesa"),
            empenhado=i.get("empenhado"),
            liquidado=i.get("liquidado"),
            pago=i.get("pago"),
        )
        for i in data
    ]


async def listar_faturas(contrato_id: int) -> list[Fatura]:
    """List invoices for a contract."""
    data: list[dict[str, Any]] = await http_get(
        f"{CONTRATO_SUBRESOURCE_URL}/{contrato_id}/faturas"
    )
    if not isinstance(data, list):
        return []
    return [
        Fatura(
            id=i.get("id"),
            numero=i.get("numero"),
            emissao=i.get("emissao"),
            vencimento=i.get("vencimento"),
            valor=i.get("valor"),
            juros=i.get("juros"),
            multa=i.get("multa"),
            glosa=i.get("glosa"),
            valorliquido=i.get("valorliquido"),
            situacao=i.get("situacao"),
        )
        for i in data
    ]


async def listar_historico(contrato_id: int) -> list[HistoricoContrato]:
    """List history (amendments/addendums) for a contract."""
    data: list[dict[str, Any]] = await http_get(
        f"{CONTRATO_SUBRESOURCE_URL}/{contrato_id}/historico"
    )
    if not isinstance(data, list):
        return []
    result: list[HistoricoContrato] = []
    for i in data:
        forn = i.get("fornecedor")
        forn_nome = forn.get("nome") if isinstance(forn, dict) else forn
        result.append(
            HistoricoContrato(
                id=i.get("id"),
                tipo=i.get("tipo"),
                numero=i.get("numero"),
                fornecedor=forn_nome,
                data_assinatura=i.get("data_assinatura"),
                vigencia_inicio=i.get("vigencia_inicio"),
                vigencia_fim=i.get("vigencia_fim"),
                valor_global=i.get("valor_global"),
                situacao_contrato=i.get("situacao_contrato"),
            )
        )
    return result


async def listar_itens(contrato_id: int) -> list[ItemContrato]:
    """List items for a contract."""
    data: list[dict[str, Any]] = await http_get(f"{CONTRATO_SUBRESOURCE_URL}/{contrato_id}/itens")
    if not isinstance(data, list):
        return []
    return [
        ItemContrato(
            tipo_item=i.get("tipo_item"),
            codigo_item=i.get("codigo_item"),
            descricao_item=i.get("descricao_item"),
            unidade=i.get("unidade"),
            quantidade=i.get("quantidade"),
            valor_unitario=i.get("valor_unitario"),
            valor_total=i.get("valor_total"),
        )
        for i in data
    ]


async def listar_terceirizados(contrato_id: int) -> list[Terceirizado]:
    """List outsourced workers for a contract."""
    data: list[dict[str, Any]] = await http_get(
        f"{CONTRATO_SUBRESOURCE_URL}/{contrato_id}/terceirizados"
    )
    if not isinstance(data, list):
        return []
    return [
        Terceirizado(
            id=i.get("id"),
            funcao=i.get("funcao"),
            jornada=i.get("jornada"),
            salario=i.get("salario"),
            custo=i.get("custo"),
            escolaridade=i.get("escolaridade"),
            situacao=i.get("situacao"),
        )
        for i in data
    ]
