"""HTTP client for the TCE-RN open data API.

The TCE-RN API uses path parameters for all endpoints. No query params.
Format is controlled by a {formato} path segment (Json/Csv).
All responses are flat JSON arrays (no wrapper/envelope).

Endpoints:
    - /InformacoesBasicasApi/JurisdicionadosTCE/Json  → listar_jurisdicionados
    - /BalancoOrcamentarioApi/Despesa/Json/{a}/{b}/{id} → buscar_despesas
    - /BalancoOrcamentarioApi/Receita/Json/{a}/{b}/{id} → buscar_receitas
    - /ProcedimentosLicitatoriosApi/LicitacaoPublica/Json/{id}/{di}/{df} → buscar_licitacoes
    - /ContratosApi/Contratos/Json/{id}/{hierarquia}    → buscar_contratos
"""

from __future__ import annotations

from typing import Any

from mcp_brasil._shared.http_client import http_get

from .constants import (
    CONTRATOS_PATH,
    DESPESA_PATH,
    JURISDICIONADOS_PATH,
    LICITACOES_PATH,
    RECEITA_PATH,
)
from .schemas import Contrato, Despesa, Jurisdicionado, Licitacao, Receita


async def listar_jurisdicionados() -> list[Jurisdicionado]:
    """Fetch all entities overseen by TCE-RN (~914 records)."""
    data: list[dict[str, Any]] = await http_get(JURISDICIONADOS_PATH)
    return [
        Jurisdicionado(
            identificador_unidade=item.get("identificadorUnidade"),
            codigo_orgao=item.get("codigoOrgao"),
            nome_orgao=item.get("nomeOrgao"),
            cnpj=item.get("cnpj"),
        )
        for item in data
    ]


async def buscar_despesas(
    *,
    ano: int,
    bimestre: int,
    id_unidade: int,
) -> list[Despesa]:
    """Fetch budget expenditure balance for a unit/year/bimester.

    Args:
        ano: Reference year (e.g. 2024).
        bimestre: Bimester (1-6).
        id_unidade: Unit ID from listar_jurisdicionados.
    """
    url = f"{DESPESA_PATH}/{ano}/{bimestre}/{id_unidade}"
    data: list[dict[str, Any]] = await http_get(url)
    return [
        Despesa(
            descricao_categoria_economica=item.get("descricaoCategoriaEconomica"),
            descricao_grupo_despesa=item.get("descricaoGrupoDespesa"),
            descricao_elemento_despesa=item.get("descricaoElementoDespesa"),
            valor_dotacao_inicial=item.get("valorDotacaoInicial"),
            valor_dotacao_atualizada=item.get("valorDotacaoAtualizada"),
            valor_empenho_ate_periodo=item.get("valorEmpenhoAtePeriodo"),
            valor_liquidacao_ate_periodo=item.get("valorLiquidacaoAtePeriodo"),
            valor_pago_ate_periodo=item.get("valorPagoAtePeriodo"),
        )
        for item in data
    ]


async def buscar_receitas(
    *,
    ano: int,
    bimestre: int,
    id_unidade: int,
) -> list[Receita]:
    """Fetch budget revenue balance for a unit/year/bimester.

    Args:
        ano: Reference year (e.g. 2024).
        bimestre: Bimester (1-6).
        id_unidade: Unit ID from listar_jurisdicionados.
    """
    url = f"{RECEITA_PATH}/{ano}/{bimestre}/{id_unidade}"
    data: list[dict[str, Any]] = await http_get(url)
    return [
        Receita(
            descricao_receita=item.get("descricaoReceita"),
            cod_natureza_receita=item.get("codNaturezaReceita"),
            valor_previsto_inicial=item.get("valorPrevistoInicial"),
            valor_previsto_atualizado=item.get("valorPrevistoAtualizado"),
            valor_realizado_no_exercicio=item.get("valorRealizadoNoExecicio"),
        )
        for item in data
    ]


async def buscar_licitacoes(
    *,
    id_unidade: int,
    data_inicio: str,
    data_fim: str,
) -> list[Licitacao]:
    """Fetch public bidding procedures for a unit within a date range.

    Args:
        id_unidade: Unit ID from listar_jurisdicionados.
        data_inicio: Start date (yyyy-MM-dd).
        data_fim: End date (yyyy-MM-dd).
    """
    url = f"{LICITACOES_PATH}/{id_unidade}/{data_inicio}/{data_fim}"
    data: list[dict[str, Any]] = await http_get(url)
    return [
        Licitacao(
            numero_licitacao=item.get("numeroLicitacao"),
            ano_licitacao=item.get("anoLicitacao"),
            modalidade=item.get("modalidade"),
            tipo_objeto=item.get("tipoObjeto"),
            descricao_objeto=item.get("descricaoObjeto"),
            valor_total_orcado=item.get("valorTotalOrcado"),
            situacao=item.get("situacaoProcedimentoLicitacao"),
            nome_jurisdicionado=item.get("nomeJurisdicionado"),
        )
        for item in data
    ]


async def buscar_contratos(
    *,
    id_unidade: int,
    considerar_hierarquia: bool = False,
) -> list[Contrato]:
    """Fetch contracts for a unit.

    Args:
        id_unidade: Unit ID from listar_jurisdicionados.
        considerar_hierarquia: Include sub-agencies.
    """
    hier = "true" if considerar_hierarquia else "false"
    url = f"{CONTRATOS_PATH}/{id_unidade}/{hier}"
    data: list[dict[str, Any]] = await http_get(url)
    return [
        Contrato(
            numero_contrato=item.get("numeroContrato"),
            ano_contrato=item.get("anoContrato"),
            objeto_contrato=item.get("objetoContrato"),
            valor_contrato=item.get("valorContrato"),
            nome_contratado=item.get("nomeContratado"),
            cpf_cnpj_contratado=item.get("cpfcnpjContratado"),
            data_inicio_vigencia=item.get("dataInicioVigencia"),
            data_termino_vigencia=item.get("dataTerminoVigencia"),
        )
        for item in data
    ]
