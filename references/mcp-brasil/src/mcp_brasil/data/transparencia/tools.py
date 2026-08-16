"""Tool functions for the Transparência feature.

Rules (ADR-001):
    - tools.py NEVER makes HTTP directly — delegates to client.py
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

from mcp_brasil._shared.formatting import format_brl, markdown_table, truncate_list
from mcp_brasil.exceptions import HttpClientError

from . import client
from .constants import DEFAULT_PAGE_SIZE


def _pagination_hint(count: int, pagina: int) -> str:
    """Return a pagination hint string based on result count and current page."""
    if count >= DEFAULT_PAGE_SIZE:
        return f"\n\n> Use `pagina={pagina + 1}` para ver mais resultados."
    if pagina > 1 and count < DEFAULT_PAGE_SIZE:
        return "\n\n> Última página de resultados."
    return ""


async def buscar_contratos(cpf_cnpj: str, pagina: int = 1) -> str:
    """Busca contratos federais por CPF ou CNPJ do fornecedor.

    Consulta o Portal da Transparência para listar contratos firmados
    com o governo federal por um fornecedor específico.

    Args:
        cpf_cnpj: CPF ou CNPJ do fornecedor (aceita com ou sem formatação).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com contratos encontrados.
    """
    contratos = await client.buscar_contratos(cpf_cnpj, pagina)
    if not contratos:
        return f"Nenhum contrato encontrado para o CPF/CNPJ '{cpf_cnpj}'."

    rows = [
        (
            c.numero or "—",
            (c.objeto or "—")[:80],
            format_brl(c.valor_final) if c.valor_final else "—",
            c.data_inicio or "—",
            c.data_fim or "—",
            (c.orgao or "—")[:40],
        )
        for c in contratos
    ]
    header = f"Contratos do fornecedor {cpf_cnpj} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Objeto", "Valor Final", "Início", "Fim", "Órgão"], rows
    )
    return table + _pagination_hint(len(contratos), pagina)


async def consultar_despesas(
    mes_ano_inicio: str,
    mes_ano_fim: str,
    codigo_favorecido: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta despesas e recursos recebidos por favorecido.

    Mostra pagamentos realizados pelo governo federal a um favorecido
    (pessoa física ou jurídica) em um período.

    Args:
        mes_ano_inicio: Mês/ano de início no formato MM/AAAA (ex: 01/2024).
        mes_ano_fim: Mês/ano de fim no formato MM/AAAA (ex: 12/2024).
        codigo_favorecido: CPF ou CNPJ do favorecido (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com despesas encontradas.
    """
    despesas = await client.consultar_despesas(
        mes_ano_inicio, mes_ano_fim, codigo_favorecido, pagina
    )
    if not despesas:
        return "Nenhuma despesa encontrada para os parâmetros informados."

    rows = [
        (
            f"{d.mes or '—'}/{d.ano or '—'}",
            (d.favorecido_nome or "—")[:50],
            format_brl(d.valor) if d.valor else "—",
            (d.orgao_nome or "—")[:40],
            d.uf or "—",
        )
        for d in despesas
    ]
    header = f"Despesas de {mes_ano_inicio} a {mes_ano_fim} (página {pagina}):\n\n"
    table = header + markdown_table(["Período", "Favorecido", "Valor", "Órgão", "UF"], rows)
    return table + _pagination_hint(len(despesas), pagina)


async def buscar_servidores(
    cpf: str | None = None,
    nome: str | None = None,
    codigo_orgao_lotacao: str | None = None,
    codigo_orgao_exercicio: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca servidores públicos federais por CPF, nome ou órgão.

    Consulta a base de servidores do Portal da Transparência.
    A API exige pelo menos um: CPF, código de órgão de lotação ou código de
    órgão de exercício. O nome sozinho não é aceito pela API — combine com
    código de órgão para buscar por nome.

    Args:
        cpf: CPF do servidor (opcional).
        nome: Nome do servidor (opcional, requer código de órgão junto).
        codigo_orgao_lotacao: Código SIAPE do órgão de lotação (ex: "3" para AGU,
            "26246" para UFPI). Permite buscar todos os servidores de um órgão.
        codigo_orgao_exercicio: Código SIAPE do órgão de exercício (alternativo
            ao código de lotação).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com servidores encontrados.
    """
    if not cpf and not codigo_orgao_lotacao and not codigo_orgao_exercicio:
        return (
            "Informe CPF ou código de órgão (lotação ou exercício) para a busca. "
            "A API exige pelo menos um desses filtros. "
            "Exemplos de códigos SIAPE: '3' (AGU), '26246' (UFPI), '25000' (MEC)."
        )

    servidores = await client.buscar_servidores(
        cpf=cpf,
        nome=nome,
        codigo_orgao_lotacao=codigo_orgao_lotacao,
        codigo_orgao_exercicio=codigo_orgao_exercicio,
        pagina=pagina,
    )
    if not servidores:
        busca = cpf or nome
        return f"Nenhum servidor encontrado para '{busca}'."

    rows = [
        (
            s.cpf or "—",
            (s.nome or "—")[:50],
            s.tipo_servidor or "—",
            s.situacao or "—",
            (s.orgao or "—")[:40],
        )
        for s in servidores
    ]
    busca = cpf or nome
    header = f"Servidores encontrados para '{busca}' (página {pagina}):\n\n"
    table = header + markdown_table(["CPF", "Nome", "Tipo", "Situação", "Órgão"], rows)
    return table + _pagination_hint(len(servidores), pagina)


async def buscar_licitacoes(
    codigo_orgao: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca licitações federais por órgão e/ou período.

    Consulta processos licitatórios do governo federal.
    Pelo menos um filtro (órgão ou datas) é recomendado.

    Args:
        codigo_orgao: Código SIAFI do órgão (ex: "26246" para UFPI).
        data_inicial: Data inicial no formato DD/MM/AAAA.
        data_final: Data final no formato DD/MM/AAAA.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com licitações encontradas.
    """
    licitacoes = await client.buscar_licitacoes(
        codigo_orgao=codigo_orgao,
        data_inicial=data_inicial,
        data_final=data_final,
        pagina=pagina,
    )
    if not licitacoes:
        return "Nenhuma licitação encontrada para os parâmetros informados."

    rows = [
        (
            lc.numero or "—",
            (lc.objeto or "—")[:60],
            lc.modalidade or "—",
            lc.situacao or "—",
            format_brl(lc.valor_estimado) if lc.valor_estimado else "—",
            lc.data_abertura or "—",
        )
        for lc in licitacoes
    ]
    header = f"Licitações encontradas (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Objeto", "Modalidade", "Situação", "Valor Est.", "Abertura"], rows
    )
    return table + _pagination_hint(len(licitacoes), pagina)


