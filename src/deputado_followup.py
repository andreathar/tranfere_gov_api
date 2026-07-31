"""
Followup de emendas por deputado — CLI interativo.

Uso:
    python3 src/deputado_followup.py AFONSO FLORENCE
    python3 src/deputado_followup.py --buscar "ULYSSES"
    python3 src/deputado_followup.py --emenda 202642740010
    python3 src/deputado_followup.py --ranking
    python3 src/deputado_followup.py --partido PT
    python3 src/deputado_followup.py --parlamentar-id 4161
    python3 src/deputado_followup.py -pid 4161 --emenda 202642740010

Mostra: perfil do deputado, trail de emendas, municípios beneficiários,
         comparação com outros deputados do mesmo partido/UF.

O flag --parlamentar-id usa busca exata por ID (indexado), mais rápido
que a busca por nome (ILIKE).
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
JOIN parlamentares_dados pd ON ranking.parlamentar_id = pd.parlamentar_id
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
LEFT JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
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

SQL_DISCRICIONARIAS_ID = """
SELECT
    ed.tipo_emenda,
    COUNT(*) AS total,
    SUM(ed.valor_total) AS valor_total,
    STRING_AGG(DISTINCT ed.status_execucao, ', ') AS status_execucao
FROM emendas_discricionarias ed
WHERE ed.parlamentar_id = %s
  AND ed.valor_total IS NOT NULL
GROUP BY ed.tipo_emenda
ORDER BY valor_total DESC
"""

SQL_DISCRICIONARIAS_DETALHE_ID = """
SELECT
    ed.ano,
    ed.tipo_emenda,
    ed.valor_total,
    ed.objeto,
    ed.status_execucao,
    ed.beneficiario_nome,
    ed.numero_convenio,
    ed.beneficiario_cnpj
FROM emendas_discricionarias ed
WHERE ed.parlamentar_id = %s
  AND ed.valor_total IS NOT NULL
ORDER BY ed.valor_total DESC
LIMIT 20
"""

# -- Variantes com parlamentos_id (exato, indexado) -------------------------

SQL_PERFIL_ID = """
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
    pd.municipio_nascimento,
    pd.parlamentar_id
FROM parlamentares_dados pd
WHERE pd.parlamentar_id = %s
LIMIT 1
"""

SQL_BUSCAR_NOME_POR_ID = """
SELECT DISTINCT pa.parlamentar_nome
FROM planos_acao pa
WHERE pa.parlamentar_id = %s
LIMIT 1
"""

SQL_RESUMO_ID = """
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
WHERE pa.parlamentar_id = %s
GROUP BY pa.parlamentar_nome
"""

SQL_EMENDAS_ID = """
SELECT
    pa.emenda_codigo,
    COUNT(*) AS planos,
    COUNT(DISTINCT pa.beneficiario_id) AS municipios,
    SUM(pa.valor_total) AS valor_total,
    STRING_AGG(DISTINCT pa.plano_acao_situacao, ', ') AS situacoes
FROM planos_acao pa
WHERE pa.parlamentar_id = %s
  AND pa.emenda_codigo IS NOT NULL AND pa.emenda_codigo != ''
GROUP BY pa.emenda_codigo
ORDER BY valor_total DESC
"""

SQL_MUNICIPIOS_ID = """
SELECT
    b.nome AS municipio,
    b.uf,
    COUNT(*) AS planos,
    SUM(pa.valor_total) AS valor_total,
    STRING_AGG(DISTINCT pa.emenda_codigo, ', ') AS emendas
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_id = %s
GROUP BY b.nome, b.uf
ORDER BY valor_total DESC
"""

SQL_DETALHE_EMENDA_ID = """
SELECT
    pa.plano_acao_codigo,
    pa.plano_acao_situacao,
    b.nome AS municipio,
    b.uf,
    pa.valor_total,
    pa.motivo_impedimento
FROM planos_acao pa
JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
WHERE pa.parlamentar_id = %s
  AND pa.emenda_codigo = %s
