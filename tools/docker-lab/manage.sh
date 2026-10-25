#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v zenity >/dev/null || { echo 'Install zenity to use this optional manager.' >&2; exit 1; }
while choice="$(zenity --list --title='Termia Docker laboratory' --width=620 --height=620 \
    --column='Action' --column='Command' --hide-column=2 --print-column=2 \
    'Open browser' browser 'Prepare / build images' prepare 'Start desktop' start \
    'Restart container (ends sessions)' restart 'Restart Wayland (ends sessions)' restart-wayland \
    'Stop desktop (ends sessions)' stop-desktop 'Status' status-desktop 'Logs' logs \
    'Check tools' check 'Monitor memory' monitor 'Stop monitor' stop-monitor \
    'SSH/SFTP smoke' ssh-smoke 'Memory cycles' memory 'Lifecycle suite' lifecycle \
    'Menu reuse' menus 'X11 smoke' smoke-x11 'Wayland smoke' smoke-wayland \
    'Close with active transfers' close-live 'Valgrind' valgrind \
    'Cancel diagnostic' cancel 'Open results' results)"; do
    case "$choice" in
        restart|restart-wayland|stop-desktop)
            zenity --question --text='This ends the sessions in this laboratory. Continue?' || continue ;;
    esac
    case "$choice" in
        browser)
            address="$(bash "$ROOT_DIR/run.sh" url)"
            xdg-open "$address"; continue ;;
        results) xdg-open "$ROOT_DIR/.runtime/evidence"; continue ;;
        stop-monitor) args=(stop monitor) ;;
        cancel) args=(stop diagnostic) ;;
        ssh-smoke|memory|lifecycle|menus|smoke-x11|smoke-wayland|close-live|valgrind) args=(run "$choice") ;;
        *) args=("$choice") ;;
    esac
    if output="$(bash "$ROOT_DIR/run.sh" "${args[@]}" 2>&1)"; then
        printf '%s\n' "$output" | zenity --text-info --title='Completed / started' --width=800 --height=500 || true
    else
        printf '%s\n' "$output" | zenity --text-info --title='Error' --width=800 --height=500 || true
    fi
done
