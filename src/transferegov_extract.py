#!/usr/bin/env python3
"""
Transferegov Genérico — Extração de Planos de Ação por Objeto.

Uso (da raiz do projeto):
  python3 src/transferegov_extract.py --discover --ano 2026
  python3 src/transferegov_extract.py --objeto 301 --ano 2026
  python3 src/transferegov_extract.py --objeto 301 --ano 2026 --negados
  python3 src/transferegov_extract.py --objeto all --ano 2026 --csv
  python3 src/transferegov_extract.py --objeto 662 --ano 2026 --situacao REPROVADO CANCELADO

Dependências:
    pip install requests pandas openpyxl
"""

import argparse
import json
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Adicionar raiz do projeto ao path para importar config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import pandas as pd

from config.settings import (
    API_URL_LISTAGEM as API_URL,
    HEADERS,
    DEFAULT_TIMEOUT as TIMEOUT,
    SLEEP_BETWEEN_PAGES as SLEEP,
    MAX_RETRIES,
    RETRY_BACKOFF,
    DEFAULT_PAGE_SIZE,
    SITUACOES_NEGADAS,
    SITUACOES_CONHECIDAS,
    OUTPUT_LOGS,
    OUTPUT_XLSX,
    OUTPUT_CSV,
    OUTPUT_JSON,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("transferegov")


# ---------------------------------------------------------------------------
# Request com retry
# ---------------------------------------------------------------------------
def make_request(session, params):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning(
                "HTTP %s página %s (tent %d/%d)",
                status, params["pageNumber"], attempt, MAX_RETRIES,
            )
            if exc.response and exc.response.status_code in (401, 403, 404):
                return None
        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "Conn error página %s (tent %d/%d): %s",
                params["pageNumber"], attempt, MAX_RETRIES, exc,
            )
        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout página %s (tent %d/%d)",
                params["pageNumber"], attempt, MAX_RETRIES,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Erro requisição: %s", exc)
            return None
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)
    return None


# ---------------------------------------------------------------------------
# Parse response
# ---------------------------------------------------------------------------
def parse_page(resp):
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        return [], 0
    if isinstance(body, list):
        return body, len(body)
    if isinstance(body, dict):
        total = body.get("total", 0)
        for key in ("listaPlanosAcao", "data", "content", "items", "results"):
            if key in body and isinstance(body[key], list):
                return body[key], total
    return [], 0


# ---------------------------------------------------------------------------
# Paginação genérica
# ---------------------------------------------------------------------------
def extract_all(objeto, ano, politicas_publicas=""):
    """Extrai todos os planos de ação com paginação."""
    session = requests.Session()
    all_records = []
    page = 1

    obj_param = "" if objeto == "all" else str(objeto)

    while True:
        params = {
            "objetoExecucao": obj_param,
            "objetoExecucaoAno": str(ano),
            "politicasPublicas": politicas_publicas,
            "pageSize": str(DEFAULT_PAGE_SIZE),
            "pageNumber": str(page),
        }

        logger.info("--- Página %d ---", page)

        resp = make_request(session, params)
        if resp is None:
            logger.error("Falha página %d. Extração interrompida.", page)
            break

        records, total = parse_page(resp)

        if page == 1:
            logger.info("Total informado pela API: %s", total)
            if records:
                logger.info("Amostra primeiro registro: %s", json.dumps(records[0], ensure_ascii=False)[:500])

        if not records:
            logger.info("Página %d vazia — fim.", page)
            break

        all_records.extend(records)
        logger.info(
            "Página %d: +%d | Acumulado: %d / %s",
            page, len(records), all_records.__len__(), total,
        )

        if len(records) < DEFAULT_PAGE_SIZE:
            break

        page += 1
        time.sleep(SLEEP)

    return all_records


