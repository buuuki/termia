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
from .keybindings import DEFAULT_KEYBINDINGS, normalize_keybinding
from .models import DEFAULT_ANSI_PALETTE, TerminalSettings

CURRENT_SCHEMA_VERSION = 1
CURRENT_CONNECTIONS_SCHEMA_VERSION = 4


def _add_schema_version(
    payload: dict[str, Any],
    kind: str,
    current_version: int = CURRENT_SCHEMA_VERSION,
) -> tuple[dict[str, Any], bool]:
    version = payload.get("schema_version", 0)
    if not isinstance(version, int) or version < 0:
        raise ValueError(f"{kind} payload has an invalid schema version.")
    if version > current_version:
        raise ValueError(f"{kind} payload uses an unsupported schema version: {version}.")
    migrated = dict(payload)
    changed = version != current_version
    migrated["schema_version"] = current_version
    return migrated, changed


def migrate_connections_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated, changed = _add_schema_version(
        payload,
        "Connections",
        CURRENT_CONNECTIONS_SCHEMA_VERSION,
    )
    if "snippets" not in migrated:
        migrated["snippets"] = []
        changed = True
    if "snippet_categories" not in migrated:
        migrated["snippet_categories"] = []
        changed = True
    servers = migrated.get("servers")
    if isinstance(servers, list):
        for server in servers:
            if isinstance(server, dict) and "command_on_start" not in server:
                server["command_on_start"] = ""
                changed = True
    profiles = migrated.get("local_terminals")
    if isinstance(profiles, list):
        for profile in profiles:
            if isinstance(profile, dict) and "password" not in profile:
                profile["password"] = ""
                changed = True
    return migrated, changed


def migrate_settings_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return _add_schema_version(payload, "Settings")


def migrate_app_settings_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Migrate legacy preference names and split-focus shortcut defaults."""
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
    if migrated.get("split_focus_shortcuts_version", 0) == 0:
        bindings = migrated.get("keybindings")
        if isinstance(bindings, dict):
            bindings = dict(bindings)
            for direction in ("left", "right", "up", "down"):
                action = f"focus_split_{direction}"
                previous = f"Ctrl+{direction.title()}"
                current = bindings.get(action)
                if action in bindings and (
                    not isinstance(current, str) or normalize_keybinding(current) != previous
                ):
                    continue
                replacement = DEFAULT_KEYBINDINGS[action]
                occupied = any(
                    other != action and isinstance(value, str)
                    and normalize_keybinding(value) == replacement
                    for other, value in bindings.items()
                )
                if not occupied:
                    bindings[action] = replacement
                elif action not in bindings:
                    # Do not introduce a default that conflicts with a custom action.
                    bindings[action] = ""
            migrated["keybindings"] = bindings
        migrated["split_focus_shortcuts_version"] = 1
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
