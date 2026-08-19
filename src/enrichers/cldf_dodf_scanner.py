"""
CLDF × DODF Scanner — busca menções de deputados distritais no Diário Oficial do DF.

Fonte: Querido Diário API (api.queridodiario.ok.org.br)
       Território: 5300108 (Brasília/DF — DODF)

O DODF publica todos os atos do Poder Legislativo (Seção I) incluindo:
  - Decretos Legislativos
  - Resoluções CLDF
  - Portarias internas
  - Atas de plenária
  - Votações aprovadas
  - Nomeações e exonerações na CLDF

Uso:
  python3 -m src.enrichers.cldf_dodf_scanner [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                                              [--mode all|deputados|atos|geral]
                                              [--dry-run] [-v]
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import time
from datetime import datetime, timedelta

import httpx

from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Querido Diário API
# ---------------------------------------------------------------------------
QD_API = "https://api.queridodiario.ok.org.br"
QD_GAZETTES = f"{QD_API}/gazettes"
DF_TERRITORY = "5300108"   # Brasília/DF — DODF

# ---------------------------------------------------------------------------
# 24 deputados distritais eleitos (CLDF 9ª Leg, 2022)
# Nomes de urna conforme TSE CDN (para matching no DODF)
# ---------------------------------------------------------------------------
DEPUTADOS_DISTRITAIS: list[dict] = [
    {"nome_urna": "FÁBIO FELIX",               "sq_candidato": 70001601758},
    {"nome_urna": "CHICO VIGILANTE",            "sq_candidato": 70001596100},
    {"nome_urna": "MAX MACIEL",                 "sq_candidato": 70001601757},
    {"nome_urna": "DANIEL DONIZET",             "sq_candidato": 70001615885},
    {"nome_urna": "MARTINS MACHADO",            "sq_candidato": 70001616707},
    {"nome_urna": "ROBÉRIO NEGREIROS",          "sq_candidato": 70001654541},
    {"nome_urna": "JORGE VIANNA",               "sq_candidato": 70001654552},
    {"nome_urna": "JAQUELINE SILVA",            "sq_candidato": 70001620312},
    {"nome_urna": "THIAGO MANZONI",             "sq_candidato": 70001615869},
    {"nome_urna": "EDUARDO PEDROSA",            "sq_candidato": 70001609144},
    {"nome_urna": "JOAQUIM RORIZ NETO",         "sq_candidato": 70001615870},
    {"nome_urna": "IOLANDO",                    "sq_candidato": 70001650810},
    {"nome_urna": "PASTOR DANIEL DE CASTRO",    "sq_candidato": 70001650210},
    {"nome_urna": "HERMETO",                    "sq_candidato": 70001650807},
    {"nome_urna": "ROOSEVELT VILELA",           "sq_candidato": 70001615877},
    {"nome_urna": "DOUTORA JANE",               "sq_candidato": 70001620311},
    {"nome_urna": "ROGÉRIO MORRO DA CRUZ",      "sq_candidato": 70001600818},
    {"nome_urna": "GABRIEL MAGNO",              "sq_candidato": 70001596090},
    {"nome_urna": "JOÃO CARDOSO PROFESSOR AUDITOR", "sq_candidato": 70001611506},
    {"nome_urna": "PAULA BELMONTE",             "sq_candidato": 70001728079},
    {"nome_urna": "RICARDO VALE",               "sq_candidato": 70001596094},
    {"nome_urna": "WELLINGTON LUIZ",            "sq_candidato": 70001650805},
    {"nome_urna": "PEPA",                       "sq_candidato": 70001650204},
    {"nome_urna": "DAYSE AMARILIO",             "sq_candidato": 70001636075},
]

# Simplified search names (remove common words that generate too much noise)
# Each tuple: (search_term, display_name)
DEPUTADO_SEARCH_TERMS: list[tuple[str, str, int]] = [
    # (query_term, nome_urna, sq_candidato)
    ("Fábio Felix",               "FÁBIO FELIX",               70001601758),
    ("Chico Vigilante",           "CHICO VIGILANTE",           70001596100),
    ("Max Maciel",                "MAX MACIEL",                70001601757),
    ("Daniel Donizet",            "DANIEL DONIZET",            70001615885),
    ("Martins Machado deputado",  "MARTINS MACHADO",           70001616707),
    ("Robério Negreiros",         "ROBÉRIO NEGREIROS",         70001654541),
    ("Jorge Vianna CLDF",         "JORGE VIANNA",              70001654552),
    ("Jaqueline Silva CLDF",      "JAQUELINE SILVA",           70001620312),
    ("Thiago Manzoni",            "THIAGO MANZONI",            70001615869),
    ("Eduardo Pedrosa CLDF",      "EDUARDO PEDROSA",           70001609144),
    ("Joaquim Roriz Neto",        "JOAQUIM RORIZ NETO",        70001615870),
    ("Iolando deputado",          "IOLANDO",                   70001650810),
    ("Pastor Daniel de Castro",   "PASTOR DANIEL DE CASTRO",   70001650210),
    ("Hermeto CLDF",              "HERMETO",                   70001650807),
    ("Roosevelt Vilela",          "ROOSEVELT VILELA",          70001615877),
    ("Doutora Jane CLDF",         "DOUTORA JANE",              70001620311),
    ("Rogério Morro da Cruz",     "ROGÉRIO MORRO DA CRUZ",     70001600818),
    ("Gabriel Magno deputado",    "GABRIEL MAGNO",             70001596090),
    ("João Cardoso deputado",     "JOÃO CARDOSO PROFESSOR AUDITOR", 70001611506),
    ("Paula Belmonte",            "PAULA BELMONTE",            70001728079),
    ("Ricardo Vale deputado",     "RICARDO VALE",              70001596094),
    ("Wellington Luiz deputado",  "WELLINGTON LUIZ",           70001650805),
    ("Pepa deputado distrital",   "PEPA",                      70001650204),
    ("Dayse Amarilio",            "DAYSE AMARILIO",            70001636075),
]

# ---------------------------------------------------------------------------
# CLDF act types to track (searches against DODF)
# ---------------------------------------------------------------------------
ATO_TYPES: list[str] = [
    "Decreto Legislativo",
    "Resolução CLDF",
    "Portaria CLDF",
    "Ata Plenária",
    "Câmara Legislativa",
    "Projeto de Lei Distrital",
    "Ordem do Dia CLDF",
]

# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def _make_client() -> httpx.Client:
    return httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "TransfereGov-CLDF-Scanner/1.0"},
        follow_redirects=True,
    )


def search_dodf(
    client: httpx.Client,
    query: str,
    since: str | None = None,
    until: str | None = None,
    size: int = 20,
    excerpt_size: int = 600,
    number_of_excerpts: int = 2,
) -> list[dict]:
    """Search DODF via Querido Diário API. Returns raw gazette dicts."""
    params: dict = {
        "querystring": query,
        "territory_ids": DF_TERRITORY,
        "size": size,
        "excerpt_size": excerpt_size,
        "number_of_excerpts": number_of_excerpts,
        "sort_by": "descending_date",
    }
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    try:
        resp = client.get(QD_GAZETTES, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("gazettes", [])
    except httpx.HTTPStatusError as e:
        log.warning("QD API HTTP error for '%s': %s", query, e)
        return []
    except Exception as e:
        log.warning("QD API error for '%s': %s", query, e)
        return []


def _make_hash(territory: str, date: str, edition: str, query: str) -> str:
    raw = f"{territory}|{date}|{edition}|{query}"
    return hashlib.md5(raw.encode()).hexdigest()


def _insert_gazettes(
    gazettes: list[dict],
    query_term: str,
    query_type: str,
    deputado_nome: str | None,
    sq_candidato: int | None,
) -> int:
    """Save gazette mentions to DB. Returns count of new rows inserted."""
    inserted = 0
    with get_connection() as conn:
        cur = conn.cursor()
        for g in gazettes:
            date_pub = g.get("date")
            edition = g.get("edition") or ""
            is_extra = g.get("is_extra_edition", False)
            gazette_url = g.get("url")
            txt_url = g.get("txt_url")
            scraped_at = g.get("scraped_at")

            excerpts = g.get("excerpts") or []
            excerpt = "\n---\n".join(
                e.replace("<em>", "").replace("</em>", "") for e in excerpts if e
            )[:2000]

            hash_key = _make_hash(DF_TERRITORY, date_pub or "", edition, query_term)

            try:
                cur.execute(
                    """
                    INSERT INTO cldf_dodf_mentions
                        (territory_id, date_pub, edition, is_extra, query_term, query_type,
                         deputado_nome, sq_candidato, excerpt, gazette_url, txt_url,
                         scraped_at, fetched_at, hash_key)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                    ON CONFLICT (hash_key) DO NOTHING
                    """,
                    (
                        DF_TERRITORY, date_pub, edition, is_extra, query_term, query_type,
                        deputado_nome, sq_candidato, excerpt, gazette_url, txt_url,
                        scraped_at, hash_key,
                    ),
                )
                inserted += cur.rowcount
            except Exception as e:
                log.warning("DB insert error for hash %s: %s", hash_key, e)
        conn.commit()
        cur.close()
    return inserted


def run_scan(
    since: str,
    until: str,
    mode: str = "all",
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Run the full DODF scan. Returns summary dict."""
    summary = {
        "deputados_scanned": 0,
        "atos_scanned": 0,
        "total_new_mentions": 0,
        "errors": 0,
        "by_deputado": {},
    }

    log.info(
        "=== CLDF × DODF Scanner | %s → %s | mode=%s dry_run=%s ===",
        since, until, mode, dry_run,
    )

    with _make_client() as client:

        # ------------------------------------------------------------------
        # 1. Search by deputado name
        # ------------------------------------------------------------------
        if mode in ("all", "deputados"):
            log.info("[1] Buscando cada deputado distrital no DODF...")
            for query, nome_urna, sqcand in DEPUTADO_SEARCH_TERMS:
                gazettes = search_dodf(client, query, since=since, until=until, size=30)
                new = 0
                if gazettes:
                    if dry_run:
                        new = len(gazettes)
                    else:
                        new = _insert_gazettes(
                            gazettes, query_term=query, query_type="deputado",
                            deputado_nome=nome_urna, sq_candidato=sqcand,
                        )
                summary["deputados_scanned"] += 1
                summary["total_new_mentions"] += new
                summary["by_deputado"][nome_urna] = {
                    "gazettes_found": len(gazettes),
                    "new_saved": new,
                }
                if verbose:
                    log.info("  %-35s → %d gazettes, %d new", nome_urna, len(gazettes), new)
                time.sleep(0.4)

        # ------------------------------------------------------------------
        # 2. Search by CLDF act types
        # ------------------------------------------------------------------
        if mode in ("all", "atos"):
            log.info("[2] Buscando tipos de atos CLDF no DODF...")
            for ato in ATO_TYPES:
                gazettes = search_dodf(client, ato, since=since, until=until, size=20)
                new = 0
                if gazettes:
                    if dry_run:
                        new = len(gazettes)
                    else:
                        new = _insert_gazettes(
                            gazettes, query_term=ato, query_type="ato_type",
                            deputado_nome=None, sq_candidato=None,
                        )
                summary["atos_scanned"] += 1
                summary["total_new_mentions"] += new
                if verbose:
                    log.info("  %-35s → %d gazettes, %d new", ato, len(gazettes), new)
                time.sleep(0.4)

        # ------------------------------------------------------------------
        # 3. General CLDF search
        # ------------------------------------------------------------------
        if mode in ("all", "geral"):
            log.info("[3] Buscando menções gerais à Câmara Legislativa no DODF...")
            for term in ["CLDF plenário", "deputado distrital votação"]:
                gazettes = search_dodf(client, term, since=since, until=until, size=20)
                new = 0
                if gazettes:
                    if dry_run:
                        new = len(gazettes)
                    else:
                        new = _insert_gazettes(
                            gazettes, query_term=term, query_type="cldf_general",
                            deputado_nome=None, sq_candidato=None,
                        )
                summary["total_new_mentions"] += new
                if verbose:
                    log.info("  %-35s → %d gazettes, %d new", term, len(gazettes), new)
                time.sleep(0.4)

    log.info(
        "=== Scan concluído | %d deputados | %d tipos de ato | %d novas menções ===",
        summary["deputados_scanned"],
        summary["atos_scanned"],
        summary["total_new_mentions"],
    )
    return summary