async def consultar_bolsa_familia(
    mes_ano: str,
    codigo_ibge: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta dados do Novo Bolsa Família por município ou NIS.

    Informe código IBGE do município OU NIS do beneficiário.
    Retorna dados de pagamento do programa de transferência de renda.

    Args:
        mes_ano: Mês/ano de referência no formato AAAAMM (ex: 202401).
        codigo_ibge: Código IBGE do município (ex: 3550308 para São Paulo).
        nis: NIS (Número de Identificação Social) do beneficiário.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Dados do Bolsa Família encontrados.
    """
    if not codigo_ibge and not nis:
        return "Informe o código IBGE do município ou o NIS do beneficiário."

    if nis:
        sacados = await client.consultar_bolsa_familia_nis(mes_ano, nis, pagina)
        if not sacados:
            return f"Nenhum dado encontrado para NIS '{nis}' em {mes_ano}."
        rows = [
            (
                s.nis or "—",
                (s.nome or "—")[:50],
                s.municipio or "—",
                s.uf or "—",
                format_brl(s.valor) if s.valor else "—",
            )
            for s in sacados
        ]
        table = f"Bolsa Família — NIS {nis} ({mes_ano}):\n\n" + markdown_table(
            ["NIS", "Nome", "Município", "UF", "Valor"], rows
        )
        return table + _pagination_hint(len(sacados), pagina)

    assert codigo_ibge is not None
    municipios = await client.consultar_bolsa_familia_municipio(mes_ano, codigo_ibge, pagina)
    if not municipios:
        return f"Nenhum dado encontrado para município {codigo_ibge} em {mes_ano}."
    rows = [
        (
            m.municipio or "—",
            m.uf or "—",
            str(m.quantidade) if m.quantidade else "—",
            format_brl(m.valor) if m.valor else "—",
            m.data_referencia or "—",
        )
        for m in municipios
    ]
    table = f"Bolsa Família — Município {codigo_ibge} ({mes_ano}):\n\n" + markdown_table(
        ["Município", "UF", "Beneficiados", "Valor", "Referência"], rows
    )
    return table + _pagination_hint(len(municipios), pagina)


async def buscar_sancoes(
    consulta: str,
    bases: list[str] | None = None,
    pagina: int = 1,
) -> str:
    """Busca sanções em bases federais (CEIS, CNEP, CEPIM, CEAF).

    Consulta simultânea nas bases de sanções do governo federal.
    Útil para due diligence, compliance e verificação anticorrupção.

    Bases disponíveis:
    - CEIS: Empresas Inidôneas e Suspensas
    - CNEP: Empresas Punidas (Lei Anticorrupção 12.846)
    - CEPIM: Entidades sem Fins Lucrativos Impedidas
    - CEAF: Expulsões da Administração Federal

    Args:
        consulta: CPF, CNPJ ou nome da pessoa/empresa a pesquisar.
        bases: Lista de bases (ex: ["ceis", "cnep"]). Padrão: todas.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Sanções encontradas agrupadas por base.
    """
    sancoes = await client.buscar_sancoes(consulta, bases, pagina)
    if not sancoes:
        bases_str = ", ".join(bases) if bases else "CEIS, CNEP, CEPIM, CEAF"
        return f"Nenhuma sanção encontrada para '{consulta}' nas bases: {bases_str}."

    items: list[str] = []
    for s in sancoes:
        parts = [f"**{s.nome or '—'}** ({s.cpf_cnpj or '—'})"]
        parts.append(f"  Fonte: {s.fonte or '—'}")
        if s.tipo:
            parts.append(f"  Tipo: {s.tipo}")
        if s.orgao:
            parts.append(f"  Órgão sancionador: {s.orgao}")
        if s.data_inicio or s.data_fim:
            parts.append(f"  Período: {s.data_inicio or '—'} a {s.data_fim or '—'}")
        if s.fundamentacao:
            parts.append(f"  Fundamentação: {s.fundamentacao}")
        items.append("\n".join(parts))

    header = f"Sanções encontradas para '{consulta}' ({len(sancoes)} resultado(s)):\n\n"
    result = header + truncate_list(items, max_items=30)
    return result + _pagination_hint(len(sancoes), pagina)


async def buscar_emendas(
    ano: int | None = None,
    nome_autor: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca emendas parlamentares por ano e/ou autor.

    Consulta emendas individuais e de bancada ao orçamento federal.

    Args:
        ano: Ano da emenda (ex: 2024).
        nome_autor: Nome do parlamentar autor da emenda.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com emendas encontradas.
    """
    emendas = await client.buscar_emendas(ano=ano, nome_autor=nome_autor, pagina=pagina)
    if not emendas:
        return "Nenhuma emenda encontrada para os parâmetros informados."

    rows = [
        (
            e.numero or "—",
            (e.autor or "—")[:40],
            e.tipo or "—",
            (e.localidade or "—")[:30],
            format_brl(e.valor_empenhado) if e.valor_empenhado else "—",
            format_brl(e.valor_pago) if e.valor_pago else "—",
        )
        for e in emendas
    ]
    header = f"Emendas parlamentares (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Autor", "Tipo", "Localidade", "Empenhado", "Pago"], rows
    )
    return table + _pagination_hint(len(emendas), pagina)


async def consultar_viagens(cpf: str, pagina: int = 1) -> str:
    """Consulta viagens a serviço de servidor federal por CPF.

    Mostra viagens realizadas a serviço, incluindo diárias e passagens.

    Args:
        cpf: CPF do servidor (aceita com ou sem formatação).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com viagens encontradas.
    """
    viagens = await client.consultar_viagens(cpf, pagina)
    if not viagens:
        return f"Nenhuma viagem encontrada para o CPF '{cpf}'."

    rows = [
        (
            (v.nome or "—")[:40],
            v.cargo or "—",
            (v.orgao or "—")[:30],
            v.destino or "—",
            f"{v.data_inicio or '—'} a {v.data_fim or '—'}",
            format_brl(v.valor_diarias) if v.valor_diarias else "—",
            format_brl(v.valor_passagens) if v.valor_passagens else "—",
        )
        for v in viagens
    ]
    header = f"Viagens do servidor CPF {cpf} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Nome", "Cargo", "Órgão", "Destino", "Período", "Diárias", "Passagens"], rows
    )
    return table + _pagination_hint(len(viagens), pagina)


async def buscar_convenios(
    orgao: str | None = None,
    convenente: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca convênios e transferências voluntárias do governo federal.

    Consulta convênios celebrados entre órgãos federais e entidades
    (estados, municípios, ONGs) para repasse de recursos.

    Args:
        orgao: Código do órgão concedente (ex: "26246").
        convenente: Nome ou CNPJ do convenente.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com convênios encontrados.
    """
    convenios = await client.buscar_convenios(orgao=orgao, convenente=convenente, pagina=pagina)
    if not convenios:
        return "Nenhum convênio encontrado para os parâmetros informados."

    rows = [
        (
            c.numero or "—",
            (c.objeto or "—")[:60],
            c.situacao or "—",
            format_brl(c.valor_convenio) if c.valor_convenio else "—",
            format_brl(c.valor_liberado) if c.valor_liberado else "—",
            (c.orgao or "—")[:30],
            (c.convenente or "—")[:30],
        )
        for c in convenios
    ]
    header = f"Convênios encontrados (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Objeto", "Situação", "Valor", "Liberado", "Órgão", "Convenente"], rows
    )
    return table + _pagination_hint(len(convenios), pagina)


async def buscar_cartoes_pagamento(
    cpf_portador: str | None = None,
    codigo_orgao: str | None = None,
    mes_ano_inicio: str | None = None,
    mes_ano_fim: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca pagamentos com cartão corporativo (suprimento de fundos).

    Consulta gastos realizados com cartão de pagamento do governo federal,
    incluindo cartão corporativo e suprimento de fundos.

    Args:
        cpf_portador: CPF do portador do cartão (opcional).
        codigo_orgao: Código do órgão (opcional).
        mes_ano_inicio: Mês/ano de início no formato MM/AAAA (ex: 01/2024).
        mes_ano_fim: Mês/ano de fim no formato MM/AAAA (ex: 12/2024).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com pagamentos encontrados.
    """
    cartoes = await client.buscar_cartoes_pagamento(
        cpf_portador=cpf_portador,
        codigo_orgao=codigo_orgao,
        mes_ano_inicio=mes_ano_inicio,
        mes_ano_fim=mes_ano_fim,
        pagina=pagina,
    )
    if not cartoes:
        return "Nenhum pagamento com cartão encontrado para os parâmetros informados."

    rows = [
        (
            (c.portador or "—")[:40],
            (c.orgao or "—")[:30],
            format_brl(c.valor) if c.valor else "—",
            c.data or "—",
            c.tipo or "—",
            (c.estabelecimento or "—")[:30],
        )
        for c in cartoes
    ]
    header = f"Pagamentos com cartão (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Portador", "Órgão", "Valor", "Data", "Tipo", "Estabelecimento"], rows
    )
    return table + _pagination_hint(len(cartoes), pagina)


