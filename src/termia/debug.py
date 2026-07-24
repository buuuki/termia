# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
import os
from pathlib import Path

from .constants import DEBUG_LOG_FILE

LOGGER = logging.getLogger("termia")


def configure_debug_logging(enabled: bool) -> None:
    if not enabled:
        LOGGER.disabled = True
        for handler in LOGGER.handlers[:]:
            LOGGER.removeHandler(handler)
            handler.close()
        return
    LOGGER.disabled = False
    if LOGGER.handlers:
        return
    os.environ.setdefault("PYTHONFAULTHANDLER", "1")
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(DEBUG_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
    except OSError as exc:
        LOGGER.warning("Could not open debug log %s: %s", DEBUG_LOG_FILE, exc)
    LOGGER.info("Debug logging enabled")


def log_startup_context(*, lock_path: Path, data_path: Path, settings_path: Path, state_dir: Path) -> None:
    LOGGER.debug("PID=%s PPID=%s", os.getpid(), os.getppid())
    LOGGER.debug("XDG_SESSION_TYPE=%s", os.environ.get("XDG_SESSION_TYPE", ""))
    LOGGER.debug("GDK_BACKEND=%s GSK_RENDERER=%s", os.environ.get("GDK_BACKEND", ""), os.environ.get("GSK_RENDERER", ""))
    LOGGER.debug("lock_path=%s data_path=%s settings_path=%s state_dir=%s", lock_path, data_path, settings_path, state_dir)


def log_lock_failure(path: Path, reason: str) -> None:
    LOGGER.debug("lock_acquisition_failed path=%s reason=%s", path, reason)


def log_store_state(store: object) -> None:
    app = getattr(getattr(store, "data", None), "app", None)
    LOGGER.debug(
        "store_state read_only=%s encryption_locked=%s storage_mode=%s recovery_messages=%s",
        getattr(store, "read_only", None),
        getattr(store, "encryption_locked", None),
        getattr(app, "connection_storage_mode", None),
        len(getattr(store, "recovery_messages", [])),
    )
