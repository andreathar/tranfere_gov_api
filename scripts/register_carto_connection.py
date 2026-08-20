#!/usr/bin/env python3
"""
Register the carto_reader Postgres role as a Connection in CARTO Workspace,
via CARTO's Connections API (https://docs.carto.com/carto-for-developers/reference/carto-api/resources-api/connections.md).

This is separate from scripts/create_carto_reader.py, which only creates the
DB role. This script additionally tells the CARTO *platform* about that role
so it shows up as a data source in CARTO Builder/Workspace, rather than being
consumed only by ad-hoc Carto Agents holding a raw connection string.

Auth: the Connections API requires an OAuth Access Token (client_credentials
grant), NOT a plain API Access Token. Create an M2M OAuth Client under
Workspace > Developers > Credentials > OAuth Clients, then set:

  export CARTO_API_BASE_URL=https://gcp-us-east1.api.carto.com   # your region/tenant
  export CARTO_OAUTH_CLIENT_ID=...
  export CARTO_OAUTH_CLIENT_SECRET=...
  export CARTO_PG_HOST=... CARTO_PG_PORT=... CARTO_PG_DB=...
  export CARTO_PG_USER=carto_reader CARTO_PG_PASS=...   # from create_carto_reader.py output

Usage:
  .venv/bin/python scripts/register_carto_connection.py

Note: CARTO Cloud reaches your database over the public internet from
region-specific static IPs — allowlist those IPs on your DB firewall first
(see CARTO's IP allowlisting guide) or the connection test will fail even
with correct credentials.
"""
from __future__ import annotations

import sys

import requests

from config import settings


def get_oauth_token() -> str:
    resp = requests.post(
        settings.CARTO_OAUTH_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.CARTO_OAUTH_CLIENT_ID,
            "client_secret": settings.CARTO_OAUTH_CLIENT_SECRET,
            "audience": settings.CARTO_OAUTH_AUDIENCE,
        },
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"OAuth response had no access_token: {resp.text}")
    return token


def register_connection(token: str) -> dict:
    url = f"{settings.CARTO_API_BASE_URL.rstrip('/')}/v3/connections"
    body = {
        "name": settings.CARTO_CONNECTION_NAME,
        "provider_id": "postgres",
        "privacy": "private",
        "config": {
            "server": settings.CARTO_PG_HOST,
            "port": settings.CARTO_PG_PORT,
            "database": settings.CARTO_PG_DB,
            "username": settings.CARTO_PG_USER,
            "password": settings.CARTO_PG_PASS,
        },
    }
    resp = requests.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    missing = [
        name
        for name in ("CARTO_API_BASE_URL", "CARTO_OAUTH_CLIENT_ID", "CARTO_OAUTH_CLIENT_SECRET")
        if not getattr(settings, name)
    ]
    if missing:
        print(f"Missing required settings: {', '.join(missing)}")
        print("See this script's docstring for the env vars to set.")
        return 1
    if not settings.CARTO_PG_PASS:
        print("CARTO_PG_PASS is empty — run scripts/create_carto_reader.py first and export the printed password.")
        return 1

    try:
        print("Requesting OAuth access token...")
        token = get_oauth_token()
        print(f"Registering connection '{settings.CARTO_CONNECTION_NAME}' at {settings.CARTO_API_BASE_URL}...")
        result = register_connection(token)
    except requests.HTTPError as exc:
        print("CARTO API request failed:", exc)
        print("Response body:", exc.response.text if exc.response is not None else "<none>")
        return 2
    except requests.RequestException as exc:
        print("Network error talking to CARTO API:", exc)
        return 3

    conn_id = result.get("id", "<unknown>")
    print(f"\nSUCCESS — connection registered (id: {conn_id}).")
    print("It should now be visible as a data source in CARTO Workspace/Builder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
