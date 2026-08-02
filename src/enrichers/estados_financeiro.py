"""
Enriquecimento de dados financeiros dos GOVERNOS ESTADUAIS via API SICONFI.

Uso: python3 -m src.enrichers.estados_financeiro [--dry-run] [--uf UF] [--ano ANO] [--rreo]

Busca dados financeiros dos 26 estados + DF (esfera ESTADUAL) via:
  1. DCA (Declaracao de Contas Anuais) — receitas, despesas, resultados,
     divida, patrimonio (mesmas contas do enricher municipal)
  2. RREO Anexo 03 (Receita Corrente Liquida) — arrecadacao ESTADUAL:
     ICMS, IPVA, ITCD, IRRF (impostos proprios) + FPE, FUNDEB (transferencias)

Diferenca para siconfi.py (municipal):
  - id_ente = codigo IBGE do ESTADO (2 digitos, ex: 35 = SP), nao do municipio
  - Contas RREO estaduais: ICMS/IPVA/ITCD integrais (nao cota-parte),
    FPE no lugar de FPM, sem IPTU/ISS/ITBI
  - Destino: tabela estados_financeiro (PK uf + exercicio)

Requer: migration_026_estados_financeiro.sql.
API: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/ (mesma do municipal)
Rate limit: 1 req/s (respeitado).
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

import psycopg2
import requests

from src.db_utils import get_connection
from src.enrichers.siconfi import (
    RREO_ANEXO_03,
    RREO_PERIODO_ANUAL,
    SICONFI_DCA_URL,
    SICONFI_RREO_URL,
    SICONFI_TIMEOUT,
    _ItemDCA,
    _strip_accents,
)

# ---------------------------------------------------------------------------
# Códigos IBGE dos 26 estados + DF (id_ente na API SICONFI)
# ---------------------------------------------------------------------------
UF_IBGE: dict[str, int] = {
    "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17,
    "MA": 21, "PI": 22, "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27,
    "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41,
    "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53,
}

# ---------------------------------------------------------------------------
# Colunas DCA (mesmas do municipal — reaproveita parse_dca_itens/CONTA_MAP)
# ---------------------------------------------------------------------------
DB_COLUMNS = [
    "receitas_correntes",
    "receitas_capital",
    "receitas_orcamentarias",
    "receitas_transferencias",
    "receitas_nao_operacionais",
    "despesas_correntes",
    "despesas_capital",
    "despesas_orcamentarias",
    "despesas_financeiras",
    "despesas_totais",
    "resultado_orcamentario",
    "resultado_primario",
    "resultado_financeiro",
    "divida_ativa",
    "divida_passiva",
    "ativo_imobilizado",
    "patrimonio_liquido",
]

# Colunas do response DCA estadual por grupo de conta
COLUNA_RECEITAS = "Receitas Brutas Realizadas"
COLUNA_DESPESAS = "Despesas Empenhadas"
COLUNA_BALANCO = "31/12/2024"

# Contas DCA estaduais de interesse: (nome, coluna do response, coluna banco)
# Match por NOME EXATO (regex) — evita pegar "Outras Receitas Correntes" ou a
# intra-orcamentaria "7.0... Receitas Correntes".
DCA_ESTADUAL_CONTA_MAP: list[tuple[str, str, str]] = [
    ("Receitas Correntes", COLUNA_RECEITAS, "receitas_correntes"),
    ("Receitas de Capital", COLUNA_RECEITAS, "receitas_capital"),
    ("Transferências Correntes", COLUNA_RECEITAS, "receitas_transferencias"),
    ("Despesas Correntes", COLUNA_DESPESAS, "despesas_correntes"),
    ("Despesas de Capital", COLUNA_DESPESAS, "despesas_capital"),
    ("Total das Despesas", COLUNA_DESPESAS, "despesas_totais"),
    # Patrimonio (anexo I-AB)
    ("Saldo Patrimonial", COLUNA_BALANCO, "patrimonio_liquido"),
]

# Mapa: nome exato -> (coluna response, coluna banco) para calculo derivado
_TOTAIS_DCA = {
    "TOTAL DAS RECEITAS": (COLUNA_RECEITAS, "receitas_orcamentarias"),
}
# Despesas totais = Exceto Intraorçamentárias + Intraorçamentárias (nao vem
# como "TOTAL DAS DESPESAS" no anexo I-C estadual)
_CONTA_DESPESAS_EXCETO = "Despesas Exceto Intraorçamentárias"
_CONTA_DESPESAS_INTRA = "Despesas Intraorçamentárias"


def _conta_exata(conta: str, alvo: str) -> bool:
    """Match por nome EXATO no final da conta (evita 'Outras Receitas Correntes').

    Aceita: '1.0.0.0.00.0.0 - Receitas Correntes' ou 'Receitas Correntes'.
    Rejeita: 'Outras Receitas Correntes', 'Demais Receitas Correntes' e a
    intra-orcamentaria '7.0.0.0.00.0.0 - Receitas Correntes'.
    """
    import re

    nome = conta.split(" - ")[-1].strip()
    if nome.lower() != alvo.lower():
        return False
    # Exclui codigos de receita/despesa intra-orcamentaria (7.x, 8.x, 9.x)
    codigo = conta.split(" - ")[0].strip()
    intra_orcamentaria = (
        re.fullmatch(r"\d+(\.\d+)*", codigo) is not None
        and codigo.split(".")[0] in ("7", "8", "9")
    )
    return not intra_orcamentaria


def _valor_de(itens: Sequence[_ItemDCA], nome: str, coluna: str) -> float | None:
    for item in itens:
        if _conta_exata(str(item.get("conta", "")), nome) and str(item.get("coluna", "")) == coluna:
            valor = item.get("valor")
            if valor is not None:
                try:
                    return float(valor)
                except (ValueError, TypeError):
                    return None
    return None


def parse_dca_estadual_itens(itens: Sequence[_ItemDCA]) -> dict[str, float | None]:
    """Converte itens DCA ESTADUAL em dict coluna_banco -> valor.

    Diferente do parse municipal: a API estadual retorna a mesma conta em
    varias colunas ('Receitas Brutas Realizadas', 'Deduccoes - FUNDEB',
    'Previsao'...). Aqui casamos por NOME EXATO + COLUNA correta por tipo, e
    calculamos resultado orcamentario = receitas - despesas (nao vem pronto).
    """
    resultado: dict[str, float | None] = {col: None for col in DB_COLUMNS}

    for nome, coluna, coluna_banco in DCA_ESTADUAL_CONTA_MAP:
        valor = _valor_de(itens, nome, coluna)
        if valor is not None:
            resultado[coluna_banco] = valor

    # Totais (anexo I-C): 'TOTAL DAS RECEITAS (III) = (I + II)' — match parcial
    for item in itens:
        conta = str(item.get("conta", "")).upper()
        coluna = str(item.get("coluna", ""))
        for chave, (coluna_alvo, coluna_banco) in _TOTAIS_DCA.items():
            if chave in conta and coluna == coluna_alvo and resultado[coluna_banco] is None:
                valor = item.get("valor")
                if valor is not None:
                    try:
                        resultado[coluna_banco] = float(valor)
                    except (ValueError, TypeError):
                        pass

    # Despesas totais = Exceto Intra + Intra (soma das duas contas do I-C)
    if resultado["despesas_orcamentarias"] is None:
        exceto = _valor_de(itens, _CONTA_DESPESAS_EXCETO, COLUNA_DESPESAS)
        intra = _valor_de(itens, _CONTA_DESPESAS_INTRA, COLUNA_DESPESAS)
        if exceto is not None:
            total_desp = exceto + (intra or 0.0)
            resultado["despesas_orcamentarias"] = total_desp
            if resultado["despesas_totais"] is None:
                resultado["despesas_totais"] = total_desp

    # Resultado orcamentario = receitas - despesas (calculo quando nao vem pronto)
    if resultado["resultado_orcamentario"] is None:
        rec = resultado.get("receitas_orcamentarias")
        desp = resultado.get("despesas_orcamentarias")
        if rec is not None and desp is not None:
            resultado["resultado_orcamentario"] = rec - desp

    return resultado

# ---------------------------------------------------------------------------
# Mapeamento RREO Anexo 03 ESTADUAL -> coluna no banco
# Estados arrecadam ICMS/IPVA/ITCD integrais; recebem FPE e FUNDEB.
# ---------------------------------------------------------------------------
RREO_ESTADUAL_CONTA_MAP: list[tuple[str, str]] = [
    ("ICMS", "arrec_icms"),
    ("IPVA", "arrec_ipva"),
    ("ITCD", "arrec_itcd"),
    ("IRRF", "arrec_irrf"),
    ("Cota-Parte do FPE", "arrec_cota_fpe"),
    ("Transferências do FUNDEB", "arrec_fundeb"),
    ("Impostos, Taxas e Contribuições de Melhoria", "arrec_impostos_geral"),
    ("Transferências Correntes", "arrec_transferencias"),
    ("Receita de Serviços", "arrec_receita_servicos"),
    ("Receita Patrimonial", "arrec_receita_patrimonial"),
    ("RECEITAS CORRENTES (I)", "arrec_receitas_correntes"),
    ("RECEITA CORRENTE LÍQUIDA (III)", "arrec_rcl"),
]

ARREC_DB_COLUMNS = [
    "arrec_icms",
    "arrec_ipva",
    "arrec_itcd",
    "arrec_irrf",
    "arrec_cota_fpe",
    "arrec_fundeb",
    "arrec_impostos_geral",
    "arrec_transferencias",
    "arrec_receita_servicos",
    "arrec_receita_patrimonial",
    "arrec_receitas_correntes",
    "arrec_rcl",
]


class _Args(argparse.Namespace):
    dry_run: bool = False
    uf: str = ""
    ano: int = 0
    rreo: bool = False


def buscar_dca_estado(uf: str, exercicio: int) -> Sequence[_ItemDCA]:
    """Busca DCA de um ESTADO (id_ente = código IBGE da UF)."""
    if uf.upper() not in UF_IBGE:
        return []
    params: dict[str, int] = {"an_exercicio": exercicio, "id_ente": UF_IBGE[uf.upper()]}
    try:
        resp = requests.get(SICONFI_DCA_URL, params=params, timeout=SICONFI_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = cast(dict[str, object], resp.json())
        raw_items = data.get("items", [])
        if not isinstance(raw_items, list):
            return []
        return cast(Sequence[_ItemDCA], [i for i in raw_items if isinstance(i, dict)])
    except (requests.RequestException, ValueError, KeyError):
        return []


def buscar_rreo_estado(uf: str, exercicio: int, periodo: int = RREO_PERIODO_ANUAL) -> Sequence[_ItemDCA]:
    """Busca RREO Anexo 03 de um ESTADO (esfera estadual)."""
    if uf.upper() not in UF_IBGE:
        return []
    params: dict[str, int | str] = {
        "an_exercicio": exercicio,
        "nr_periodo": periodo,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": RREO_ANEXO_03,
        "id_ente": UF_IBGE[uf.upper()],
    }
    try:
        resp = requests.get(SICONFI_RREO_URL, params=params, timeout=SICONFI_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = cast(dict[str, object], resp.json())
        raw_items = data.get("items", [])
        if not isinstance(raw_items, list):
            return []
        return cast(Sequence[_ItemDCA], [i for i in raw_items if isinstance(i, dict)])
    except (requests.RequestException, ValueError, KeyError):
        return []


def parse_rreo_estadual_itens(itens: Sequence[_ItemDCA]) -> dict[str, float | None]:
    """Converte itens RREO Anexo 03 ESTADUAL em dict coluna_banco -> valor.

    ATENCAO: a API retorna a MESMA conta em ~14 colunas (cada mes <MR-1>..<MR>,
    "PREVISAO ATUALIZADA" e "TOTAL (ULTIMOS 12 MESES)"). Somar todas infla o
    valor. Aqui usamos apenas a coluna "TOTAL (ULTIMOS 12 MESES)" — o acumulado
    real do exercicio. Fallback: soma dos valores mensais <MR*> quando a coluna
    de total nao existir.
    """
    # Normaliza colunas uma vez
    def _norm_col(item: _ItemDCA) -> str:
        return _strip_accents(str(item.get("coluna", "")).lower())

    tem_total = any("total (ultimos 12 meses)" in _norm_col(i) for i in itens)
    itens_alvo = [
        i for i in itens
        if "total (ultimos 12 meses)" in _norm_col(i)
        if tem_total
    ] or [
        i for i in itens
        if _norm_col(i).startswith("<mr")
    ]

    resultado: dict[str, float | None] = {col: None for col in ARREC_DB_COLUMNS}

    for texto_conta, coluna_banco in RREO_ESTADUAL_CONTA_MAP:
        texto_lower = _strip_accents(texto_conta).lower()
        total: float = 0.0
        encontrado = False
        for item in itens_alvo:
            conta = _strip_accents(str(item.get("conta", ""))).lower()
            if texto_lower in conta:
                valor = item.get("valor")
                if valor is not None:
                    try:
                        total += float(valor)
                        encontrado = True
                    except (ValueError, TypeError):
                        continue
        if encontrado and resultado[coluna_banco] is None:
            resultado[coluna_banco] = total

    return resultado


def upsert_financeiro(
    cur: psycopg2.extensions.cursor,
    uf: str,
    exercicio: int,
    dados: dict[str, float | None],
    dry_run: bool = False,
) -> None:
    """Upsert de dados financeiros estaduais no banco."""
    if dry_run:
        return

    colunas_str = ", ".join(DB_COLUMNS)
    placeholders = ", ".join(["%s"] * len(DB_COLUMNS))
    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in DB_COLUMNS)
    valores: list[float | None] = [dados.get(c) for c in DB_COLUMNS]

    cur.execute(
        f"""
        INSERT INTO estados_financeiro
            (uf, exercicio, {colunas_str}, atualizado_em)
        VALUES (%s, %s, {placeholders}, %s)
        ON CONFLICT (uf, exercicio) DO UPDATE SET
            {update_str},
            atualizado_em = EXCLUDED.atualizado_em
        """,
        (uf, exercicio, *valores, datetime.now(UTC)),
    )


def upsert_arrecadacao(
    cur: psycopg2.extensions.cursor,
    uf: str,
    exercicio: int,
    dados: dict[str, float | None],
    dry_run: bool = False,
) -> None:
    """Upsert de arrecadacao RREO estadual no banco."""
    if dry_run:
        return

    colunas_str = ", ".join(ARREC_DB_COLUMNS + ["arrec_fonte_rreo", "atualizado_em"])
    placeholders = ", ".join(["%s"] * (len(ARREC_DB_COLUMNS) + 2))
    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in ARREC_DB_COLUMNS)
    update_str += ", arrec_fonte_rreo = EXCLUDED.arrec_fonte_rreo"
    update_str += ", atualizado_em = EXCLUDED.atualizado_em"

    valores: list[Any] = [dados.get(c) for c in ARREC_DB_COLUMNS]
    valores.append("SICONFI/RREO-A03")
    valores.append(datetime.now(UTC))

    cur.execute(
        f"""
        INSERT INTO estados_financeiro
            (uf, exercicio, {colunas_str})
        VALUES (%s, %s, {placeholders})
        ON CONFLICT (uf, exercicio) DO UPDATE SET
            {update_str}
        """,
        (uf, exercicio, *valores),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquecer estados com dados financeiros SICONFI esfera estadual (DCA + RREO)",
    )
    _ = parser.add_argument("--dry-run", action="store_true", help="Mostrar sem escrever no DB")
    _ = parser.add_argument("--uf", type=str, default="", help="UF especifica (vazio=todos)")
    _ = parser.add_argument("--ano", type=int, default=0, help="Exercicio (0=2024)")
    _ = parser.add_argument(
        "--rreo",
        action="store_true",
        help="Tambem buscar RREO Anexo 03 (arrecadacao estadual: ICMS, IPVA, ITCD, FPE...)",
    )
    args: _Args = parser.parse_args(namespace=_Args())

    # Exercicio: usar informado ou 2024 (DCA costuma ter 1-2 anos de atraso)
    exercicio: int = args.ano or 2024
    ufs: list[str] = [args.uf.upper()] if args.uf else list(UF_IBGE.keys())

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(DISTINCT uf) FROM estados_financeiro")
    row = cur.fetchone()
    ja_feitos = row[0] if row else 0
    print(f"Ja enriquecidos: {ja_feitos} UFs | Alvo: {len(ufs)} | Exercicio: {exercicio}")
    if args.dry_run:
        print("  [DRY-RUN] Nenhum dado sera escrito no banco")

    # ========================================================================
    # FASE 1 — DCA estadual
    # ========================================================================
    total_dca_ok = 0
    total_dca_vazio = 0
    inicio = time.time()

    for i, uf in enumerate(ufs):
        itens = buscar_dca_estado(uf, exercicio)
        dados = parse_dca_estadual_itens(itens) if itens else {}
        tem_dados = any(v is not None for v in dados.values())

        if args.dry_run:
            campos = sum(1 for v in dados.values() if v is not None)
            status = "\u2713" if tem_dados else "\u2717"
            resumo = " | ".join(f"{k}={v:,.0f}" for k, v in dados.items() if v is not None)[:110]
            print(f"  {status} {uf} [{exercicio}] | {campos} campos | {resumo}")
        elif tem_dados:
            upsert_financeiro(cur, uf, exercicio, dados)
            total_dca_ok += 1
        else:
            total_dca_vazio += 1

        if i < len(ufs) - 1:
            time.sleep(1.0)  # rate limit SICONFI

    if not args.dry_run:
        conn.commit()

    print(f"\nDCA concluido em {time.time() - inicio:.1f}s | OK: {total_dca_ok} | Sem dados: {total_dca_vazio}")

    # ========================================================================
    # FASE 2 — RREO Anexo 03 estadual (arrecadacao)
    # ========================================================================
    if not args.rreo:
        print("\n[INFO] Use --rreo para buscar arrecadacao estadual (ICMS, IPVA, ITCD, FPE, FUNDEB)")
        conn.close()
        return

    print(f"\n{'=' * 60}")
    print("FASE 2: RREO Anexo 03 — Arrecadacao Estadual")
    print(f"{'=' * 60}")

    total_rreo_ok = 0
    total_rreo_vazio = 0
    inicio_rreo = time.time()

    for i, uf in enumerate(ufs):
        itens_rreo = buscar_rreo_estado(uf, exercicio)
        dados_rreo = parse_rreo_estadual_itens(itens_rreo) if itens_rreo else {}
        tem_dados_rreo = any(v is not None for v in dados_rreo.values())

        if args.dry_run:
            campos = sum(1 for v in dados_rreo.values() if v is not None)
            status = "\u2713" if tem_dados_rreo else "\u2717"
            impostos = [
                f"ICMS={dados_rreo.get('arrec_icms') or 0:,.0f}",
                f"IPVA={dados_rreo.get('arrec_ipva') or 0:,.0f}",
                f"ITCD={dados_rreo.get('arrec_itcd') or 0:,.0f}",
                f"FPE={dados_rreo.get('arrec_cota_fpe') or 0:,.0f}",
                f"RCL={dados_rreo.get('arrec_rcl') or 0:,.0f}",
            ]
            print(f"  {status} {uf} [{exercicio}] | {campos} campos | {', '.join(impostos)}")
        elif tem_dados_rreo:
            upsert_arrecadacao(cur, uf, exercicio, dados_rreo)
            total_rreo_ok += 1
        else:
            total_rreo_vazio += 1

        if i < len(ufs) - 1:
            time.sleep(1.0)

    if not args.dry_run:
        conn.commit()

    conn.close()
    print(f"\nRREO concluido em {time.time() - inicio_rreo:.1f}s | OK: {total_rreo_ok} | Sem dados: {total_rreo_vazio}")


if __name__ == "__main__":
    main()