async def buscar_pep(
    cpf: str | None = None,
    nome: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca Pessoas Expostas Politicamente (PEP).

    Consulta a base de PEPs do governo federal — pessoas que ocupam ou
    ocuparam cargos, empregos ou funções públicas relevantes.

    Args:
        cpf: CPF da pessoa (opcional se nome fornecido).
        nome: Nome da pessoa (opcional se CPF fornecido).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com PEPs encontrados.
    """
    if not cpf and not nome:
        return "Informe CPF ou nome para buscar Pessoas Expostas Politicamente."

    peps = await client.buscar_pep(cpf=cpf, nome=nome, pagina=pagina)
    if not peps:
        busca = cpf or nome
        return f"Nenhuma PEP encontrada para '{busca}'."

    rows = [
        (
            p.cpf or "—",
            (p.nome or "—")[:40],
            (p.orgao or "—")[:30],
            p.funcao or "—",
            p.data_inicio or "—",
            p.data_fim or "—",
        )
        for p in peps
    ]
    busca = cpf or nome
    header = f"PEPs encontradas para '{busca}' (página {pagina}):\n\n"
    table = header + markdown_table(["CPF", "Nome", "Órgão", "Função", "Início", "Fim"], rows)
    return table + _pagination_hint(len(peps), pagina)


async def buscar_acordos_leniencia(
    nome_empresa: str | None = None,
    cnpj: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca acordos de leniência (anticorrupção).

    Consulta acordos firmados com empresas envolvidas em atos ilícitos
    contra a administração pública (Lei Anticorrupção 12.846/2013).

    Args:
        nome_empresa: Nome da empresa (opcional).
        cnpj: CNPJ da empresa (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com acordos encontrados.
    """
    acordos = await client.buscar_acordos_leniencia(
        nome_empresa=nome_empresa, cnpj=cnpj, pagina=pagina
    )
    if not acordos:
        return "Nenhum acordo de leniência encontrado para os parâmetros informados."

    rows = [
        (
            (a.empresa or "—")[:40],
            a.cnpj or "—",
            (a.orgao or "—")[:30],
            a.situacao or "—",
            a.data_inicio or "—",
            format_brl(a.valor) if a.valor else "—",
        )
        for a in acordos
    ]
    header = f"Acordos de leniência (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Empresa", "CNPJ", "Órgão", "Situação", "Início", "Valor Multa"], rows
    )
    return table + _pagination_hint(len(acordos), pagina)


async def buscar_notas_fiscais(
    cnpj_emitente: str | None = None,
    data_emissao_de: str | None = None,
    data_emissao_ate: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca notas fiscais eletrônicas vinculadas a gastos federais.

    Consulta notas fiscais eletrônicas relacionadas a despesas
    do governo federal.

    Args:
        cnpj_emitente: CNPJ do emitente da nota (opcional).
        data_emissao_de: Data de emissão inicial DD/MM/AAAA (opcional).
        data_emissao_ate: Data de emissão final DD/MM/AAAA (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com notas fiscais encontradas.
    """
    notas = await client.buscar_notas_fiscais(
        cnpj_emitente=cnpj_emitente,
        data_emissao_de=data_emissao_de,
        data_emissao_ate=data_emissao_ate,
        pagina=pagina,
    )
    if not notas:
        return "Nenhuma nota fiscal encontrada para os parâmetros informados."

    rows = [
        (
            n.numero or "—",
            n.serie or "—",
            (n.emitente or "—")[:40],
            n.cnpj_emitente or "—",
            format_brl(n.valor) if n.valor else "—",
            n.data_emissao or "—",
        )
        for n in notas
    ]
    header = f"Notas fiscais (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Série", "Emitente", "CNPJ", "Valor", "Emissão"], rows
    )
    return table + _pagination_hint(len(notas), pagina)


async def consultar_beneficio_social(
    cpf: str | None = None,
    nis: str | None = None,
    mes_ano: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta benefícios sociais (BPC, seguro-desemprego, etc.) por CPF ou NIS.

    Consulta programas sociais do governo federal além do Bolsa Família,
    como BPC (Benefício de Prestação Continuada) e seguro-desemprego.

    Args:
        cpf: CPF do beneficiário (opcional se NIS fornecido).
        nis: NIS do beneficiário (opcional se CPF fornecido).
        mes_ano: Mês/ano de referência no formato AAAAMM (ex: 202401).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com benefícios encontrados.
    """
    if not cpf and not nis:
        return "Informe CPF ou NIS do beneficiário."

    beneficios = await client.consultar_beneficio_social(
        cpf=cpf, nis=nis, mes_ano=mes_ano, pagina=pagina
    )
    if not beneficios:
        busca = cpf or nis
        return f"Nenhum benefício social encontrado para '{busca}'."

    rows = [
        (
            b.tipo or "—",
            (b.nome_beneficiario or "—")[:40],
            format_brl(b.valor) if b.valor else "—",
            b.mes_referencia or "—",
            b.municipio or "—",
            b.uf or "—",
        )
        for b in beneficios
    ]
    busca = cpf or nis
    header = f"Benefícios sociais para '{busca}' (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Tipo", "Beneficiário", "Valor", "Referência", "Município", "UF"], rows
    )
    return table + _pagination_hint(len(beneficios), pagina)


async def consultar_cpf(cpf: str, pagina: int = 1) -> str:
    """Consulta vínculos e benefícios de uma pessoa física por CPF.

    Mostra informações consolidadas sobre os vínculos de uma pessoa
    com o governo federal (servidores, beneficiários, fornecedores).

    Args:
        cpf: CPF da pessoa (aceita com ou sem formatação).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Informações sobre vínculos encontrados.
    """
    vinculos = await client.consultar_cpf(cpf, pagina)
    if not vinculos:
        return f"Nenhum vínculo encontrado para o CPF '{cpf}'."

    items: list[str] = []
    for v in vinculos:
        parts = [f"**{v.nome or '—'}** (CPF: {v.cpf or '—'})"]
        if v.tipo_vinculo:
            parts.append(f"  Tipo: {v.tipo_vinculo}")
        if v.orgao:
            parts.append(f"  Órgão: {v.orgao}")
        if v.beneficios:
            parts.append(f"  Benefícios: {v.beneficios}")
        items.append("\n".join(parts))

    header = f"Vínculos do CPF {cpf} ({len(vinculos)} resultado(s), página {pagina}):\n\n"
    result = header + truncate_list(items, max_items=30)
    return result + _pagination_hint(len(vinculos), pagina)


async def consultar_cnpj(cnpj: str, pagina: int = 1) -> str:
    """Consulta sanções e contratos de pessoa jurídica por CNPJ.

    Mostra informações consolidadas sobre uma empresa junto ao
    governo federal (contratos, sanções, pendências).

    Args:
        cnpj: CNPJ da empresa (aceita com ou sem formatação).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Informações sobre vínculos encontrados.
    """
    try:
        vinculos = await client.consultar_cnpj(cnpj, pagina)
    except HttpClientError as exc:
        if "403" in str(exc):
            return (
                f"Acesso negado ao consultar CNPJ '{cnpj}'. "
                "A chave API pode não ter permissão para o endpoint de pessoas jurídicas. "
                "Verifique as permissões em portaldatransparencia.gov.br."
            )
        return f"Erro ao consultar CNPJ '{cnpj}': {exc}"
    if not vinculos:
        return f"Nenhum vínculo encontrado para o CNPJ '{cnpj}'."

    items: list[str] = []
    for v in vinculos:
        parts = [f"**{v.razao_social or '—'}** (CNPJ: {v.cnpj or '—'})"]
        if v.sancoes:
            parts.append(f"  Sanções: {v.sancoes}")
        if v.contratos:
            parts.append(f"  Contratos: {v.contratos}")
        items.append("\n".join(parts))

    header = f"Vínculos do CNPJ {cnpj} ({len(vinculos)} resultado(s), página {pagina}):\n\n"
    result = header + truncate_list(items, max_items=30)
    return result + _pagination_hint(len(vinculos), pagina)


async def detalhar_contrato(id_contrato: int) -> str:
    """Detalha um contrato federal específico por ID.

    Retorna informações completas de um contrato, incluindo
    modalidade, licitação, situação e valores.

    Args:
        id_contrato: ID do contrato no Portal da Transparência.

    Returns:
        Detalhes do contrato.
    """
    contrato = await client.detalhar_contrato(id_contrato)
    if not contrato:
        return f"Contrato com ID {id_contrato} não encontrado."

    lines = [
        f"## Contrato {contrato.numero or id_contrato}\n",
        f"- **Objeto:** {contrato.objeto or '—'}",
        f"- **Fornecedor:** {contrato.fornecedor or '—'}",
        f"- **Órgão:** {contrato.orgao or '—'}",
        f"- **Modalidade:** {contrato.modalidade or '—'}",
        f"- **Situação:** {contrato.situacao or '—'}",
        f"- **Valor Inicial:** "
        f"{format_brl(contrato.valor_inicial) if contrato.valor_inicial else '—'}",
        f"- **Valor Final:** {format_brl(contrato.valor_final) if contrato.valor_final else '—'}",
        f"- **Vigência:** {contrato.data_inicio or '—'} a {contrato.data_fim or '—'}",
        f"- **Licitação:** {contrato.licitacao or '—'}",
    ]
    return "\n".join(lines)


