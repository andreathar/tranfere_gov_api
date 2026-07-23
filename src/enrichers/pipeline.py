"""
Pipeline de enriquecimento orquestrador.

Uso: python3 -m src.enrichers.pipeline [--fase 1|2|3|all] [--dry-run]

Fase 1: Validação CNPJ + IBGE
Fase 2: Perfil Câmara
Fase 3: Vinculação parlamentar-beneficiário
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def run_script(script: str, extra_args: list = None) -> int:
    """Executa um script enricher como subprocesso."""
    cmd = [sys.executable, "-m", f"src.enrichers.{script}"]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*60}")
    print(f"EXECUTANDO: {' '.join(cmd)}")
    print(f"{'='*60}")
    return subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent.parent)).returncode


def fase1_validacao_ibge(dry_run: bool, limit: int):
    """Fase 1: Validação CNPJ + Enriquecimento IBGE."""
    print("\n\n>>> FASE 1: Validação CNPJ + IBGE")
    args = ["--limit", str(limit)] if limit > 0 else []
    if dry_run:
        args.append("--dry-run")

    rc = run_script("validacao", args)
    if rc != 0:
        print(f"AVISO: validacao retornou código {rc}")

    rc = run_script("ibge", ["--dry-run"] if dry_run else [])
    if rc != 0:
        print(f"AVISO: ibge retornou código {rc}")


def fase2_perfil_camara(dry_run: bool, limit: int):
    """Fase 2: Perfil de parlamentares via Câmara."""
    print("\n\n>>> FASE 2: Perfil Câmara")
    args = ["--limit", str(limit)] if limit > 0 else []
    if dry_run:
        args.append("--dry-run")

    rc = run_script("camara", args)
    if rc != 0:
        print(f"AVISO: camara retornou código {rc}")


def fase3_vinculacao(dry_run: bool):
    """Fase 3: Vincula parlamentares a beneficiários."""
    import psycopg2
    from config.settings import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS

    print("\n\n>>> FASE 3: Vinculação parlamentar-beneficiário")

    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO parlamentar_beneficiario
            (parlamentar_nome, beneficiario_id, emenda_codigo, valor_total, plano_acao_situacao)
        SELECT parlamentar_nome, beneficiario_id, emenda_codigo,
            SUM(valor_total), MAX(plano_acao_situacao)
        FROM planos_acao
        WHERE parlamentar_nome IS NOT NULL AND parlamentar_nome != ''
          AND beneficiario_id IS NOT NULL
        GROUP BY parlamentar_nome, beneficiario_id, emenda_codigo
        ON CONFLICT (parlamentar_nome, beneficiario_id, emenda_codigo) DO UPDATE SET
            valor_total = EXCLUDED.valor_total,
            plano_acao_situacao = EXCLUDED.plano_acao_situacao
    """)
    vinculados = cur.rowcount
    conn.commit()
    conn.close()

    print(f"  Vinculações: {vinculados}")


def main():
    parser = argparse.ArgumentParser(description="Pipeline de enriquecimento")
    parser.add_argument("--fase", default="all", help="Fase a executar: 1, 2, 3 ou all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N items por fase")
    args = parser.parse_args()

    inicio = time.time()

    if args.fase in ("1", "all"):
        fase1_validacao_ibge(args.dry_run, args.limit)

    if args.fase in ("2", "all"):
        fase2_perfil_camara(args.dry_run, args.limit)

    if args.fase in ("3", "all"):
        fase3_vinculacao(args.dry_run)

    duracao = time.time() - inicio
    print(f"\nPipeline concluído em {duracao:.1f}s")


if __name__ == "__main__":
    main()
