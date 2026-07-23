# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

from .constants import (
    DEFAULT_TERMINAL_BACKGROUND,
    DEFAULT_TERMINAL_FONT_FAMILY,
    DEFAULT_TERMINAL_FOREGROUND,
    LEGACY_ANSI_PALETTE,
)
from .models import DEFAULT_ANSI_PALETTE, TerminalSettings

CURRENT_SCHEMA_VERSION = 1


def _add_schema_version(payload: dict[str, Any], kind: str) -> tuple[dict[str, Any], bool]:
    version = payload.get("schema_version", 0)
    if not isinstance(version, int) or version < 0:
        raise ValueError(f"{kind} payload has an invalid schema version.")
    if version > CURRENT_SCHEMA_VERSION:
        raise ValueError(f"{kind} payload uses an unsupported schema version: {version}.")
    migrated = dict(payload)
    changed = version != CURRENT_SCHEMA_VERSION
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
    return migrated, changed


def migrate_connections_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return _add_schema_version(payload, "Connections")


def migrate_settings_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return _add_schema_version(payload, "Settings")


def migrate_app_settings_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Rename the old sudo-labelled password shortcut settings."""
    migrated = dict(payload)
    changed = False
    aliases = {
        "sudo_password_shortcut": "send_password_shortcut",
        "sudo_password_enter": "send_password_enter",
    }
    for old_key, new_key in aliases.items():
        if old_key in migrated:
            migrated.setdefault(new_key, migrated[old_key])
            del migrated[old_key]
            changed = True
    return migrated, changed


def migrate_statistics_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return _add_schema_version(payload, "Statistics")


def migrate_history_event_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return _add_schema_version(payload, "History event")


def migrate_embedded_settings_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    embedded = {key: payload[key] for key in ("app", "terminal") if key in payload}
    if not embedded:
        return {}, False
    return migrate_settings_payload(embedded)


def migrate_embedded_statistics_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        return {}, False
    return migrate_statistics_payload(statistics)


def migrate_legacy_terminal_settings(terminal: TerminalSettings) -> tuple[TerminalSettings, bool]:
    changed = False
    if (
        terminal.font_family == "Ubuntu Mono"
        and terminal.font_size == 13
        and terminal.foreground == "#839496"
        and terminal.background == "#002b36"
    ):
        terminal.font_family = DEFAULT_TERMINAL_FONT_FAMILY
        terminal.foreground = DEFAULT_TERMINAL_FOREGROUND
        terminal.background = DEFAULT_TERMINAL_BACKGROUND
        changed = True
    if terminal.ansi_palette == LEGACY_ANSI_PALETTE:
        terminal.ansi_palette = DEFAULT_ANSI_PALETTE.copy()
        changed = True
    return terminal, changed
