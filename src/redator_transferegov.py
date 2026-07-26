#!/usr/bin/env python3
"""
TransfereGov — Redator Oficial de Documentos.

Gera documentos oficiais (nota técnica, ofício, parecer, despacho) seguindo
o Manual de Redação da Presidência da República, 3ª edição (2018).

Combina dados reais do PostgreSQL (planos de ação, deputados, municípios)
com as normas de redação oficial para produzir documentos formatados.

Uso:
  python3 src/redator_transferegov.py nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
  python3 src/redator_transferegov.py oficio --dest "Governador" --cargo "Governador do Estado" --assunto "Relatório de Emendas"
  python3 src/redator_transferegov.py parecer --processo "001/2026" --consulta "Análise de emendas impedidas"
  python3 src/redator_transferegov.py despacho --assunto "Encaminhamento de relatório"
  python3 src/redator_transferegov.py validar --arquivo "docs/nota.txt" --tipo nota_tecnica
  python3 src/redator_transferegov.py listar-tipos
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from src.db_utils import query_df
from src.formatters import fmt_brl, fmt_num

# Diretório base para saída de documentos gerados
_REDATOR_DIR = Path(__file__).parent / "redator"

# Subpastas por tipo de documento
_SUBPASTAS = {
    "nota-tecnica": "notas_tecnicas",
    "oficio": "oficios",
    "parecer": "pareceres",
    "despacho": "despachos",
}


def _gerar_caminhosaida(comando: str, texto: str) -> Path:
    """Gera caminho automático em src/redator/<tipo>/ com data + id."""
    hoje = datetime.now()
    data_str = hoje.strftime("%Y%m%d")
    hora_str = hoje.strftime("%H%M%S")
    subpasta = _SUBPASTAS.get(comando, "outros")
    # Extrair identificador do texto (primeira linha ou código)
    if comando == "oficio":
        # Pegar número do ofício se existir
        import re

        m = re.search(r"Nº (\d+)/", texto)
        num = m.group(1) if m else "000"
        nome = f"oficio_{data_str}_{num}.txt"
    elif comando == "nota-tecnica":
        # Pegar parlamentar se existir
        import re

        m = re.search(r"ASSUNTO:.*— (.+)", texto)
        parlamentar = m.group(1).strip().replace(" ", "_").lower() if m else "geral"
        nome = f"nota_tecnica_{data_str}_{parlamentar}.txt"
    elif comando == "parecer":
        import re

        m = re.search(r"PROCESSO/REFERÊNCIA: (.+)", texto)
        proc = m.group(1).strip().replace("/", "-") if m else "001"
        nome = f"parecer_{data_str}_{proc}.txt"
    elif comando == "despacho":
        import re

        m = re.search(r"Assunto: (.+)", texto)
        assunto = m.group(1).strip().replace(" ", "_").lower()[:30] if m else "geral"
        nome = f"despacho_{data_str}_{assunto}.txt"
    else:
        nome = f"doc_{data_str}_{hora_str}.txt"
    return _REDATOR_DIR / subpasta / nome


log = logging.getLogger("redator")

# ---------------------------------------------------------------------------
# CONSTANTES — Manual de Redação 3ª edição (2018)
# ---------------------------------------------------------------------------

MESES = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

TIPOS_DOCUMENTO = {
    "oficio": "Ofício",
    "despacho": "Despacho",
    "portaria": "Portaria",
    "parecer": "Parecer",
    "nota_tecnica": "Nota Técnica",
    "ata": "Ata",
}

PREFIXOS_DOCUMENTO = {
    "oficio": "OFÍCIO",
    "despacho": "Despacho",
    "portaria": "PORTARIA",
    "parecer": "Parecer",
    "nota_tecnica": "NOTA TÉCNICA",
    "ata": "ATA",
    # Legados (abolidos na 3ª edição, mas retrocompatíveis)
    "memorando": "OFÍCIO",
    "aviso": "OFÍCIO",
}

# Pronomes de tratamento — Manual de Redação 3ª edição
# Regra: "Excelentíssimo" APENAS para os 3 Chefes de Poder.
# Demais: "Senhor/Senhora + Cargo". DD e Ilmo. foram ABOLIDOS.
PRONOMES_TRATAMENTO: dict[str, dict[str, str]] = {
    "presidente da república": {
        "vocativo": "Excelentíssimo Senhor Presidente da República,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "presidente do congresso nacional": {
        "vocativo": "Excelentíssimo Senhor Presidente do Congresso Nacional,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "presidente do supremo tribunal federal": {
        "vocativo": "Excelentíssimo Senhor Presidente do Supremo Tribunal Federal,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "governador": {
        "vocativo": "Senhor Governador,",
        "enderecamento": "Ao Senhor",
    },
    "prefeito": {
        "vocativo": "Senhor Prefeito,",
        "enderecamento": "Ao Senhor",
    },
    "deputado federal": {
        "vocativo": "Senhor Deputado,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "deputado": {
        "vocativo": "Senhor Deputado,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "senador": {
        "vocativo": "Senhor Senador,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "secretário": {
        "vocativo": "Senhor Secretário,",
        "enderecamento": "Ao Senhor",
    },
    "secretário-executivo": {
        "vocativo": "Senhor Secretário-Executivo,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "ministro": {
        "vocativo": "Senhor Ministro,",
        "enderecamento": "A Sua Excelência o Senhor",
    },
    "diretor": {
        "vocativo": "Senhor Diretor,",
        "enderecamento": "Ao Senhor",
    },
    "coordenador": {
        "vocativo": "Senhor Coordenador,",
        "enderecamento": "Ao Senhor",
    },
}

# Fechos oficiais — 3ª edição
# APENAS dois fechos admitidos:
FECHOS = {
    "superior": "Respeitosamente,",
    "igual": "Atenciosamente,",
}

# ---------------------------------------------------------------------------
# FORMATADORES DE REDAÇÃO OFICIAL
# ---------------------------------------------------------------------------


def formatar_data_extenso(cidade: str = "Brasília", estado: str = "DF") -> str:
    """Formata a data atual no padrão oficial brasileiro por extenso.

    Regras do Manual de Redação:
    - Nome da cidade (sem sigla da UF na data)
    - Dia ordinal se for 1º, cardinal sem zero à esquerda
    - Mês com inicial minúscula
    - Ponto-final ao término
    """
    hoje = datetime.now()
    mes = MESES[hoje.month]
    dia = "1º" if hoje.day == 1 else str(hoje.day)
    return f"{cidade}, {dia} de {mes} de {hoje.year}."


def gerar_numeracao(
    tipo: str,
    numero: int,
    ano: int | None = None,
    setor: str = "",
) -> str:
    """Gera a numeração oficial de um documento.

    Padrão: TIPO Nº NÚMERO/ANO/SIGLAS
    Siglas do setor: da menor para a maior hierarquia.
    """
    if tipo in ("memorando", "aviso"):
        tipo = "oficio"
    prefixo = PREFIXOS_DOCUMENTO.get(tipo, tipo.upper())
    ano_final = ano or datetime.now().year
    if setor:
        return f"{prefixo} Nº {numero}/{ano_final}/{setor}"
    return f"{prefixo} Nº {numero}/{ano_final}"


def consultar_pronome_tratamento(cargo: str) -> dict[str, str]:
    """Retorna pronome de tratamento correto para um cargo público.

    Busca case-insensitive. Retorna dict com 'vocativo' e 'enderecamento'.
    """
    cargo_lower = cargo.lower().strip()
    if cargo_lower in PRONOMES_TRATAMENTO:
        return PRONOMES_TRATAMENTO[cargo_lower]
    # Busca parcial
    for chave, valor in PRONOMES_TRATAMENTO.items():
        if cargo_lower in chave or chave in cargo_lower:
            return valor
    # Fallback genérico
    return {
        "vocativo": "Senhor(a),",
        "enderecamento": "Ao(A) Senhor(a)",
    }


def obter_fecho(nivel: str = "igual") -> str:
    """Retorna o fecho adequado conforme a hierarquia."""
    return FECHOS.get(nivel, FECHOS["igual"])


def validar_documento(texto: str, tipo: str) -> list[str]:
    """Valida se um documento segue as normas de redação oficial.

    Retorna lista de problemas encontrados (vazia = válido).
    """
    problemas = []

    # Verificar data por extenso
    import re

    padrao_data = r"\d{1,2}/\d{1,2}/\d{4}"
    if re.search(padrao_data, texto):
        problemas.append("⚠️  Data no formato numérico (DD/MM/AAAA) — usar formato por extenso")

    # Verificar pronomes abolidos
    for pronome_abolido in ["Digníssimo", "Ilmo.", "Ilustríssimo", "D."]:
        if pronome_abolido in texto:
            problemas.append(
                f"⚠️  Pronome '{pronome_abolido}' ABOLIDO na 3ª edição — "
                "usar 'Senhor/Senhora + Cargo'"
            )

    # Verificar gerúndio excessivo
    gerundios = re.findall(r"\b\w+ando\b|\b\w+endo\b|\b\w+indo\b", texto)
    if len(gerundios) > 3:
        problemas.append(
            f"⚠️  Possível gerúndio excessivo ({len(gerundios)} ocorrências) — "
            "preferir verbos no presente"
        )

    # Verificar memorando/aviso
    for tipo_abolido in ["MEMORANDO", "Memorando", "AVISO", "Aviso"]:
        if tipo_abolido in texto:
            problemas.append(f"⚠️  '{tipo_abolido}' ABOLIDO na 3ª edição — usar 'OFÍCIO'")

    return problemas


# ---------------------------------------------------------------------------
# CONSULTAS AO BANCO DE DADOS
# ---------------------------------------------------------------------------


def buscar_parlamentar(nome: str) -> dict[str, Any] | None:
    """Busca deputado por nome (parcial, case-insensitive)."""
    df = query_df(
        "SELECT deputado_id, nome, nome_urna, sigla_partido, uf, situacao "
        "FROM parlamentares_dados WHERE UPPER(nome) LIKE UPPER(%s) LIMIT 1",
        (f"%{nome}%",),
    )
    if df.empty:
        return None
    return cast(dict[str, Any], df.iloc[0].to_dict())


def buscar_planos_parlamentar(
    parlamentar_nome: str,
    ano: int | None = None,
) -> pd.DataFrame:
    """Busca planos de ação de um parlamentar, com opção de filtrar por ano."""
    sql = """
        SELECT plano_acao_codigo, objeto_descricao, beneficiario_nome,
               beneficiario_uf AS uf, plano_acao_situacao, valor_total,
               emenda_codigo, motivo_impedimento
        FROM v_planos_completo
        WHERE UPPER(parlamentar_nome) LIKE UPPER(%s)
    """
    params: list[Any] = [f"%{parlamentar_nome}%"]
    if ano:
        sql += " AND emenda_ano = %s"
        params.append(ano)
    sql += " ORDER BY valor_total DESC"
    return query_df(sql, params)


def resumo_impedidos(ano: int | None = None) -> pd.DataFrame:
    """Retorna resumo de planos impedidos por UF e objeto."""
    sql = """
        SELECT beneficiario_uf AS uf, objeto_descricao,
               COUNT(*) AS total,
               SUM(valor_total) AS valor_total,
               COUNT(DISTINCT parlamentar_nome) AS parlamentares
        FROM v_planos_completo
        WHERE plano_acao_situacao IN
            ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO', 'REPROVADO', 'CANCELADO')
    """
    params: list[Any] = []
    if ano:
        sql += " AND emenda_ano = %s"
        params.append(ano)
    sql += """
        GROUP BY uf, objeto_descricao
        ORDER BY valor_total DESC
        LIMIT 30
    """
    return query_df(sql, params)


def resumo_geral(ano: int | None = None) -> dict[str, Any]:
    """Retorna resumo geral dos planos de ação."""
    sql = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE plano_acao_situacao = 'APROVADO') AS aprovados,
            COUNT(*) FILTER (WHERE plano_acao_situacao IN
                ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO')) AS impedidos,
            COUNT(*) FILTER (WHERE plano_acao_situacao = 'REPROVADO') AS reprovados,
            COUNT(*) FILTER (WHERE plano_acao_situacao = 'CANCELADO') AS cancelados,
            COUNT(*) FILTER (WHERE plano_acao_situacao = 'EM_EXECUCAO') AS em_execucao,
            COUNT(*) FILTER (WHERE plano_acao_situacao = 'CONCLUIDO') AS concluidos,
            SUM(valor_total) AS valor_total,
            COUNT(DISTINCT parlamentar_nome) AS parlamentares,
            COUNT(DISTINCT beneficiario_nome) AS beneficiarios
        FROM v_planos_completo
    """
    params: list[Any] = []
    if ano:
        sql += " WHERE emenda_ano = %s"
        params.append(ano)
    df = query_df(sql, params)
    if df.empty:
        return {}
    return cast(dict[str, Any], df.iloc[0].to_dict())


