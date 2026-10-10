#!/usr/bin/env python3
"""Agrega o impacto legislativo/orçamentário dos deputados distritais por RA.

Popula duas tabelas criadas na migration_051_deputado_ra_impacto.sql:

1. ``cldf_deputado_ra_impacto`` — para cada deputado, quantas proposições ele
   assina (autor OU co-autor) que citam cada Região Administrativa. A fonte é
   ``cldf_proposicoes.autor_nome`` (string "Deputado X, Deputado Y, ...") e
   ``cldf_proposicoes.regiao_admin`` (string "REGIÃO IX - CEILÂNDIA; REGIÃO X -
   GUARÁ"), ambos normalizados por ``_limpar_multivalor()`` em
   ``src/enrichers/cldf_enrichment.py``.

2. ``cldf_ra_emendas_resumo`` — para cada RA, soma das emendas orçamentárias
   (``cldf_emendas``) cuja Unidade Orçamentária é a Administração Regional
   daquela RA (casamento por nome, ver ``UO_PARA_RA`` abaixo). Este valor NÃO
   é atribuído a um deputado — ``cldf_emendas`` não registra o parlamentar
   proponente, só a UO beneficiária.

Idempotente (upsert via ON CONFLICT). Uso:
    .venv/bin/python -m src.enrichers.deputado_ra_impacto [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import re
import unicodedata
from collections import Counter, defaultdict

from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("deputado_ra_impacto")

# ---------------------------------------------------------------------------
# Normalização de nomes
# ---------------------------------------------------------------------------


def norm(texto: str | None) -> str:
    """Remove acentos, caixa alta, colapsa espaços — para casamento de nomes."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(limpo.upper().split())


# Autor extraído de cldf_proposicoes.autor_nome via regex às vezes vem
# abreviado/incompleto em relação a df_deputados_distritais_cldf.nome_candidato.
DEPUTADO_ALIASES: dict[str, str] = {
    "FABIO FELIX": "FABIO FÉLIX",
    "JOAO CARDOSO": "JOAO CARDOSO PROFESSOR-AUDITOR",
    "ROOSEVELT VILELA PIRES": "ROOSEVELT VILELA",
}

# RA extraída de cldf_proposicoes.regiao_admin ("REGIÃO IX - CEILÂNDIA") às
# vezes não bate 1:1 com df_regioes_administrativas.nome_ra por diferenças de
# grafia/sigla histórica. Chaves e valores já normalizados (norm()).
RA_ALIASES: dict[str, str] = {
    "SIA": "SETOR DE INDUSTRIAS",
    "SETOR COMPL. DE IND. E ABASTECIMENTO / ESTRUTURAL": "SCIA",
}

AUTOR_PATTERN = re.compile(r"Deputad[oa]\s+([^,]+)")
RA_PATTERN = re.compile(r"^REGI[AÃ]O\s+[IVXL]+\s*-?\s*(.+)$", re.IGNORECASE)

# Casamento nome_uo (cldf_emendas) -> nome_ra (df_regioes_administrativas).
# nome_uo segue o padrão "ADM. REG. DE/DO/DA <RA>" ou, para RAs mais recentes,
# "ADMINISTRAÇÃO REGIONAL DE <RA> - RA - <romano>".
UO_PREFIXES = (
    "ADMINISTRAÇÃO REGIONAL DE ",
    "ADMINISTRACAO REGIONAL DE ",
    "ADM. REG. DE ",
    "ADM. REG. DO ",
    "ADM. REG. DA ",
)


def extrair_ra_de_uo(nome_uo: str) -> str | None:
    """Extrai o nome normalizado da RA a partir do nome da Unidade Orçamentária.

    Retorna None quando a UO não é uma Administração Regional (ex: secretarias,
    empresas públicas) — essas linhas não entram no agregado por RA.
    """
    texto = nome_uo.strip()
    upper = texto.upper()
    resto = None
    for prefixo in UO_PREFIXES:
        if upper.startswith(prefixo):
            resto = texto[len(prefixo) :]
            break
    if resto is None:
        return None
    # Remove sufixo " - RA - XXXV" quando presente.
    resto = re.sub(r"\s*-\s*RA\s*-\s*[IVXL]+\s*$", "", resto, flags=re.IGNORECASE)
    return norm(resto)


# ---------------------------------------------------------------------------
# 1. Deputado × RA (proposições)
# ---------------------------------------------------------------------------


