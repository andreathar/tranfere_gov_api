"""
Enriquecimento CLDF — Baixa CSVs do CKAN (dados.cl.df.gov.br) e proposições
do PLE API para enriquecer deputados distritais do DF.

Fontes:
  - CKAN: emendas parlamentares, despesas, empenhos, verbas indenizatórias
  - PLE API: proposições legislativas (proposicoes_ano.json)

Uso:
  python3 -m src.enrichers.cldf_enrichment [--fase all|emendas|despesas|empenhos|verbas|proposicoes]
                                           [--ano 2024] [--dry-run] [--limit N] [-v]
"""

import argparse
import csv
import io
import logging
import re
import time
from datetime import datetime

import httpx

from config.settings import OUTPUT_DIR
from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CKAN resource URLs (dados.cl.df.gov.br)
# ---------------------------------------------------------------------------
CKAN_BASE = "https://dados.cl.df.gov.br"

# Emendas parlamentares por ano (CSV, delimitador ";")
EMENDAS_RESOURCES: dict[int, str] = {
    2021: f"{CKAN_BASE}/dataset/80a9618a-44fb-4f9e-bdd1-7125f3265dcf/resource/e95bec86-614a-46b5-ba0d-af5242aecdba/download",
    2022: f"{CKAN_BASE}/dataset/80a9618a-44fb-4f9e-bdd1-7125f3265dcf/resource/f2b2e59b-68d2-4434-aa9f-9d0d77c4bd41/download",
    2023: f"{CKAN_BASE}/dataset/80a9618a-44fb-4f9e-bdd1-7125f3265dcf/resource/68183e04-b5e6-4f24-9160-6d15b6486ef8/download",
    2024: f"{CKAN_BASE}/dataset/80a9618a-44fb-4f9e-bdd1-7125f3265dcf/resource/ac2212b7-58c2-4fb2-9284-8e9257e5416e/download",
    2025: f"{CKAN_BASE}/dataset/80a9618a-44fb-4f9e-bdd1-7125f3265dcf/resource/36ab2cb2-99ad-4f6a-b4e4-d09a448207e5/download",
}

# Total de despesas (CSV, delimitador ";")
DESPESAS_URL = (
    f"{CKAN_BASE}/dataset/bb493d1e-4847-4c3b-b859-d0bca5a63c1b"
    f"/resource/00b42444-c607-4d8f-b539-7a8ac18a8be0/download"
)

# Empenhos detalhados (CSV, delimitador ";")
EMPENHOS_URL = (
    f"{CKAN_BASE}/dataset/dcb57d9b-349d-4f8f-89af-effc4ab09045"
    f"/resource/4001b516-6134-4c94-a558-627b9e7a59e4/download"
)

# Verbas indenizatórias por ano (CSV, delimitador ";")
VERBAS_RESOURCES: dict[int, str] = {
    2022: f"{CKAN_BASE}/dataset/662b8e54-727c-4e97-873c-d8c168ecc465/resource/09d49794-524a-41d0-8461-3f5f784e4065/download",
    2023: f"{CKAN_BASE}/dataset/662b8e54-727c-4e97-873c-d8c168ecc465/resource/65722740-44b5-47e2-a7c1-c05f25f6e936/download",
    2024: f"{CKAN_BASE}/dataset/662b8e54-727c-4e97-873c-d8c168ecc465/resource/fb6dd7ff-f9aa-47ee-8fad-ed479fe2c1a2/download",
}

# Proposições CLDF (CKAN CSV por ano — JSON disponível mas CSV mais simples)
PROPOSICOES_CKAN_BASE = (
    f"{CKAN_BASE}/dataset/bd3aca51-e4b1-4d6f-83bf-ccbc5bbc3cd8"
)
PROPOSICOES_CKAN_RESOURCES: dict[int, str] = {
    2023: f"{PROPOSICOES_CKAN_BASE}/resource/645c87ae-aed9-4113-a51b-9002298b98dd/download",
    2024: f"{PROPOSICOES_CKAN_BASE}/resource/c6282e10-284f-42d0-a817-3af4797cc19c/download",
    2025: f"{PROPOSICOES_CKAN_BASE}/resource/52f5d422-cc72-4aca-b0bb-931b7bfdc8b1/download",
    2026: f"{PROPOSICOES_CKAN_BASE}/resource/659101ab-83c5-4484-bc88-2ad465be6d10/download",
}

