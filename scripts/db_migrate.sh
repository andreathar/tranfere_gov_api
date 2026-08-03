#!/usr/bin/env bash
# Aplica migrations data/migration_*.sql não registradas em schema_migrations.
#
# Uso:
#   scripts/db_migrate.sh                Aplica pendentes em ordem lexical e registra
#   scripts/db_migrate.sh --status       Lista aplicadas e pendentes
#   scripts/db_migrate.sh --mark-applied Registra todas as existentes como aplicadas
#                                        (sem executar — para banco já migrado)
#
# A tabela schema_migrations é criada por data/migration_001_track.sql (idempotente).

set -euo pipefail
cd "$(dirname "$0")/.."

PGHOST="${PGHOST:-127.0.0.1}"
PGDATABASE="${PGDATABASE:-transferegov_db}"
PGUSER="${PGUSER:-cognee}"
export PGPASSWORD="${PGPASSWORD:-cognee}"

PSQL=(psql -q -v ON_ERROR_STOP=1 -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE")

# Bootstrap: garante que a tabela de tracking exista (CREATE TABLE IF NOT EXISTS)
"${PSQL[@]}" -f data/migration_001_track.sql

# Migrations gerenciadas: todos os migration_*.sql exceto o bootstrap (001_track)
mapfile -t MIGRATIONS < <(ls data/migration_*.sql | sort | grep -v 'migration_001_track.sql')

is_applied() {
    local base="$1"
    "${PSQL[@]}" -tA -c "SELECT 1 FROM schema_migrations WHERE filename = '$base'" | grep -q 1
}

register() {
    local base="$1"
    "${PSQL[@]}" -c "INSERT INTO schema_migrations (filename) VALUES ('$base')"
}

cmd_status() {
    local total=0 pendentes=0
    echo "=== Aplicadas ==="
    "${PSQL[@]}" -c "SELECT filename, applied_at FROM schema_migrations ORDER BY filename"
    echo "=== Pendentes ==="
    for f in "${MIGRATIONS[@]}"; do
        base=$(basename "$f")
        if ! is_applied "$base"; then
            echo "  $base"
            pendentes=$((pendentes + 1))
        else
            total=$((total + 1))
        fi
    done
    if [ "$pendentes" -eq 0 ]; then
        echo "  (nada a aplicar)"
    fi
    echo
    echo "Aplicadas: $total | Pendentes: $pendentes"
}

cmd_apply() {
    local aplicadas=0
    for f in "${MIGRATIONS[@]}"; do
        base=$(basename "$f")
        if is_applied "$base"; then
            continue
        fi
        echo "Aplicando $base..."
        "${PSQL[@]}" -f "$f"
        register "$base"
        aplicadas=$((aplicadas + 1))
    done
    if [ "$aplicadas" -eq 0 ]; then
        echo "Nada a aplicar."
    else
        echo "Aplicadas: $aplicadas"
    fi
}

cmd_mark_applied() {
    local total=0
    for f in "${MIGRATIONS[@]}"; do
        base=$(basename "$f")
        if ! is_applied "$base"; then
            register "$base"
            total=$((total + 1))
        fi
    done
    echo "Registradas como aplicadas: $total (total em schema_migrations: $(psql -tA -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -c 'SELECT COUNT(*) FROM schema_migrations'))"
}

case "${1:-}" in
    --status)        cmd_status ;;
    --mark-applied)  cmd_mark_applied ;;
    "")              cmd_apply ;;
    *)               echo "Uso: $0 [--status|--mark-applied]" >&2; exit 1 ;;
esac
