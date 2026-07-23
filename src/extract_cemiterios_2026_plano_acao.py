#!/usr/bin/env python3
"""
Extração dos Planos de Ação de 2026 - Objeto 301 (Reforma de Cemitérios)
via API pública do Transferegov (especiais).

Uso: python3 src/extract_cemiterios_2026_plano_acao.py
"""

import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import pandas as pd

from config.settings import (
    API_URL_LISTAGEM as API_URL,
    HEADERS,
    DEFAULT_TIMEOUT as REQUEST_TIMEOUT,
    SLEEP_BETWEEN_PAGES,
    MAX_RETRIES,
    RETRY_BACKOFF,
    DEFAULT_PAGE_SIZE,
    OUTPUT_LOGS,
    OUTPUT_JSON,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = OUTPUT_LOGS / "extract_cemiterios_2026_plano_acao.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

DEFAULT_PARAMS = {
    "objetoExecucao": "301",
    "objetoExecucaoAno": "2026",
    "politicasPublicas": "",
    "pageSize": str(DEFAULT_PAGE_SIZE),
    "pageNumber": "1",
}


# ---------------------------------------------------------------------------
# Request com retry
# ---------------------------------------------------------------------------
def make_request(session, params):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "HTTP %s página %s (tent %d/%d)",
                status, params["pageNumber"], attempt, MAX_RETRIES,
            )
            if exc.response is not None and exc.response.status_code in (401, 403, 404):
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


def parse_page(resp):
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("listaPlanosAcao", "data", "content", "items", "results"):
            if key in body and isinstance(body[key], list):
                return body[key]
    return []


# ---------------------------------------------------------------------------
# Extração principal
# ---------------------------------------------------------------------------
def extract_plano_acao():
    session = requests.Session()
    all_records = []
    page = 1

    while True:
        params = {**DEFAULT_PARAMS, "pageNumber": str(page)}
        logger.info("--- Página %d ---", page)

        resp = make_request(session, params)
        if resp is None:
            logger.error("Falha página %d. Extração interrompida.", page)
            break

        if page == 1:
            logger.info("HTTP %d | %d bytes", resp.status_code, len(resp.content))
            logger.info("Amostra: %s", resp.text[:2000])

        records = parse_page(resp)
        if not records:
            logger.info("Página %d vazia — fim.", page)
            break

        all_records.extend(records)
        logger.info("Página %d: +%d | Acumulado: %d", page, len(records), len(all_records))

        if len(records) < DEFAULT_PAGE_SIZE:
            break

        page += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    return all_records


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_to_excel(records, filepath):
    if not records:
        logger.warning("Nenhum registro para exportar.")
        return

    df = pd.DataFrame(records)
    logger.info("DataFrame: %d linhas x %d colunas", len(df), len(df.columns))

    for col in df.columns:
        if "valor" in col.lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Planos de Acao")
        ws = writer.sheets["Planos de Acao"]
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].fillna("").astype(str).str.len().max() if len(df) else 0,
                len(str(col)),
            ) + 2
            col_letter = chr(65 + idx) if idx < 26 else chr(64 + idx // 26) + chr(65 + idx % 26)
            ws.column_dimensions[col_letter].width = min(max_len, 60)

    logger.info("Excel: %s", filepath)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_xlsx = "cemiterios_2026.xlsx"
    output_backup = f"cemiterios_2026_{ts}.xlsx"

    logger.info("=" * 70)
    logger.info("EXTRAÇÃO — Planos de Ação 2026 | Objeto 301 (Cemitérios)")
    logger.info("Endpoint: %s", API_URL)
    logger.info("=" * 70)

    try:
        records = extract_plano_acao()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário.")
        return 130

    if not records:
        logger.warning("Nenhum registro extraído.")
        return 1

    logger.info("Total: %d registros", len(records))

    json_path = OUTPUT_JSON / f"cemiterios_2026_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info("JSON: %s", json_path)

    try:
        export_to_excel(records, output_xlsx)
        export_to_excel(records, output_backup)
    except Exception as exc:
        logger.exception("Erro ao exportar Excel: %s", exc)
        return 1

    df = pd.DataFrame(records)
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Registros:  {len(df)}")
    print(f"Colunas:    {len(df.columns)}")
    print(f"Excel:      {output_xlsx}")
    print(f"JSON:       {json_path}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
