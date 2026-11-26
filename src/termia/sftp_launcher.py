# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Host SFTP entry point, independent of terminal-session orchestration."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .sftp_connection import SFTPConnection
from .sftp_service import Endpoint
from .transfer_lifecycle import ManagedTransfer


class SFTPTool:
    def __init__(
        self,
        session_exists: Callable[[str], bool],
        is_shutting_down: Callable[[], bool],
        register_transfer: Callable[[ManagedTransfer], None],
        unregister_transfer: Callable[[ManagedTransfer], None],
        translate: Callable[[str], str],
    ) -> None:
        self.session_exists = session_exists
        self.is_shutting_down = is_shutting_down
        self.register_transfer = register_transfer
        self.unregister_transfer = unregister_transfer
        self.translate = translate
        self.transfers: set[ManagedTransfer] = set()

    def forget(self, transfer: ManagedTransfer) -> None:
        self.transfers.discard(transfer)
        self.unregister_transfer(transfer)

    def cancel_all(self) -> None:
        for transfer in tuple(self.transfers):
            transfer.cancel_active_transfer(close_dialog=True)

    def browse(
        self,
        popover: Gtk.Popover,
        parent: Gtk.Window,
        owner_id: str | None,
        endpoint: Endpoint,
        title: str,
        get_view: Callable[[], Callable | None],
    ) -> None:
        popover.popdown()

        def open_window() -> bool:
            if self.is_shutting_down():
                return GLib.SOURCE_REMOVE
            if owner_id is not None and not self.session_exists(owner_id):
                return GLib.SOURCE_REMOVE
            create_view = get_view()
            if create_view is None:
                return GLib.SOURCE_REMOVE
            window = create_view(
                parent,
                SFTPConnection(endpoint).explorer(),
                title,
                self.translate,
                self.forget,
                owner_id,
            )
            self.transfers.add(window)
            self.register_transfer(window)
            window.present()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(open_window)
