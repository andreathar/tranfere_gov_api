"""Tool functions for the Redator Oficial feature.

Based on Manual de Redação da Presidência da República, 3ª edição (2018).

Rules (ADR-001):
    - Returns formatted strings for LLM consumption
"""

from __future__ import annotations

import re
from datetime import datetime

from .constants import MESES, PREFIXOS_DOCUMENTO, PRONOMES_TRATAMENTO


async def formatar_data_extenso(
    cidade: str = "Brasília",
    estado: str = "DF",
) -> str:
    """Formata a data atual no padrão oficial brasileiro por extenso.

    Segue o Manual de Redação: nome da cidade (sem sigla da UF na data),
    dia ordinal se for 1º, cardinal sem zero à esquerda para os demais,
    mês com inicial minúscula, ponto-final ao término.

    Args:
        cidade: Nome da cidade. Default: Brasília.
        estado: Sigla do estado (UF). Default: DF.

    Returns:
        Data formatada (ex: "Brasília, 22 de março de 2026.").
    """
    hoje = datetime.now()
    mes = MESES[hoje.month]
    dia = "1º" if hoje.day == 1 else str(hoje.day)
    return f"{cidade}, {dia} de {mes} de {hoje.year}."


async def gerar_numeracao(
    tipo: str,
    numero: int,
    ano: int | None = None,
    setor: str = "",
) -> str:
    """Gera a numeração oficial de um documento.

    Segue o padrão do Manual de Redação: TIPO Nº NÚMERO/ANO/SIGLAS.
    Siglas do setor vão da menor para a maior hierarquia.

    Nota: Na 3ª edição do Manual, "memorando" e "aviso" foram abolidos.
    Ambos são automaticamente convertidos para "OFÍCIO".

    Args:
        tipo: Tipo do documento (oficio, despacho, portaria, parecer,
              nota_tecnica, ata). Aceita "memorando" por retrocompatibilidade.
        numero: Número sequencial do documento.
        ano: Ano do documento (default: ano atual).
        setor: Siglas do setor (ex: SAA/SE/MT). Opcional.

    Returns:
        Numeração formatada (ex: "OFÍCIO Nº 652/2026/SAA/SE/MT").
    """
    ano = ano or datetime.now().year
    tipo = tipo.lower().strip()

    prefixo = PREFIXOS_DOCUMENTO.get(tipo, tipo.capitalize())

    if setor:
        return f"{prefixo} Nº {numero}/{ano}/{setor}"
    return f"{prefixo} Nº {numero}/{ano}"


async def consultar_pronome_tratamento(cargo: str) -> str:
    """Retorna o pronome de tratamento correto para um cargo público.

    Segue a tabela oficial do Manual de Redação da Presidência (3ª edição).

    REGRAS IMPORTANTES:
    - "Excelentíssimo" é reservado APENAS para os 3 Chefes de Poder
      (Presidente da República, do Congresso Nacional e do STF)
    - Demais autoridades: vocativo "Senhor/Senhora + Cargo"
    - Digníssimo (DD) e Ilustríssimo (Ilmo.) foram ABOLIDOS
    - Evitar "Doutor" indiscriminadamente

    Args:
        cargo: Cargo do destinatário (ex: "Governador", "Secretário", "Juiz").

    Returns:
        Pronome de tratamento, vocativo, abreviatura e endereçamento.
    """
    cargo_lower = cargo.lower().strip()

    # Busca exata
    if cargo_lower in PRONOMES_TRATAMENTO:
        p = PRONOMES_TRATAMENTO[cargo_lower]
        return (
            f"Cargo: {cargo}\n"
            f"Tratamento: {p['tratamento']}\n"
            f"Vocativo: {p['vocativo']}\n"
            f"Abreviatura: {p['abreviatura']}\n"
            f"Endereçamento: {p['enderecamento']}"
        )

    # Busca parcial
    for key, p in PRONOMES_TRATAMENTO.items():
        if key in cargo_lower or cargo_lower in key:
            return (
                f"Cargo: {cargo} (similar a: {key})\n"
                f"Tratamento: {p['tratamento']}\n"
                f"Vocativo: {p['vocativo']}\n"
                f"Abreviatura: {p['abreviatura']}\n"
                f"Endereçamento: {p['enderecamento']}"
            )

    # Default — Vossa Senhoria
    return (
        f"Cargo: {cargo}\n"
        f"Tratamento: Vossa Senhoria (padrão para demais autoridades)\n"
        f"Vocativo: Senhor(a) {cargo},\n"
        f"Abreviatura: V. Sa.\n"
        f"Endereçamento: Ao Senhor / À Senhora"
    )


