#!/usr/bin/env python3
"""
Script: limpar_personas_duplicadas.py
Propósito:
  1. Analisa qualidade das personas geradas por deputado
  2. Para cada deputado com múltiplas personas, mantém APENAS a melhor:
       Critério: versao_prompt DESC → qualidade_ok DESC → score_qualidade DESC
                 → LENGTH(analise_gerada) DESC → data_analise DESC
  3. Deleta todas as personas inferiores
  4. Reseta o dossie_checkpoint dos deputados cuja melhor versão restante é <= v5
     (status='fail'), para que entrem na fila do próximo --lote
  5. Exibe relatório completo antes de executar (--dry-run por padrão)

Uso:
  python3 scripts/limpar_personas_duplicadas.py           # dry-run (só mostra)
  python3 scripts/limpar_personas_duplicadas.py --executar # executa de verdade
"""

import argparse
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from src.db_utils import get_connection


def analisar_estado(cur) -> dict:
    """Retorna métricas gerais do estado atual das personas."""
    cur.execute("""
        SELECT COUNT(*) FROM parlamentares_personas WHERE tipo_politico='deputado'
    """)
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT deputado_id) FROM parlamentares_personas
        WHERE tipo_politico='deputado'
    """)
    total_deps = cur.fetchone()[0]

    cur.execute("""
        SELECT versao_prompt, COUNT(*), AVG(score_qualidade)::numeric(5,2),
               AVG(LENGTH(analise_gerada))::int
        FROM parlamentares_personas WHERE tipo_politico='deputado'
        GROUP BY versao_prompt ORDER BY versao_prompt
    """)
    por_versao = cur.fetchall()

    cur.execute("""
        SELECT n_personas, COUNT(*) FROM (
            SELECT deputado_id, COUNT(*) as n_personas FROM parlamentares_personas
            WHERE tipo_politico='deputado' GROUP BY deputado_id
        ) t GROUP BY n_personas ORDER BY n_personas
    """)
    distribuicao = cur.fetchall()

    return {
        "total_registros": total,
        "total_deputados": total_deps,
        "por_versao": por_versao,
        "distribuicao": distribuicao,
    }


def calcular_melhor_por_deputado(cur) -> tuple[list, list]:
    """
    Retorna:
      - ids_manter: lista de IDs a preservar (1 por deputado)
      - ids_deletar: lista de IDs a deletar (duplicatas inferiores)
    """
    cur.execute("""
        WITH ranked AS (
            SELECT id, deputado_id, versao_prompt, score_qualidade,
                   qualidade_ok, LENGTH(analise_gerada) as len, data_analise,
                   modelo_usado,
                   ROW_NUMBER() OVER (
                       PARTITION BY deputado_id
                       ORDER BY
                           versao_prompt DESC,
                           COALESCE(qualidade_ok::int, 0) DESC,
                           COALESCE(score_qualidade, 0) DESC,
                           LENGTH(analise_gerada) DESC,
                           data_analise DESC
                   ) AS rn
            FROM parlamentares_personas
            WHERE tipo_politico = 'deputado'
        )
        SELECT id, deputado_id, versao_prompt, score_qualidade, qualidade_ok,
               len, modelo_usado, rn
        FROM ranked
        ORDER BY deputado_id, rn
    """)
    rows = cur.fetchall()

    ids_manter = []
    ids_deletar = []
    melhores = {}   # deputado_id -> row da melhor

    for (id_, dep_id, versao, score, qok, length, modelo, rn) in rows:
        if rn == 1:
            ids_manter.append(id_)
            melhores[dep_id] = {
                "id": id_, "versao": versao, "score": score,
                "qok": qok, "len": length, "modelo": modelo
            }
        else:
            ids_deletar.append(id_)

    return ids_manter, ids_deletar, melhores


def calcular_deprecados(melhores: dict) -> list[int]:
    """
    Retorna lista de deputado_id cuja melhor versão restante é <= v5.
    Estes terão o checkpoint resetado para 'fail' para entrarem na fila.
    """
    return [
        dep_id for dep_id, info in melhores.items()
        if info["versao"] <= 5
    ]


def imprimir_relatorio(estado_antes: dict, ids_deletar: list, melhores: dict,
                       deps_deprecados: list, cur):
    """Imprime relatório completo."""
    print("\n" + "=" * 70)
    print(" RELATÓRIO DE LIMPEZA DE PERSONAS ".center(70, "="))
    print("=" * 70)

    print(f"\n📊 ESTADO ATUAL:")
    print(f"   Total de registros: {estado_antes['total_registros']}")
    print(f"   Deputados únicos com persona: {estado_antes['total_deputados']}")

    print(f"\n📋 POR VERSÃO (antes):")
    for (v, n, avg_score, avg_len) in estado_antes["por_versao"]:
        print(f"   v{v}: {n:4d} registros | avg_score={avg_score} | avg_len={avg_len} chars")

    print(f"\n👥 DISTRIBUIÇÃO (personas por deputado):")
    for (n_p, n_deps) in estado_antes["distribuicao"]:
        print(f"   {n_p} persona(s): {n_deps} deputados")

    print(f"\n🗑️  AÇÃO - DELETAR DUPLICATAS:")
    print(f"   Registros a MANTER (melhor por deputado): {len(melhores)}")
    print(f"   Registros a DELETAR (versões inferiores): {len(ids_deletar)}")

    print(f"\n📈 MELHOR VERSÃO POR DEPUTADO (após limpeza):")
    por_versao_apos: dict = {}
    for dep_id, info in melhores.items():
        v = info["versao"]
        por_versao_apos[v] = por_versao_apos.get(v, 0) + 1
    for v in sorted(por_versao_apos):
        print(f"   v{v}: {por_versao_apos[v]:4d} deputados")

    print(f"\n⚠️  DEPUTADOS COM VERSÃO ANTIGA (≤ v5) — FILA DE REGENERAÇÃO:")
    print(f"   Total: {len(deps_deprecados)} deputados terão checkpoint resetado para 'fail'")

    if deps_deprecados:
        # Pegar nomes dos primeiros 10
        ids_str = ", ".join(str(x) for x in deps_deprecados[:20])
        cur.execute(
            f"SELECT nome, deputado_id FROM parlamentares_dados "
            f"WHERE deputado_id IN ({ids_str}) ORDER BY nome LIMIT 10"
        )
        exemplos = cur.fetchall()
        print(f"   Exemplos (primeiros 10):")
        for (nome, dep_id) in exemplos:
            info = melhores.get(dep_id, {})
            print(f"     {nome} (dep_id={dep_id}) → melhor atual: v{info.get('versao','?')} "
                  f"score={info.get('score', 'N/A')}")

    print(f"\n🎯 RESUMO:")
    print(f"   Antes: {estado_antes['total_registros']} registros")
    print(f"   Após:  {len(melhores)} registros (1 por deputado)")
    print(f"   Ganho: -{len(ids_deletar)} registros deletados")
    print(f"   Regenerar: {len(deps_deprecados)} deputados entrarão na fila (v≤5 → resetar)")
    print("=" * 70)


def executar_limpeza(conn, ids_deletar: list, deps_deprecados: list,
                     rag_version: int = 8) -> None:
    """Executa a limpeza no banco de dados."""
    cur = conn.cursor()

    if ids_deletar:
        print(f"\n🗑️  Deletando {len(ids_deletar)} personas duplicadas...")
        cur.execute(
            "DELETE FROM parlamentares_personas WHERE id = ANY(%s)",
            (ids_deletar,)
        )
        print(f"   ✅ {cur.rowcount} registros deletados.")

    if deps_deprecados:
        print(f"\n🔄 Resetando checkpoint de {len(deps_deprecados)} deputados com v≤5...")
        # Deletar checkpoint existente destes deputados (versão atual)
        # para que entrem na fila do próximo --lote sem --regerar
        cur.execute(
            """
            DELETE FROM dossie_checkpoint
            WHERE tipo = 'deputado'
              AND politico_id = ANY(%s)
              AND versao = %s
            """,
            (deps_deprecados, rag_version)
        )
        deletados_chk = cur.rowcount
        print(f"   ✅ {deletados_chk} entradas de checkpoint removidas "
              f"(entrarão na fila do próximo --lote).")

    conn.commit()
    print("\n✅ Limpeza concluída e commitada.")


def verificar_estado_final(cur):
    """Exibe estado após a limpeza."""
    cur.execute("""
        SELECT versao_prompt, COUNT(*), AVG(score_qualidade)::numeric(5,2),
               AVG(LENGTH(analise_gerada))::int,
               SUM(CASE WHEN qualidade_ok THEN 1 ELSE 0 END) as ok_count
        FROM parlamentares_personas WHERE tipo_politico='deputado'
        GROUP BY versao_prompt ORDER BY versao_prompt
    """)
    print("\n📊 ESTADO FINAL POR VERSÃO:")
    for (v, n, avg_score, avg_len, ok) in cur.fetchall():
        print(f"   v{v}: {n:4d} deputados | avg_score={avg_score} | avg_len={avg_len} | ok={ok}")

    cur.execute("""
        SELECT COUNT(*) FROM dossie_checkpoint
        WHERE tipo='deputado' AND versao=8
    """)
    chk = cur.fetchone()[0]
    print(f"\n   Checkpoint v8 restante: {chk} entradas")

    cur.execute("""
        SELECT COUNT(*) FROM parlamentares_dados pd
        WHERE NOT EXISTS (
            SELECT 1 FROM dossie_checkpoint dc
            WHERE dc.tipo='deputado' AND dc.politico_id=pd.deputado_id AND dc.versao=8
        )
    """)
    sem_chk = cur.fetchone()[0]
    print(f"   Deputados SEM checkpoint v8 (entrarão na próxima fila): {sem_chk}")


def main():
    parser = argparse.ArgumentParser(
        description="Limpa personas duplicadas e reseta checkpoint de versões antigas."
    )
    parser.add_argument(
        "--executar",
        action="store_true",
        help="Executa a limpeza (sem esta flag, apenas mostra o relatório)",
    )
    args = parser.parse_args()

    dry_run = not args.executar

    if dry_run:
        print("\n⚠️  MODO DRY-RUN (use --executar para aplicar as mudanças)\n")

    # Importar versão RAG atual
    try:
        from src.enrichers.rag_persona import RAG_PERSONA_VERSION
        rag_version = RAG_PERSONA_VERSION
    except ImportError:
        rag_version = 8  # fallback

    print(f"📌 RAG_PERSONA_VERSION atual: v{rag_version}")

    with get_connection() as conn:
        cur = conn.cursor()

        # 1. Estado atual
        estado_antes = analisar_estado(cur)

        # 2. Calcular melhores
        ids_manter, ids_deletar, melhores = calcular_melhor_por_deputado(cur)

        # 3. Deputados com versão antiga
        deps_deprecados = calcular_deprecados(melhores)

        # 4. Relatório
        imprimir_relatorio(estado_antes, ids_deletar, melhores, deps_deprecados, cur)

        if not dry_run:
            confirm = input("\n❓ Confirmar execução? (s/N): ").strip().lower()
            if confirm != "s":
                print("❌ Cancelado pelo usuário.")
                return

            executar_limpeza(conn, ids_deletar, deps_deprecados, rag_version)
            verificar_estado_final(cur)
        else:
            print("\n💡 Execute com --executar para aplicar as mudanças.")
            print(f"   Próximo passo após limpeza:")
            print(f"   ./run.sh cron-dossie --lote {len(deps_deprecados) + 53} "
                  f"  # regenera v≤5 + sem persona")


if __name__ == "__main__":
    main()
