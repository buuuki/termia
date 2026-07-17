#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COPY_CURRENT_CONFIG=0
FRESH_INSTANCE=0
PROFILE_NAME="test-instance"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --copy-current-config)
            COPY_CURRENT_CONFIG=1
            ;;
        --fresh)
            FRESH_INSTANCE=1
            ;;
        --help|-h)
            echo "Usage: $0 [--copy-current-config] [--fresh] [profile-name]"
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
        *)
            PROFILE_NAME="$1"
            ;;
    esac
    shift
done

if [ "${FRESH_INSTANCE}" -eq 1 ]; then
    DATA_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/termia-${USER:-user}-${PROFILE_NAME}.XXXXXX")"
else
    DATA_ROOT="${TERMIA_TEST_DATA_DIR:-${TMPDIR:-/tmp}/termia-${USER:-user}-${PROFILE_NAME}}"
fi

mkdir -p "${DATA_ROOT}/config" "${DATA_ROOT}/state"

if [ "${COPY_CURRENT_CONFIG}" -eq 1 ]; then
    SOURCE_CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/termia"
    TARGET_CONFIG_DIR="${DATA_ROOT}/config/termia"
    mkdir -p "${TARGET_CONFIG_DIR}"
    for CONFIG_FILE in connections.json settings.json; do
        if [ -f "${SOURCE_CONFIG_DIR}/${CONFIG_FILE}" ]; then
            cp "${SOURCE_CONFIG_DIR}/${CONFIG_FILE}" "${TARGET_CONFIG_DIR}/${CONFIG_FILE}"
        fi
    done
fi

echo "Starting Termia test instance"
echo "Profile: ${PROFILE_NAME}"
echo "Config:  ${DATA_ROOT}/config/termia"
echo "State:   ${DATA_ROOT}/state/termia"
echo "Fresh:   $([ "${FRESH_INSTANCE}" -eq 1 ] && echo enabled || echo disabled)"
echo "Copy:    current config $([ "${COPY_CURRENT_CONFIG}" -eq 1 ] && echo enabled || echo disabled)"
echo "Debug:   PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1 G_ENABLE_DIAGNOSTIC=1 G_MESSAGES_DEBUG=all"
echo "PID:     $$"

cd "${REPO_ROOT}"
exec env \
    XDG_CONFIG_HOME="${DATA_ROOT}/config" \
    XDG_STATE_HOME="${DATA_ROOT}/state" \
    PYTHONFAULTHANDLER="${PYTHONFAULTHANDLER:-1}" \
    PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}" \
    G_ENABLE_DIAGNOSTIC="${G_ENABLE_DIAGNOSTIC:-1}" \
    G_MESSAGES_DEBUG="${G_MESSAGES_DEBUG:-all}" \
    python3 run_termia.py
