# SPDX-FileCopyrightText: 2026 Jordi Pons
# Copyright (C) 2026 Jordi Pons
# This file is distributed under the terms of the GNU General Public License.
from __future__ import annotations

import gi

gi.require_version("Vte", "3.91")
from gi.repository import GLib, Vte


def spawn_terminal_process(
    terminal: Vte.Terminal,
    working_directory: str | None,
    command: list[str],
    environment: list[str],
) -> int:
    _ok, child_pid = terminal.spawn_sync(
        Vte.PtyFlags.DEFAULT,
        working_directory,
        command,
        environment,
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        None,
    )
    return child_pid
