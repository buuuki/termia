# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import GObject, Gtk, Vte

from .sidebar_projection import SidebarRow as RowObject
from .terminal_processes import TerminalProcess


@dataclass
class SignalConnections:
    """Own only our handlers, without keeping native emitters alive."""

    handlers: list[tuple[Callable, int]] = field(default_factory=list, repr=False)

    def connect(self, emitter: GObject.Object, signal: str, callback: Callable, *data) -> int:
        handler = emitter.connect(signal, callback, *data)
        self.handlers.append((emitter.weak_ref(), handler))
        return handler

    def disconnect(self) -> None:
        handlers, self.handlers = self.handlers, []
        for reference, handler in handlers:
            emitter = reference()
            if emitter is not None and emitter.handler_is_connected(handler):
                GObject.Object.disconnect(emitter, handler)


@dataclass
class TerminalPane:
    id: str
    terminal: Vte.Terminal
    container: Gtk.Widget
    status_label: Gtk.Label
    timer_label: Gtk.Label
    disconnect_button: Gtk.Button
    status_bar: Gtk.Widget
    title: str
    started_at: float
    server_id: str | None = None
    local_profile_id: str | None = None
    exit_handler_id: int | None = None
    exit_processed: bool = False
    child_pid: int | None = None
    child_process: TerminalProcess | None = None
    connected: bool = True
    disconnect_requested: bool = False
    pending_reconnect: bool = False
    duration_recorded: bool = False
    history_start_recorded: bool = False
    history_end_recorded: bool = False
    history_kind: str = ""
    history_started_at: str = ""
    history_title: str = ""
    history_server_name: str = ""
    history_host: str = ""
    history_user: str = ""
    history_port: int = 0
    ui_signals: SignalConnections = field(default_factory=SignalConnections, repr=False)
    retired: bool = False
    timer_generation: int = 0

    def release_exit_handler(self) -> None:
        if self.exit_handler_id is not None:
            if self.terminal.handler_is_connected(self.exit_handler_id):
                self.terminal.disconnect(self.exit_handler_id)
            self.exit_handler_id = None

    def retire(self) -> None:
        self.retired = True
        self.ui_signals.disconnect()
        # A live child still needs its final accounting callback.
        if self.child_process is None:
            self.release_exit_handler()


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
    local_profile_id: str | None = None
    detached_window: Gtk.Window | None = None
    child_pid: int | None = None
    child_process: TerminalProcess | None = None
    connected: bool = True
    disconnect_requested: bool = False
    pending_reconnect: bool = False
    duration_recorded: bool = False
    history_start_recorded: bool = False
    history_end_recorded: bool = False
    history_kind: str = ""
    history_started_at: str = ""
    history_title: str = ""
    history_server_name: str = ""
    history_host: str = ""
    history_user: str = ""
    history_port: int = 0
    split_terminals: list[Vte.Terminal] = field(default_factory=list)
    split_child_pids: dict[int, int] = field(default_factory=dict)
    split_processes: dict[int, TerminalProcess] = field(default_factory=dict)
    active_terminal_ids: set[int] = field(default_factory=set)
    panes: dict[int, TerminalPane] = field(default_factory=dict)

    def retire(self) -> None:
        signals = getattr(self.tab_label, "_termia_signals", None)
        if signals is not None:
            signals.disconnect()
        for pane in self.panes.values():
            pane.retire()

    def pane_for_terminal(self, terminal: Vte.Terminal) -> TerminalPane | None:
        return self.panes.get(id(terminal))

    def active_panes(self) -> tuple[TerminalPane, ...]:
        return tuple(
            pane
            for terminal_id, pane in self.panes.items()
            if terminal_id in self.active_terminal_ids
        )
