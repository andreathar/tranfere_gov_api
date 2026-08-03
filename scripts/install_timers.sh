#!/usr/bin/env bash
# Instala, remove ou consulta os timers systemd (user) dos jobs agendados do TransfereGov.
#
# Os timers substituem o crontab documentado em docs/CRON_JOBS.md:
#   - cron-diario   → seg-sex 21:00  (DOU)
#   - cron-qdrant   → seg 02:00      (indexação vetorial RAG)
#   - cron-dossie   → dias 1 e 16 04:00 (personas analíticas)
#
# Vantagens vs crontab: logs via journald, Persistent=true (roda job perdido
# após reboot), RandomizedDelaySec, status via systemctl.
#
# Uso:
#   scripts/install_timers.sh install   # cria, habilita e inicia os timers
#   scripts/install_timers.sh remove    # para e remove os timers
#   scripts/install_timers.sh status    # mostra estado dos timers
#   scripts/install_timers.sh test <job> # roda o job imediatamente (./run.sh <job>)

set -euo pipefail

# Resolve o diretório do projeto (raiz do repo, onde fica run.sh)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_SH="$PROJECT_DIR/run.sh"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
PREFIX="transferegov"

# ---------------------------------------------------------------------------
# Definição dos jobs: nome do comando em run.sh → OnCalendar (sintaxe systemd)
# ---------------------------------------------------------------------------
JOBS=(
  "cron-diario|Mon..Fri 21:00:00|Worker do Diario Oficial da Uniao (DOU)"
  "cron-qdrant|Mon 02:00:00|Indexador vetorial Qdrant (RAG)"
  "cron-dossie|*-*-01,16 04:00:00|Gerador de personas analiticas (dossies)"
)

ensure_user_bus() {
    if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ ! -S "${XDG_RUNTIME_DIR}/bus" ]; then
        export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    fi
    if ! systemctl --user is-system-running >/dev/null 2>&1; then
        echo "ERRO: systemd user não está rodando (systemctl --user falhou)." >&2
        exit 1
    fi
}

write_unit() {
    local job="$1" calendar="$2" desc="$3" kind="$4"
    local unit_name="${PREFIX}-${job}.${kind}"
    local file="$UNIT_DIR/$unit_name"

    if [ "$kind" = "service" ]; then
        cat > "$file" <<EOF
[Unit]
Description=${desc}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
Environment=PATH=${PROJECT_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${RUN_SH} ${job}
EOF
    else
        cat > "$file" <<EOF
[Unit]
Description=${desc} (timer)

[Timer]
OnCalendar=${calendar}
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF
    fi
    echo "  ✓ $unit_name"
}

install() {
    ensure_user_bus
    mkdir -p "$UNIT_DIR"
    echo "Instalando timers em $UNIT_DIR"
    echo "Projeto: $PROJECT_DIR"
    for entry in "${JOBS[@]}"; do
        local job calendar desc
        IFS='|' read -r job calendar desc <<< "$entry"
        write_unit "$job" "$calendar" "$desc" service
        write_unit "$job" "$calendar" "$desc" timer
    done

    systemctl --user daemon-reload
    for entry in "${JOBS[@]}"; do
        local job
        IFS='|' read -r job _ _ <<< "$entry"
        systemctl --user enable --now "${PREFIX}-${job}.timer"
        echo "  ✓ ${PREFIX}-${job}.timer habilitado e iniciado"
    done
    echo ""
    echo "Timers ativos:"
    systemctl --user list-timers --all | grep -E "transferegov|NEXT" || true
    echo ""
    echo "Logs: journalctl --user -u ${PREFIX}-cron-diario --since today"
}

remove() {
    ensure_user_bus
    for entry in "${JOBS[@]}"; do
        local job
        IFS='|' read -r job _ _ <<< "$entry"
        systemctl --user disable --now "${PREFIX}-${job}.timer" 2>/dev/null || true
        rm -f "$UNIT_DIR/${PREFIX}-${job}.timer" "$UNIT_DIR/${PREFIX}-${job}.service"
        echo "  ✓ ${PREFIX}-${job} removido"
    done
    systemctl --user daemon-reload
    echo "Timers TransfereGov removidos."
}

status() {
    ensure_user_bus
    systemctl --user list-timers --all | grep -E "transferegov|NEXT" || echo "Nenhum timer TransfereGov ativo."
    echo ""
    for entry in "${JOBS[@]}"; do
        local job
        IFS='|' read -r job _ _ <<< "$entry"
        echo "--- ${PREFIX}-${job}.service (última execução) ---"
        systemctl --user show "${PREFIX}-${job}.service" --property=Result,ExecMainStatus 2>/dev/null || echo "  (nunca executado)"
    done
}

test_job() {
    local job="${1:-}"
    if [ -z "$job" ]; then
        echo "Uso: scripts/install_timers.sh test <job>" >&2
        exit 1
    fi
    if [ ! -x "$RUN_SH" ]; then chmod +x "$RUN_SH"; fi
    echo "Rodando ./run.sh $job (foreground)..."
    exec "$RUN_SH" "$job"
}

case "${1:-install}" in
    install) install ;;
    remove) remove ;;
    status) status ;;
    test) test_job "${2:-}" ;;
    *)
        echo "Uso: $0 [install|remove|status|test <job>]" >&2
        exit 1
        ;;
esac