async def detalhar_servidor(id_servidor: int) -> str:
    """Detalha um servidor público federal por ID, incluindo remuneração.

    Retorna informações completas de um servidor, incluindo cargo,
    função e remuneração bruta e líquida.

    Args:
        id_servidor: ID do servidor no Portal da Transparência.

    Returns:
        Detalhes do servidor.
    """
    servidor = await client.detalhar_servidor(id_servidor)
    if not servidor:
        return f"Servidor com ID {id_servidor} não encontrado."

    lines = [
        f"## Servidor {servidor.nome or id_servidor}\n",
        f"- **CPF:** {servidor.cpf or '—'}",
        f"- **Tipo:** {servidor.tipo_servidor or '—'}",
        f"- **Situação:** {servidor.situacao or '—'}",
        f"- **Órgão:** {servidor.orgao or '—'}",
        f"- **Cargo:** {servidor.cargo or '—'}",
        f"- **Função:** {servidor.funcao or '—'}",
        f"- **Remuneração Básica:** "
        f"{format_brl(servidor.remuneracao_basica) if servidor.remuneracao_basica else '—'}",
    ]
    if servidor.honorarios:
        lines.append(f"- **Honorários Advocatícios:** {format_brl(servidor.honorarios)}")
    if servidor.outras_remuneracoes:
        lines.append(f"- **Outras Remunerações:** {format_brl(servidor.outras_remuneracoes)}")
    if servidor.jetons:
        lines.append(f"- **Jetons:** {format_brl(servidor.jetons)}")
    lines.append(
        "- **Remuneração Líquida:** "
        + (
            format_brl(servidor.remuneracao_apos_deducoes)
            if servidor.remuneracao_apos_deducoes
            else "—"
        )
    )
    return "\n".join(lines)


# --- Novas tools (port completo da API) ---


