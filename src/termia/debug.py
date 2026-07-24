# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
import os
from pathlib import Path

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from .constants import DEBUG_LOG_FILE

LOGGER = logging.getLogger("termia")
_GLIB_WRITER_CONFIGURED = False


def _glib_field(fields: object, key: str) -> str | None:
    if isinstance(fields, dict):
        value = fields.get(key)
        return str(value) if value is not None else None
    for field in fields:  # type: ignore[union-attr]
        if field.key == key:
            value = field.value
            return value.decode() if isinstance(value, bytes) else str(value)
    return None


def _write_glib_log(
    log_level: GLib.LogLevelFlags,
    fields: object,
    _n_fields: int,
    _user_data: object,
) -> GLib.LogWriterOutput:
    message = _glib_field(fields, "MESSAGE")
    if not message:
        return GLib.LogWriterOutput.UNHANDLED
    if log_level & (GLib.LogLevelFlags.LEVEL_ERROR | GLib.LogLevelFlags.LEVEL_CRITICAL):
        level = logging.ERROR
    elif log_level & GLib.LogLevelFlags.LEVEL_WARNING:
        level = logging.WARNING
    elif log_level & GLib.LogLevelFlags.LEVEL_DEBUG:
        level = logging.DEBUG
    else:
        level = logging.INFO
    domain = _glib_field(fields, "GLIB_DOMAIN") or "GLib"
    LOGGER.log(level, "[%s] %s", domain, message)
    return GLib.LogWriterOutput.HANDLED


def configure_debug_logging(enabled: bool) -> None:
    global _GLIB_WRITER_CONFIGURED
    if not enabled:
        LOGGER.disabled = True
        for handler in LOGGER.handlers[:]:
            LOGGER.removeHandler(handler)
            handler.close()
        return
    LOGGER.disabled = False
    if LOGGER.handlers:
        return
    os.environ.setdefault("G_MESSAGES_DEBUG", "all")
    os.environ.setdefault("GSK_DEBUG", "renderer")
    os.environ.setdefault("PYTHONFAULTHANDLER", "1")
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(DEBUG_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
        if not _GLIB_WRITER_CONFIGURED:
            GLib.log_set_writer_func(_write_glib_log, None)
            _GLIB_WRITER_CONFIGURED = True
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
