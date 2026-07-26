"""
Enriquecimento de municipios via API SICONFI (Tesouro Nacional).

Uso: python3 -m src.enrichers.siconfi [--dry-run] [--uf UF] [--limit N] [--ano ANO] [--rreo]

Busca dados financeiros dos municipios mapeados via:
  1. DCA (Declaracao de Contas Anuais) — dados agregados anuais:
     - Receitas correntes/capital/orcamentarias
     - Despesas correntes/capital/orcamentarias
     - Resultado orcamentario/primario/financeiro
     - Divida ativa/passiva, ativo imobilizado/patrimonio liquido
  2. RREO Anexo 03 (Receita Corrente Liquida) — arrecadacao de impostos:
     - IPTU, ISS, ITBI, IRRF
     - Cota-partes: ICMS, IPVA, ITR, FPM
     - Transferencias, receita de servicos/patrimonial

Requer: tabela municipios_ibge populada (via ibge.py), migration_007 e migration_012.
API: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/
Rate limit: 1 req/s (respeitado).
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TypedDict, cast

import psycopg2
import requests

from src.db_utils import get_connection

# ---------------------------------------------------------------------------
# API SICONFI — Declaracao de Contas Anuais (DCA)
# ---------------------------------------------------------------------------
SICONFI_DCA_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca"
SICONFI_TIMEOUT = 30

# ---------------------------------------------------------------------------
# API SICONFI — RREO Anexo 03 (Receita Corrente Liquida)
# ---------------------------------------------------------------------------
SICONFI_RREO_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"
RREO_ANEXO_03 = "RREO-Anexo 03"
RREO_PERIODO_ANUAL = 6  # 6o bimestre (Nov-Dez) consolida o ano

# ---------------------------------------------------------------------------
# Mapeamento: nome da conta no response DCA -> coluna no banco
# Baseado na estrutura real da API SICONFI / DCA
# ---------------------------------------------------------------------------
# A API retorna itens com campos: anexo, conta, coluna, valor
# Cada linha = uma conta + coluna (ex: "Receitas Correntes" + "Despesas Empenhadas")

# Anexos DCA relevantes
ANEXO_BALANCO = "Balanco Orcamentario"
ANEXO_RCL = "RCL"
ANEXO_DEMAIS_CONTAS = "Demais Contas"

# Colunas de interesse no response
COLUNA_VALOR = "Balanco Orcamentario"  # coluna principal do Anexo I-AB

# Mapeamento conta DCA -> coluna do banco
# Chave = texto exato ou parcial da conta no response
# Formato: (texto_match, coluna_banco)
CONTA_MAP: list[tuple[str, str]] = [
    ("Receitas Correntes", "receitas_correntes"),
    ("Receitas de Capital", "receitas_capital"),
    ("Receitas Orcamentarias", "receitas_orcamentarias"),
    ("Transferencias Correntes", "receitas_transferencias"),
    ("Receitas Nao Operacionais", "receitas_nao_operacionais"),
    ("Despesas Correntes", "despesas_correntes"),
    ("Despesas de Capital", "despesas_capital"),
    ("Despesas Orcamentarias", "despesas_orcamentarias"),
    ("Despesas Financeiras", "despesas_financeiras"),
    ("Total das Despesas", "despesas_totais"),
    ("Resultado Orcamentario", "resultado_orcamentario"),
    ("Resultado Primario", "resultado_primario"),
    ("Resultado Financeiro", "resultado_financeiro"),
    ("Divida Ativa", "divida_ativa"),
    ("Divida Passiva Consolidada", "divida_passiva"),
    ("Divida Consolidada Liquida", "divida_passiva"),  # variacao
    ("Ativo Imobilizado", "ativo_imobilizado"),
    ("Patrimonio Liquido", "patrimonio_liquido"),
]

# Colunas do banco (para INSERT/UPDATE)
DB_COLUMNS = [
    "receitas_correntes", "receitas_capital", "receitas_orcamentarias",
    "receitas_transferencias", "receitas_nao_operacionais",
    "despesas_correntes", "despesas_capital", "despesas_orcamentarias",
    "despesas_financeiras", "despesas_totais",
    "resultado_orcamentario", "resultado_primario", "resultado_financeiro",
    "divida_ativa", "divida_passiva", "ativo_imobilizado", "patrimonio_liquido",
]

# ---------------------------------------------------------------------------
# Mapeamento: conta RREO Anexo 03 -> coluna no banco (arrecadacao de impostos)
# Fonte: RREO-Anexo 03 (Receita Corrente Liquida) — soma dos 6 bimestres
# ---------------------------------------------------------------------------
RREO_A03_CONTA_MAP: list[tuple[str, str]] = [
    ("IPTU",                              "arrec_iptu"),
    ("ISS",                               "arrec_iss"),
    ("ITBI",                              "arrec_itbi"),
    ("IRRF",                              "arrec_irrf"),
    ("Cota-Parte do ICMS",                "arrec_cota_icms"),
    ("Cota-Parte do IPVA",                "arrec_cota_ipva"),
    ("Cota-Parte do ITR",                 "arrec_cota_itr"),
    ("Cota-Parte do FPM",                 "arrec_cota_fpm"),
    ("Impostos, Taxas e Contribuicoes",   "arrec_impostos_geral"),
    ("Transferencias Correntes",          "arrec_transferencias"),
    ("Receita de Servicos",               "arrec_receita_servicos"),
    ("Receita Patrimonial",               "arrec_receita_patrimonial"),
    ("RECEITAS CORRENTES",                "arrec_receitas_correntes"),
]

# Colunas de arrecadacao no banco (para INSERT/UPDATE)
ARREC_DB_COLUMNS = [
    "arrec_iptu", "arrec_iss", "arrec_itbi", "arrec_irrf",
    "arrec_cota_icms", "arrec_cota_ipva", "arrec_cota_itr", "arrec_cota_fpm",
    "arrec_impostos_geral", "arrec_transferencias",
    "arrec_receita_servicos", "arrec_receita_patrimonial",
    "arrec_receitas_correntes",
]




# ---------------------------------------------------------------------------
# Tipagem da resposta SICONFI
# ---------------------------------------------------------------------------
class _ItemDCA(TypedDict, total=False):
    exercicio: int
    periodo: int
    periodicidade: str
    instituicao: str
    cod_ibge: int
    populacao: int
    uf: str
    rotulo: str
    conta: str
    cod_conta: str
    coluna: str
    anexo: str
    esfera: str
    poder: str
    valor: float


# ---------------------------------------------------------------------------
# Args tipados (argparse.Namespace e Any)
# ---------------------------------------------------------------------------
class _SiconfiArgs(argparse.Namespace):
    dry_run: bool = False
    uf: str = ""
    limit: int = 0
    ano: int = 0
    rreo: bool = False


def buscar_dca_municipio(
    municipio_id: int,
    exercicio: int,
    timeout: int = SICONFI_TIMEOUT,
) -> Sequence[_ItemDCA]:
    """Busca DCA de um municipio para um exercicio.

    API: GET /dca?an_exercicio={ano}&id_ente={cod_ibge}
    Response: {"items": [{"conta": ..., "coluna": ..., "valor": ..., "anexo": ...}]}
    """
    params: dict[str, int] = {"an_exercicio": exercicio, "id_ente": municipio_id}
    try:
        resp = requests.get(SICONFI_DCA_URL, params=params, timeout=timeout)
        if resp.status_code != 200:
            return []
        data = cast(dict[str, object], resp.json())
        raw_items = data.get("items", [])
        if not isinstance(raw_items, list):
            return []
        return cast(  # type: ignore[return-value]
            Sequence[_ItemDCA],
            [i for i in raw_items if isinstance(i, dict)],  # pyright: ignore[reportUnknownVariableType]
        )
    except (requests.RequestException, ValueError, KeyError):
        return []


def _extrair_valor_conta(
    itens: Sequence[_ItemDCA],
    texto_conta: str,
) -> float | None:
    """Extrai o valor de uma conta especifica da lista de itens DCA.

    Busca case-insensitive por substring no campo 'conta'.
    Retorna o primeiro match encontrado (ultimo periodo disponivel).
    """
    texto_lower = texto_conta.lower()
    for item in itens:
        conta = str(item.get("conta", "")).lower()
        if texto_lower in conta:
            valor = item.get("valor")
            if valor is not None:
                try:
                    return float(valor)
                except (ValueError, TypeError):
                    continue
    return None


def parse_dca_itens(
    itens: Sequence[_ItemDCA],
) -> dict[str, float | None]:
    """Converte itens DCA em dict coluna_banco -> valor.

    Para cada mapeamento em CONTA_MAP, busca o valor correspondente
    na lista de itens retornada pela API.
    """
    resultado: dict[str, float | None] = {col: None for col in DB_COLUMNS}

    for texto_conta, coluna_banco in CONTA_MAP:
        valor = _extrair_valor_conta(itens, texto_conta)
        if valor is not None and resultado[coluna_banco] is None:
            resultado[coluna_banco] = valor

    return resultado


def upsert_financeiro(
    cur: psycopg2.extensions.cursor,
    municipio_id: int,
    exercicio: int,
    dados: dict[str, float | None],
    dry_run: bool = False,
) -> None:
    """Upsert de dados financeiros no banco."""
    if dry_run:
        return

    colunas_str = ", ".join(DB_COLUMNS)
    placeholders = ", ".join(["%s"] * len(DB_COLUMNS))
    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in DB_COLUMNS)

    valores: list[float | None] = [dados.get(c) for c in DB_COLUMNS]

    cur.execute(
        f"""
        INSERT INTO municipios_financeiro
            (municipio_id, exercicio, {colunas_str}, atualizado_em)
        VALUES (%s, %s, {placeholders}, %s)
        ON CONFLICT (municipio_id, exercicio) DO UPDATE SET
            {update_str},
            atualizado_em = EXCLUDED.atualizado_em
        """,
        (municipio_id, exercicio, *valores, datetime.now(UTC)),
    )


# ---------------------------------------------------------------------------
# RREO Anexo 03 — Arrecadacao de Impostos
# ---------------------------------------------------------------------------

def buscar_rreo_a03(
    municipio_id: int,
    exercicio: int,
    periodo: int = RREO_PERIODO_ANUAL,
    timeout: int = SICONFI_TIMEOUT,
) -> Sequence[_ItemDCA]:
    """Busca RREO Anexo 03 (RCL) de um municipio para um exercicio.

    API: GET /rreo?an_exercicio={ano}&nr_periodo={periodo}
         &co_tipo_demonstrativo=RREO&no_anexo=RREO-Anexo 03&id_ente={cod_ibge}
    Response: {"items": [{"conta": ..., "coluna": ..., "valor": ..., ...}]}
    """
    params: dict[str, int | str] = {
        "an_exercicio": exercicio,
        "nr_periodo": periodo,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": RREO_ANEXO_03,
        "id_ente": municipio_id,
    }
    try:
        resp = requests.get(SICONFI_RREO_URL, params=params, timeout=timeout)
        if resp.status_code != 200:
            return []
        data = cast(dict[str, object], resp.json())
        raw_items = data.get("items", [])
        if not isinstance(raw_items, list):
            return []
        return cast(
            Sequence[_ItemDCA],
            [i for i in raw_items if isinstance(i, dict)],
        )
    except (requests.RequestException, ValueError, KeyError):
        return []


def parse_rreo_a03_itens(
    itens: Sequence[_ItemDCA],
) -> dict[str, float | None]:
    """Converte itens RREO Anexo 03 em dict coluna_banco -> valor (soma anual).

    Para cada mapeamento em RREO_A03_CONTA_MAP, soma os valores de todos
    os periodos (bimestres) para a mesma conta, retornando o total anual.
    Usa normalizacao ASCII para lidar com acentos da API SICONFI.
    """
    import unicodedata

    def _strip_accents(s: str) -> str:
        """Remove acentos de uma string (NFKD decomposition + strip)."""
        return "".join(
            c for c in unicodedata.normalize("NFKD", s)
            if unicodedata.category(c) != "Mn"
        )

    resultado: dict[str, float | None] = {col: None for col in ARREC_DB_COLUMNS}

    for texto_conta, coluna_banco in RREO_A03_CONTA_MAP:
        texto_lower = _strip_accents(texto_conta).lower()
        total: float = 0.0
        encontrado = False
        for item in itens:
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


def upsert_arrecadacao(
    cur: psycopg2.extensions.cursor,
    municipio_id: int,
    exercicio: int,
    dados: dict[str, float | None],
    dry_run: bool = False,
) -> None:
    """Upsert de dados de arrecadacao de impostos no banco."""
    if dry_run:
        return

    colunas_str = ", ".join(ARREC_DB_COLUMNS + ["arrec_fonte_rreo", "arrec_atualizado_em"])
    placeholders = ", ".join(["%s"] * (len(ARREC_DB_COLUMNS) + 2))
    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in ARREC_DB_COLUMNS)
    update_str += ", arrec_fonte_rreo = EXCLUDED.arrec_fonte_rreo"
    update_str += ", arrec_atualizado_em = EXCLUDED.arrec_atualizado_em"

    valores: list[float | None | str] = [dados.get(c) for c in ARREC_DB_COLUMNS]
    valores.append("SICONFI/RREO-A03")
    valores.append(datetime.now(UTC))

    cur.execute(
        f"""
        INSERT INTO municipios_financeiro
            (municipio_id, exercicio, {colunas_str})
        VALUES (%s, %s, {placeholders})
        ON CONFLICT (municipio_id, exercicio) DO UPDATE SET
            {update_str}
        """,
        (municipio_id, exercicio, *valores),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquecer municipios com dados financeiros SICONFI (DCA + RREO)",
    )
    _ = parser.add_argument("--dry-run", action="store_true", help="Mostrar sem escrever no DB")
    _ = parser.add_argument("--uf", type=str, default="", help="UF especifica (vazio=todas)")
    _ = parser.add_argument("--limit", type=int, default=0, help="Max. municipios (0=todos)")
    _ = parser.add_argument(
        "--ano", type=int, default=0,
        help="Exercicio (0=ano mais recente disponivel)",
    )
    _ = parser.add_argument(
        "--rreo", action="store_true",
        help="Tambem buscar RREO Anexo 03 (arrecadacao de impostos por municipio)",
    )
    args: _SiconfiArgs = parser.parse_args(namespace=_SiconfiArgs())

    conn = get_connection()
    cur = conn.cursor()

    # Buscar municipios mapeados (com codigo IBGE), excluindo ja enriquecidos
    uf_filtro: str = args.uf.upper()
    where_extra = ""
    params: list[str | int] = []
    if uf_filtro:
        where_extra = " AND m.uf = %s"
        params.append(uf_filtro)

    cur.execute(
        f"""
        SELECT m.municipio_id, m.nome, m.uf
        FROM municipios_ibge m
        WHERE NOT EXISTS (
            SELECT 1 FROM municipios_financeiro f
            WHERE f.municipio_id = m.municipio_id
        ) {where_extra}
        ORDER BY m.uf, m.nome
        """,
        params,
    )

    municipios: list[tuple[int, str, str]] = cur.fetchall()
    if args.limit > 0:
        municipios = municipios[: args.limit]

    cur.execute("SELECT COUNT(DISTINCT municipio_id) FROM municipios_financeiro")
    row = cur.fetchone()
    ja_feitos = row[0] if row else 0
    print(f"Ja enriquecidos: {ja_feitos} | Restantes: {len(municipios)}")

    # Exercicio: usar informado ou detectar o mais recente
    exercicio: int = args.ano

    print(f"Municipios para enriquecer: {len(municipios)}")
    if exercicio:
        print(f"Exercicio fixo: {exercicio}")
    else:
        print("Exercicio: detectando o mais recente por municipio")

    if args.dry_run:
        print("  [DRY-RUN] Nenhum dado sera escrito no banco")

    total_atualizados = 0
    total_sem_dados = 0
    inicio = time.time()

    for i, (mun_id, nome, uf) in enumerate(municipios):
        # Se nao fixou ano, detectar o mais recente para este municipio
        ano_atual = exercicio
        itens: Sequence[_ItemDCA] = []
        if not ano_atual:
            # Tentar anos recentes (2025 -> 2023) — DCA costuma ter 1-2 anos de atraso
            for candidato in (2025, 2024, 2023):
                itens = buscar_dca_municipio(mun_id, candidato)
                if itens:
                    ano_atual = candidato
                    break
            else:
                ano_atual = 2024  # fallback
        else:
            itens = buscar_dca_municipio(mun_id, ano_atual)

        if not itens:
            itens = buscar_dca_municipio(mun_id, ano_atual)

        dados = parse_dca_itens(itens) if itens else {}
        tem_dados = any(v is not None for v in dados.values())

        if args.dry_run:
            campos_preenchidos = sum(1 for v in dados.values() if v is not None)
            status = "\u2713" if tem_dados else "\u2717"
            resumo = " | ".join(
                f"{k}={v:,.0f}" for k, v in dados.items()
                if v is not None
            )[:120]
            msg = (
                f"  {status} {mun_id} - {nome} ({uf}) [{ano_atual}]"
                + f" | {campos_preenchidos} campos | {resumo}"
            )
            print(msg)
        elif tem_dados:
            upsert_financeiro(cur, mun_id, ano_atual, dados)
            total_atualizados += 1
        else:
            total_sem_dados += 1

        # Rate limit (1 req/s — SICONFI e rigoroso)
        if i < len(municipios) - 1:
            time.sleep(1.0)

        # Progresso a cada 20 municipios
        if (i + 1) % 20 == 0:
            elapsed = time.time() - inicio
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  ... {i + 1}/{len(municipios)} ({rate:.1f} mun/s)")

    if not args.dry_run:
        conn.commit()

    elapsed_dca = time.time() - inicio
    print(f"\nDCA concluido em {elapsed_dca:.1f}s")
    if args.dry_run:
        print(f"  Municipios DCA: {len(municipios)} (dry-run, sem escrita)")
    else:
        print(f"  Atualizados DCA: {total_atualizados} | Sem dados: {total_sem_dados}")

    # ========================================================================
    # FASE 2 — RREO Anexo 03: Arrecadacao de Impostos
    # ========================================================================
    if not args.rreo:
        print("\n[INFO] Use --rreo para buscar arrecadacao de impostos (RREO Anexo 03)")
        conn.close()
        return

    print(f"\n{'='*60}")
    print("FASE 2: RREO Anexo 03 — Arrecadacao de Impostos")
    print(f"{'='*60}")

    # Buscar municipios que ja tem financeiro DCA mas sem dados RREO
    uf_filtro_rreo: str = args.uf.upper()
    where_rreo = ""
    params_rreo: list[str | int] = []
    if uf_filtro_rreo:
        where_rreo = " AND m.uf = %s"
        params_rreo.append(uf_filtro_rreo)

    cur.execute(
        f"""
        SELECT m.municipio_id, m.nome, m.uf, mf.exercicio
        FROM municipios_financeiro mf
        JOIN municipios_ibge m ON mf.municipio_id = m.municipio_id
        WHERE mf.arrec_fonte_rreo IS NULL {where_rreo}
        ORDER BY m.uf, m.nome
        """,
        params_rreo,
    )
    mun_rreo: list[tuple[int, str, str, int]] = cur.fetchall()
    if args.limit > 0:
        mun_rreo = mun_rreo[: args.limit]

    print(f"Municipios para RREO: {len(mun_rreo)}")
    if args.dry_run:
        print("  [DRY-RUN] Nenhum dado sera escrito no banco")

    total_rreo_ok = 0
    total_rreo_vazio = 0
    inicio_rreo = time.time()

    for i, (mun_id, nome, uf, ano) in enumerate(mun_rreo):
        itens_rreo = buscar_rreo_a03(mun_id, ano)
        dados_rreo = parse_rreo_a03_itens(itens_rreo) if itens_rreo else {}
        tem_dados_rreo = any(v is not None for v in dados_rreo.values())

        if args.dry_run:
            campos = sum(1 for v in dados_rreo.values() if v is not None)
            status = "\u2713" if tem_dados_rreo else "\u2717"
            # Mostrar impostos principais
            impostos = [
                f"IPTU={dados_rreo.get('arrec_iptu') or 0:,.0f}",
                f"ISS={dados_rreo.get('arrec_iss') or 0:,.0f}",
                f"ICMS={dados_rreo.get('arrec_cota_icms') or 0:,.0f}",
                f"FPM={dados_rreo.get('arrec_cota_fpm') or 0:,.0f}",
            ]
            msg = (
                f"  {status} {mun_id} - {nome} ({uf}) [{ano}]"
                + f" | {campos} campos | {', '.join(impostos)}"
            )
            print(msg)
        elif tem_dados_rreo:
            upsert_arrecadacao(cur, mun_id, ano, dados_rreo)
            total_rreo_ok += 1
        else:
            total_rreo_vazio += 1

        # Rate limit (1 req/s — SICONFI e rigoroso)
        if i < len(mun_rreo) - 1:
            time.sleep(1.0)

        # Progresso a cada 20 municipios
        if (i + 1) % 20 == 0:
            elapsed = time.time() - inicio_rreo
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  ... {i + 1}/{len(mun_rreo)} ({rate:.1f} mun/s)")

    if not args.dry_run:
        conn.commit()

    conn.close()

    elapsed_rreo = time.time() - inicio_rreo
    print(f"\nRREO concluido em {elapsed_rreo:.1f}s")
    if args.dry_run:
        print(f"  Municipios RREO: {len(mun_rreo)} (dry-run, sem escrita)")
    else:
        print(f"  Atualizados RREO: {total_rreo_ok} | Sem dados: {total_rreo_vazio}")


if __name__ == "__main__":
    main()
