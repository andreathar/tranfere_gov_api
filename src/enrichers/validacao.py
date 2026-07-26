"""
Validação de CNPJs via BrasilAPI.

Uso: python3 -m src.enrichers.validacao [--dry-run] [--limit N]

Valida CNPJs dos beneficiários no banco e salva resultados em validacao_cnpj.
"""

import argparse
import time

import requests

from config.settings import (
    BRASILAPI_BASE,
    ENRICH_RATE_LIMIT,
)
from src.db_utils import get_connection


def validar_cnpj(cnpj: str) -> dict:
    """Consulta BrasilAPI para validar CNPJ."""
    cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
    url = f"{BRASILAPI_BASE}/cnpj/v1/{cnpj_clean}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "razao_social": data.get("razao_social", ""),
                "nome_fantasia": data.get("nome_fantasia", ""),
                "situacao_cadastral": data.get("situacao_cadastral", ""),
                "data_situacao": data.get("data_situacao_cadastral", ""),
                "porte": data.get("porte", ""),
                "natureza_juridica": data.get("natureza_juridica", ""),
                "cep": data.get("cep", ""),
                "telefone": data.get("telefone", ""),
                "email": data.get("email", ""),
                "valido": True,
                "erro": None,
            }
        elif resp.status_code == 404:
            return {"valido": False, "erro": "CNPJ não encontrado"}
        else:
            return {"valido": False, "erro": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"valido": False, "erro": str(e)[:200]}


def main():
    parser = argparse.ArgumentParser(description="Validar CNPJs via BrasilAPI")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostrar, sem salvar")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N CNPJs (0=todos)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Buscar CNPJs únicos não validados
    cur.execute("""
        SELECT DISTINCT b.cnpj
        FROM beneficiarios b
        LEFT JOIN validacao_cnpj vc ON b.cnpj = vc.cnpj
        WHERE b.cnpj IS NOT NULL AND b.cnpj != ''
          AND vc.cnpj IS NULL
        ORDER BY b.cnpj
    """)
    cnpjs = [row[0] for row in cur.fetchall()]

    if args.limit > 0:
        cnpjs = cnpjs[: args.limit]

    print(f"CNPJs para validar: {len(cnpjs)}")
    if not cnpjs:
        print("Nenhum CNPJ pendente.")
        return

    validos = 0
    invalidos = 0
    erros = 0

    for i, cnpj in enumerate(cnpjs, 1):
        result = validar_cnpj(cnpj)

        if args.dry_run:
            status = "V" if result["valido"] else "X"
            print(
                f"  [{i}/{len(cnpjs)}] {cnpj} {status} {result.get('razao_social', result.get('erro', ''))[:50]}"
            )
        else:
            cur.execute(
                """
                INSERT INTO validacao_cnpj
                    (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                     data_situacao, porte, natureza_juridica, cep, telefone, email,
                     valido, erro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cnpj) DO UPDATE SET
                    razao_social = EXCLUDED.razao_social,
                    nome_fantasia = EXCLUDED.nome_fantasia,
                    situacao_cadastral = EXCLUDED.situacao_cadastral,
                    valido = EXCLUDED.valido,
                    erro = EXCLUDED.erro,
                    checked_at = NOW()
            """,
                (
                    cnpj,
                    result.get("razao_social"),
                    result.get("nome_fantasia"),
                    result.get("situacao_cadastral"),
                    result.get("data_situacao"),
                    result.get("porte"),
                    result.get("natureza_juridica"),
                    result.get("cep"),
                    result.get("telefone"),
                    result.get("email"),
                    result["valido"],
                    result.get("erro"),
                ),
            )

        if result["valido"]:
            validos += 1
        elif result.get("erro") == "CNPJ não encontrado":
            invalidos += 1
        else:
            erros += 1

        if i % 10 == 0:
            conn.commit()
            print(f"  [{i}/{len(cnpjs)}] V={validos} X={invalidos} E={erros}")

        time.sleep(ENRICH_RATE_LIMIT)

    conn.commit()
    conn.close()

    print(f"\nResultado: {validos} válidos, {invalidos} inválidos, {erros} erros")


if __name__ == "__main__":
    main()
