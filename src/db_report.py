#!/usr/bin/env python3
"""
Relatórios TransfereGov — queries SQL direto no banco.

Uso:
    python3 src/db_report.py resumo          # resumo geral
    python3 src/db_report.py estado         # por estado
    python3 src/db_report.py objeto         # por objeto
    python3 src/db_report.py negados        # planos negados
    python3 src/db_report.py municipio SE   # planos de um estado
    python3 src/db_report.py emenda         # por parlamentar/emenda
    python3 src/db_report.py top 10         # top N valores
    python3 src.db_report.py sql "SELECT…"  # query customizada
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from config.settings import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS

DB_CONFIG = {
    "host": PG_HOST,
    "port": PG_PORT,
    "dbname": PG_DB,
    "user": PG_USER,
    "password": PG_PASS,
}

QUERIES = {
    "resumo": """
        SELECT
            (SELECT COUNT(*) FROM planos_acao) AS total_planos,
            (SELECT COUNT(*) FROM beneficiarios) AS total_municipios,
            (SELECT COUNT(*) FROM objetos) AS total_objetos,
            (SELECT SUM(valor_total) FROM planos_acao) AS valor_total,
            (SELECT SUM(CASE WHEN plano_acao_situacao = 'CIENTE' THEN 1 ELSE 0 END) FROM planos_acao) AS cientes,
            (SELECT SUM(CASE WHEN plano_acao_situacao = 'APROVADO' THEN 1 ELSE 0 END) FROM planos_acao) AS aprovados,
            (SELECT SUM(CASE WHEN plano_acao_situacao = 'EM_EXECUCAO' THEN 1 ELSE 0 END) FROM planos_acao) AS em_execucao,
            (SELECT SUM(CASE WHEN plano_acao_situacao = 'CONCLUIDO' THEN 1 ELSE 0 END) FROM planos_acao) AS concluidos,
            (SELECT SUM(CASE WHEN plano_acao_situacao IN ('REPROVADO','IMPEDIDO','CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) FROM planos_acao) AS negados;
    """,

    "estado": "SELECT * FROM v_resumo_por_estado",

    "objeto": "SELECT * FROM v_resumo_por_objeto",

    "negados": """
        SELECT
            plano_acao_codigo,
            beneficiario_nome,
            beneficiario_uf,
            plano_acao_situacao,
            motivo_impedimento,
            valor_total
        FROM v_negados
    """,

    "emenda": """
        SELECT
            codigo_emenda_formatado,
            COUNT(*) AS planos,
            SUM(valor_total) AS valor_total,
            STRING_AGG(DISTINCT beneficiario_uf, ', ') AS ufs
        FROM v_planos_completo
        WHERE codigo_emenda_formatado IS NOT NULL AND codigo_emenda_formatado != ''
        GROUP BY codigo_emenda_formatado
        ORDER BY valor_total DESC
    """,
}


def format_brl(value):
    """Formata valor como R$ brasileiro."""
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def print_table(cur):
    """Imprime resultados como tabela formatada."""
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    if not rows:
        print("Nenhum resultado encontrado.")
        return

    # Larguras
    widths = [len(c) for c in cols]
    str_rows = []
    for row in rows:
        sr = []
        for i, val in enumerate(row):
            if isinstance(val, float):
                s = format_brl(val) if "valor" in cols[i].lower() else f"{val:,.2f}"
            elif val is None:
                s = "—"
            else:
                s = str(val)
            sr.append(s)
            widths[i] = max(widths[i], len(s))
        str_rows.append(sr)

    # Header
    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    sep = "-+-".join("-" * w for w in widths)

    print(header)
    print(sep)
    for sr in str_rows:
        print(" | ".join(sr[i].ljust(widths[i]) for i in range(len(cols))))

    print(f"\n({len(rows)} registros)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1].lower()
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    if cmd == "sql":
        # Query customizada
        if len(sys.argv) < 3:
            print("Uso: db_report.py sql \"SELECT ...\"")
            return 1
        sql = " ".join(sys.argv[2:])
        cur.execute(sql)
        print_table(cur)

    elif cmd == "municipio":
        # Filtrar por UF
        uf = sys.argv[2].upper() if len(sys.argv) > 2 else ""
        if not uf:
            print("Uso: db_report.py municipio UF")
            return 1
        cur.execute("""
            SELECT
                plano_acao_codigo,
                beneficiario_nome,
                plano_acao_situacao,
                valor_total,
                codigo_emenda_formatado
            FROM v_planos_completo
            WHERE beneficiario_uf = %s
            ORDER BY valor_total DESC
        """, (uf,))
        print(f"Planos no estado {uf}:")
        print_table(cur)

    elif cmd == "top":
        # Top N valores
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        cur.execute("""
            SELECT
                plano_acao_codigo,
                beneficiario_nome,
                beneficiario_uf,
                plano_acao_situacao,
                valor_total
            FROM v_planos_completo
            ORDER BY valor_total DESC
            LIMIT %s
        """, (n,))
        print(f"Top {n} planos por valor:")
        print_table(cur)

    elif cmd in QUERIES:
        cur.execute(QUERIES[cmd])
        print_table(cur)

    else:
        print(f"Comando desconhecido: {cmd}")
        print("Comandos: resumo, estado, objeto, negados, emenda, municipio, top, sql")
        return 1

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