def _carregar_deputados(cur) -> dict[str, tuple[int, str, str]]:
    """Retorna {nome_normalizado: (id, nome_candidato, sigla_partido)}."""
    cur.execute("SELECT id, nome_candidato, sigla_partido FROM df_deputados_distritais_cldf")
    return {norm(nome): (did, nome, partido) for did, nome, partido in cur.fetchall()}


def _carregar_ras(cur) -> dict[str, int]:
    """Retorna {nome_normalizado: ra_codigo}."""
    cur.execute("SELECT ra_codigo, nome_ra FROM df_regioes_administrativas")
    return {norm(nome): codigo for codigo, nome in cur.fetchall()}


def agregar_deputado_ra(cur, *, dry_run: bool) -> int:
    """Popula cldf_deputado_ra_impacto a partir de cldf_proposicoes."""
    deputados = _carregar_deputados(cur)
    ras = _carregar_ras(cur)

    cur.execute(
        "SELECT autor_nome, regiao_admin, ano, tema "
        "FROM cldf_proposicoes WHERE regiao_admin <> '' AND autor_nome <> ''"
    )
    linhas = cur.fetchall()

    # (deputado_id, ra_codigo) -> {"anos": [...], "temas": Counter(), "n": int}
    agregados: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"anos": [], "temas": Counter(), "n": 0}
    )
    deputados_sem_match: Counter = Counter()
    ras_sem_match: Counter = Counter()

    for autor_nome, regiao_admin, ano, tema in linhas:
        nomes_dep = set()
        for m in AUTOR_PATTERN.finditer(autor_nome):
            nome = m.group(1).strip()
            chave = norm(DEPUTADO_ALIASES.get(norm(nome), nome))
            if chave in deputados:
                nomes_dep.add(chave)
            else:
                deputados_sem_match[nome] += 1

        codigos_ra = set()
        for parte in regiao_admin.split(";"):
            parte = parte.strip()
            match_ra = RA_PATTERN.match(parte)
            if not match_ra:
                continue  # DISTRITO FEDERAL (INTEIRO), ENTORNO, OUTROS ESTADOS
            nome_ra = match_ra.group(1).strip()
            chave_ra = RA_ALIASES.get(norm(nome_ra), norm(nome_ra))
            if chave_ra in ras:
                codigos_ra.add(chave_ra)
            else:
                ras_sem_match[nome_ra] += 1

        for chave_dep in nomes_dep:
            dep_id = deputados[chave_dep][0]
            for chave_ra in codigos_ra:
                ra_codigo = ras[chave_ra]
                bucket = agregados[(dep_id, ra_codigo)]
                bucket["n"] += 1
                if ano:
                    bucket["anos"].append(ano)
                if tema:
                    for t in tema.split(";"):
                        t = t.strip()
                        if t:
                            bucket["temas"][t] += 1

    if deputados_sem_match:
        log.warning(
            "Autores não casados com df_deputados_distritais_cldf (%d distintos): %s",
            len(deputados_sem_match),
            "; ".join(f"{n} ({c})" for n, c in deputados_sem_match.most_common(10)),
        )
    if ras_sem_match:
        log.warning(
            "RAs não casadas com df_regioes_administrativas (%d distintos): %s",
            len(ras_sem_match),
            "; ".join(f"{n} ({c})" for n, c in ras_sem_match.most_common(10)),
        )

    # Precisamos do nome_ra "bonito" (com acento/caixa original), não normalizado.
    cur.execute("SELECT ra_codigo, nome_ra FROM df_regioes_administrativas")
    nome_bonito = {codigo: nome for codigo, nome in cur.fetchall()}
    dep_por_id = {v[0]: v for v in deputados.values()}

    gravados = 0
    for (dep_id, ra_codigo), bucket in agregados.items():
        _, nome_candidato, sigla_partido = dep_por_id[dep_id]
        nome_ra = nome_bonito[ra_codigo]
        temas_principais = "; ".join(t for t, _ in bucket["temas"].most_common(3))
        anos = bucket["anos"]

        if not dry_run:
            cur.execute(
                """
                INSERT INTO cldf_deputado_ra_impacto (
                    deputado_id, nome_candidato, sigla_partido, ra_codigo, nome_ra,
                    total_proposicoes, primeira_proposicao, ultima_proposicao,
                    temas_principais
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (deputado_id, ra_codigo) DO UPDATE SET
                    nome_candidato = EXCLUDED.nome_candidato,
                    sigla_partido = EXCLUDED.sigla_partido,
                    nome_ra = EXCLUDED.nome_ra,
                    total_proposicoes = EXCLUDED.total_proposicoes,
                    primeira_proposicao = EXCLUDED.primeira_proposicao,
                    ultima_proposicao = EXCLUDED.ultima_proposicao,
                    temas_principais = EXCLUDED.temas_principais,
                    updated_at = NOW()
                """,
                (
                    dep_id,
                    nome_candidato,
                    sigla_partido,
                    ra_codigo,
                    nome_ra,
                    bucket["n"],
                    min(anos) if anos else None,
                    max(anos) if anos else None,
                    temas_principais,
                ),
            )
        gravados += 1

    log.info(
        "Deputado x RA: %d combinações %s (de %d proposições geo-referenciadas)",
        gravados,
        "(dry-run)" if dry_run else "gravadas",
        len(linhas),
    )
    return gravados


