# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bundled SFTP entry point, independent of terminal-session orchestration."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .models import Server
from .sftp_service import Endpoint
from .transfer_lifecycle import ManagedTransfer
from .ui_state import TerminalSession


class SFTPTool:
    def __init__(
        self,
        parent_for_session: Callable[[TerminalSession | None], Gtk.Window],
        session_exists: Callable[[str], bool],
        is_shutting_down: Callable[[], bool],
        register_transfer: Callable[[ManagedTransfer], None],
        unregister_transfer: Callable[[ManagedTransfer], None],
        translate: Callable[[str], str],
    ) -> None:
        self.parent_for_session = parent_for_session
        self.session_exists = session_exists
        self.is_shutting_down = is_shutting_down
        self.register_transfer = register_transfer
        self.unregister_transfer = unregister_transfer
        self.translate = translate

    def browse(
        self,
        popover: Gtk.Popover,
        session: TerminalSession | None,
        server: Server,
    ) -> None:
        popover.popdown()
        parent = self.parent_for_session(session)
        endpoint = Endpoint(server.host, server.port, server.user, server.public_key, server.password)

        def open_window() -> bool:
            if self.is_shutting_down():
                return GLib.SOURCE_REMOVE
            if session is not None and not self.session_exists(session.id):
                return GLib.SOURCE_REMOVE
            from .sftp_view import SFTPWindow

            window = SFTPWindow(
                parent,
                endpoint,
                server.name,
                self.translate,
                self.unregister_transfer,
                session.id if session is not None else None,
            )
            self.register_transfer(window)
            window.present()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(open_window)
