"""
Followup de emendas por deputado — CLI interativo.

Uso:
    python3 src/deputado_followup.py AFONSO FLORENCE
    python3 src/deputado_followup.py --buscar "ULYSSES"
    python3 src/deputado_followup.py --emenda 202642740010
    python3 src/deputado_followup.py --ranking
    python3 src/deputado_followup.py --partido PT

Mostra: perfil do deputado, trail de emendas, municípios beneficiários,
         comparação com outros deputados do mesmo partido/UF.
"""

from __future__ import annotations

import argparse
import sys

from src.db_utils import get_connection

# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------
from src.formatters import format_brl


def print_section(title: str, width: int = 72) -> None:
    """Imprime cabeçalho de seção."""
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_table(rows: list[tuple], cols: list[str], brl_cols: set[int] | None = None) -> None:
    """Imprime tabela formatada."""
    if not rows:
        print("  Nenhum resultado encontrado.")
        return

    brl_cols = brl_cols or set()
    widths = [len(c) for c in cols]
    str_rows: list[list[str]] = []

    for row in rows:
        sr: list[str] = []
        for i, val in enumerate(row):
            if i in brl_cols and isinstance(val, int | float):
                s = format_brl(val)
            elif val is None:
                s = "—"
            else:
                s = str(val)
            sr.append(s)
            widths[i] = max(widths[i], len(s))
        str_rows.append(sr)

    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    sep = "-+-".join("-" * w for w in widths)
    print(f"  {header}")
    print(f"  {sep}")
    for sr in str_rows:
        print(f"  {' | '.join(sr[i].ljust(widths[i]) for i in range(len(cols)))}")
    print(f"\n  ({len(rows)} registros)")


# ---------------------------------------------------------------------------
# Queries principais
# ---------------------------------------------------------------------------

SQL_PERFIL = """
SELECT
    pd.nome,
    pd.sigla_partido,
    pd.uf,
    pd.situacao,
    pd.escolaridade,
    pd.gabinete_telefone,
    pd.gabinete_email,
    pd.url_foto,
    pd.data_nascimento,
    pd.municipio_nascimento
FROM parlamentares_dados pd
WHERE pd.nome ILIKE %s
LIMIT 1
"""

SQL_RESUMO = """
SELECT
    pa.parlamentar_nome,
    COUNT(*) AS total_planos,
    COUNT(DISTINCT pa.emenda_codigo) AS emendas,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    SUM(pa.valor_total) AS valor_total,
    AVG(pa.valor_total) AS valor_medio,
    SUM(CASE WHEN pa.plano_acao_situacao IN
        ('REPROVADO','IMPEDIDO','IMPEDIDO_REJEICAO_PLANO_TRABALHO',
         'CANCELADO','NAO_CUMPROU') THEN 1 ELSE 0 END) AS negados,
    SUM(CASE WHEN pa.plano_acao_situacao = 'EM_EXECUCAO' THEN 1 ELSE 0 END) AS em_execucao,
    SUM(CASE WHEN pa.plano_acao_situacao = 'CONCLUIDO' THEN 1 ELSE 0 END) AS concluidos
FROM planos_acao pa
WHERE pa.parlamentar_nome ILIKE %s
GROUP BY pa.parlamentar_nome
"""

SQL_EMENDAS = """
SELECT
    pa.emenda_codigo,
    COUNT(*) AS planos,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    SUM(pa.valor_total) AS valor_total,
    STRING_AGG(DISTINCT pa.plano_acao_situacao, ', ') AS situacoes
FROM planos_acao pa
WHERE pa.parlamentar_nome ILIKE %s
  AND pa.emenda_codigo IS NOT NULL AND pa.emenda_codigo != ''
GROUP BY pa.emenda_codigo
ORDER BY valor_total DESC
"""

SQL_MUNICIPIOS = """
SELECT
    b.nome AS municipio,
    b.uf,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor_total,
    STRING_AGG(DISTINCT pa.emenda_codigo, ', ') AS emendas
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_nome ILIKE %s
GROUP BY b.nome, b.uf
ORDER BY valor_total DESC
"""

