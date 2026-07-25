#!/bin/bash
# Quick DB structure check
source .venv/bin/activate

python3 << 'PYEOF'
import psycopg2

conn = psycopg2.connect(
    host="127.0.0.1", dbname="transferegov_db",
    user="cognee", password="cognee"
)
cur = conn.cursor()

tables = [
    "v_ranking_parlamentares_enriquecido",
    "parlamentar_beneficiario",
    "parlamentares_dados",
    "parlamentares",
    "v_resumo_por_parlamentar",
]

for t in tables:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position", (t,)
    )
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n=== {t} ({len(cols)} cols) ===")
    for c in cols:
        print(f"  {c}")

# Deputado followup: CORONEL ULYSSES
print("\n\n=== FOLLOWUP EXAMPLE: CORONEL ULYSSES ===")
cur.execute("""
    SELECT 
        plano_acao_codigo, plano_acao_situacao, 
        valor_total, emenda_codigo, beneficiario_nome, uf
    FROM planos_acao
    WHERE parlamentar_nome = 'CORONEL ULYSSES'
    ORDER BY valor_total DESC
""")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
print("-" * 120)
for row in cur.fetchall():
    print(" | ".join(str(v)[:25] for v in row))

# Enriched data check
print("\n=== PARLAMENTAR ENRICHED DATA ===")
cur.execute("""
    SELECT pd.nome, pd.sigla_partido, pd.uf, pd.escolaridade, pd.gabinete_email
    FROM parlamentares_dados pd
    LIMIT 5
""")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for row in cur.fetchall():
    print(" | ".join(str(v)[:30] for v in row))

# Stats
print("\n=== STATS ===")
cur.execute("SELECT COUNT(*) FROM parlamentares_dados")
print(f"Parlamentares com dados Câmara: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM parlamentar_beneficiario")
print(f"Vinculações parlamentar-beneficiário: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM validacao_cnpj")
print(f"CNPJs validados: {cur.fetchone()[0]}")

conn.close()
PYEOF
