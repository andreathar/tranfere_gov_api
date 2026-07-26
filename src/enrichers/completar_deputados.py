"""
Busca detalhes dos deputados que faltam partido via API da Câmara.

Uso: python3 src/enrichers/completar_deputados.py

Busca detalhes apenas para deputados sem sigla_partido preenchida.
"""

import time

import requests

from config.settings import (
    CAMARA_API_BASE,
    ENRICH_RATE_LIMIT,
)
from src.db_utils import get_connection


def main():
    conn = get_connection()
    cur = conn.cursor()

    # Buscar deputados sem partido
    cur.execute("""
        SELECT id, deputado_id, nome
        FROM parlamentares_dados
        WHERE (sigla_partido IS NULL OR sigla_partido = '')
          AND deputado_id IS NOT NULL
        ORDER BY nome
    """)
    deputados = cur.fetchall()
    print(f"Deputados sem partido: {len(deputados)}")

    atualizados = 0

    for i, (row_id, dep_id, nome) in enumerate(deputados, 1):
        try:
            resp = requests.get(f"{CAMARA_API_BASE}/deputados/{dep_id}", timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("dados", {})
                status = data.get("ultimoStatus", {})
                sigla = status.get("siglaPartido", "")
                uf = status.get("siglaUf", "")
                situacao = status.get("situacao", "")
                gabinete = status.get("gabinete", {})
                foto = status.get("urlFoto", "")

                if sigla:
                    cur.execute(
                        """
                        UPDATE parlamentares_dados SET
                            sigla_partido = %s, uf = %s, situacao = %s,
                            gabinete_telefone = %s, gabinete_email = %s, url_foto = %s
                        WHERE id = %s
                    """,
                        (
                            sigla,
                            uf,
                            situacao,
                            gabinete.get("telefone"),
                            gabinete.get("email"),
                            foto,
                            row_id,
                        ),
                    )
                    atualizados += 1

        except Exception as e:
            print(f"  Erro {nome}: {e}")

        if i % 25 == 0:
            conn.commit()
            print(f"  [{i}/{len(deputados)}] Atualizados={atualizados}")

        time.sleep(ENRICH_RATE_LIMIT)

    conn.commit()
    conn.close()
    print(f"\nResultado: {atualizados}/{len(deputados)} atualizados com partido")


if __name__ == "__main__":
    main()