async def validar_documento(texto: str, tipo: str) -> str:
    """Valida se um documento segue as normas de redação oficial.

    Verifica aspectos formais conforme o Manual de Redação (3ª edição):
    data por extenso, fecho adequado, numeração, gerúndios, parágrafos.

    Args:
        texto: Texto do documento para validar.
        tipo: Tipo do documento (oficio, despacho, portaria, parecer,
              nota_tecnica, ata).

    Returns:
        Relatório de validação com problemas encontrados e sugestões.
    """
    problemas: list[str] = []
    sugestoes: list[str] = []

    # Verifica data por extenso
    meses_lista = list(MESES.values())
    tem_data = any(mes in texto.lower() for mes in meses_lista)
    if not tem_data:
        problemas.append("Sem data por extenso no documento")

    # Verifica fecho (apenas para tipos que exigem)
    fechos_validos = ["atenciosamente", "respeitosamente", "é o parecer", "s.m.j."]
    tem_fecho = any(fecho in texto.lower() for fecho in fechos_validos)
    if not tem_fecho and tipo in ("oficio", "memorando"):
        problemas.append(
            "Sem fecho oficial — use 'Respeitosamente,' (superior) "
            "ou 'Atenciosamente,' (mesma hierarquia ou inferior)"
        )

    # Verifica numeração
    tem_numeracao = "Nº" in texto or "nº" in texto or "n°" in texto
    if not tem_numeracao and tipo in ("oficio", "portaria", "parecer", "nota_tecnica"):
        sugestoes.append("Sem numeração (padrão: TIPO Nº X/ANO/SETOR)")

    # Verifica uso de expressões abolidas
    abolidos = ["digníssimo", "ilustríssimo", "ilmo.", "d.d."]
    for termo in abolidos:
        if termo in texto.lower():
            problemas.append(f"Termo abolido encontrado: '{termo}' — não usar (Manual 3ª ed.)")

    # Verifica "Tenho a honra de" e similares
    expressoes_evitar = ["tenho a honra", "tenho o prazer", "cumpre-me informar"]
    for expr in expressoes_evitar:
        if expr in texto.lower():
            sugestoes.append(
                f"Expressão '{expr}' — preferir forma direta: 'Informo', 'Solicito', 'Comunico'"
            )

    # Verifica gerúndio excessivo
    gerundios = re.findall(r"\b\w+ndo\b", texto)
    if len(gerundios) > 5:
        sugestoes.append(
            f"{len(gerundios)} gerúndios encontrados — redação oficial prefere formas diretas"
        )

    # Verifica parágrafos muito longos
    paragrafos = [p for p in texto.split("\n\n") if p.strip()]
    longos = [p for p in paragrafos if len(p) > 500]
    if longos:
        sugestoes.append(
            f"{len(longos)} parágrafo(s) com mais de 500 caracteres — "
            "considere dividir para clareza"
        )

    # Monta relatório
    if not problemas and not sugestoes:
        return "Documento segue as normas de redação oficial. Nenhum problema encontrado."

    relatorio = "RELATÓRIO DE VALIDAÇÃO\n\n"
    if problemas:
        relatorio += "Problemas encontrados:\n"
        relatorio += "\n".join(f"  - {p}" for p in problemas)
        relatorio += "\n\n"
    if sugestoes:
        relatorio += "Sugestões de melhoria:\n"
        relatorio += "\n".join(f"  - {s}" for s in sugestoes)

    return relatorio


async def listar_tipos_documento() -> str:
    """Lista todos os tipos de documento oficial suportados.

    Na 3ª edição do Manual de Redação, "memorando" e "aviso" foram
    abolidos como tipos distintos — tudo é "ofício" agora.

    Returns:
        Lista formatada dos tipos com descrição.
    """
    tipos = {
        "oficio": "Comunicação oficial (substitui memorando e aviso desde a 3ª edição)",
        "despacho": "Decisão administrativa sobre processo ou requerimento",
        "portaria": "Ato normativo de autoridade administrativa",
        "parecer": "Manifestação técnica ou jurídica sobre consulta",
        "nota_tecnica": "Análise técnica com dados e recomendações",
        "ata": "Registro de reunião ou assembleia",
    }

    linhas = ["Tipos de documento oficial suportados:\n"]
    for tipo, desc in tipos.items():
        linhas.append(f"  - {tipo}: {desc}")

    linhas.append(
        "\nNota: 'memorando' e 'aviso' foram abolidos na 3ª edição do Manual. "
        "Use 'ofício' para todas as comunicações oficiais."
    )
    linhas.append(
        "\nUse os prompts do redator para gerar cada tipo. "
        "Exemplo: selecione 'Redator de Ofício' no menu de prompts."
    )
    return "\n".join(linhas)