def print_report(summary: dict) -> None:
    """Print a readable scan report."""
    print("\n" + "=" * 60)
    print("CLDF × DODF Scanner — Relatório")
    print("=" * 60)
    print(f"Deputados buscados:   {summary['deputados_scanned']}")
    print(f"Tipos de ato:         {summary['atos_scanned']}")
    print(f"Novas menções salvas: {summary['total_new_mentions']}")
    print(f"Erros:                {summary['errors']}")

    if summary["by_deputado"]:
        print("\n--- Menções por Deputado ---")
        # Sort by gazettes_found desc
        ranked = sorted(
            summary["by_deputado"].items(),
            key=lambda kv: kv[1]["gazettes_found"],
            reverse=True,
        )
        for nome, stats in ranked:
            bar = "█" * min(stats["gazettes_found"], 30)
            print(f"  {nome:<35} {stats['gazettes_found']:>3} gazettes  {bar}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="CLDF × DODF Scanner")
    parser.add_argument(
        "--since",
        default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
        help="Data início (YYYY-MM-DD). Default: 1 ano atrás.",
    )
    parser.add_argument(
        "--until",
        default=datetime.today().strftime("%Y-%m-%d"),
        help="Data fim (YYYY-MM-DD). Default: hoje.",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "deputados", "atos", "geral"],
        default="all",
        help="Modo de busca. Default: all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não salvar no banco — só mostrar o que seria coletado.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    summary = run_scan(
        since=args.since,
        until=args.until,
        mode=args.mode,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    print_report(summary)


if __name__ == "__main__":
    main()
