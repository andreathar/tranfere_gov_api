"""
Perfil de parlamentares via API da Câmara dos Deputados.

Uso: python3 -m src.enrichers.camara [--dry-run] [--limit N]

Busca dados dos deputados que são autores de emendas no programa.
"""

import argparse
import time

import psycopg2
import requests

from config.settings import (
    CAMARA_API_BASE,
    ENRICH_RATE_LIMIT,
    PG_DB,
    PG_HOST,
    PG_PASS,
    PG_PORT,
    PG_USER,
)


def get_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )


def buscar_deputado(nome: str) -> dict | None:
    """Busca deputado por nome na API da Câmara (1 request apenas)."""
    url = f"{CAMARA_API_BASE}/deputados"
    params = {"nome": nome, "itens": 5, "ordem": "ASC", "ordenarPor": "nome"}
    try:
        resp = requests.get(url, params=params, timeout=15)  # type: ignore[arg-type]
        if resp.status_code == 200:
            data: dict = resp.json()
            deputados: list = data.get("dados", [])
            if deputados:
                result: dict = deputados[0]
                return result
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Enriquecer perfil de parlamentares via Câmara")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N parlamentares (0=todos)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Buscar parlamentares únicos não cadastrados
    cur.execute("""
        SELECT DISTINCT parlamentar_nome
        FROM planos_acao
        WHERE parlamentar_nome IS NOT NULL AND parlamentar_nome != ''
        ORDER BY parlamentar_nome
    """)
    nomes = [row[0].strip() for row in cur.fetchall()]

    if args.limit > 0:
        nomes = nomes[:args.limit]

    print(f"Parlamentares para buscar: {len(nomes)}")

    encontrados = 0
    nao_encontrados = 0

    for i, nome in enumerate(nomes, 1):
        # Pular se já existe
        cur.execute("SELECT id FROM parlamentares_dados WHERE nome = %s", (nome,))
        if cur.fetchone():
            continue

        dep = buscar_deputado(nome)

        if dep:
            encontrados += 1
            status = dep.get("ultimoStatus", {})
            if args.dry_run:
                partido = status.get("siglaPartido", "?")
                uf = status.get("siglaUf", "?")
                print(f"  [{i}/{len(nomes)}] {nome} ({partido}/{uf})")
            else:
                cur.execute("""
                    INSERT INTO parlamentares_dados
                        (deputado_id, nome, nome_urna, sigla_partido, uf, situacao,
                         gabinete_numero, gabinete_predio, gabinete_telefone, gabinete_email,
                         url_foto, ultimo_status, data_nascimento, municipio_nascimento,
                         uf_nascimento, escolaridade)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (deputado_id) DO UPDATE SET
                        nome = EXCLUDED.nome,
                        sigla_partido = EXCLUDED.sigla_partido,
                        uf = EXCLUDED.uf
                """, (
                    dep.get("id"),
                    dep.get("nome", nome),
                    status.get("nomeEleitoral", nome),
                    status.get("siglaPartido"),
                    status.get("siglaUf"),
                    status.get("situacao"),
                    status.get("gabinete", {}).get("nome"),
                    status.get("gabinete", {}).get("predio"),
                    status.get("gabinete", {}).get("telefone"),
                    status.get("gabinete", {}).get("email"),
                    status.get("urlFoto"),
                    status.get("situacao"),
                    dep.get("dataNascimento"),
                    dep.get("municipioNascimento"),
                    dep.get("ufNascimento"),
                    dep.get("escolaridade"),
                ))
        else:
            nao_encontrados += 1
            if args.dry_run:
                print(f"  [{i}/{len(nomes)}] {nome} — não encontrado")

        if i % 25 == 0:
            conn.commit()
            print(f"  [{i}/{len(nomes)}] Encontrados={encontrados} Não encontrados={nao_encontrados}")

        time.sleep(ENRICH_RATE_LIMIT)

    conn.commit()
    conn.close()

    print(f"\nResultado: {encontrados} encontrados, {nao_encontrados} não encontrados")


if __name__ == "__main__":
    main()