SQL_DETALHE_EMENDA = """
SELECT
    pa.plano_acao_codigo,
    pa.plano_acao_situacao,
    b.nome AS municipio,
    b.uf,
    pa.valor_total,
    pa.motivo_impedimento
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_nome ILIKE %s
  AND pa.emenda_codigo = %s
ORDER BY pa.valor_total DESC
"""

SQL_COMPARACAO_PARTIDO = """
SELECT
    ranking.parlamentar_nome,
    ranking.total_planos,
    ranking.valor_total,
    ranking.municipios,
    ranking.valor_medio
FROM v_ranking_parlamentares_enriquecido ranking
JOIN parlamentares_dados pd ON ranking.parlamentar_nome = pd.nome
WHERE pd.sigla_partido = %s
ORDER BY ranking.valor_total DESC
LIMIT 15
"""

SQL_LISTAR_DEPUTADOS = """
SELECT DISTINCT
    pa.parlamentar_nome,
    pd.sigla_partido,
    pd.uf
FROM planos_acao pa
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome
WHERE pa.parlamentar_nome ILIKE %s
ORDER BY pa.parlamentar_nome
LIMIT 20
"""

SQL_RANKING = """
SELECT
    parlamentar_nome,
    total_planos,
    valor_total,
    municipios,
    valor_medio
FROM v_ranking_parlamentares_enriquecido
ORDER BY valor_total DESC
LIMIT 20
"""


# ---------------------------------------------------------------------------
# Funções de exibição
# ---------------------------------------------------------------------------


def buscar_deputados(conn, termo: str) -> list[tuple]:
    """Busca deputados por nome (parcial, case-insensitive)."""
    cur = conn.cursor()
    cur.execute(SQL_LISTAR_DEPUTADOS, (f"%{termo}%",))
    return cur.fetchall()  # type: ignore[no-any-return]


def mostrar_perfil(conn, nome: str) -> bool:
    """Mostra perfil completo do deputado. Retorna True se encontrado."""
    cur = conn.cursor()
    cur.execute(SQL_PERFIL, (nome,))
    row = cur.fetchone()
    if not row:
        return False

    cols = [d[0] for d in cur.description]
    print_section("PERFIL DO DEPUTADO")
    for i, c in enumerate(cols):
        val = row[i]
        if c == "url_foto" and val:
            print(f"  {c:25s} = {val}")
        elif c in ("data_nascimento",) and val:
            print(f"  {c:25s} = {val.strftime('%d/%m/%Y')}")
        else:
            print(f"  {c:25s} = {val or '—'}")
    return True


def mostrar_resumo(conn, nome: str) -> None:
    """Mostra resumo geral de emendas do deputado."""
    cur = conn.cursor()
    cur.execute(SQL_RESUMO, (nome,))
    row = cur.fetchone()
    if not row:
        return

    print_section("RESUMO DE EMENDAS")
    print(f"  Parlamentar:          {row[0]}")
    print(f"  Total de planos:      {row[1]}")
    print(f"  Emendas únicas:       {row[2]}")
    print(f"  Municípios:           {row[3]}")
    print(f"  Valor total:          {format_brl(row[4])}")
    print(f"  Valor médio/plano:    {format_brl(row[5])}")
    print(f"  Negados:              {row[6]}")
    print(f"  Em execução:          {row[7]}")
    print(f"  Concluídos:           {row[8]}")