# ---------------------------------------------------------------------------
# Descobrir objetos
# ---------------------------------------------------------------------------
def discover_objects(ano):
    """Varre a API para listar todos os objetos disponíveis num ano."""
    session = requests.Session()
    objetos = {}
    page = 1

    logger.info("Descobrindo objetos para ano %s...", ano)

    while True:
        params = {
            "objetoExecucao": "",
            "objetoExecucaoAno": str(ano),
            "politicasPublicas": "",
            "pageSize": str(DEFAULT_PAGE_SIZE),
            "pageNumber": str(page),
        }

        resp = make_request(session, params)
        if resp is None:
            break

        records, total = parse_page(resp)
        if not records:
            break

        for r in records:
            oid = r.get("objetoId")
            desc = r.get("objetoDescricao", "")
            if oid and oid not in objetos:
                objetos[oid] = desc

        logger.info(
            "Página %d: +%d registros | objetos únicos: %d",
            page, len(records), len(objetos),
        )

        if len(records) < DEFAULT_PAGE_SIZE:
            break

        page += 1
        time.sleep(0.5)

    return objetos


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_excel(df, filepath):
    """Exporta DataFrame para Excel com auto-width."""
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Planos de Acao")
        ws = writer.sheets["Planos de Acao"]
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].fillna("").astype(str).str.len().max() if len(df) else 0,
                len(str(col)),
            ) + 2
            col_letter = (
                chr(65 + idx) if idx < 26
                else chr(64 + idx // 26) + chr(65 + idx % 26)
            )
            ws.column_dimensions[col_letter].width = min(max_len, 60)
    logger.info("Excel: %s", filepath)


def export_csv(df, filepath):
    """Exporta DataFrame para CSV."""
    df.to_csv(filepath, index=False, sep=";", encoding="utf-8-sig")
    logger.info("CSV: %s", filepath)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Extrai Planos de Ação do Transferegov.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s --discover --ano 2026
  %(prog)s --objeto 301 --ano 2026
  %(prog)s --objeto 301 --ano 2026 --negados
  %(prog)s --objeto all --ano 2026 --csv
  %(prog)s --objeto 662 --ano 2026 --situacao REPROVADO CANCELADO
        """,
    )

    parser.add_argument("--discover", action="store_true",
                        help="Descobrir todos os objetos disponíveis")
    parser.add_argument("--objeto", type=str, default="301",
                        help="Código do objeto (default: 301). Use 'all' para todos.")
    parser.add_argument("--ano", type=str, default="2026",
                        help="Ano exercício (default: 2026)")
    parser.add_argument("--situacao", nargs="+", default=None,
                        help="Filtrar por situação(ões). Ex: REPROVADO IMPEDIDO")
    parser.add_argument("--negados", action="store_true",
                        help="Atalho: filtra REPROVADO IMPEDIDO CANCELADO NAO_CUMPROU")
    parser.add_argument("--csv", action="store_true",
                        help="Também exportar CSV")
    parser.add_argument("--output", type=str, default=None,
                        help="Nome base do arquivo de saída (sem extensão)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Logging verboso")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    log_file = OUTPUT_LOGS / f"transferegov_{ts}.log"
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger.info("=" * 70)
    logger.info("TRANSFEREGOV — Extração de Planos de Ação")
    logger.info("Endpoint: %s", API_URL)
    logger.info("=" * 70)

    # ---- Modo discover ----
    if args.discover:
        objetos = discover_objects(args.ano)
        print(f"\n{'COD':>5}  DESCRIÇÃO")
        print("-" * 70)
        for oid in sorted(objetos.keys()):
            print(f"{oid:>5}  {objetos[oid]}")
        print(f"\nTotal: {len(objetos)} objetos disponíveis para {args.ano}")

        # Salvar como JSON
        disc_path = OUTPUT_JSON / f"objetos_disponiveis_{args.ano}_{ts}.json"
        with open(disc_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in objetos.items()}, f, ensure_ascii=False, indent=2)
        logger.info("Lista salva: %s", disc_path)
        return 0

    # ---- Modo extração ----
    objeto = args.objeto
    ano = args.ano

    # Resolver situação
    situacao_filter = None
    if args.negados:
        situacao_filter = SITUACOES_NEGADAS
    elif args.situacao:
        situacao_filter = set(s.upper() for s in args.situacao)

    logger.info("Objeto: %s | Ano: %s | Filtro situação: %s", objeto, ano, situacao_filter)

    records = extract_all(objeto, ano)

    if not records:
        logger.warning("Nenhum registro encontrado.")
        return 1

    df = pd.DataFrame(records)

    # Converter valores monetários
    for col in df.columns:
        if "valor" in col.lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Logar situações
    if "planoAcaoSituacao" in df.columns:
        logger.info("Situações encontradas:")
        for sit, count in df["planoAcaoSituacao"].value_counts().items():
            logger.info("  %-25s %d", sit, count)

    # Filtrar por situação
    if situacao_filter:
        before = len(df)
        df = df[df["planoAcaoSituacao"].isin(situacao_filter)].copy()
        logger.info("Filtro situacao: %d → %d registros", before, len(df))
        if df.empty:
            logger.info("Nenhum registro com situação %s para objeto %s/%s.",
                        situacao_filter, objeto, ano)

    # Nome de saída
    if args.output:
        base = args.output
    else:
        obj_tag = "all" if objeto == "all" else objeto
        sit_tag = "_negados" if args.negados else (
            "_".join(sorted(situacao_filter)) if situacao_filter else ""
        )
        base = f"transferegov_{obj_tag}_{ano}{sit_tag}"

    # Exportar
    xlsx_path = OUTPUT_XLSX / f"{base}.xlsx"
    export_excel(df, xlsx_path)

    if args.csv:
        export_csv(df, OUTPUT_CSV / f"{base}.csv")

    # JSON backup
    json_path = OUTPUT_JSON / f"{base}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict("records"), f, ensure_ascii=False, indent=2)
    logger.info("JSON: %s", json_path)

    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Objeto:           {objeto}")
    print(f"Ano:              {ano}")
    print(f"Registros:        {len(df)}")
    print(f"Colunas:          {len(df.columns)}")
    print(f"Arquivo:          {xlsx_path}")
    if "planoAcaoSituacao" in df.columns:
        print(f"Situações:        {df['planoAcaoSituacao'].value_counts().to_dict()}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
