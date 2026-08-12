#!/usr/bin/env python3
"""Healthcheck script for TransfereGov services."""

import sys
from pathlib import Path

from config.settings import (
    LOCALAI_BASE_URL,
    MODAL_VLLM_URL,
    PG_DB,
    PG_HOST,
    PG_PASS,
    PG_PORT,
    PG_USER,
    QDRANT_URL,
    QDRANT_COLLECTION,
    USE_LOCAL_VLLM,
    USE_MODAL_VLLM,
)
from src.db_utils import get_connection


def check_postgres() -> bool:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        print("postgres: ok")
        return True
    except Exception as exc:
        print(f"postgres: error -> {exc}")
        return False


def check_qdrant() -> bool:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=QDRANT_URL, trust_env=False)
        collections = [c.name for c in client.get_collections().collections]
        if QDRANT_COLLECTION in collections:
            print(f"qdrant: ok ({QDRANT_COLLECTION})")
            return True
        print(f"qdrant: error -> collection {QDRANT_COLLECTION} not found")
        return False
    except Exception as exc:
        print(f"qdrant: error -> {exc}")
        return False


def check_localai() -> bool:
    try:
        import httpx

        url = LOCALAI_BASE_URL.rstrip("/") if LOCALAI_BASE_URL else ""
        if not url:
            print("localai: skipped (LOCALAI_BASE_URL unset)")
            return True
        with httpx.Client(timeout=10, trust_env=False) as client:
            resp = client.get(f"{url}/v1/models")
            if resp.status_code == 200:
                print("localai: ok")
                return True
            print(f"localai: error -> status {resp.status_code}")
            return False
    except Exception as exc:
        print(f"localai: error -> {exc}")
        return False


def check_modalllm() -> bool:
    if not USE_MODAL_VLLM or not MODAL_VLLM_URL:
        print("modal-vllm: skipped")
        return True
    try:
        import httpx

        url = MODAL_VLLM_URL.rstrip("/")
        with httpx.Client(timeout=10, trust_env=False) as client:
            resp = client.get(f"{url}/v1/models")
            if resp.status_code == 200:
                print("modal-vllm: ok")
                return True
            print(f"modal-vllm: error -> status {resp.status_code}")
            return False
    except Exception as exc:
        print(f"modal-vllm: error -> {exc}")
        return False


def main() -> int:
    print("TransfereGov healthcheck")
    print("------------------------")
    checks = [
        check_postgres(),
        check_qdrant(),
        check_localai(),
        check_modalllm(),
    ]
    if all(checks):
        print("all checks passed")
        return 0
    print("one or more checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