def mostrar_emendas(conn, nome: str) -> None:
    """Mostra lista de emendas do deputado."""
    cur = conn.cursor()
    cur.execute(SQL_EMENDAS, (nome,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section("EMENDAS")
    cols = ["emenda_codigo", "planos", "municipios", "valor_total", "situacoes"]
    print_table(rows, cols, brl_cols={3})


def mostrar_municipios(conn, nome: str) -> None:
    """Mostra municípios beneficiários."""
    cur = conn.cursor()
    cur.execute(SQL_MUNICIPIOS, (nome,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section("MUNICÍPIOS BENEFICIÁRIOS")
    cols = ["municipio", "uf", "planos", "valor_total", "emendas"]
    print_table(rows, cols, brl_cols={3})


def mostrar_detalhe_emenda(conn, nome: str, emenda: str) -> None:
    """Mostra detalhes de uma emenda específica."""
    cur = conn.cursor()
    cur.execute(SQL_DETALHE_EMENDA, (nome, emenda))
    rows = cur.fetchall()
    if not rows:
        print(f"\n  Nenhum plano encontrado para emenda {emenda}")
        return

    print_section(f"DETALHE EMENDA {emenda}")
    cols = ["plano_acao_codigo", "situacao", "municipio", "uf", "valor_total", "motivo"]
    print_table(rows, cols, brl_cols={4})


def mostrar_comparacao(conn, nome: str) -> None:
    """Compara com outros deputados do mesmo partido."""
    cur = conn.cursor()

    # Buscar partido do deputado
    cur.execute(SQL_PERFIL, (nome,))
    perfil = cur.fetchone()
    if not perfil:
        return

    partido = perfil[1]  # sigla_partido
    if not partido:
        return

    cur.execute(SQL_COMPARACAO_PARTIDO, (partido,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section(f"COMPARAÇÃO — PARTIDO {partido} (top 15)")
    cols = ["parlamentar_nome", "total_planos", "valor_total", "municipios", "valor_medio"]
    print_table(rows, cols, brl_cols={2, 4})


def mostrar_ranking() -> None:
    """Mostra ranking geral de parlamentares."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL_RANKING)
    rows = cur.fetchall()

    print_section("RANKING DE PARLAMENTARES (top 20)")
    cols = ["parlamentar_nome", "total_planos", "valor_total", "municipios", "valor_medio"]
    print_table(rows, cols, brl_cols={2, 4})
    conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="Followup de emendas por deputado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python3 src/deputado_followup.py AFONSO FLORENCE\n"
            "  python3 src/deputado_followup.py --buscar ULYSSES\n"
            "  python3 src/deputado_followup.py --emenda 202642740010\n"
            "  python3 src/deputado_followup.py --ranking\n"
            "  python3 src/deputado_followup.py --partido PT\n"
        ),
    )
    parser.add_argument("nome", nargs="*", help="Nome do deputado (parcial)")
    parser.add_argument("--buscar", "-b", help="Buscar deputado por nome parcial")
    parser.add_argument("--emenda", "-e", help="Detalhar emenda específica")
    parser.add_argument("--ranking", "-r", action="store_true", help="Ranking geral")
    parser.add_argument("--partido", "-p", help="Comparar deputados de um partido")

    args = parser.parse_args()

    # Comando: ranking
    if args.ranking:
        mostrar_ranking()
        return 0

    # Resolver nome do deputado
    termo = " ".join(args.nome) if args.nome else args.buscar
    if not termo and not args.emenda:
        parser.print_help()
        return 1

    conn = get_connection()

    # Se busca parcial, listar opções
    if args.buscar or not args.emenda:
        deputados = buscar_deputados(conn, termo)
        if len(deputados) > 1:
            print(f"\n  {len(deputados)} deputados encontrados com '{termo}':")
            for d in deputados:
                print(f"    - {d[0]} ({d[1] or '?'}/{d[2] or '?'})")
            print("\n  Refine o nome e tente novamente.")
            conn.close()
            return 1
        if len(deputados) == 0:
            print(f"\n  Nenhum deputado encontrado com '{termo}'.")
            conn.close()
            return 1
        termo = deputados[0][0]

    # Detalhe de emenda específica
    if args.emenda:
        mostrar_detalhe_emenda(conn, termo, args.emenda)
        conn.close()
        return 0

    # Followup completo
    if not mostrar_perfil(conn, termo):
        print(f"\n  Deputado '{termo}' não encontrado em parlamentares_dados.")
        print("  (pode ter emendas mas sem dados da Câmara)")
        conn.close()
        return 1

    mostrar_resumo(conn, termo)
    mostrar_emendas(conn, termo)
    mostrar_municipios(conn, termo)

    if args.partido:
        mostrar_comparacao(conn, termo)
    else:
        mostrar_comparacao(conn, termo)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
