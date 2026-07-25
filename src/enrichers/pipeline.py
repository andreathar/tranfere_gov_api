"""
Pipeline de enriquecimento orquestrador.

Uso: python3 -m src.enrichers.pipeline [--fase 1|2|3|4|5|6|all] [--dry-run]

Fase 1: Validação CNPJ + IBGE
Fase 2: Perfil Câmara
Fase 3: Vinculação parlamentar-beneficiário
Fase 4: Processos Judiciais (DataJud)
Fase 5: Compras Públicas (PNCP/Contratos.gov)
Fase 6: Saúde + Educação (CNES/INEP)
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_script(script: str, extra_args: list | None = None) -> int:
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
    from src.db_utils import get_connection

    print("\n\n>>> FASE 3: Vinculação parlamentar-beneficiário")

    conn = get_connection()
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


def fase4_datajud(dry_run: bool, limit: int):
    """Fase 4: Processos judiciais (DataJud) via mcp-brasil."""
    print("\n\n>>> FASE 4: Processos Judiciais (DataJud)")
    args = ["--limit", str(limit)] if limit > 0 else []
    if dry_run:
        print("AVISO: fase 4 (datajud) ignora --dry-run pois usa MCP diretamente.")

    rc = run_script("datajud", args)
    if rc != 0:
        print(f"AVISO: datajud retornou código {rc}")


def fase5_compras(dry_run: bool, limit: int, ano: int):
    """Fase 5: Compras públicas (PNCP/Contratos.gov) para municípios beneficiários."""
    print("\n\n>>> FASE 5: Compras Públicas (PNCP/Contratos.gov)")
    args = ["--limit", str(limit)] if limit > 0 else []
    args.extend(["--ano", str(ano)])
    if dry_run:
        args.append("--dry-run")

    rc = run_script("compras", args)
    if rc != 0:
        print(f"AVISO: compras retornou código {rc}")


def fase6_saude_educacao(dry_run: bool, limit: int):
    """Fase 6: Saúde (CNES) + Educação (IDEB) para municípios beneficiários."""
    print("\n\n>>> FASE 6: Saúde + Educação Municipal")
    args = ["--limit", str(limit)] if limit > 0 else []
    if dry_run:
        args.append("--dry-run")

    rc = run_script("saude_educacao", args)
    if rc != 0:
        print(f"AVISO: saude_educacao retornou código {rc}")


def main():
    parser = argparse.ArgumentParser(description="Pipeline de enriquecimento")
    parser.add_argument("--fase", default="all", help="Fase a executar: 1-6 ou all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N items por fase")
    parser.add_argument("--ano", type=int, default=2026, help="Ano para compras públicas (fase 5)")
    args = parser.parse_args()

    inicio = time.time()

    if args.fase in ("1", "all"):
        fase1_validacao_ibge(args.dry_run, args.limit)

    if args.fase in ("2", "all"):
        fase2_perfil_camara(args.dry_run, args.limit)

    if args.fase in ("3", "all"):
        fase3_vinculacao(args.dry_run)

    if args.fase in ("4", "all"):
        fase4_datajud(args.dry_run, args.limit)

    if args.fase in ("5", "all"):
        fase5_compras(args.dry_run, args.limit, args.ano)

    if args.fase in ("6", "all"):
        fase6_saude_educacao(args.dry_run, args.limit)

    duracao = time.time() - inicio
    print(f"\nPipeline concluído em {duracao:.1f}s")


if __name__ == "__main__":
    main()
