# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import GObject, Gtk, Vte


class RowObject(GObject.Object):
    def __init__(self, kind: str, item_id: str, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.kind = kind
        self.item_id = item_id
        self.title = title
        self.subtitle = subtitle


@dataclass
class TerminalSession:
    id: str
    server_id: str | None
    title: str
    terminal: Vte.Terminal
    page: Gtk.Widget
    tab_label: Gtk.Widget
    status_label: Gtk.Label
    timer_label: Gtk.Label
    disconnect_button: Gtk.Button
    status_bar: Gtk.Widget
    started_at: float
    title_locked: bool = False
    last_directory_title: str = ""
    detached_window: Gtk.Window | None = None
    timeout_id: int | None = None
    child_pid: int | None = None
    connected: bool = True
    disconnect_requested: bool = False
    pending_reconnect: bool = False
    duration_recorded: bool = False
