#!/usr/bin/env bash
# Atalhos para os scripts de extração Transferegov.
# Uso: ./run.sh <comando>
#
# Comandos:
#   discover       — Listar todos os objetos disponíveis para 2026
#   cemiterios     — Extrair todos os planos de cemitérios (objeto 301)
#   negados        — Extrair planos negados/perdidos de cemitérios
#   all            — Extrair TODOS os objetos de 2026
#   help           — Mostrar esta ajuda

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
SRC="src"

usage() {
    cat <<EOF
Uso: $0 <comando>

Comandos:
  discover           Listar todos os objetos disponíveis para 2026
  cemiterios         Extrair todos os planos de cemitérios (objeto 301)
  negados            Extrair planos negados/perdidos de cemitérios
  all                Extrair TODOS os objetos de 2026
  help               Mostrar esta ajuda

Exemplos:
  ./run.sh discover
  ./run.sh cemiterios
  ./run.sh negados
  ./run.sh all
EOF
}

case "${1:-help}" in
    discover)
        $PYTHON "$SRC/transferegov_extract.py" --discover --ano 2026
        ;;
    cemiterios)
        $PYTHON "$SRC/extract_cemiterios_2026_plano_acao.py"
        ;;
    negados)
        $PYTHON "$SRC/extract_cemiterios_2026_negados.py"
        ;;
    all)
        $PYTHON "$SRC/transferegov_extract.py" --objeto all --ano 2026 --csv
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Comando desconhecido: $1"
        echo ""
        usage
        exit 1
        ;;
esac
