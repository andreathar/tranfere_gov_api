"""Tool functions for the Contratos.gov.br feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
    - Uses Context for structured logging and progress reporting
"""

from __future__ import annotations

from fastmcp import Context

from . import client


async def listar_contratos_unidade(
    unidade_codigo: int,
    ctx: Context,
) -> str:
    """Lista contratos ativos de uma Unidade Gestora (UG) no Contratos.gov.br.

    Retorna todos os contratos ativos vinculados à UG informada, com
    dados de fornecedor, objeto, valor e vigência. A API Contratos.gov.br
    cobre contratos federais gerenciados a partir de 2021.

    Args:
        unidade_codigo: Código da Unidade Gestora (UG/UASG) — ex: 110161.

    Returns:
        Lista de contratos ativos da UG com dados resumidos.
    """
    await ctx.info(f"Buscando contratos da UG {unidade_codigo}...")
    contratos = await client.listar_contratos_ug(unidade_codigo)

    if not contratos:
        return f"Nenhum contrato ativo encontrado para a UG {unidade_codigo}."

    lines = [f"**{len(contratos)} contratos ativos na UG {unidade_codigo}**\n"]
    for i, c in enumerate(contratos, 1):
        lines.extend(
            [
                f"### {i}. {c.objeto or 'Sem descrição'}",
                f"**ID:** {c.id} | **Nº:** {c.numero or 'N/A'}",
                f"**Fornecedor:** {c.fornecedor_nome or 'N/A'} ({c.fornecedor_cnpj_cpf or 'N/A'})",
                f"**Valor global:** {c.valor_global or 'N/A'}",
                f"**Vigência:** {c.vigencia_inicio or 'N/A'} a {c.vigencia_fim or 'N/A'}",
                f"**Situação:** {c.situacao or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)


async def consultar_contrato_id(
    contrato_id: int,
    ctx: Context,
) -> str:
    """Consulta um contrato específico pelo ID no Contratos.gov.br.

    Retorna dados completos do contrato: órgão, fornecedor, objeto,
    valores, vigência, modalidade e fundamento legal.

    Args:
        contrato_id: ID numérico do contrato no sistema Contratos.gov.br.

    Returns:
        Dados completos do contrato.
    """
    await ctx.info(f"Consultando contrato ID {contrato_id}...")
    c = await client.consultar_contrato(contrato_id)

    if not c:
        return f"Contrato {contrato_id} não encontrado."

    return "\n".join(
        [
            f"## Contrato {c.numero or contrato_id}",
            f"**Órgão:** {c.orgao_nome or 'N/A'} ({c.orgao_codigo or 'N/A'})",
            f"**UG:** {c.unidade_nome or 'N/A'} ({c.unidade_codigo or 'N/A'})",
            f"**Fornecedor:** {c.fornecedor_nome or 'N/A'} ({c.fornecedor_cnpj_cpf or 'N/A'})",
            f"**Objeto:** {c.objeto or 'N/A'}",
            f"**Tipo:** {c.tipo or 'N/A'} | **Categoria:** {c.categoria or 'N/A'}",
            f"**Modalidade:** {c.modalidade or 'N/A'}",
            f"**Fundamento legal:** {c.fundamento_legal or 'N/A'}",
            f"**Valor inicial:** {c.valor_inicial or 'N/A'}"
            f" | **Valor global:** {c.valor_global or 'N/A'}",
            f"**Valor parcela:** {c.valor_parcela or 'N/A'}"
            f" | **Acumulado:** {c.valor_acumulado or 'N/A'}",
            f"**Assinatura:** {c.data_assinatura or 'N/A'}"
            f" | **Publicação:** {c.data_publicacao or 'N/A'}",
            f"**Vigência:** {c.vigencia_inicio or 'N/A'} a {c.vigencia_fim or 'N/A'}",
            f"**Situação:** {c.situacao or 'N/A'}",
        ]
    )


async def consultar_empenhos_contrato(
    contrato_id: int,
    ctx: Context,
) -> str:
    """Lista empenhos (compromissos orçamentários) de um contrato.

    Empenhos representam a reserva de dotação orçamentária para pagamento
    do contrato. Mostra valores empenhados, liquidados e pagos.

    Args:
        contrato_id: ID numérico do contrato no Contratos.gov.br.

    Returns:
        Lista de empenhos vinculados ao contrato.
    """
    await ctx.info(f"Buscando empenhos do contrato {contrato_id}...")
    empenhos = await client.listar_empenhos(contrato_id)

    if not empenhos:
        return f"Nenhum empenho encontrado para o contrato {contrato_id}."

    lines = [f"**{len(empenhos)} empenhos no contrato {contrato_id}**\n"]
    for i, e in enumerate(empenhos, 1):
        lines.extend(
            [
                f"### {i}. Empenho {e.numero or 'N/A'}",
                f"**Credor:** {e.credor or 'N/A'}",
                f"**Natureza despesa:** {e.naturezadespesa or 'N/A'}",
                f"**Empenhado:** {e.empenhado or 'N/A'}"
                f" | **Liquidado:** {e.liquidado or 'N/A'}"
                f" | **Pago:** {e.pago or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)


async def consultar_faturas_contrato(
    contrato_id: int,
    ctx: Context,
) -> str:
    """Lista faturas (notas fiscais) de um contrato.

    Mostra as faturas emitidas pelo fornecedor, incluindo valor,
    glosas, juros, multas e situação de pagamento.

    Args:
        contrato_id: ID numérico do contrato no Contratos.gov.br.

    Returns:
        Lista de faturas do contrato.
    """
    await ctx.info(f"Buscando faturas do contrato {contrato_id}...")
    faturas = await client.listar_faturas(contrato_id)

    if not faturas:
        return f"Nenhuma fatura encontrada para o contrato {contrato_id}."

    lines = [f"**{len(faturas)} faturas no contrato {contrato_id}**\n"]
    for i, f in enumerate(faturas, 1):
        lines.extend(
            [
                f"### {i}. Fatura {f.numero or 'N/A'}",
                f"**Emissão:** {f.emissao or 'N/A'} | **Vencimento:** {f.vencimento or 'N/A'}",
                f"**Valor:** {f.valor or 'N/A'} | **Líquido:** {f.valorliquido or 'N/A'}",
                f"**Glosa:** {f.glosa or 'N/A'}"
                f" | **Juros:** {f.juros or 'N/A'}"
                f" | **Multa:** {f.multa or 'N/A'}",
                f"**Situação:** {f.situacao or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)


async def consultar_historico_contrato(
    contrato_id: int,
    ctx: Context,
) -> str:
    """Lista termos aditivos e apostilamentos de um contrato.

    Mostra o histórico de alterações contratuais: prorrogações,
    acréscimos, supressões e apostilamentos.

    Args:
        contrato_id: ID numérico do contrato no Contratos.gov.br.

    Returns:
        Histórico de alterações do contrato.
    """
    await ctx.info(f"Buscando histórico do contrato {contrato_id}...")
    historico = await client.listar_historico(contrato_id)

    if not historico:
        return f"Nenhum registro de histórico para o contrato {contrato_id}."

    lines = [f"**{len(historico)} registros no histórico do contrato {contrato_id}**\n"]
    for i, h in enumerate(historico, 1):
        lines.extend(
            [
                f"### {i}. {h.tipo or 'N/A'} nº {h.numero or 'N/A'}",
                f"**Fornecedor:** {h.fornecedor or 'N/A'}",
                f"**Assinatura:** {h.data_assinatura or 'N/A'}",
                f"**Vigência:** {h.vigencia_inicio or 'N/A'} a {h.vigencia_fim or 'N/A'}",
                f"**Valor global:** {h.valor_global or 'N/A'}",
                f"**Situação:** {h.situacao_contrato or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)


async def consultar_itens_contrato(
    contrato_id: int,
    ctx: Context,
) -> str:
    """Lista itens (materiais e serviços) de um contrato.

    Retorna todos os itens contratados com descrição, quantidade,
    valor unitário e valor total.

    Args:
        contrato_id: ID numérico do contrato no Contratos.gov.br.

    Returns:
        Lista de itens do contrato.
    """
    await ctx.info(f"Buscando itens do contrato {contrato_id}...")
    itens = await client.listar_itens(contrato_id)

    if not itens:
        return f"Nenhum item encontrado para o contrato {contrato_id}."

    lines = [f"**{len(itens)} itens no contrato {contrato_id}**\n"]
    for i, item in enumerate(itens, 1):
        lines.extend(
            [
                f"### {i}. {item.descricao_item or 'Sem descrição'}",
                f"**Código:** {item.codigo_item or 'N/A'} | **Tipo:** {item.tipo_item or 'N/A'}",
                f"**Qtd:** {item.quantidade or 'N/A'}"
                f" {item.unidade or ''}"
                f" x {item.valor_unitario or 'N/A'}"
                f" = **{item.valor_total or 'N/A'}**",
                "",
            ]
        )
    return "\n".join(lines)


async def consultar_terceirizados_contrato(
    contrato_id: int,
    ctx: Context,
) -> str:
    """Lista trabalhadores terceirizados vinculados a um contrato.

    Retorna os postos de trabalho terceirizados com função, jornada,
    salário e custo para a administração.

    Args:
        contrato_id: ID numérico do contrato no Contratos.gov.br.

    Returns:
        Lista de terceirizados do contrato.
    """
    await ctx.info(f"Buscando terceirizados do contrato {contrato_id}...")
    terceirizados = await client.listar_terceirizados(contrato_id)

    if not terceirizados:
        return f"Nenhum terceirizado encontrado para o contrato {contrato_id}."

    lines = [f"**{len(terceirizados)} terceirizados no contrato {contrato_id}**\n"]
    for i, t in enumerate(terceirizados, 1):
        lines.extend(
            [
                f"### {i}. {t.funcao or 'Função N/A'}",
                f"**Jornada:** {t.jornada or 'N/A'}"
                f" | **Salário:** {t.salario or 'N/A'}"
                f" | **Custo:** {t.custo or 'N/A'}",
                f"**Escolaridade:** {t.escolaridade or 'N/A'}"
                f" | **Situação:** {t.situacao or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)