# PLE API (alternativa para proposições mais recentes)
PLE_API_BASE = "https://ple.cl.df.gov.br/pleservico/api/public"

# Mapeamento de meses
MESES_MAP = {
    "janeiro": "Janeiro", "fevereiro": "Fevereiro", "março": "Março",
    "abril": "Abril", "maio": "Maio", "junho": "Junho",
    "julho": "Julho", "agosto": "Agosto", "setembro": "Setembro",
    "outubro": "Outubro", "novembro": "Novembro", "dezembro": "Dezembro",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_csv(url: str) -> str:
    """Baixa CSV de URL CKAN e retorna conteúdo como string.

    Detecta automaticamente BOM (UTF-8/UTF-16) e encoding do conteúdo.
    """
    log.info("Baixando CSV: %s", url[:100])
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    raw = resp.content

    # Strip BOM (UTF-8 EF BB BF, UTF-16 LE FF FE, UTF-16 BE FE FF)
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    elif raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        raw = raw[2:]

    # Tentar UTF-8 primeiro; fallback para latin-1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _parse_brl(valor: str) -> float:
    """Converte valor monetário para float.

    Detecta automaticamente:
    - Formato BRL: '1.234.567,89' → 1234567.89
    - Formato CKAN: '700000.00000000' → 700000.0  (8 casas decimais)
    - Formato CKAN negativo: '-3120000.00000000' → -3120000.0
    - Formato puro: '1234567.89' → 1234567.89
    """
    if not valor or valor.strip() == "":
        return 0.0
    valor = valor.strip()
    # CKAN format: "700000.00000000" or "-3120000.00000000"
    # Ponto seguido de 8 dígitos = formato decimal padrão (não milhar BRL)
    if re.match(r"^-?\d+\.\d{8}$", valor):
        return float(valor)
    # Formato BRL clássico: "1.234.567,89" — pontos são separador de milhar
    return float(valor.replace(".", "").replace(",", "."))


def _safe_int(valor: str) -> int | None:
    """Tenta converter para int, retorna None se falhar."""
    try:
        return int(valor.strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _safe_date(valor: str) -> str | None:
    """Tenta parsear data, retorna ISO date ou None."""
    if not valor or valor.strip() == "":
        return None
    valor = valor.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 1. Emendas Parlamentares
# ---------------------------------------------------------------------------

def sync_emendas(*, ano: int | None = None, dry_run: bool = False) -> int:
    """Baixa emendas parlamentares do CKAN e insere no banco."""
    anos = [ano] if ano else list(EMENDAS_RESOURCES.keys())
    total = 0

    for a in sorted(anos):
        url = EMENDAS_RESOURCES.get(a)
        if not url:
            log.warning("Sem emendas disponíveis para %d", a)
            continue

        try:
            conteudo = _fetch_csv(url)
            reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
        except Exception as e:
            log.error("Erro ao baixar emendas %d: %s", a, e)
            continue

        inseridos = 0
        with get_connection() as conn, conn.cursor() as cur:
            for row in reader:
                id_emenda = _safe_int(row.get("ID_EMENDA", ""))
                if not id_emenda:
                    continue

                # Verificar duplicata
                cur.execute("SELECT 1 FROM cldf_emendas WHERE id_emenda = %s", (id_emenda,))
                if cur.fetchone():
                    continue

                data_emenda = _safe_date(row.get("DATA_EMENDA", ""))

                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO cldf_emendas (
                            ano_emenda, data_emenda, id_emenda, lei_emenda, nr_emenda,
                            pt, pt_compartilhado, status_emenda, cod_uo, nome_uo,
                            vl_lei_alteracao, vl_bloqueado_siggo, vl_disponivel,
                            vl_empenhado, vl_emenda, vl_desbloqueado,
                            vl_saldo_a_solicitar, vl_liquidado
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id_emenda) DO UPDATE SET
                            vl_empenhado = EXCLUDED.vl_empenhado,
                            vl_liquidado = EXCLUDED.vl_liquidado,
                            vl_emenda = EXCLUDED.vl_emenda,
                            updated_at = NOW()
                        """,
                        (
                            a, data_emenda, id_emenda,
                            row.get("LEI_EMENDA", ""),
                            row.get("NR_EMENDA", ""),
                            row.get("PT", ""),
                            _safe_int(row.get("PT_COMPARTILHADO", "0")) or 0,
                            row.get("STATUS_EMENDA", "ATIVO"),
                            row.get("COD_UO", ""),
                            row.get("NOME_UO", ""),
                            _parse_brl(row.get("VL_LEI_ALTERACAO", "0")),
                            _parse_brl(row.get("VL_BLOQUEADO_SIGGO", "0")),
                            _parse_brl(row.get("VL_DISPONIVEL", "0")),
                            _parse_brl(row.get("VL_EMPENHADO", "0")),
                            _parse_brl(row.get("VL_EMENDA", "0")),
                            _parse_brl(row.get("VL_DESBLOQUEADO", "0")),
                            _parse_brl(row.get("VL_SALDO_A_SOLICITAR", "0")),
                            _parse_brl(row.get("VL_LIQUIDADO", "0")),
                        ),
                    )
                inseridos += 1

        total += inseridos
        log.info("Emendas %d: %d registros %s", a, inseridos,
                 "(dry-run)" if dry_run else "inseridos")

    return total


# ---------------------------------------------------------------------------
# 2. Despesas por UO
# ---------------------------------------------------------------------------

def sync_despesas(*, dry_run: bool = False) -> int:
    """Baixa total de despesas do CKAN e insere no banco."""
    try:
        conteudo = _fetch_csv(DESPESAS_URL)
        reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
    except Exception as e:
        log.error("Erro ao baixar despesas: %s", e)
        return 0

    inseridos = 0
    with get_connection() as conn, conn.cursor() as cur:
        for row in reader:
            ano = _safe_int(row.get("Ano", ""))
            mes_raw = (row.get("Mês", "") or row.get("Mes", "")).strip()
            uo = (row.get("UO", "") or "").strip()

            if not ano or not mes_raw or not uo:
                continue

            mes = MESES_MAP.get(mes_raw.lower(), mes_raw)

            # Verificar duplicata
            cur.execute(
                "SELECT 1 FROM cldf_despesas WHERE ano = %s AND mes = %s AND uo_codigo = %s",
                (ano, mes, uo),
            )
            if cur.fetchone():
                continue

            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO cldf_despesas (ano, mes, uo_codigo, empenhado, liquidado, pago)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ano, mes, uo_codigo) DO UPDATE SET
                        empenhado = EXCLUDED.empenhado,
                        liquidado = EXCLUDED.liquidado,
                        pago = EXCLUDED.pago,
                        updated_at = NOW()
                    """,
                    (
                        ano, mes, uo,
                        _parse_brl(row.get("Empenhado", "0")),
                        _parse_brl(row.get("Liquidado", "0")),
                        _parse_brl(row.get("Pago", "0")),
                    ),
                )
            inseridos += 1

    log.info("Despesas: %d registros %s", inseridos, "(dry-run)" if dry_run else "inseridos")
    return inseridos


# ---------------------------------------------------------------------------
# 3. Empenhos Detalhados
# ---------------------------------------------------------------------------

def sync_empenhos(*, dry_run: bool = False, limit: int | None = None) -> int:
    """Baixa empenhos detalhados do CKAN e insere no banco."""
    try:
        conteudo = _fetch_csv(EMPENHOS_URL)
        reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
    except Exception as e:
        log.error("Erro ao baixar empenhos: %s", e)
        return 0

    inseridos = 0
    with get_connection() as conn, conn.cursor() as cur:
        for row in reader:
            if limit and inseridos >= limit:
                break

            numero_ne = (row.get("Número da NE", "") or row.get("Numero da NE", "")).strip()
            if not numero_ne:
                continue

            # Verificar duplicata
            cur.execute("SELECT 1 FROM cldf_empenhos WHERE numero_ne = %s", (numero_ne,))
            if cur.fetchone():
                continue

            ano = _safe_int(row.get("Ano", ""))
            mes_raw = (row.get("Mês", "") or row.get("Mes", "")).strip()
            mes = MESES_MAP.get(mes_raw.lower(), mes_raw) if mes_raw else ""

            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO cldf_empenhos (
                        ano, mes, numero_ne, credor, especificacao,
                        quantidade, valor_unitario, valor_total,
                        modalidade, identificacao
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (numero_ne) DO UPDATE SET
                        valor_total = EXCLUDED.valor_total,
                        updated_at = NOW()
                    """,
                    (
                        ano, mes, numero_ne,
                        (row.get("Credor", "") or "").strip(),
                        (row.get("Especificação", "") or row.get("Especificacao", "") or "").strip()[:500],
                        _safe_int(row.get("Quantidade", "")),
                        _parse_brl(row.get("Valor Unitário", "") or row.get("Valor Unitario", "") or "0"),
                        _parse_brl(row.get("Valor Total", "0")),
                        (row.get("Modalidade", "") or "").strip(),
                        (row.get("Identificação", "") or row.get("Identificacao", "") or "").strip(),
                    ),
                )
            inseridos += 1

    log.info("Empenhos: %d registros %s", inseridos, "(dry-run)" if dry_run else "inseridos")
    return inseridos


# ---------------------------------------------------------------------------
# 4. Verbas Indenizatórias
# ---------------------------------------------------------------------------

def sync_verbas(*, ano: int | None = None, dry_run: bool = False) -> int:
    """Baixa verbas indenizatórias do CKAN e insere no banco."""
    anos = [ano] if ano else list(VERBAS_RESOURCES.keys())
    total = 0

    for a in sorted(anos):
        url = VERBAS_RESOURCES.get(a)
        if not url:
            log.warning("Sem verbas disponíveis para %d", a)
            continue

        try:
            conteudo = _fetch_csv(url)
            reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
        except Exception as e:
            log.error("Erro ao baixar verbas %d: %s", a, e)
            continue

        inseridos = 0
        with get_connection() as conn, conn.cursor() as cur:
            for row in reader:
                nome = (row.get("NOME_PARLAMENTAR", "") or "").strip()
                valor = _parse_brl(row.get("VALOR_DESPESA", "0"))
                data = _safe_date(row.get("DATA_COMPROVANTE", ""))

                if not nome:
                    continue

                # Usar combinacao nome+data+valor para deduplicacao
                nr_comp = (row.get("NR_COMPROVANTE", "") or "").strip()

                # Verificar duplicata
                cur.execute(
                    "SELECT 1 FROM cldf_verbas_indenizatorias WHERE nr_comprovante = %s AND nome_parlamentar = %s",
                    (nr_comp, nome) if nr_comp else (None, None),
                )
                if cur.fetchone():
                    continue

                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO cldf_verbas_indenizatorias (
                            nome_parlamentar, cpf_parlamentar, nome_prestador,
                            cnpj_prestador, cpf_prestador, nr_comprovante,
                            data_comprovante, valor_despesa, classificacao, observacoes
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            nome,
                            (row.get("CPF_PARLAMENTAR", "") or "").strip(),
                            (row.get("NOME_PRESTADOR", "") or "").strip(),
                            (row.get("CNPJ_PRESTADOR", "") or "").strip(),
                            (row.get("CPF_PRESTADOR", "") or "").strip(),
                            nr_comp,
                            data,
                            valor,
                            (row.get("CLASSIFICACAO", "") or "").strip(),
                            (row.get("OBSERVACOES", "") or "").strip(),
                        ),
                    )
                inseridos += 1

        total += inseridos
        log.info("Verbas %d: %d registros %s", a, inseridos,
                 "(dry-run)" if dry_run else "inseridos")

    return total


# ---------------------------------------------------------------------------
# 5. Proposições CLDF (PLE API)
# ---------------------------------------------------------------------------

def sync_proposicoes_ple(*, limit: int = 200, dry_run: bool = False) -> int:
    """Busca proposições via PLE API (POST /proposicao/filter) e insere."""
    inseridos = 0
    page = 1
    per_page = 50

    with get_connection() as conn, conn.cursor() as cur:
        while inseridos < limit:
            payload = {
                "regiaoAdministrativa": "",
                "tema": "",
                "tipoProposicao": "",
                "numeroProposicao": "",
                "anoInicio": 2023,
                "anoFim": 2026,
                "situacaoProposicao": "",
                "offset": (page - 1) * per_page,
                "limit": per_page,
            }

            try:
                resp = httpx.post(
                    f"{PLE_API_BASE}/proposicao/filter",
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                log.error("Erro PLE API (pag %d): %s", page, e)
                break

            # PLE API usa formato Spring Boot paginado: {content, totalElements, ...}
            items = (
                data.get("content")           # Spring Boot Page format
                or data.get("items", [])      # alternativa
                or data.get("data", [])       # alternativa
                or (data if isinstance(data, list) else [])
            )
            if not items:
                break

            for item in items:
                if inseridos >= limit:
                    break

                prop_id = str(item.get("id", ""))
                if not prop_id:
                    continue

                # Verificar duplicata
                cur.execute("SELECT 1 FROM cldf_proposicoes WHERE proposicao_id = %s", (prop_id,))
                if cur.fetchone():
                    continue

                # Mapear campos do PLE API (Spring Boot format)
                tipo = item.get("tipoProposicao", "") or ""
                numero_ano = item.get("siglaNumeroAno", "") or ""
                ementa = item.get("ementa", "") or ""
                tema = (item.get("temaNome", "") or "").strip("#")
                autor = item.get("autoria", "") or ""
                data_apres = _safe_date(item.get("dataLeitura", "") or "")
                situacao = item.get("situacaoProposicao", "") or item.get("etapa", "") or ""
                ra = (item.get("regiaoAdministrativaNome", "") or "").strip("#")
                descricao = item.get("descricaoProposicao", "") or ""

                # Extrair numero e ano de siglaNumeroAno (ex: "IND 10977/2026")
                numero = 0
                ano = 0
                if "/" in numero_ano:
                    parts = numero_ano.split("/")
                    nums = parts[0].strip().split()
                    if len(nums) > 1:
                        try:
                            numero = int(nums[-1])
                        except ValueError:
                            pass
                    try:
                        ano = int(parts[1].strip())
                    except (ValueError, IndexError):
                        pass

                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO cldf_proposicoes (
                            proposicao_id, tipo, numero, ano, ementa,
                            regiao_admin, tema, autor_nome,
                            data_apresentacao, situacao_atual
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (proposicao_id) DO UPDATE SET
                            situacao_atual = EXCLUDED.situacao_atual,
                            updated_at = NOW()
                        """,
                        (
                            prop_id, tipo, numero, ano, ementa[:1000],
                            ra, tema, autor, data_apres, situacao,
                        ),
                    )
                inseridos += 1

            page += 1
            time.sleep(0.5)  # Rate limit

    log.info("Proposições PLE: %d registros %s", inseridos,
             "(dry-run)" if dry_run else "inseridos")
    return inseridos


def sync_proposicoes_ckan(*, ano: int | None = None, dry_run: bool = False) -> int:
    """Baixa proposições via CKAN CSV (alternativa ao PLE API).

    CKAN CSVs de proposições podem usar vírgula ou ponto-e-vírgula como
    delimitador.  Detectamos automaticamente olhando a primeira linha de
    cabeçalho.
    """
    anos = [ano] if ano else list(PROPOSICOES_CKAN_RESOURCES.keys())
    total = 0

    for a in sorted(anos):
        url = PROPOSICOES_CKAN_RESOURCES.get(a)
        if not url:
            log.warning("Sem proposições CKAN disponíveis para %d", a)
            continue

        try:
            conteudo = _fetch_csv(url)
            # Auto-detect delimiter: CSVs de proposições CKAN do DF usam
            # vírgula (,) enquanto outros datasets do DF usam ponto-e-vírgula.
            primeira_linha = conteudo.split("\n", 1)[0]
            delim = ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","
            reader = csv.DictReader(io.StringIO(conteudo), delimiter=delim)
            headers = reader.fieldnames or []
            log.debug("Proposições CKAN %d: delimitador=%r cols=%s", a, delim, headers[:5])
        except Exception as e:
            log.error("Erro ao baixar proposições CKAN %d: %s", a, e)
            continue

        inseridos = 0
        with get_connection() as conn, conn.cursor() as cur:
            for row in reader:
                # --- ID da proposição ---
                # CSVs do CLDF tipicamente trazem: tipo_prop, numero_prop,
                # ano_prop.  Geramos um ID estável a partir desses campos.
                tipo = (
                    row.get("tipo_prop", "") or row.get("TIPO_PROPOSICAO", "")
                    or row.get("tipo", "") or row.get("SIGLA_TIPO", "") or ""
                ).strip()
                numero = _safe_int(
                    row.get("numero_prop", "") or row.get("NUMERO", "")
                    or row.get("numero", "") or ""
                )
                ano_prop = _safe_int(
                    row.get("ano_prop", "") or row.get("ANO", "")
                    or row.get("ano", "") or ""
                )
                if not ano_prop:
                    ano_prop = a  # fallback para o ano do resource

                if tipo and numero and ano_prop:
                    prop_id_str = f"CKAN_{tipo}{numero}/{ano_prop}"
                else:
                    # Fallback: usa linha como ID
                    prop_id_str = f"CKAN_{a}_{inseridos}"

                # Verificar duplicata
                cur.execute(
                    "SELECT 1 FROM cldf_proposicoes WHERE proposicao_id = %s",
                    (prop_id_str,),
                )
                if cur.fetchone():
                    continue

                ementa = (
                    row.get("ementa", "") or row.get("EMENTA", "")
                    or row.get("OBJETO", "") or ""
                ).strip()
                situacao = (
                    row.get("situacao", "") or row.get("SITUACAO", "")
                    or row.get("situacao_atual", "") or ""
                ).strip()
                data_leitura = (
                    row.get("data_leitura", "") or row.get("DATA_APRESENTACAO", "")
                    or ""
                ).strip()

                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO cldf_proposicoes (
                            proposicao_id, tipo, numero, ano, ementa,
                            situacao_atual, data_apresentacao
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (proposicao_id) DO NOTHING
                        """,
                        (
                            prop_id_str, tipo, numero, ano_prop,
                            ementa[:1000], situacao, data_leitura or None,
                        ),
                    )
                inseridos += 1

        total += inseridos
        log.info(
            "Proposições CKAN %d: %d registros %s",
            a, inseridos, "(dry-run)" if dry_run else "inseridos",
        )

    return total


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

FASES = {
    "emendas": ("Emendas Parlamentares", sync_emendas),
    "despesas": ("Despesas por UO", sync_despesas),
    "empenhos": ("Empenhos Detalhados", sync_empenhos),
    "verbas": ("Verbas Indenizatórias", sync_verbas),
    "proposicoes": ("Proposições CLDF (CKAN CSV)", sync_proposicoes_ckan),
}


def run_pipeline(
    *,
    fase: str = "all",
    ano: int | None = None,
    limit: int = 200,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, int]:
    """Executa pipeline de enriquecimento CLDF."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    resultados: dict[str, int] = {}
    inicio = time.time()

    if fase == "all":
        ordem = ["emendas", "despesas", "empenhos", "verbas", "proposicoes"]
    else:
        ordem = [fase]

    for f in ordem:
        if f not in FASES:
            log.warning("Fase desconhecida: %s (disponíveis: %s)", f, ", ".join(FASES))
            continue

        nome, func = FASES[f]
        log.info("─── Fase: %s ───", nome)

        try:
            if f == "proposicoes":
                count = func(ano=ano, dry_run=dry_run)
            elif f == "empenhos":
                count = func(dry_run=dry_run, limit=limit)
            elif f in ("emendas", "verbas"):
                count = func(ano=ano, dry_run=dry_run)
            else:
                count = func(dry_run=dry_run)
            resultados[f] = count
        except Exception as e:
            log.error("Erro na fase %s: %s", f, e)
            resultados[f] = -1

    elapsed = time.time() - inicio
    log.info("Pipeline CLDF concluído em %.1fs: %s", elapsed, resultados)
    return resultados


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enriquecimento CLDF — Deputados Distritais do DF"
    )
    parser.add_argument(
        "--fase", default="all",
        choices=["all", "emendas", "despesas", "empenhos", "verbas", "proposicoes"],
        help="Fase do pipeline (default: all)",
    )
    parser.add_argument("--ano", type=int, help="Filtrar por ano (emendas/verbas)")
    parser.add_argument("--limit", type=int, default=200, help="Limite de registros (proposições/empenhos)")
    parser.add_argument("--dry-run", action="store_true", help="Não gravar no banco")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug")
    args = parser.parse_args()

    resultados = run_pipeline(
        fase=args.fase,
        ano=args.ano,
        limit=args.limit,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print("\n=== Resultados ===")
    for fase, count in resultados.items():
        status = "ERRO" if count < 0 else f"{count} registros"
        print(f"  {fase:15s}: {status}")


if __name__ == "__main__":
    main()
