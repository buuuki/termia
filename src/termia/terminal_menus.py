# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Vte

from .connection_utils import find_server
from .keybindings import keybinding_accelerator
from .terminal_menu_actions import (
    TerminalMenuActions,
    status_bar_action_label_key,
)
from .ui_state import TerminalSession


class TerminalMenusMixin:
    def on_terminal_right_click(
        self, _gesture: Gtk.GestureClick, _n_press: int, x: float, y: float,
        session: TerminalSession, terminal: Vte.Terminal,
    ) -> None:
        pane = session.pane_for_terminal(terminal)
        window = terminal.get_root()
        if pane is None or not isinstance(window, Gtk.Window):
            return
        valid, point = terminal.compute_point(window.get_child(), Graphene.Point().init(x, y))
        if not valid or self.session_registry.get(session.id) is not session:
            return
        terminal.grab_focus()
        menus = getattr(self, "_terminal_context_menus", None)
        if menus is None:
            menus = self._terminal_context_menus = {}
        popover = menus.get(window)
        if popover is None:
            popover = Gtk.PopoverMenu.new_from_model_full(Gio.Menu(), Gtk.PopoverMenuFlags.NESTED)
            popover.add_css_class("termia-menu-popover")
            popover.set_has_arrow(False)
            popover.set_cascade_popdown(False)
            popover.set_parent(window.get_child())
            popover.connect("closed", self.on_native_terminal_menu_closed)
            menus[window] = popover
            window.connect("destroy", self.on_terminal_context_window_destroy)
        popover.popdown()
        actions: TerminalMenuActions = self.terminal_menu_actions
        target = (session, terminal, pane, window)
        popover._termia_target = target
        group = Gio.SimpleActionGroup()
        menu = Gio.Menu()

        def add(model, name, label, callback, accelerator=""):
            action = Gio.SimpleAction.new(name, None)

            def activate(_action, _parameter):
                if getattr(popover, "_termia_target", None) is not target:
                    return
                popover._termia_target = None
                popover.popdown()

                def dispatch():
                    if (
                        self.session_registry.get(session.id) is session
                        and session.pane_for_terminal(terminal) is pane
                        and terminal.get_root() is window and window.get_visible()
                        and not getattr(self, "shutdown_in_progress", False)
                    ):
                        callback()
                    return GLib.SOURCE_REMOVE

                GLib.timeout_add(100, dispatch)

            action.connect("activate", activate)
            group.add_action(action)
            item = Gio.MenuItem.new(self.t(label), f"terminal-menu.{name}")
            accelerator = keybinding_accelerator(accelerator)
            if accelerator:
                item.set_attribute_value("accel", GLib.Variant("s", accelerator))
            model.append_item(item)

        add(menu, "disconnect", "disconnect", lambda: actions.disconnect(popover, session, terminal))
        add(menu, "status", status_bar_action_label_key(pane.status_bar.get_visible()),
            lambda: actions.toggle_status_bar(popover, session, terminal))
        if session.detached_window is not None:
            add(menu, "reattach", "reattach_tab", lambda: actions.reattach_tab(popover, session))
        add(menu, "copy", "copy", lambda: actions.copy(popover, terminal),
            self.store.data.app.keybindings.get("copy", ""))
        add(menu, "paste", "paste", lambda: actions.paste(popover, terminal),
            self.store.data.app.keybindings.get("paste", ""))
        server_id = pane.server_id
        if server_id is not None and find_server(self.store.data.servers, server_id) is not None:
            def server_action(callback):
                server = find_server(self.store.data.servers, server_id)
                if server is not None:
                    callback(popover, session, server)

            if actions.browse_files is not None:
                add(menu, "sftp", "sftp_browse", lambda: server_action(actions.browse_files))
            add(menu, "send", "send_files_to_server", lambda: server_action(actions.send_files))
        if actions.run_snippet is not None:
            add(menu, "snippet", "run_snippet", lambda: actions.run_snippet(popover, session, terminal))
        add(menu, "configure", "configure_terminal", lambda: actions.configure(popover, session))
        if actions.session_statistics is not None:
            add(menu, "statistics", "session_statistics",
                lambda: actions.session_statistics(popover, session, terminal))
        section = Gio.Menu()
        split = Gio.Menu()
        for direction in ("up", "down", "right", "left"):
            add(split, f"split-{direction}", f"split_{direction}",
                lambda value=direction: actions.split(popover, session, terminal, value))
        add(split, "split-connection", "open_connection_in_split",
            lambda: actions.split_connection(popover, session, terminal))
        section.append_submenu(self.t("split"), split)
        tab = Gio.Menu()
        for name, label, callback in (
            ("rename", "rename_tab", lambda: actions.rename_tab(popover, session)),
            ("duplicate", "duplicate_tab", lambda: actions.duplicate_tab(popover, session)),
            ("new", "new_tab", lambda: actions.new_tab(popover)),
        ):
            accelerator = (
                self.store.data.app.keybindings.get("new_local_terminal", "")
                if name == "new" else ""
            )
            add(tab, name, label, callback, accelerator)
        add(tab, "close", "close_tab", lambda: actions.close_tab(popover, session))
        section.append_submenu(self.t("tab"), tab)
        menu.append_section(None, section)
        popover.insert_action_group("terminal-menu", group)
        popover.set_menu_model(menu)
        self.configure_terminal_submenu_leave(popover)
        rect = Gdk.Rectangle()
        rect.x, rect.y = int(point.x), int(point.y)
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

    def on_native_terminal_menu_closed(self, popover: Gtk.PopoverMenu) -> None:
        pending = getattr(popover, "_termia_leave_id", None)
        if pending is not None:
            GLib.source_remove(pending)
            popover._termia_leave_id = None
        target = getattr(popover, "_termia_target", None)

        def clear_target():
            if popover.get_visible():
                return GLib.SOURCE_REMOVE
            if getattr(popover, "_termia_target", None) is target:
                popover._termia_target = None
            if not popover.get_visible() and getattr(popover, "_termia_target", None) is None:
                # Hidden menus must not retain closed sessions via callbacks.
                popover.insert_action_group("terminal-menu", None)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(clear_target)

    def configure_terminal_submenu_leave(self, popover: Gtk.PopoverMenu) -> None:
        """Keep Termia's leave-to-close behavior around native nested menus."""
        hovered = set()
        popover._termia_hovered = hovered
        panels = []

        def changed(_controller, entered, widget):
            if entered:
                hovered.add(widget)
            else:
                hovered.discard(widget)
            pending = getattr(popover, "_termia_leave_id", None)
            if pending is not None:
                GLib.source_remove(pending)
                popover._termia_leave_id = None
            if not hovered and popover.get_visible():
                def close_if_outside():
                    popover._termia_leave_id = None
                    if getattr(popover, "_termia_hovered", None) is hovered and not hovered:
                        for panel in panels:
                            panel.popdown()
                        # Closing a nested popover leaves GTK's pointer grab on
                        # the old menu; refresh the root to restore autohide.
                        popover.popdown()
                        popover.popup()
                    return GLib.SOURCE_REMOVE

                popover._termia_leave_id = GLib.timeout_add(120, close_if_outside)

        def watch(widget):
            controller = Gtk.EventControllerMotion()
            controller.set_name("termia-submenu-leave")
            controller.connect("enter", lambda source, _x, _y: changed(source, True, widget))
            controller.connect("leave", lambda source: changed(source, False, widget))
            widget.add_controller(controller)

        def visit(widget):
            if isinstance(widget, Gtk.Popover) and widget is not popover:
                panels.append(widget)
                watch(widget)
            elif isinstance(widget, Gtk.Label) and widget.get_label() in {self.t("split"), self.t("tab")}:
                watch(widget.get_parent())
            child = widget.get_first_child()
            while child is not None:
                visit(child)
                child = child.get_next_sibling()

        visit(popover)

    def dispose_terminal_context_menu(self, window: Gtk.Window) -> None:
        popover = getattr(self, "_terminal_context_menus", {}).pop(window, None)
        if popover is not None:
            popover._termia_target = None
            popover.popdown()
            popover.insert_action_group("terminal-menu", None)
            if popover.get_parent() is not None:
                popover.unparent()

    def on_terminal_context_window_destroy(self, window: Gtk.Window) -> None:
        self.dispose_terminal_context_menu(window)