ORDER BY pa.valor_total DESC
"""


# ---------------------------------------------------------------------------
# Funções de exibição
# ---------------------------------------------------------------------------


def buscar_deputados(conn, termo: str) -> list[tuple]:
    """Busca deputados por nome (parcial, case-insensitive)."""
    cur = conn.cursor()
    cur.execute(SQL_LISTAR_DEPUTADOS, (f"%{termo}%",))
    return cur.fetchall()  # type: ignore[no-any-return]


def mostrar_perfil(conn, nome: str, parlamentar_id: int | None = None) -> bool:
    """Mostra perfil completo do deputado. Retorna True se encontrado."""
    cur = conn.cursor()
    if parlamentar_id is not None:
        cur.execute(SQL_PERFIL_ID, (parlamentar_id,))
    else:
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


def mostrar_resumo(conn, nome: str, parlamentar_id: int | None = None) -> None:
    """Mostra resumo geral de emendas do deputado."""
    cur = conn.cursor()
    if parlamentar_id is not None:
        cur.execute(SQL_RESUMO_ID, (parlamentar_id,))
    else:
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


def mostrar_emendas(conn, nome: str, parlamentar_id: int | None = None) -> None:
    """Mostra lista de emendas do deputado."""
    cur = conn.cursor()
    if parlamentar_id is not None:
        cur.execute(SQL_EMENDAS_ID, (parlamentar_id,))
    else:
        cur.execute(SQL_EMENDAS, (nome,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section("EMENDAS")
    cols = ["emenda_codigo", "planos", "municipios", "valor_total", "situacoes"]
    print_table(rows, cols, brl_cols={3})


def mostrar_municipios(conn, nome: str, parlamentar_id: int | None = None) -> None:
    """Mostra municípios beneficiários."""
    cur = conn.cursor()
    if parlamentar_id is not None:
        cur.execute(SQL_MUNICIPIOS_ID, (parlamentar_id,))
    else:
        cur.execute(SQL_MUNICIPIOS, (nome,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section("MUNICÍPIOS BENEFICIÁRIOS")
    cols = ["municipio", "uf", "planos", "valor_total", "emendas"]
    print_table(rows, cols, brl_cols={3})


def mostrar_detalhe_emenda(
    conn, nome: str, emenda: str, parlamentar_id: int | None = None
) -> None:
    """Mostra detalhes de uma emenda específica."""
    cur = conn.cursor()
    if parlamentar_id is not None:
        cur.execute(SQL_DETALHE_EMENDA_ID, (parlamentar_id, emenda))
    else:
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


def mostrar_emendas_discricionarias(conn, parlamentar_id: int) -> None:
    """Mostra emendas discricionarias do deputado, com tipo_emenda."""
    cur = conn.cursor()

    # Resumo por tipo_emenda
    cur.execute(SQL_DISCRICIONARIAS_ID, (parlamentar_id,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section("EMENDAS DISCRICIONÁRIAS (resumo por tipo)")
    cols = ["tipo_emenda", "total", "valor_total", "status"]
    print_table(rows, cols, brl_cols={2})

    # Detalhe
    cur.execute(SQL_DISCRICIONARIAS_DETALHE_ID, (parlamentar_id,))
    rows = cur.fetchall()
    if not rows:
        return

    print_section("EMENDAS DISCRICIONÁRIAS (top 20)")
    cols = ["ano", "tipo_emenda", "valor_total", "objeto", "status", "beneficiario", "convenio"]
    print_table(rows, cols, brl_cols={2})


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
            "  python3 src/deputado_followup.py --parlamentar-id 4161\n"
            "  python3 src/deputado_followup.py -pid 4161 --emenda 202642740010\n"
        ),
    )
    parser.add_argument("nome", nargs="*", help="Nome do deputado (parcial)")
    parser.add_argument("--buscar", "-b", help="Buscar deputado por nome parcial")
    parser.add_argument("--emenda", "-e", help="Detalhar emenda específica")
    parser.add_argument("--ranking", "-r", action="store_true", help="Ranking geral")
    parser.add_argument("--partido", "-p", help="Comparar deputados de um partido")
    parser.add_argument(
        "--parlamentar-id",
        "-pid",
        type=int,
        help="ID do parlamentar no TransfereGov (exato, mais rápido que nome)",
    )

    args = parser.parse_args()

    # Comando: ranking
    if args.ranking:
        mostrar_ranking()
        return 0

    # Resolver nome do deputado
    pid: int | None = args.parlamentar_id
    termo = " ".join(args.nome) if args.nome else args.buscar
    if not termo and not args.emenda and pid is None:
        parser.print_help()
        return 1

    conn = get_connection()

    # Se ID fornecido, buscar nome diretamente (exato, indexado)
    if pid is not None:
        cur = conn.cursor()
        cur.execute(SQL_BUSCAR_NOME_POR_ID, (pid,))
        row = cur.fetchone()
        if not row:
            print(f"\n  Nenhum plano encontrado com parlamentar_id = {pid}.")
            conn.close()
            return 1
        termo = row[0]
    # Se busca parcial (nome), listar opções
    elif args.buscar or not args.emenda:
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

    # Após os blocos acima, termo é garantidamente str
    assert termo is not None

    # Detalhe de emenda específica
    if args.emenda:
        mostrar_detalhe_emenda(conn, termo, args.emenda, parlamentar_id=pid)
        conn.close()
        return 0

    # Followup completo
    if not mostrar_perfil(conn, termo, parlamentar_id=pid):
        print(f"\n  Deputado '{termo}' não encontrado em parlamentares_dados.")
        print("  (pode ter emendas mas sem dados da Câmara)")
        conn.close()
        return 1

    mostrar_resumo(conn, termo, parlamentar_id=pid)
    mostrar_emendas(conn, termo, parlamentar_id=pid)
    mostrar_municipios(conn, termo, parlamentar_id=pid)

    if pid is not None:
        mostrar_emendas_discricionarias(conn, pid)

    if args.partido:
        mostrar_comparacao(conn, termo)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