def listar_parlamentares_impedidos(ano: int | None = None, limite: int = 20) -> pd.DataFrame:
    """Lista parlamentares com mais planos impedidos."""
    sql = """
        SELECT parlamentar_nome, sigla_partido, beneficiario_uf AS uf,
               COUNT(*) AS total_impedidos,
               SUM(valor_total) AS valor_total
        FROM v_planos_completo pa
        LEFT JOIN parlamentares_dados pd ON UPPER(pa.parlamentar_nome) = UPPER(pd.nome)
        WHERE plano_acao_situacao IN
            ('IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO')
    """
    params: list[Any] = []
    if ano:
        sql += " AND emenda_ano = %s"
        params.append(ano)
    sql += """
        GROUP BY parlamentar_nome, sigla_partido, uf
        ORDER BY valor_total DESC
        LIMIT %s
    """
    params.append(limite)
    return query_df(sql, params)


# ---------------------------------------------------------------------------
# GERADORES DE DOCUMENTOS
# ---------------------------------------------------------------------------


def gerar_nota_tecnica(
    parlamentar: str | None = None,
    ano: int | None = None,
    cidade: str = "Brasília",
    orgao: str = "Secretaria de Planejamento",
    autoridade: str = "Secretário de Planejamento",
) -> str:
    """Gera nota técnica sobre impedimentos de planos de ação."""
    hoje = formatar_data_extenso(cidade)
    consultar_pronome_tratamento("secretário")
    resumo = resumo_geral(ano)

    doc = []
    doc.append("NOTA TÉCNICA")
    doc.append("")

    if parlamentar:
        doc.append(f"ASSUNTO: Análise de Planos de Ação Impedidos — {parlamentar.upper()}")
    else:
        doc.append(
            "ASSUNTO: Panorama de Planos de Ação Impedidos no âmbito das Transferências Especiais"
        )
    doc.append(f"DATA: {hoje}")
    doc.append(f"ÓRGÃO: {orgao}")
    doc.append("")

    # 1. INTRODUÇÃO
    doc.append("1. INTRODUÇÃO")
    doc.append("")
    doc.append(
        "A presente nota técnica tem por objetivo analisar a situação dos "
        "Planos de Ação no âmbito do Programa de Transferências Especiais "
        "(Programa 25) do sistema Transferegov, com foco nos planos que "
        "apresentam situação de impedimento ou rejeição."
    )
    doc.append("")

    # 2. ANÁLISE — Dados gerais
    doc.append("2. ANÁLISE")
    doc.append("")
    if resumo:
        doc.append("2.1 Panorama Geral")
        doc.append("")
        doc.append(
            f"O total de planos de ação registrados é de {fmt_num(resumo.get('total', 0))},"
        )
        doc.append(f"abrangendo {fmt_num(resumo.get('parlamentares', 0))} parlamentares")
        doc.append(f"e {fmt_num(resumo.get('beneficiarios', 0))} beneficiários.")
        doc.append(f"O valor total dos planos é {fmt_brl(resumo.get('valor_total', 0))}.")
        doc.append("")
        doc.append("A distribuição por situação é a seguinte:")
        doc.append("")
        doc.append(f"  • Aprovados:          {fmt_num(resumo.get('aprovados', 0))}")
        doc.append(f"  • Em Execução:         {fmt_num(resumo.get('em_execucao', 0))}")
        doc.append(f"  • Concluídos:          {fmt_num(resumo.get('concluidos', 0))}")
        doc.append(f"  • Impedidos:           {fmt_num(resumo.get('impedidos', 0))}")
        doc.append(f"  • Reprovados:          {fmt_num(resumo.get('reprovados', 0))}")
        doc.append(f"  • Cancelados:          {fmt_num(resumo.get('cancelados', 0))}")
        doc.append("")

    # 2.2 Detalhamento por parlamentar (se especificado)
    if parlamentar:
        planos = buscar_planos_parlamentar(parlamentar, ano)
        if not planos.empty:
            doc.append(f"2.2 Planos de {parlamentar.upper()}")
            doc.append("")
            doc.append(
                f"Foram encontrados {len(planos)} planos de ação para "
                f"o(a) parlamentar {parlamentar.upper()}."
            )
            doc.append("")

            for _, row in planos.head(10).iterrows():
                sit = row.get("plano_acao_situacao", "N/I")
                cod = row.get("plano_acao_codigo", "N/I")
                obj = row.get("objeto_descricao", "N/I")
                val = fmt_brl(row.get("valor_total", 0))
                mot = row.get("motivo_impedimento", "")
                doc.append(f"  • {cod} — {obj}")
                doc.append(f"    Situação: {sit} | Valor: {val}")
                if mot and str(mot) != "nan":
                    doc.append(f"    Motivo: {mot}")
                doc.append("")

            if len(planos) > 10:
                doc.append(f"  (... e mais {len(planos) - 10} planos)")
                doc.append("")
        else:
            doc.append(
                f"Não foram encontrados planos de ação para o(a) parlamentar "
                f"{parlamentar.upper()}."
            )
            doc.append("")

    # 2.3 Top impedidos por UF
    doc.append("2.3 Concentração de Impedimentos por UF")
    doc.append("")
    impedidos = resumo_impedidos(ano)
    if not impedidos.empty:
        uf_resumo = (
            impedidos.groupby("uf")
            .agg(
                total=("total", "sum"),
                valor=("valor_total", "sum"),
            )
            .sort_values("valor", ascending=False)
            .head(10)
        )
        for uf, row in uf_resumo.iterrows():
            doc.append(f"  • {uf}: {fmt_num(row['total'])} planos — {fmt_brl(row['valor'])}")
        doc.append("")

    # 3. CONCLUSÃO E RECOMENDAÇÕES
    doc.append("3. CONCLUSÃO E RECOMENDAÇÕES")
    doc.append("")
    doc.append("Diante dos dados apresentados, recomenda-se:")
    doc.append("")
    doc.append(
        "  I — Priorizar a análise dos planos com situação IMPEDIDO por "
        "Restrição Técnica, verificando a possibilidade de regularização;"
    )
    doc.append(
        "  II — Articular com os parlamentares autores para atualização "
        "dos planos de ação que estejam com informações desatualizadas;"
    )
    doc.append(
        "  III — Acompanhar a evolução dos planos em Execução para "
        "garantir a regularidade da aplicação dos recursos;"
    )
    doc.append(
        "  IV — Disponibilizar relatório atualizado mensalmente para "
        "cias de controle e órgãos gestores."
    )
    doc.append("")
    doc.append(
        f"{cidade}, {datetime.now().day} de {MESES[datetime.now().month]} de {datetime.now().year}."
    )
    doc.append("")
    doc.append("")
    doc.append(f"{'_' * 40}")
    doc.append(f"{autoridade}")
    doc.append(orgao)

    return "\n".join(doc)