async def buscar_imoveis_funcionais(
    regiao: str | None = None,
    cep: str | None = None,
    endereco: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca imóveis funcionais da União.

    Consulta a relação de imóveis funcionais do governo federal,
    que são destinados a uso de servidores em razão do cargo.

    Args:
        regiao: Região para filtrar (ex: Centro-Oeste). Opcional.
        cep: CEP do imóvel. Opcional.
        endereco: Trecho do endereço. Opcional.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com imóveis encontrados.
    """
    imoveis = await client.buscar_imoveis_funcionais(
        regiao=regiao, cep=cep, endereco=endereco, pagina=pagina
    )
    if not imoveis:
        return "Nenhum imóvel funcional encontrado para os parâmetros informados."

    rows = [
        (
            (i.endereco or "—")[:50],
            i.cep or "—",
            i.regiao or "—",
            i.situacao or "—",
            (i.orgao_responsavel or "—")[:30],
        )
        for i in imoveis
    ]
    header = f"Imóveis funcionais (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Endereço", "CEP", "Região", "Situação", "Órgão Responsável"], rows
    )
    return table + _pagination_hint(len(imoveis), pagina)


async def buscar_permissionarios_imoveis(
    cpf: str | None = None,
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca ocupantes/permissionários de imóveis funcionais.

    Consulta quem ocupa os imóveis funcionais da União.

    Args:
        cpf: CPF do permissionário (opcional).
        codigo_orgao: Código do órgão (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com permissionários encontrados.
    """
    perms = await client.buscar_permissionarios(cpf=cpf, orgao=codigo_orgao, pagina=pagina)
    if not perms:
        return "Nenhum permissionário encontrado para os parâmetros informados."

    rows = [
        (
            p.cpf or "—",
            (p.nome or "—")[:40],
            (p.orgao or "—")[:30],
            p.cargo or "—",
            format_brl(p.valor_pago_mes) if p.valor_pago_mes else "—",
        )
        for p in perms
    ]
    header = f"Permissionários de imóveis funcionais (página {pagina}):\n\n"
    table = header + markdown_table(["CPF", "Nome", "Órgão", "Cargo", "Valor Pago/Mês"], rows)
    return table + _pagination_hint(len(perms), pagina)


async def buscar_renuncias_fiscais(
    cnpj: str | None = None,
    uf: str | None = None,
    codigo_ibge: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca renúncias de receita fiscal (gastos tributários).

    Consulta valores de renúncias fiscais concedidas pelo governo,
    incluindo isenções, imunidades e benefícios tributários.

    Args:
        cnpj: CNPJ da empresa (opcional).
        uf: Sigla da UF, ex: SP, RJ (opcional).
        codigo_ibge: Código IBGE do município (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com renúncias encontradas.
    """
    renuncias = await client.buscar_renuncias_fiscais(
        cnpj=cnpj, uf=uf, codigo_ibge=codigo_ibge, pagina=pagina
    )
    if not renuncias:
        return "Nenhuma renúncia fiscal encontrada para os parâmetros informados."

    rows = [
        (
            r.cnpj or "—",
            (r.razao_social or "—")[:40],
            r.tipo_renuncia or "—",
            r.tributo or "—",
            r.uf or "—",
            format_brl(r.valor) if r.valor else "—",
            str(r.ano) if r.ano else "—",
        )
        for r in renuncias
    ]
    header = f"Renúncias fiscais (página {pagina}):\n\n"
    table = header + markdown_table(
        ["CNPJ", "Razão Social", "Tipo Renúncia", "Tributo", "UF", "Valor", "Ano"], rows
    )
    return table + _pagination_hint(len(renuncias), pagina)


async def buscar_empresas_beneficios_fiscais(
    cnpj: str | None = None,
    tipo: str = "habilitadas",
    pagina: int = 1,
) -> str:
    """Busca empresas habilitadas a benefícios fiscais ou imunes/isentas.

    Consulta empresas com tratamento tributário diferenciado.

    Args:
        cnpj: CNPJ da empresa (opcional).
        tipo: 'habilitadas' para benefícios fiscais ou 'imunes' para
            imunes/isentas. Padrão: habilitadas.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com empresas encontradas.
    """
    empresas = await client.buscar_empresas_beneficios_fiscais(cnpj=cnpj, tipo=tipo, pagina=pagina)
    if not empresas:
        return f"Nenhuma empresa ({tipo}) encontrada para os parâmetros informados."

    rows = [
        (
            e.cnpj or "—",
            (e.razao_social or "—")[:40],
            (e.beneficio_fiscal or "—")[:30],
            e.fruicao_vigente or "—",
            e.uf or "—",
        )
        for e in empresas
    ]
    header = f"Empresas {tipo} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["CNPJ", "Razão Social", "Benefício Fiscal", "Fruição/Tipo", "UF"], rows
    )
    return table + _pagination_hint(len(empresas), pagina)


async def listar_orgaos(
    tipo: str = "siape",
    pagina: int = 1,
) -> str:
    """Lista órgãos do governo federal cadastrados no SIAPE ou SIAFI.

    Útil para obter códigos de órgãos necessários em outras consultas.

    Args:
        tipo: 'siape' para sistema de pessoal ou 'siafi' para sistema
            financeiro. Padrão: siape.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com órgãos encontrados.
    """
    orgaos = await client.listar_orgaos(tipo=tipo, pagina=pagina)
    if not orgaos:
        return f"Nenhum órgão {tipo.upper()} encontrado."

    rows = [
        (
            o.codigo or "—",
            (o.descricao or "—")[:60],
        )
        for o in orgaos
    ]
    header = f"Órgãos {tipo.upper()} (página {pagina}):\n\n"
    table = header + markdown_table(["Código", "Descrição"], rows)
    return table + _pagination_hint(len(orgaos), pagina)


async def consultar_coronavirus_transferencias(
    mes_ano: str,
    pagina: int = 1,
) -> str:
    """Consulta transferências emergenciais relacionadas à COVID-19.

    Dados de repasses feitos pelo governo federal para enfrentamento
    da pandemia de coronavírus.

    ⚠️ Endpoint upstream do Portal da Transparência aparentemente
    descontinuado — retorna lista vazia (HTTP 200) para todos os períodos
    testados entre 2020 e 2021. O programa de auxílio emergencial terminou
    em 2021 e os dados podem ter migrado para os endpoints regulares de
    transferências. Para dados pós-pandemia, use `consultar_despesas` ou
    `buscar_viagens_orgao`.

    Args:
        mes_ano: Mês/ano no formato AAAAMM (ex: 202003 para março de 2020).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com transferências encontradas.
    """
    transf = await client.consultar_coronavirus_transferencias(mes_ano=mes_ano, pagina=pagina)
    if not transf:
        return "Nenhuma transferência COVID-19 encontrada."

    rows = [
        (
            t.tipo or "—",
            (t.orgao or "—")[:30],
            (t.favorecido or "—")[:40],
            format_brl(t.valor) if t.valor else "—",
            (t.acao or "—")[:30],
        )
        for t in transf
    ]
    header = f"Transferências COVID-19 (página {pagina}):\n\n"
    table = header + markdown_table(["Tipo", "Órgão", "Favorecido", "Valor", "Ação"], rows)
    return table + _pagination_hint(len(transf), pagina)


async def consultar_coronavirus_despesas(
    mes_ano: str,
    pagina: int = 1,
) -> str:
    """Consulta despesas públicas relacionadas à COVID-19.

    Dados de execução orçamentária federal para enfrentamento
    da pandemia de coronavírus.

    Args:
        mes_ano: Mês/ano no formato AAAAMM (ex: 202003 para março de 2020).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com despesas encontradas.
    """
    despesas = await client.consultar_coronavirus_despesas(mes_ano=mes_ano, pagina=pagina)
    if not despesas:
        return "Nenhuma despesa COVID-19 encontrada."

    rows = [
        (
            (d.funcao or "—")[:25],
            (d.acao or "—")[:30],
            d.grupo_despesa or "—",
            format_brl(d.empenhado) if d.empenhado else "—",
            format_brl(d.pago) if d.pago else "—",
        )
        for d in despesas
    ]
    header = f"Despesas COVID-19 (página {pagina}):\n\n"
    table = header + markdown_table(["Função", "Ação", "Grupo Despesa", "Empenhado", "Pago"], rows)
    return table + _pagination_hint(len(despesas), pagina)


async def buscar_viagens_orgao(
    codigo_orgao: str | None = None,
    data_ida_de: str | None = None,
    data_ida_ate: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca viagens a serviço por período e órgão.

    Consulta viagens oficiais por órgão e período, sem necessidade de CPF.
    Diferente de consultar_viagens (que busca por CPF), esta busca
    permite filtrar por órgão e período.

    Args:
        codigo_orgao: Código do órgão (ex: "26246").
        data_ida_de: Data de ida início DD/MM/AAAA (opcional).
        data_ida_ate: Data de ida fim DD/MM/AAAA (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com viagens encontradas.
    """
    viagens = await client.buscar_viagens_orgao(
        codigo_orgao=codigo_orgao,
        data_ida_de=data_ida_de,
        data_ida_ate=data_ida_ate,
        pagina=pagina,
    )
    if not viagens:
        return "Nenhuma viagem encontrada para os parâmetros informados."

    rows = [
        (
            (v.nome or "—")[:40],
            (v.orgao or "—")[:30],
            v.destino or "—",
            f"{v.data_inicio or '—'} a {v.data_fim or '—'}",
            format_brl(v.valor_diarias) if v.valor_diarias else "—",
        )
        for v in viagens
    ]
    header = f"Viagens a serviço (página {pagina}):\n\n"
    table = header + markdown_table(["Nome", "Órgão", "Destino", "Período", "Diárias"], rows)
    return table + _pagination_hint(len(viagens), pagina)


async def detalhar_viagem(id_viagem: int) -> str:
    """Detalha uma viagem a serviço por ID.

    Retorna informações completas de uma viagem, incluindo destino,
    período, valores de diárias e passagens.

    Args:
        id_viagem: ID da viagem no Portal da Transparência.

    Returns:
        Detalhes da viagem.
    """
    viagem = await client.detalhar_viagem(id_viagem)
    if not viagem:
        return f"Viagem com ID {id_viagem} não encontrada."

    lines = [
        f"## Viagem {viagem.id or id_viagem}\n",
        f"- **Servidor:** {viagem.nome or '—'}",
        f"- **CPF:** {viagem.cpf or '—'}",
        f"- **Cargo:** {viagem.cargo or '—'}",
        f"- **Órgão:** {viagem.orgao or '—'}",
        f"- **Destino:** {viagem.destino or '—'}",
        f"- **Período:** {viagem.data_inicio or '—'} a {viagem.data_fim or '—'}",
        f"- **Diárias:** {format_brl(viagem.valor_diarias) if viagem.valor_diarias else '—'}",
        f"- **Passagens:** "
        f"{format_brl(viagem.valor_passagens) if viagem.valor_passagens else '—'}",
    ]
    return "\n".join(lines)


async def buscar_remuneracoes_servidores(
    cpf: str | None = None,
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca remunerações de servidores públicos federais.

    Consulta dados de remuneração (bruta e líquida) dos servidores.
    Informe CPF ou código de órgão.

    Args:
        cpf: CPF do servidor (opcional).
        codigo_orgao: Código SIAPE do órgão (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com remunerações encontradas.
    """
    if not cpf and not codigo_orgao:
        return "Informe CPF ou código de órgão para buscar remunerações."

    remuneracoes = await client.buscar_remuneracoes_servidores(
        cpf=cpf, codigo_orgao=codigo_orgao, pagina=pagina
    )
    if not remuneracoes:
        return "Nenhuma remuneração encontrada para os parâmetros informados."

    rows = [
        (
            r.cpf or "—",
            (r.nome or "—")[:40],
            (r.orgao or "—")[:30],
            format_brl(r.remuneracao_basica) if r.remuneracao_basica else "—",
            format_brl(r.remuneracao_apos_deducoes) if r.remuneracao_apos_deducoes else "—",
        )
        for r in remuneracoes
    ]
    header = f"Remunerações de servidores (página {pagina}):\n\n"
    table = header + markdown_table(["CPF", "Nome", "Órgão", "Remuneração Bruta", "Líquida"], rows)
    return table + _pagination_hint(len(remuneracoes), pagina)


async def buscar_servidores_por_orgao(
    codigo_orgao: str,
    pagina: int = 1,
) -> str:
    """Busca servidores agregados por órgão.

    Retorna a quantidade de servidores lotados em cada órgão.

    Args:
        codigo_orgao: Código SIAPE do órgão.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com dados agregados.
    """
    agregados = await client.buscar_servidores_por_orgao(codigo_orgao=codigo_orgao, pagina=pagina)
    if not agregados:
        return f"Nenhum dado encontrado para o órgão '{codigo_orgao}'."

    rows = [
        (
            a.orgao_codigo or "—",
            (a.orgao_nome or "—")[:50],
            str(a.quantidade) if a.quantidade else "—",
        )
        for a in agregados
    ]
    header = f"Servidores por órgão {codigo_orgao} (página {pagina}):\n\n"
    table = header + markdown_table(["Código", "Órgão", "Quantidade"], rows)
    return table + _pagination_hint(len(agregados), pagina)


async def listar_funcoes_cargos(
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> str:
    """Lista funções e cargos de confiança do governo federal.

    Consulta funções gratificadas e cargos de confiança.

    Args:
        codigo_orgao: Código SIAPE do órgão para filtrar (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com funções e cargos encontrados.
    """
    funcoes = await client.listar_funcoes_cargos(codigo_orgao=codigo_orgao, pagina=pagina)
    if not funcoes:
        return "Nenhuma função/cargo encontrado para os parâmetros informados."

    rows = [
        (
            (f.nome or "—")[:40],
            f.nivel or "—",
            (f.orgao or "—")[:30],
            f.tipo or "—",
        )
        for f in funcoes
    ]
    header = f"Funções e cargos de confiança (página {pagina}):\n\n"
    table = header + markdown_table(["Nome", "Nível", "Órgão", "Tipo"], rows)
    return table + _pagination_hint(len(funcoes), pagina)


async def consultar_seguro_defeso(
    mes_ano: str,
    codigo_ibge: str | None = None,
    cpf: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta seguro-defeso (pescador artesanal) por município ou CPF/NIS.

    O seguro-defeso é um benefício pago ao pescador profissional
    artesanal durante o período de proibição da pesca (defeso).

    Args:
        mes_ano: Mês/ano de referência no formato AAAAMM (ex: 202401).
        codigo_ibge: Código IBGE do município (opcional).
        cpf: CPF do beneficiário (opcional).
        nis: NIS do beneficiário (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com dados do seguro-defeso.
    """
    if not codigo_ibge and not cpf and not nis:
        return "Informe código IBGE do município, CPF ou NIS do beneficiário."

    dados = await client.consultar_seguro_defeso(
        mes_ano=mes_ano, codigo_ibge=codigo_ibge, cpf=cpf, nis=nis, pagina=pagina
    )
    if not dados:
        return "Nenhum dado de seguro-defeso encontrado."

    rows = [
        (
            d.nis or "—",
            (d.nome or "—")[:40],
            d.municipio or "—",
            d.uf or "—",
            format_brl(d.valor) if d.valor else "—",
        )
        for d in dados
    ]
    header = f"Seguro-defeso ({mes_ano}, página {pagina}):\n\n"
    table = header + markdown_table(["NIS", "Nome", "Município", "UF", "Valor"], rows)
    return table + _pagination_hint(len(dados), pagina)


async def consultar_garantia_safra(
    mes_ano: str,
    codigo_ibge: str | None = None,
    cpf: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta garantia-safra (agricultura familiar) por município ou CPF/NIS.

    A garantia-safra beneficia agricultores familiares que tiveram
    perda de safra por seca ou excesso de chuvas.

    Args:
        mes_ano: Mês/ano de referência no formato AAAAMM (ex: 202401).
        codigo_ibge: Código IBGE do município (opcional).
        cpf: CPF do beneficiário (opcional).
        nis: NIS do beneficiário (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com dados da garantia-safra.
    """
    if not codigo_ibge and not cpf and not nis:
        return "Informe código IBGE do município, CPF ou NIS do beneficiário."

    dados = await client.consultar_garantia_safra(
        mes_ano=mes_ano, codigo_ibge=codigo_ibge, cpf=cpf, nis=nis, pagina=pagina
    )
    if not dados:
        return "Nenhum dado de garantia-safra encontrado."

    rows = [
        (
            d.nis or "—",
            (d.nome or "—")[:40],
            d.municipio or "—",
            d.uf or "—",
            format_brl(d.valor) if d.valor else "—",
        )
        for d in dados
    ]
    header = f"Garantia-safra ({mes_ano}, página {pagina}):\n\n"
    table = header + markdown_table(["NIS", "Nome", "Município", "UF", "Valor"], rows)
    return table + _pagination_hint(len(dados), pagina)


async def consultar_peti(
    mes_ano: str,
    codigo_ibge: str | None = None,
    cpf: str | None = None,
    nis: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta PETI (Erradicação do Trabalho Infantil) por município ou CPF/NIS.

    O PETI é um programa que combate o trabalho infantil por meio de
    transferência de renda e ações socioeducativas.

    Args:
        mes_ano: Mês/ano de referência no formato AAAAMM (ex: 202401).
        codigo_ibge: Código IBGE do município (opcional).
        cpf: CPF do beneficiário (opcional).
        nis: NIS do beneficiário (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com dados do PETI.
    """
    if not codigo_ibge and not cpf and not nis:
        return "Informe código IBGE do município, CPF ou NIS do beneficiário."

    dados = await client.consultar_peti(
        mes_ano=mes_ano, codigo_ibge=codigo_ibge, cpf=cpf, nis=nis, pagina=pagina
    )
    if not dados:
        return "Nenhum dado do PETI encontrado."

    rows = [
        (
            d.nis or "—",
            (d.nome or "—")[:40],
            d.municipio or "—",
            d.uf or "—",
            format_brl(d.valor) if d.valor else "—",
        )
        for d in dados
    ]
    header = f"PETI ({mes_ano}, página {pagina}):\n\n"
    table = header + markdown_table(["NIS", "Nome", "Município", "UF", "Valor"], rows)
    return table + _pagination_hint(len(dados), pagina)


async def detalhar_licitacao(id_licitacao: int) -> str:
    """Detalha uma licitação federal por ID.

    Retorna informações completas de uma licitação, incluindo
    modalidade, processo, situação e fornecedor vencedor.

    Args:
        id_licitacao: ID da licitação no Portal da Transparência.

    Returns:
        Detalhes da licitação.
    """
    lic = await client.detalhar_licitacao(id_licitacao)
    if not lic:
        return f"Licitação com ID {id_licitacao} não encontrada."

    lines = [
        f"## Licitação {lic.numero or id_licitacao}\n",
        f"- **Objeto:** {lic.objeto or '—'}",
        f"- **Modalidade:** {lic.modalidade or '—'}",
        f"- **Situação:** {lic.situacao or '—'}",
        f"- **Órgão:** {lic.orgao or '—'}",
        f"- **Processo:** {lic.processo or '—'}",
        f"- **Valor Estimado:** {format_brl(lic.valor_estimado) if lic.valor_estimado else '—'}",
        f"- **Data Abertura:** {lic.data_abertura or '—'}",
        f"- **Fornecedor Vencedor:** {lic.fornecedor_vencedor or '—'}",
    ]
    return "\n".join(lines)


async def buscar_licitacao_por_processo(
    numero_processo: str,
    pagina: int = 1,
) -> str:
    """Busca licitações por número de processo.

    Args:
        numero_processo: Número do processo da licitação.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com licitações encontradas.
    """
    licitacoes = await client.buscar_licitacao_por_processo(
        numero_processo=numero_processo, pagina=pagina
    )
    if not licitacoes:
        return f"Nenhuma licitação encontrada para o processo '{numero_processo}'."

    rows = [
        (
            lc.numero or "—",
            (lc.objeto or "—")[:60],
            lc.modalidade or "—",
            lc.situacao or "—",
            format_brl(lc.valor_estimado) if lc.valor_estimado else "—",
        )
        for lc in licitacoes
    ]
    header = f"Licitações do processo {numero_processo} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Objeto", "Modalidade", "Situação", "Valor Est."], rows
    )
    return table + _pagination_hint(len(licitacoes), pagina)


async def buscar_participantes_licitacao(
    id_licitacao: int,
    pagina: int = 1,
) -> str:
    """Busca participantes de uma licitação.

    Lista empresas e pessoas que participaram do processo licitatório.

    Args:
        id_licitacao: ID da licitação.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com participantes encontrados.
    """
    participantes = await client.buscar_participantes_licitacao(
        id_licitacao=id_licitacao, pagina=pagina
    )
    if not participantes:
        return f"Nenhum participante encontrado para a licitação {id_licitacao}."

    rows = [
        (
            p.cpf_cnpj or "—",
            (p.nome or "—")[:40],
            p.situacao or "—",
            format_brl(p.valor_proposta) if p.valor_proposta else "—",
        )
        for p in participantes
    ]
    header = f"Participantes da licitação {id_licitacao} (página {pagina}):\n\n"
    table = header + markdown_table(["CPF/CNPJ", "Nome", "Situação", "Valor Proposta"], rows)
    return table + _pagination_hint(len(participantes), pagina)


async def listar_modalidades_licitacao() -> str:
    """Lista todas as modalidades de licitação disponíveis.

    Retorna as modalidades cadastradas (concorrência, pregão, etc.).

    Returns:
        Lista de modalidades de licitação.
    """

    modalidades = await client.listar_modalidades_licitacao()
    if not modalidades:
        return "Nenhuma modalidade de licitação encontrada."

    items: list[str] = []
    for m in modalidades:
        if isinstance(m, dict):
            codigo = m.get("codigo") or m.get("id") or "—"
            desc = m.get("descricao") or m.get("nome") or "—"
            items.append(f"- **{codigo}**: {desc}")
        else:
            items.append(f"- {m}")

    return f"Modalidades de licitação ({len(items)}):\n\n" + "\n".join(items)


async def buscar_itens_licitados(
    id_licitacao: int,
    pagina: int = 1,
) -> str:
    """Busca itens de uma licitação.

    Lista os materiais/serviços que foram licitados.

    Args:
        id_licitacao: ID da licitação.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com itens licitados.
    """
    itens = await client.buscar_itens_licitados(id_licitacao=id_licitacao, pagina=pagina)
    if not itens:
        return f"Nenhum item encontrado para a licitação {id_licitacao}."

    rows = [
        (
            (i.descricao or "—")[:60],
            str(i.quantidade) if i.quantidade else "—",
            format_brl(i.valor_estimado) if i.valor_estimado else "—",
            format_brl(i.valor_homologado) if i.valor_homologado else "—",
            (i.fornecedor or "—")[:30],
        )
        for i in itens
    ]
    header = f"Itens da licitação {id_licitacao} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Descrição", "Qtd", "Valor Est.", "Valor Homol.", "Fornecedor"], rows
    )
    return table + _pagination_hint(len(itens), pagina)


async def buscar_empenhos_licitacao(
    id_licitacao: int,
    pagina: int = 1,
) -> str:
    """Busca empenhos vinculados a uma licitação.

    Lista os documentos de empenho (compromissos de pagamento)
    gerados a partir da licitação.

    Args:
        id_licitacao: ID da licitação.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com empenhos encontrados.
    """
    empenhos = await client.buscar_empenhos_licitacao(id_licitacao=id_licitacao, pagina=pagina)
    if not empenhos:
        return f"Nenhum empenho encontrado para a licitação {id_licitacao}."

    rows = [
        (
            e.codigo or "—",
            e.tipo or "—",
            e.data or "—",
            format_brl(e.valor) if e.valor else "—",
            (e.favorecido or "—")[:30],
        )
        for e in empenhos
    ]
    header = f"Empenhos da licitação {id_licitacao} (página {pagina}):\n\n"
    table = header + markdown_table(["Código", "Tipo", "Data", "Valor", "Favorecido"], rows)
    return table + _pagination_hint(len(empenhos), pagina)


async def buscar_contratos_licitacao(
    id_licitacao: int,
    pagina: int = 1,
) -> str:
    """Busca contratos vinculados a uma licitação.

    Lista os contratos firmados a partir do processo licitatório.

    Args:
        id_licitacao: ID da licitação.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com contratos encontrados.
    """
    contratos = await client.buscar_contratos_licitacao(id_licitacao=id_licitacao, pagina=pagina)
    if not contratos:
        return f"Nenhum contrato encontrado para a licitação {id_licitacao}."

    rows = [
        (
            c.numero or "—",
            (c.objeto or "—")[:50],
            format_brl(c.valor_final) if c.valor_final else "—",
            c.data_inicio or "—",
            (c.fornecedor or "—")[:30],
        )
        for c in contratos
    ]
    header = f"Contratos da licitação {id_licitacao} (página {pagina}):\n\n"
    table = header + markdown_table(["Número", "Objeto", "Valor", "Início", "Fornecedor"], rows)
    return table + _pagination_hint(len(contratos), pagina)


async def buscar_unidades_gestoras(
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca unidades gestoras de licitações/contratos.

    Lista as UGs (Unidades Gestoras) que conduzem processos de compra.

    Args:
        codigo_orgao: Código do órgão para filtrar (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com unidades gestoras.
    """
    ugs = await client.buscar_unidades_gestoras(codigo_orgao=codigo_orgao, pagina=pagina)
    if not ugs:
        return "Nenhuma unidade gestora encontrada."

    rows = [
        (
            u.codigo or "—",
            (u.nome or "—")[:40],
            (u.orgao_vinculado or "—")[:30],
            u.municipio or "—",
            u.uf or "—",
        )
        for u in ugs
    ]
    header = f"Unidades gestoras (página {pagina}):\n\n"
    table = header + markdown_table(["Código", "Nome", "Órgão Vinculado", "Município", "UF"], rows)
    return table + _pagination_hint(len(ugs), pagina)


async def buscar_documentos_emenda(codigo_emenda: str) -> str:
    """Busca documentos relacionados a uma emenda parlamentar.

    Lista documentos de execução (empenhos, pagamentos) vinculados
    a uma emenda específica.

    Args:
        codigo_emenda: Código da emenda parlamentar.

    Returns:
        Tabela com documentos encontrados.
    """
    docs = await client.buscar_documentos_emenda(codigo_emenda=codigo_emenda)
    if not docs:
        return f"Nenhum documento encontrado para a emenda '{codigo_emenda}'."

    rows = [
        (
            d.codigo or "—",
            d.tipo or "—",
            (d.descricao or "—")[:40],
            format_brl(d.valor) if d.valor else "—",
            d.data or "—",
        )
        for d in docs
    ]
    return f"Documentos da emenda {codigo_emenda}:\n\n" + markdown_table(
        ["Código", "Tipo", "Descrição", "Valor", "Data"], rows
    )


async def consultar_despesas_orgao(
    codigo_orgao: str,
    ano: int | None = None,
    pagina: int = 1,
) -> str:
    """Consulta despesas públicas por órgão.

    Mostra a execução orçamentária (empenhado, liquidado, pago) de
    um órgão específico do governo federal.

    Args:
        codigo_orgao: Código do órgão (SIAFI).
        ano: Ano de referência (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com despesas por órgão.
    """
    despesas = await client.consultar_despesas_orgao(
        codigo_orgao=codigo_orgao, ano=ano, pagina=pagina
    )
    if not despesas:
        return f"Nenhuma despesa encontrada para o órgão '{codigo_orgao}'."

    rows = [
        (
            d.orgao_codigo or "—",
            (d.orgao_nome or "—")[:40],
            format_brl(d.empenhado) if d.empenhado else "—",
            format_brl(d.liquidado) if d.liquidado else "—",
            format_brl(d.pago) if d.pago else "—",
        )
        for d in despesas
    ]
    header = f"Despesas do órgão {codigo_orgao} (página {pagina}):\n\n"
    table = header + markdown_table(["Código", "Órgão", "Empenhado", "Liquidado", "Pago"], rows)
    return table + _pagination_hint(len(despesas), pagina)


async def consultar_despesas_funcional(
    ano: int,
    codigo_funcao: str | None = None,
    codigo_orgao: str | None = None,
    pagina: int = 1,
) -> str:
    """Consulta despesas por classificação funcional-programática.

    Mostra a execução orçamentária por função, subfunção, programa e ação.

    Args:
        ano: Ano de referência.
        codigo_funcao: Código da função (ex: "12" para Educação). Opcional.
        codigo_orgao: Código do órgão (opcional).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com despesas funcionais.
    """
    despesas = await client.consultar_despesas_funcional(
        ano=ano, codigo_funcao=codigo_funcao, codigo_orgao=codigo_orgao, pagina=pagina
    )
    if not despesas:
        return "Nenhuma despesa funcional-programática encontrada."

    rows = [
        (
            d.funcao or "—",
            (d.programa or "—")[:30],
            (d.acao or "—")[:30],
            format_brl(d.empenhado) if d.empenhado else "—",
            format_brl(d.pago) if d.pago else "—",
        )
        for d in despesas
    ]
    header = f"Despesas funcionais ({ano}, página {pagina}):\n\n"
    table = header + markdown_table(["Função", "Programa", "Ação", "Empenhado", "Pago"], rows)
    return table + _pagination_hint(len(despesas), pagina)


async def buscar_documentos_despesa(
    codigo_orgao: str | None = None,
    ano: int | None = None,
    codigo_favorecido: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca documentos de despesa (empenhos, liquidações, pagamentos).

    Consulta documentos de execução orçamentária do governo federal.

    Args:
        codigo_orgao: Código do órgão (opcional).
        ano: Ano de referência (opcional).
        codigo_favorecido: CPF/CNPJ do favorecido (opcional, ativa busca
            por favorecido).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com documentos encontrados.
    """
    docs = await client.buscar_documentos_despesa(
        codigo_orgao=codigo_orgao,
        ano=ano,
        codigo_favorecido=codigo_favorecido,
        pagina=pagina,
    )
    if not docs:
        return "Nenhum documento de despesa encontrado."

    rows = [
        (
            d.codigo or "—",
            d.tipo or "—",
            d.data or "—",
            format_brl(d.valor) if d.valor else "—",
            (d.favorecido or "—")[:30],
            (d.orgao or "—")[:25],
        )
        for d in docs
    ]
    header = f"Documentos de despesa (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Código", "Tipo", "Data", "Valor", "Favorecido", "Órgão"], rows
    )
    return table + _pagination_hint(len(docs), pagina)


async def buscar_itens_empenho(
    codigo_documento: str,
    pagina: int = 1,
) -> str:
    """Busca itens de um empenho de despesa.

    Lista os materiais/serviços empenhados em um documento específico.

    Args:
        codigo_documento: Código do documento de empenho.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com itens do empenho.
    """
    itens = await client.buscar_itens_empenho(codigo_documento=codigo_documento, pagina=pagina)
    if not itens:
        return f"Nenhum item encontrado para o empenho '{codigo_documento}'."

    rows = [
        (
            (i.descricao or "—")[:60],
            str(i.quantidade) if i.quantidade else "—",
            format_brl(i.valor_unitario) if i.valor_unitario else "—",
            format_brl(i.valor_total) if i.valor_total else "—",
        )
        for i in itens
    ]
    header = f"Itens do empenho {codigo_documento} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Descrição", "Quantidade", "Valor Unitário", "Valor Total"], rows
    )
    return table + _pagination_hint(len(itens), pagina)


async def detalhar_convenio(id_convenio: int) -> str:
    """Detalha um convênio federal por ID.

    Retorna informações completas de um convênio, incluindo
    valores, tipo de instrumento e contrapartida.

    Args:
        id_convenio: ID do convênio no Portal da Transparência.

    Returns:
        Detalhes do convênio.
    """
    conv = await client.detalhar_convenio(id_convenio)
    if not conv:
        return f"Convênio com ID {id_convenio} não encontrado."

    lines = [
        f"## Convênio {conv.numero or id_convenio}\n",
        f"- **Objeto:** {conv.objeto or '—'}",
        f"- **Situação:** {conv.situacao or '—'}",
        f"- **Órgão Concedente:** {conv.orgao or '—'}",
        f"- **Convenente:** {conv.convenente or '—'}",
        f"- **Tipo Instrumento:** {conv.tipo_instrumento or '—'}",
        f"- **Valor Convênio:** {format_brl(conv.valor_convenio) if conv.valor_convenio else '—'}",
        f"- **Valor Liberado:** {format_brl(conv.valor_liberado) if conv.valor_liberado else '—'}",
        f"- **Contrapartida:** "
        f"{format_brl(conv.valor_contrapartida) if conv.valor_contrapartida else '—'}",
        f"- **Vigência:** {conv.data_inicio or '—'} a {conv.data_fim or '—'}",
    ]
    return "\n".join(lines)


async def buscar_convenio_numero(numero: str) -> str:
    """Busca convênio por número.

    Localiza um convênio específico pelo seu número.

    Args:
        numero: Número do convênio.

    Returns:
        Dados do convênio encontrado.
    """
    convenios = await client.buscar_convenio_numero(numero=numero)
    if not convenios:
        return f"Nenhum convênio encontrado com número '{numero}'."

    rows = [
        (
            c.numero or "—",
            (c.objeto or "—")[:60],
            c.situacao or "—",
            format_brl(c.valor_convenio) if c.valor_convenio else "—",
            (c.orgao or "—")[:30],
        )
        for c in convenios
    ]
    return f"Convênio(s) número {numero}:\n\n" + markdown_table(
        ["Número", "Objeto", "Situação", "Valor", "Órgão"], rows
    )


async def buscar_contratos_geral(
    codigo_orgao: str | None = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    pagina: int = 1,
) -> str:
    """Busca geral de contratos federais por órgão e/ou período.

    Diferente de buscar_contratos (que busca por CPF/CNPJ do fornecedor),
    esta ferramenta permite buscar contratos por órgão e período.

    Args:
        codigo_orgao: Código do órgão (SIAFI).
        data_inicial: Data inicial (DD/MM/AAAA).
        data_final: Data final (DD/MM/AAAA).
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com contratos encontrados.
    """
    contratos = await client.buscar_contratos_geral(
        codigo_orgao=codigo_orgao,
        data_inicial=data_inicial,
        data_final=data_final,
        pagina=pagina,
    )
    if not contratos:
        return "Nenhum contrato encontrado para os parâmetros informados."

    rows = [
        (
            c.numero or "—",
            (c.objeto or "—")[:50],
            format_brl(c.valor_final) if c.valor_final else "—",
            c.data_inicio or "—",
            c.modalidade or "—",
            (c.fornecedor or "—")[:30],
        )
        for c in contratos
    ]
    header = f"Contratos federais (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Número", "Objeto", "Valor", "Início", "Modalidade", "Fornecedor"], rows
    )
    return table + _pagination_hint(len(contratos), pagina)


async def buscar_contrato_numero(numero: str) -> str:
    """Busca contrato federal por número.

    Localiza um contrato específico pelo seu número.

    Args:
        numero: Número do contrato.

    Returns:
        Dados do contrato encontrado.
    """
    contratos = await client.buscar_contrato_numero(numero=numero)
    if not contratos:
        return f"Nenhum contrato encontrado com número '{numero}'."

    rows = [
        (
            c.numero or "—",
            (c.objeto or "—")[:50],
            format_brl(c.valor_final) if c.valor_final else "—",
            c.situacao or "—",
            (c.fornecedor or "—")[:30],
        )
        for c in contratos
    ]
    return f"Contrato(s) número {numero}:\n\n" + markdown_table(
        ["Número", "Objeto", "Valor", "Situação", "Fornecedor"], rows
    )


async def buscar_termos_aditivos(
    id_contrato: int,
    pagina: int = 1,
) -> str:
    """Busca termos aditivos de um contrato federal.

    Lista alterações contratuais (prorrogações, acréscimos, etc.).

    Args:
        id_contrato: ID do contrato.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com termos aditivos encontrados.
    """
    termos = await client.buscar_termos_aditivos(id_contrato=id_contrato, pagina=pagina)
    if not termos:
        return f"Nenhum termo aditivo encontrado para o contrato {id_contrato}."

    rows = [
        (
            t.numero or "—",
            (t.objeto or "—")[:60],
            t.data or "—",
            format_brl(t.valor) if t.valor else "—",
        )
        for t in termos
    ]
    header = f"Termos aditivos do contrato {id_contrato} (página {pagina}):\n\n"
    table = header + markdown_table(["Número", "Objeto", "Data", "Valor"], rows)
    return table + _pagination_hint(len(termos), pagina)


async def buscar_itens_contratados(
    id_contrato: int,
    pagina: int = 1,
) -> str:
    """Busca itens de um contrato federal.

    Lista materiais/serviços incluídos no contrato.

    Args:
        id_contrato: ID do contrato.
        pagina: Página de resultados (padrão: 1).

    Returns:
        Tabela com itens contratados.
    """
    itens = await client.buscar_itens_contratados(id_contrato=id_contrato, pagina=pagina)
    if not itens:
        return f"Nenhum item encontrado para o contrato {id_contrato}."

    rows = [
        (
            (i.descricao or "—")[:60],
            str(i.quantidade) if i.quantidade else "—",
            format_brl(i.valor_unitario) if i.valor_unitario else "—",
            format_brl(i.valor_total) if i.valor_total else "—",
        )
        for i in itens
    ]
    header = f"Itens do contrato {id_contrato} (página {pagina}):\n\n"
    table = header + markdown_table(
        ["Descrição", "Quantidade", "Valor Unitário", "Valor Total"], rows
    )
    return table + _pagination_hint(len(itens), pagina)


async def detalhar_sancao(
    base: str,
    id_sancao: int,
) -> str:
    """Detalha uma sanção por base e ID.

    Busca informações completas de uma sanção específica nas bases
    CEIS, CNEP, CEPIM ou CEAF.

    Args:
        base: Base de sanções: 'ceis', 'cnep', 'cepim' ou 'ceaf'.
        id_sancao: ID da sanção na base.

    Returns:
        Detalhes da sanção.
    """
    sancao = await client.detalhar_sancao(base=base, id_sancao=id_sancao)
    if not sancao:
        return f"Sanção {id_sancao} não encontrada na base '{base}'."

    lines = [
        f"## Sanção {base.upper()} #{id_sancao}\n",
        f"- **Nome:** {sancao.nome or '—'}",
        f"- **CPF/CNPJ:** {sancao.cpf_cnpj or '—'}",
        f"- **Fonte:** {sancao.fonte or '—'}",
        f"- **Tipo:** {sancao.tipo or '—'}",
        f"- **Órgão Sancionador:** {sancao.orgao or '—'}",
        f"- **Período:** {sancao.data_inicio or '—'} a {sancao.data_fim or '—'}",
        f"- **Fundamentação:** {sancao.fundamentacao or '—'}",
        f"- **Processo:** {sancao.processo or '—'}",
    ]
    if sancao.valor_multa:
        lines.append(f"- **Valor Multa:** {format_brl(sancao.valor_multa)}")
    return "\n".join(lines)


async def buscar_nota_fiscal_chave(chave: str) -> str:
    """Busca nota fiscal eletrônica por chave de acesso.

    Localiza uma nota fiscal específica pela chave de acesso (44 dígitos).

    Args:
        chave: Chave de acesso da nota fiscal eletrônica.

    Returns:
        Dados da nota fiscal encontrada.
    """
    nota = await client.buscar_nota_fiscal_chave(chave=chave)
    if not nota:
        return f"Nenhuma nota fiscal encontrada para a chave '{chave}'."

    lines = [
        f"## Nota Fiscal {nota.numero or '—'}\n",
        f"- **Série:** {nota.serie or '—'}",
        f"- **Emitente:** {nota.emitente or '—'}",
        f"- **CNPJ Emitente:** {nota.cnpj_emitente or '—'}",
        f"- **Valor:** {format_brl(nota.valor) if nota.valor else '—'}",
        f"- **Data Emissão:** {nota.data_emissao or '—'}",
    ]
    return "\n".join(lines)
