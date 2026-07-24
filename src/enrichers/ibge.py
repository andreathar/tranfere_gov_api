"""
Enriquecimento de municípios via API do IBGE.

Uso: python3 -m src.enrichers.ibge [--dry-run] [--uf UF]

Busca dados demográficos/econômicos dos municípios beneficiários.
"""

import argparse

import psycopg2
import requests

from config.settings import IBGE_API_BASE, PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER


def get_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )


def buscar_municipios_ibge(uf: str) -> list:
    """Busca todos os municípios de uma UF via IBGE (localidades)."""
    url = f"{IBGE_API_BASE}/localidades/estados/{uf}/municipios"
    resp = requests.get(url, timeout=15)
    if resp.status_code == 200:
        return resp.json()  # type: ignore[no-any-return]
    return []


def main():
    parser = argparse.ArgumentParser(description="Enriquecer municípios via IBGE")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uf", type=str, default="", help="UF específica (vazio=todas)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Buscar UFs dos beneficiários
    if args.uf:
        ufs = [args.uf.upper()]
    else:
        cur.execute("SELECT DISTINCT uf FROM beneficiarios WHERE uf IS NOT NULL ORDER BY uf")
        ufs = [row[0] for row in cur.fetchall()]

    print(f"UFs para processar: {len(ufs)}")

    total_inseridos = 0

    for uf in ufs:
        print(f"\n--- {uf} ---")
        municipios = buscar_municipios_ibge(uf)
        print(f"  Municípios IBGE: {len(municipios)}")

        for mun in municipios:
            mun_id = mun.get("id")
            nome = mun.get("nome", "")
            micro = mun.get("microrregiao") or {}
            meso = micro.get("mesorregiao") or {}
            uf_data = meso.get("UF") or {}
            regiao_data = uf_data.get("regiao") or {}
            regiao = regiao_data.get("nome", "")
            mesorregiao = meso.get("nome", "")
            microrregiao = micro.get("nome", "")

            if args.dry_run:
                print(f"    {mun_id} - {nome}")
            else:
                cur.execute("""
                    INSERT INTO municipios_ibge
                        (municipio_id, nome, uf, regiao, mesorregiao, microrregiao)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (municipio_id) DO UPDATE SET
                        nome = EXCLUDED.nome,
                        regiao = EXCLUDED.regiao,
                        mesorregiao = EXCLUDED.mesorregiao,
                        microrregiao = EXCLUDED.microrregiao
                """, (mun_id, nome, uf, regiao, mesorregiao, microrregiao))
                total_inseridos += 1

        conn.commit()
        print(f"  {uf}: {len(municipios)} municípios processados")

    conn.close()
    print(f"\nTotal: {total_inseridos} municípios enriquecidos")


if __name__ == "__main__":
    main()