def gerar_oficio(
    destinatario: str,
    cargo_destinatario: str,
    assunto: str,
    corpo: str,
    orgao_remetente: str = "Secretaria de Planejamento",
    numero: int | None = None,
    cidade: str = "Brasília",
) -> str:
    """Gera ofício seguindo o Manual de Redação 3ª edição."""
    pronomes = consultar_pronome_tratamento(cargo_destinatario)
    vocativo = pronomes["vocativo"]
    hoje = formatar_data_extenso(cidade)
    num = gerar_numeracao("oficio", numero or 1) if numero else ""

    doc = []
    if num:
        doc.append(num)
        doc.append("")
    doc.append(hoje)
    doc.append("")
    doc.append(vocativo)
    doc.append("")

    # Corpo do ofício
    for paragrafo in corpo.split("\n"):
        doc.append(f"    {paragrafo.strip()}")
        doc.append("")

    # Fecho
    doc.append(obter_fecho("superior"))
    doc.append("")
    doc.append("")
    doc.append(f"{'_' * 40}")
    doc.append(orgao_remetente)

    return "\n".join(doc)


def gerar_parecer(
    processo: str,
    consulta: str,
    area: str = "técnico",
    orgao: str = "Assessoria Técnica",
    autoridade: str = "Assessor Técnico",
    cidade: str = "Brasília",
) -> str:
    """Gera parecer técnico/jurídico seguindo o Manual de Redação."""
    hoje = formatar_data_extenso(cidade)

    doc = []
    doc.append(f"PARECER {area.upper()} Nº 001/{datetime.now().year}")
    doc.append("")
    doc.append(f"PROCESSO/REFERÊNCIA: {processo}")
    doc.append(f"DATA: {hoje}")
    doc.append("")

    # EMENTA
    doc.append("EMENTA")
    doc.append("")
    doc.append(f"{consulta}")
    doc.append("")

    # I — RELATÓRIO
    doc.append("I — DO RELATÓRIO")
    doc.append("")
    doc.append(f"Trata-se de consulta ({processo}) que solicita análise referente a: {consulta}.")
    doc.append("")

    # II — FUNDAMENTAÇÃO
    doc.append("II — DA FUNDAMENTAÇÃO")
    doc.append("")
    doc.append("A análise técnica observou os seguintes aspectos:")
    doc.append("")
    doc.append("  a) Conformidade com a legislação vigente;")
    doc.append("  b) Alinhamento com as diretrizes do Programa de Transferências Especiais;")
    doc.append("  c) Regularidade dos procedimentos administrativos.")
    doc.append("")

    # III — CONCLUSÃO
    doc.append("III — DA CONCLUSÃO")
    doc.append("")
    doc.append("Diante do exposto, é o parecer, s.m.j.")
    doc.append("")
    doc.append("")
    doc.append(
        f"{cidade}, {datetime.now().day} de {MESES[datetime.now().month]} de {datetime.now().year}."
    )
    doc.append("")
    doc.append("")
    doc.append(f"{'_' * 40}")
    doc.append(f"{autoridade}")
    doc.append(orgao)

    return "\n".join(doc)


