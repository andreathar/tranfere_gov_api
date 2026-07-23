#!/usr/bin/env python3
"""
Extração de Planos de Ação 2026 (Objeto 301 - Cemitérios) PERDIDOS ou NEGADOS.

Uso: python3 src/extract_cemiterios_2026_negados.py
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
    DEFAULT_TIMEOUT as TIMEOUT,
    SLEEP_BETWEEN_PAGES as SLEEP,
    MAX_RETRIES,
    RETRY_BACKOFF,
    DEFAULT_PAGE_SIZE,
    SITUACOES_NEGADAS,
    OUTPUT_LOGS,
    OUTPUT_JSON,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = OUTPUT_LOGS / "extract_cemiterios_2026_negados.log"
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


def make_request(session, params):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning("HTTP %s página %s (tent %d/%d)", status, params["pageNumber"], attempt, MAX_RETRIES)
            if exc.response and exc.response.status_code in (401, 403, 404):
                return None
        except requests.exceptions.ConnectionError as exc:
            logger.warning("Conn error página %s (tent %d/%d): %s", params["pageNumber"], attempt, MAX_RETRIES, exc)
        except requests.exceptions.Timeout:
            logger.warning("Timeout página %s (tent %d/%d)", params["pageNumber"], attempt, MAX_RETRIES)
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


def extract_all():
    session = requests.Session()
    all_records = []
    page = 1

    while True:
        params = {**DEFAULT_PARAMS, "pageNumber": str(page)}
        logger.info("--- Página %d ---", page)

        resp = make_request(session, params)
        if resp is None:
            logger.error("Falha página %d. Abortando.", page)
            break

        if page == 1:
            logger.info("Amostra: %s", resp.text[:1500])

        records = parse_page(resp)
        if not records:
            logger.info("Página %d vazia — fim.", page)
            break

        all_records.extend(records)
        logger.info("Página %d: +%d | Acumulado: %d", page, len(records), len(all_records))

        if len(records) < DEFAULT_PAGE_SIZE:
            break

        page += 1
        time.sleep(SLEEP)

    return all_records


def export(records, basename):
    if not records:
        logger.warning("Nenhum registro para exportar.")
        return

    df = pd.DataFrame(records)

    for col in df.columns:
        if "valor" in col.lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")

    xlsx = f"{basename}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Negados/Perdidos")
        ws = writer.sheets["Negados/Perdidos"]
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].fillna("").astype(str).str.len().max() if len(df) else 0,
                len(str(col)),
            ) + 2
            col_letter = chr(65 + idx) if idx < 26 else chr(64 + idx // 26) + chr(65 + idx % 26)
            ws.column_dimensions[col_letter].width = min(max_len, 60)
    logger.info("Excel: %s", xlsx)

    csv = f"{basename}.csv"
    df.to_csv(csv, index=False, sep=";", encoding="utf-8-sig")
    logger.info("CSV: %s", csv)


def main():
    logger.info("=" * 70)
    logger.info("EXTRAÇÃO — Planos NEGADOS/PERDIDOS 2026 | Objeto 301 (Cemitérios)")
    logger.info("=" * 70)

    try:
        records = extract_all()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário.")
        return 130

    if not records:
        logger.warning("Nenhum registro extraído.")
        return 1

    df = pd.DataFrame(records)

    logger.info("Todas as situações:")
    for sit, count in df["planoAcaoSituacao"].value_counts().items():
        logger.info("  %-20s %d", sit, count)

    df_neg = df[df["planoAcaoSituacao"].isin(SITUACOES_NEGADAS)].copy()

    logger.info("-" * 50)
    logger.info("Total extraído:    %d", len(df))
    logger.info("Negados/Perdidos:  %d", len(df_neg))
    logger.info("-" * 50)

    if df_neg.empty:
        logger.info("Nenhum plano negado/perdido encontrado.")
        logger.info("Exportando todos os %d registros como referência...", len(df))
        export(df.to_dict("records"), "cemiterios_2026_todos")
    else:
        for _, row in df_neg.iterrows():
            logger.info(
                "  %s | %s | %s | R$ %s | %s",
                row.get("planoAcaoCodigo", "?"),
                row.get("beneficiarioNome", "?"),
                row.get("uf", "?"),
                f"{row.get('valorTotal', 0):,.2f}",
                row.get("motivoImpedimento", "-"),
            )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        export(df_neg.to_dict("records"), "cemiterios_2026_negados")
        export(df_neg.to_dict("records"), f"cemiterios_2026_negados_{ts}")

        json_path = OUTPUT_JSON / f"cemiterios_2026_negados_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(df_neg.to_dict("records"), f, ensure_ascii=False, indent=2)
        logger.info("JSON: %s", json_path)

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Total extraído:   {len(df)}")
    print(f"Negados/Perdidos: {len(df_neg)}")
    print(f"Situações:        {df['planoAcaoSituacao'].value_counts().to_dict()}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
