#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PROFILE_NAME="${1:-test-instance}"
DATA_ROOT="${TERMIA_TEST_DATA_DIR:-${TMPDIR:-/tmp}/termia-${USER:-user}-${PROFILE_NAME}}"

mkdir -p "${DATA_ROOT}/config" "${DATA_ROOT}/state"

echo "Starting Termia test instance"
echo "Profile: ${PROFILE_NAME}"
echo "Config:  ${DATA_ROOT}/config/termia"
echo "State:   ${DATA_ROOT}/state/termia"
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