def gerar_despacho(
    assunto: str,
    texto: str,
    autoridade: str = "Secretário de Planejamento",
    orgao: str = "Secretaria de Planejamento",
    cidade: str = "Brasília",
) -> str:
    """Gera despacho administrativo seguindo o Manual de Redação."""
    hoje = formatar_data_extenso(cidade)

    doc = []
    doc.append("DESPACHO")
    doc.append("")
    doc.append(hoje)
    doc.append("")

    # Referência
    doc.append(f"Assunto: {assunto}")
    doc.append("")

    # Texto decisório
    doc.append(texto)
    doc.append("")

    # Sem fecho obrigatório (despacho)
    doc.append("")
    doc.append(f"{'_' * 40}")
    doc.append(autoridade)
    doc.append(orgao)

    return "\n".join(doc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Redator Oficial de Documentos — TransfereGov",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s nota-tecnica --parlamentar "AFONSO FLORENCE" --ano 2026
  %(prog)s nota-tecnica --ano 2026 --output docs/nota_impedidos.txt
  %(prog)s oficio --dest "Governador" --cargo "Governador do Estado" \\
           --assunto "Relatório de Emendas" --corpo "Segue em anexo..."
  %(prog)s parecer --processo "001/2026" --consulta "Análise de emendas"
  %(prog)s despacho --assunto "Encaminhamento" --texto "Encaminho..."
  %(prog)s validar --arquivo "docs/nota.txt" --tipo nota_tecnica
  %(prog)s listar-tipos
        """,
    )
    sub = parser.add_subparsers(dest="comando", help="Tipo de documento")

    # --- nota-tecnica ---
    nt = sub.add_parser("nota-tecnica", help="Gerar nota técnica sobre impedimentos")
    nt.add_argument("--parlamentar", type=str, default=None, help="Nome do parlamentar (filtro)")
    nt.add_argument("--ano", type=int, default=None, help="Ano de exercício (filtro)")
    nt.add_argument(
        "--cidade", type=str, default="Brasília", help="Cidade para data (default: Brasília)"
    )
    nt.add_argument(
        "--orgao", type=str, default="Secretaria de Planejamento", help="Órgão emissor"
    )
    nt.add_argument(
        "--autoridade",
        type=str,
        default="Secretário de Planejamento",
        help="Autoridade que assina",
    )
    nt.add_argument(
        "--output", "-o", type=str, default=None, help="Arquivo de saída (default: stdout)"
    )

    # --- oficio ---
    of = sub.add_parser("oficio", help="Gerar ofício oficial")
    of.add_argument("--dest", type=str, required=True, help="Nome do destinatário")
    of.add_argument("--cargo", type=str, required=True, help="Cargo do destinatário")
    of.add_argument("--assunto", type=str, required=True, help="Assunto do ofício")
    of.add_argument("--corpo", type=str, required=True, help="Corpo do ofício (texto)")
    of.add_argument(
        "--orgao", type=str, default="Secretaria de Planejamento", help="Órgão remetente"
    )
    of.add_argument("--numero", type=int, default=None, help="Número sequencial do ofício")
    of.add_argument("--cidade", type=str, default="Brasília", help="Cidade para data")
    of.add_argument("--output", "-o", type=str, default=None, help="Arquivo de saída")

    # --- parecer ---
    pa = sub.add_parser("parecer", help="Gerar parecer técnico/jurídico")
    pa.add_argument("--processo", type=str, required=True, help="Número do processo/referência")
    pa.add_argument("--consulta", type=str, required=True, help="Pergunta ou tema a ser analisado")
    pa.add_argument(
        "--area",
        type=str,
        default="técnico",
        choices=["técnico", "jurídico", "contábil"],
        help="Área do parecer",
    )
    pa.add_argument("--orgao", type=str, default="Assessoria Técnica")
    pa.add_argument("--autoridade", type=str, default="Assessor Técnico")
    pa.add_argument("--cidade", type=str, default="Brasília")
    pa.add_argument("--output", "-o", type=str, default=None)

    # --- despacho ---
    de = sub.add_parser("despacho", help="Gerar despacho administrativo")
    de.add_argument("--assunto", type=str, required=True)
    de.add_argument("--texto", type=str, required=True, help="Texto decisório do despacho")
    de.add_argument("--autoridade", type=str, default="Secretário de Planejamento")
    de.add_argument("--orgao", type=str, default="Secretaria de Planejamento")
    de.add_argument("--cidade", type=str, default="Brasília")
    de.add_argument("--output", "-o", type=str, default=None)

    # --- validar ---
    va = sub.add_parser("validar", help="Validar documento existente")
    va.add_argument("--arquivo", type=str, required=True, help="Caminho do arquivo de texto")
    va.add_argument(
        "--tipo",
        type=str,
        required=True,
        choices=list(TIPOS_DOCUMENTO.keys()),
        help="Tipo do documento",
    )

    # --- listar-tipos ---
    sub.add_parser("listar-tipos", help="Listar tipos de documento suportados")

    # --- utils ---
    parser.add_argument("--data", action="store_true", help="Apenas mostrar a data por extenso")
    parser.add_argument(
        "--pronomes", type=str, default=None, help="Consultar pronome de tratamento para um cargo"
    )
    parser.add_argument(
        "--numeracao",
        nargs=3,
        metavar=("TIPO", "NUMERO", "SETOR"),
        help="Gerar numeração (ex: oficio 142 SAA/SE/MT)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    # Utilitários soltos
    if args.data:
        print(formatar_data_extenso())
        return 0

    if args.pronomes:
        info = consultar_pronome_tratamento(args.pronomes)
        print(f"Cargo:        {args.pronomes}")
        print(f"Vocativo:     {info['vocativo']}")
        print(f"Endereçamento: {info['enderecamento']}")
        return 0

    if args.numeracao:
        tipo, numero, setor = args.numeracao
        print(gerar_numeracao(tipo, int(numero), setor=setor))
        return 0

    if not args.comando:
        print("Use --help para ver os comandos disponíveis.")
        return 1

    # Geradores de documento
    if args.comando == "listar-tipos":
        print("Tipos de documento suportados:")
        print()
        for chave, nome in TIPOS_DOCUMENTO.items():
            prefixo = PREFIXOS_DOCUMENTO.get(chave, "")
            print(f"  {chave:20s} {nome:15s}  prefixo: {prefixo}")
        print()
        print("Nota: Na 3ª edição do Manual, 'memorando' e 'aviso' foram")
        print("      abolidos — tudo é 'ofício' agora.")
        return 0

    if args.comando == "nota-tecnica":
        texto = gerar_nota_tecnica(
            parlamentar=args.parlamentar,
            ano=args.ano,
            cidade=args.cidade,
            orgao=args.orgao,
            autoridade=args.autoridade,
        )
    elif args.comando == "oficio":
        texto = gerar_oficio(
            destinatario=args.dest,
            cargo_destinatario=args.cargo,
            assunto=args.assunto,
            corpo=args.corpo,
            orgao_remetente=args.orgao,
            numero=args.numero,
            cidade=args.cidade,
        )
    elif args.comando == "parecer":
        texto = gerar_parecer(
            processo=args.processo,
            consulta=args.consulta,
            area=args.area,
            orgao=args.orgao,
            autoridade=args.autoridade,
            cidade=args.cidade,
        )
    elif args.comando == "despacho":
        texto = gerar_despacho(
            assunto=args.assunto,
            texto=args.texto,
            autoridade=args.autoridade,
            orgao=args.orgao,
            cidade=args.cidade,
        )
    elif args.comando == "validar":
        try:
            conteudo = Path(args.arquivo).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"❌ Arquivo não encontrado: {args.arquivo}")
            return 1
        problemas = validar_documento(conteudo, args.tipo)
        if problemas:
            print(
                f"Documento do tipo '{args.tipo}' — {len(problemas)} problema(s) encontrado(s):\n"
            )
            for p in problemas:
                print(f"  {p}")
            return 1
        print(f"✅ Documento do tipo '{args.tipo}' — válido conforme Manual de Redação 3ª edição.")
        return 0
    else:
        print(f"Comando desconhecido: {args.comando}")
        return 1

    # Saída
    saida = Path(args.output) if args.output else _gerar_caminhosaida(args.comando, texto)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(texto, encoding="utf-8")
    print(f"📄 Documento salvo: {saida}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
