"""
Perfil de parlamentares via API da Câmara dos Deputados.

Uso: python3 -m src.enrichers.camara [--dry-run] [--limit N]

Busca dados dos deputados que são autores de emendas no programa.
"""

import argparse
import time
from typing import Any

import requests

from config.settings import (
    CAMARA_API_BASE,
    ENRICH_RATE_LIMIT,
)
from src.db_utils import get_connection
from src.formatters import strip_accents


def buscar_deputado(nome: str, parlamentar_id: int | None = None) -> dict[str, object] | None:
    """Busca deputado por nome na API da Câmara (1 request apenas)."""
    # Normalizar nome (remover acentos) para maximizar match na API
    nome_busca = strip_accents(nome)
    url = f"{CAMARA_API_BASE}/deputados"
    params: dict[str, int | str] = {
        "nome": nome_busca,
        "itens": 5,
        "ordem": "ASC",
        "ordenarPor": "nome",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data: dict[str, Any] = resp.json()
            deputados: list[dict[str, Any]] = data.get("dados", [])
            if deputados:
                dep_id = deputados[0].get("id")
                # Busca detalhada
                detalhe_resp = requests.get(f"{url}/{dep_id}", timeout=15)
                if detalhe_resp.status_code == 200:
                    detail_json = detalhe_resp.json()
                    detail_data: dict[str, object] = detail_json.get("dados", {})
                    return detail_data
                return deputados[0]
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

    # Buscar parlamentares únicos não cadastrados, com parlamentar_id
    cur.execute("""
        SELECT DISTINCT pa.parlamentar_nome,
               pa.parlamentar_id
        FROM planos_acao pa
        LEFT JOIN parlamentares p ON pa.parlamentar_id = p.parlamentar_id
        WHERE pa.parlamentar_id IS NOT NULL
        ORDER BY pa.parlamentar_nome
    """)
    nomes_info = [(row[0].strip(), row[1]) for row in cur.fetchall()]

    if args.limit > 0:
        nomes_info = nomes_info[: args.limit]

    print(f"Parlamentares para buscar: {len(nomes_info)}")

    encontrados = 0
    nao_encontrados = 0

    for i, (nome, parlamentar_id) in enumerate(nomes_info, 1):
        # Pular se já existe e está preenchido (accent-insensitive)
        cur.execute(
            "SELECT id FROM parlamentares_dados"
            " WHERE f_unaccent(UPPER(nome)) = f_unaccent(UPPER(%s)) AND ultimo_status IS NOT NULL",
            (strip_accents(nome),),
        )
        if cur.fetchone():
            continue

        dep = buscar_deputado(nome, parlamentar_id=parlamentar_id)

        if dep:
            encontrados += 1
            status = dep.get("ultimoStatus", {})
            if args.dry_run:
                partido = status.get("siglaPartido", "?")
                uf = status.get("siglaUf", "?")
                print(f"  [{i}/{len(nomes_info)}] {nome} ({partido}/{uf})")
            else:
                cur.execute(
                    """
                    INSERT INTO parlamentares_dados
                        (deputado_id, nome, nome_urna, sigla_partido, uf, situacao,
                         gabinete_numero, gabinete_predio, gabinete_telefone, gabinete_email,
                         url_foto, ultimo_status, data_nascimento, municipio_nascimento,
                         uf_nascimento, escolaridade)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (deputado_id) DO UPDATE SET
                        nome = EXCLUDED.nome,
                        sigla_partido = EXCLUDED.sigla_partido,
                        uf = EXCLUDED.uf,
                        gabinete_numero = EXCLUDED.gabinete_numero,
                        gabinete_predio = EXCLUDED.gabinete_predio,
                        gabinete_telefone = EXCLUDED.gabinete_telefone,
                        gabinete_email = EXCLUDED.gabinete_email,
                        ultimo_status = EXCLUDED.ultimo_status,
                        data_nascimento = EXCLUDED.data_nascimento,
                        municipio_nascimento = EXCLUDED.municipio_nascimento,
                        uf_nascimento = EXCLUDED.uf_nascimento,
                        escolaridade = EXCLUDED.escolaridade
                """,
                    (
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
                    ),
                )
        else:
            nao_encontrados += 1
            if args.dry_run:
                print(f"  [{i}/{len(nomes_info)}] {nome} — não encontrado")

        if i % 25 == 0:
            conn.commit()
            print(
                f"  [{i}/{len(nomes_info)}] Encontrados={encontrados} Não encontrados={nao_encontrados}"
            )

        time.sleep(ENRICH_RATE_LIMIT)

    conn.commit()
    conn.close()

    print(f"\nResultado: {encontrados} encontrados, {nao_encontrados} não encontrados")


if __name__ == "__main__":
    main()
