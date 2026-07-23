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

# Ativar venv se existir
if [ -f ".venv/bin/activate" ]; then
    . .venv/bin/activate
fi

PYTHON="${PYTHON:-python3}"
SRC="src"

usage() {
    cat <<EOF
Uso: $0 <comando> [opções]

Comandos:
  discover           Listar todos os objetos disponíveis para 2026
  cemiterios         Extrair cemitérios (objeto 301) — aceita args extras
  negados            Extrair negados/perdidos (objeto 301) — aceita args extras
  import             Importar JSONs para o banco PostgreSQL
  report             Relatórios do banco (resumo|estado|objeto|negados|emenda|top|sql)
  dashboard          Dashboard interativo HTML com gráficos Plotly
  enrich             Pipeline de enriquecimento (CNPJ + IBGE + Câmara)
  validate           Validar CNPJs via BrasilAPI
  ibge               Enriquecer municípios via IBGE
  camara             Perfil de parlamentares via Câmara
  all                Extrair TODOS os objetos de 2026
  help               Mostrar esta ajuda

Flags extras (passar após o comando):
  --db               Salvar no PostgreSQL
  --csv              Exportar CSV além de Excel
  --programa N       Filtrar por programaId (25 = Transferências Especiais)
  --uf UF            Filtrar por UF
  --situacao-api S   Filtrar por situação na API (ex: IMPEDIDO)
  -v                 Logging verboso

Exemplos:
  ./run.sh discover
  ./run.sh cemiterios --db --csv
  ./run.sh negados --db
  ./run.sh import
  ./run.sh report resumo
  ./run.sh report parlamentar
  ./run.sh report sql "SELECT ..."

Extração por programa + situação:
  python3 src/transferegov_extract.py --objeto all --ano 2026 --programa 25 --situacao-api IMPEDIDO --db --csv
EOF
}

case "${1:-help}" in
    discover)
        $PYTHON "$SRC/transferegov_extract.py" --discover --ano 2026
        ;;
    cemiterios)
        $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 "$@"
        ;;
    negados)
        $PYTHON "$SRC/transferegov_extract.py" --objeto 301 --ano 2026 --negados "$@"
        ;;
    import)
        $PYTHON "$SRC/db_import.py" "${@:2}"
        ;;
    report)
        $PYTHON "$SRC/db_report.py" "${@:2}"
        ;;
    dashboard)
        $PYTHON "$SRC/dashboard.py" "${@:2}"
        ;;
    enrich)
        $PYTHON -m src.enrichers.pipeline "${@:2}"
        ;;
    validate)
        $PYTHON -m src.enrichers.validacao "${@:2}"
        ;;
    ibge)
        $PYTHON -m src.enrichers.ibge "${@:2}"
        ;;
    camara)
        $PYTHON -m src.enrichers.camara "${@:2}"
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
