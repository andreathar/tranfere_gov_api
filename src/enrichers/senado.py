"""
senado — Enriquecedor de Senadores (Dados da API do Senado Federal)

Sincroniza perfil completo dos 81 senadores em exercício com o banco PostgreSQL.
Coleta: nome, partido, UF, email, mandato, votações e relatorias.

Uso:
  python3 -m src.enrichers.senado [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import time

import requests

from config.settings import ENRICH_RATE_LIMIT, SENADO_API_BASE
from src.db_utils import get_connection

SENADO_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "TransfereGov-Enricher/1.0",
}


def _get(endpoint: str) -> dict | None:
    """GET genérico na API do Senado com retry e rate limit."""
    url = f"{SENADO_API_BASE}{endpoint}"
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=SENADO_HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  ⏳ Rate limit — aguardando {wait}s...")
                time.sleep(wait)
                continue
            print(f"  ⚠️  HTTP {resp.status_code} para {url}")
        except requests.RequestException as exc:
            print(f"  ⚠️  Erro de conexão: {exc}")
        time.sleep(ENRICH_RATE_LIMIT)
    return None


def _listar_senadores() -> list[dict]:
    """Lista todos os senadores em exercício."""
    data = _get("/senador/lista/atual.json")
    if not data:
        return []
    try:
        return data["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
    except (KeyError, TypeError):
        return []


def _detalhe_senador(codigo: int) -> dict | None:
    """Busca detalhe completo de um senador."""
    data = _get(f"/senador/{codigo}.json")
    if not data:
        return None
    try:
        return data["DetalheParlamentar"]["Parlamentar"]
    except (KeyError, TypeError):
        return None


def _contar_votacoes(codigo: int) -> int:
    """Conta votações de um senador."""
    data = _get(f"/senador/{codigo}/votacoes.json")
    if not data:
        return 0
    try:
        votacoes = data["VotacoesParlamentar"]["Parlamentar"]["Votacoes"]["Votacao"]
        return len(votacoes) if isinstance(votacoes, list) else 1
    except (KeyError, TypeError):
        return 0


def _contar_relatorias(codigo: int) -> int:
    """Conta relatorias de um senador.

    Tenta /materias/relatorias.json e /materias.json como fallback.
    A API do Senado pode mudar endpoints entre versões.
    """
    for path in (
        f"/senador/{codigo}/materias/relatorias.json",
        f"/senador/{codigo}/materias.json",
    ):
        data = _get(path)
        if not data:
            continue
        try:
            materias = data["ParlamentarMaterias"]["Materias"]["Materia"]
            return len(materias) if isinstance(materias, list) else 1
        except (KeyError, TypeError):
            pass
    return 0


def sync_senadores(dry_run: bool = False, limit: int = 0) -> None:
    """Sincroniza senadores com o banco PostgreSQL."""
    conn = get_connection()
    cur = conn.cursor()

    # 1. Listar senadores em exercício
    print("🔎 Listando senadores em exercício...")
    senadores = _listar_senadores()
    if not senadores:
        print("❌ Não foi possível listar senadores.")
        return
    print(f"📊 Senadores encontrados: {len(senadores)}")

    if limit > 0:
        senadores = senadores[:limit]
        print(f"  (limitado a {limit})")

    records: list[tuple] = []
    erros = 0

    for i, s in enumerate(senadores, 1):
        # A API aninha em IdentificacaoParlamentar
        ident = s.get("IdentificacaoParlamentar", {})
        mand = s.get("Mandato", {})

        codigo_raw = ident.get("CodigoParlamentar", "")
        try:
            codigo = int(codigo_raw)
        except (ValueError, TypeError):
            continue
        if not codigo:
            continue

        # Dados básicos da listagem (fonte primária — já traz tudo)
        nome_completo = ident.get("NomeCompletoParlamentar", "") or ident.get(
            "NomeParlamentar", ""
        )
        nome_parlamentar = ident.get("NomeParlamentar", "") or nome_completo
        partido = ident.get("SiglaPartidoParlamentar", "")
        uf = ident.get("UfParlamentar", "")
        foto_url = ident.get("UrlFotoParlamentar", "")
        email = ident.get("EmailParlamentar", "")

        # Mandato a partir da listagem
        leg1 = mand.get("PrimeiraLegislaturaDoMandato", {})
        leg2 = mand.get("SegundaLegislaturaDoMandato", {})
        mandato_inicio = leg1.get("DataInicio") if leg1 else None
        mandato_fim = leg2.get("DataFim") if leg2 else None
        legislatura = None
        if leg2:
            legislatura = leg2.get("NumeroLegislatura")
        elif leg1:
            legislatura = leg1.get("NumeroLegislatura")

        print(f"  [{i}/{len(senadores)}] {nome_completo} ({partido}/{uf}) ✅")

        records.append(
            (
                codigo,  # senador_codigo (PK)
                nome_completo,  # nome_completo
                nome_parlamentar,  # nome_parlamentar
                partido,  # sigla_partido
                uf,  # uf
                email,  # email
                foto_url,  # foto_url
                mandato_inicio,  # mandato_inicio
                mandato_fim,  # mandato_fim
                legislatura,  # legislatura
                0,  # total_votacoes (enriquecer depois se necessário)
                0,  # total_relatorias (enriquecer depois se necessário)
            )
        )

    print(f"\n✅ Senadores coletados: {len(records)} | Erros: {erros}")

    # 4. UPSERT no PostgreSQL
    if not dry_run and records:
        insert_sql = """
            INSERT INTO senadores_dados (
                senador_codigo, nome_completo, nome_parlamentar, sigla_partido, uf,
                email, foto_url, mandato_inicio, mandato_fim, legislatura,
                total_votacoes, total_relatorias, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (senador_codigo) DO UPDATE SET
                nome_completo = EXCLUDED.nome_completo,
                nome_parlamentar = EXCLUDED.nome_parlamentar,
                sigla_partido = EXCLUDED.sigla_partido,
                uf = EXCLUDED.uf,
                email = EXCLUDED.email,
                foto_url = EXCLUDED.foto_url,
                mandato_inicio = EXCLUDED.mandato_inicio,
                mandato_fim = EXCLUDED.mandato_fim,
                legislatura = EXCLUDED.legislatura,
                total_votacoes = EXCLUDED.total_votacoes,
                total_relatorias = EXCLUDED.total_relatorias,
                updated_at = NOW()
        """
        cur.executemany(insert_sql, records)
        conn.commit()
        print(f"💾 {len(records)} senadores sincronizados na tabela 'senadores_dados'!")
    elif dry_run and records:
        print(f"🔍 DRY-RUN: {len(records)} senadores seriam inseridos:")
        for r in records[:10]:
            print(f"  {r[1]} ({r[3]}/{r[4]}) — votos={r[10]} rel={r[11]}")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar senadores via API do Senado Federal")
    parser.add_argument("--dry-run", action="store_true", help="Não salvar alterações no banco")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N senadores (0=todos)")
    args = parser.parse_args()
    sync_senadores(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
