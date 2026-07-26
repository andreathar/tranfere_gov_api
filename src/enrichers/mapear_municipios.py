"""
Gera tabela de mapeamento beneficiários → municípios IBGE.

Resolve o problema de nomes diferentes entre beneficiários e IBGE:
  - Acentos vs sem acentos
  - Prefixos ("MUNICIPIO DE", "ESTADO DE")
  - Abreviações

Uso: python3 -m src.enrichers.mapear_municipios [--dry-run]
"""

import argparse
import unicodedata

from src.db_utils import get_connection


def normalize(text: str) -> str:
    """Remove acentos, lowercase, remove prefixos comuns."""
    if not text:
        return ""
    # Remove acentos
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.upper().strip()
    # Remove prefixos
    for prefix in ["MUNICIPIO DE ", "MUNICÍPIO DE ", "ESTADO DE ", "ESTADO DA ", "ESTADO DO "]:
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description="Mapear beneficiários → IBGE")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Buscar todos os beneficiários
    cur.execute("SELECT beneficiario_id, nome, uf FROM beneficiarios WHERE uf IS NOT NULL")
    benef = cur.fetchall()
    print(f"Beneficiários: {len(benef)}")

    # Buscar todos os municípios IBGE
    cur.execute("SELECT municipio_id, nome, uf FROM municipios_ibge")
    ibge = cur.fetchall()
    print(f"Municípios IBGE: {len(ibge)}")

    # Index IBGE por (normalize(nome), uf)
    ibge_index = {}
    for mun_id, nome, uf in ibge:
        key = (normalize(nome), uf)
        ibge_index[key] = mun_id

    # Mapear
    mapeados = 0
    nao_mapeados = 0
    inserts = []

    for ben_id, nome, uf in benef:
        key = (normalize(nome), uf)
        mun_id = ibge_index.get(key)

        if mun_id:
            mapeados += 1
            inserts.append((ben_id, mun_id))
        else:
            nao_mapeados += 1
            if args.dry_run and nao_mapeados <= 10:
                print(f"  SEM MATCH: {nome} ({uf})")

    print(f"\nMapeados: {mapeados} | Não mapeados: {nao_mapeados}")

    if not args.dry_run and inserts:
        # Criar tabela de mapeamento se não existir
        cur.execute("""
            CREATE TABLE IF NOT EXISTS beneficiario_ibge_map (
                beneficiario_id INTEGER PRIMARY KEY REFERENCES beneficiarios(beneficiario_id),
                municipio_id INTEGER REFERENCES municipios_ibge(municipio_id),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Inserir mapeamentos
        cur.executemany(
            """
            INSERT INTO beneficiario_ibge_map (beneficiario_id, municipio_id)
            VALUES (%s, %s)
            ON CONFLICT (beneficiario_id) DO UPDATE SET municipio_id = EXCLUDED.municipio_id
        """,
            inserts,
        )
        conn.commit()
        print(f"Tabela beneficiario_ibge_map populada: {len(inserts)} registros")

    conn.close()


if __name__ == "__main__":
    main()