# ---------------------------------------------------------------------------
# 2. RA × Emendas (orçamento)
# ---------------------------------------------------------------------------


def agregar_ra_emendas(cur, *, dry_run: bool) -> int:
    """Popula cldf_ra_emendas_resumo a partir de cldf_emendas.nome_uo."""
    ras = _carregar_ras(cur)
    cur.execute("SELECT ra_codigo, nome_ra FROM df_regioes_administrativas")
    nome_bonito = {codigo: nome for codigo, nome in cur.fetchall()}

    cur.execute(
        "SELECT nome_uo, ano_emenda, vl_emenda, vl_empenhado, vl_liquidado FROM cldf_emendas"
    )
    linhas = cur.fetchall()

    agregados: dict[int, dict] = defaultdict(
        lambda: {"n": 0, "vl_emenda": 0, "vl_empenhado": 0, "vl_liquidado": 0, "anos": []}
    )
    uo_sem_match: Counter = Counter()

    for nome_uo, ano_emenda, vl_emenda, vl_empenhado, vl_liquidado in linhas:
        chave_ra = extrair_ra_de_uo(nome_uo or "")
        if chave_ra is None:
            continue  # UO não é Administração Regional (secretaria, empresa, etc.)
        chave_ra = RA_ALIASES.get(chave_ra, chave_ra)
        if chave_ra not in ras:
            uo_sem_match[nome_uo] += 1
            continue
        ra_codigo = ras[chave_ra]
        bucket = agregados[ra_codigo]
        bucket["n"] += 1
        bucket["vl_emenda"] += vl_emenda or 0
        bucket["vl_empenhado"] += vl_empenhado or 0
        bucket["vl_liquidado"] += vl_liquidado or 0
        if ano_emenda:
            bucket["anos"].append(ano_emenda)

    if uo_sem_match:
        log.warning(
            "UOs de Administração Regional não casadas com RA local (%d distintas): %s",
            len(uo_sem_match),
            "; ".join(f"{n} ({c})" for n, c in uo_sem_match.most_common(10)),
        )

    gravados = 0
    for ra_codigo, bucket in agregados.items():
        nome_ra = nome_bonito[ra_codigo]
        anos = bucket["anos"]
        if not dry_run:
            cur.execute(
                """
                INSERT INTO cldf_ra_emendas_resumo (
                    ra_codigo, nome_ra, total_emendas, vl_emenda, vl_empenhado,
                    vl_liquidado, ano_min, ano_max
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ra_codigo) DO UPDATE SET
                    nome_ra = EXCLUDED.nome_ra,
                    total_emendas = EXCLUDED.total_emendas,
                    vl_emenda = EXCLUDED.vl_emenda,
                    vl_empenhado = EXCLUDED.vl_empenhado,
                    vl_liquidado = EXCLUDED.vl_liquidado,
                    ano_min = EXCLUDED.ano_min,
                    ano_max = EXCLUDED.ano_max,
                    updated_at = NOW()
                """,
                (
                    ra_codigo,
                    nome_ra,
                    bucket["n"],
                    bucket["vl_emenda"],
                    bucket["vl_empenhado"],
                    bucket["vl_liquidado"],
                    min(anos) if anos else None,
                    max(anos) if anos else None,
                ),
            )
        gravados += 1

    log.info(
        "RA x Emendas: %d RAs %s (de %d emendas, %d sem UO de Administração Regional)",
        gravados,
        "(dry-run)" if dry_run else "gravadas",
        len(linhas),
        sum(uo_sem_match.values()),
    )
    return gravados


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run(*, dry_run: bool = False) -> tuple[int, int]:
    with get_connection() as conn, conn.cursor() as cur:
        n_dep_ra = agregar_deputado_ra(cur, dry_run=dry_run)
        n_ra_emendas = agregar_ra_emendas(cur, dry_run=dry_run)
    return n_dep_ra, n_ra_emendas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Não grava no banco.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
