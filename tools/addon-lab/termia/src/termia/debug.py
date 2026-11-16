# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import faulthandler
import logging
import os
from pathlib import Path

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

from .constants import DEBUG_LOG_FILE

LOGGER = logging.getLogger("termia")
_GLIB_WRITER_CONFIGURED = False
_FAULT_HANDLER_CONFIGURED = False


def log_event(event: str, **fields: object) -> None:
    """Write a privacy-safe, machine-searchable application lifecycle event."""
    details = " ".join(f"{key}={value}" for key, value in sorted(fields.items()) if value is not None)
    LOGGER.debug("event=%s%s", event, f" {details}" if details else "")


def _write_glib_log(
    log_level: GLib.LogLevelFlags,
    fields: object,
    _n_fields: int,
    _user_data: object,
) -> GLib.LogWriterOutput:
    if LOGGER.disabled:
        return GLib.LogWriterOutput.UNHANDLED
    if log_level & (GLib.LogLevelFlags.LEVEL_ERROR | GLib.LogLevelFlags.LEVEL_CRITICAL):
        level = logging.ERROR
    elif log_level & GLib.LogLevelFlags.LEVEL_WARNING:
        level = logging.WARNING
    elif log_level & GLib.LogLevelFlags.LEVEL_DEBUG:
        level = logging.DEBUG
    else:
        level = logging.INFO
    try:
        message = GLib.log_writer_format_fields(log_level, fields, False).strip()
    except (TypeError, ValueError, UnicodeError) as exc:
        LOGGER.warning("Could not format GLib diagnostic: %s", exc)
        return GLib.LogWriterOutput.HANDLED
    if message and level >= logging.WARNING:
        LOGGER.log(level, "%s", message)
    return GLib.LogWriterOutput.HANDLED


def configure_debug_logging(enabled: bool) -> None:
    global _FAULT_HANDLER_CONFIGURED, _GLIB_WRITER_CONFIGURED
    if not enabled:
        if _FAULT_HANDLER_CONFIGURED and faulthandler.is_enabled():
            faulthandler.disable()
        _FAULT_HANDLER_CONFIGURED = False
        LOGGER.disabled = True
        for handler in LOGGER.handlers[:]:
            LOGGER.removeHandler(handler)
            handler.close()
        return
    LOGGER.disabled = False
    if LOGGER.handlers:
        return
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    try:
        DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(DEBUG_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
        faulthandler.enable(file=file_handler.stream, all_threads=True)
        _FAULT_HANDLER_CONFIGURED = True
        if not _GLIB_WRITER_CONFIGURED:
            GLib.log_set_writer_func(_write_glib_log, None)
            _GLIB_WRITER_CONFIGURED = True
    except OSError as exc:
        LOGGER.warning("Could not open debug log %s: %s", DEBUG_LOG_FILE, exc)
    LOGGER.info("Debug logging enabled")


def log_startup_context(*, lock_path: Path, data_path: Path, settings_path: Path, state_dir: Path) -> None:
    log_event(
        "application.started",
        pid=os.getpid(),
        parent_pid=os.getppid(),
        session_type=os.environ.get("XDG_SESSION_TYPE", "unknown"),
        gdk_backend=os.environ.get("GDK_BACKEND", "default"),
        gsk_renderer=os.environ.get("GSK_RENDERER", "default"),
        locations_configured=all((lock_path, data_path, settings_path, state_dir)),
    )


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
