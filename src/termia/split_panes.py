# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import GLib, Gtk, Vte

from .ui_state import TerminalSession


class SplitPaneController:
    def __init__(
        self,
        create_terminal: Callable[[TerminalSession], Vte.Terminal],
        wrap_terminal: Callable[[Vte.Terminal], Gtk.ScrolledWindow],
        replace_terminal: Callable[[Gtk.Widget, Gtk.Widget], bool],
    ) -> None:
        self.create_terminal = create_terminal
        self.wrap_terminal = wrap_terminal
        self.replace_terminal = replace_terminal

    def split_terminal(
        self,
        session: TerminalSession,
        terminal: Vte.Terminal,
        direction: str,
    ) -> Vte.Terminal | None:
        target = terminal.get_parent()
        if not isinstance(target, Gtk.Widget):
            return None

        new_terminal = self.create_terminal(session)
        new_scroller = self.wrap_terminal(new_terminal)
        orientation = Gtk.Orientation.HORIZONTAL if direction in {"left", "right"} else Gtk.Orientation.VERTICAL
        paned = Gtk.Paned(orientation=orientation)
        paned.add_css_class("termia-split-pane")
        paned.set_wide_handle(False)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        paned.set_resize_start_child(True)
        paned.set_resize_end_child(True)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)

        if not self.replace_terminal(target, paned):
            session.split_terminals.remove(new_terminal)
            session.active_terminal_ids.discard(id(new_terminal))
            return None

        if direction in {"left", "up"}:
            paned.set_start_child(new_scroller)
            paned.set_end_child(target)
        else:
            paned.set_start_child(target)
            paned.set_end_child(new_scroller)

        def center_split() -> bool:
            size = paned.get_width() if orientation == Gtk.Orientation.HORIZONTAL else paned.get_height()
            if size > 0:
                paned.set_position(size // 2)
            new_terminal.grab_focus()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(80, center_split)
        return new_terminal
