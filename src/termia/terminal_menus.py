# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, GLib, Gtk, Vte

from .connection_utils import find_server
from .keybindings import keybinding_label
from .ui_state import TerminalSession


class TerminalMenusMixin:
    def on_terminal_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_autohide(True)
        popover.set_parent(terminal)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        active_submenu: dict[str, Gtk.Popover | None] = {"popover": None}
        popover.connect("closed", lambda *_args: self.close_active_terminal_submenu(active_submenu))
        self.add_context_menu_item(menu, self.t("disconnect"), lambda: self.disconnect_from_terminal_menu(popover, session))
        if not session.status_bar.get_visible():
            self.add_context_menu_item(
                menu, self.t("show_session_status_bar"), lambda: self.show_session_status_bar_from_menu(popover, session)
            )
        self.add_terminal_shortcut_menu_item(
            menu,
            self.t("copy"),
            self.store.data.app.keybindings.get("copy", ""),
            lambda: self.copy_terminal_selection(popover, terminal),
        )
        self.add_terminal_shortcut_menu_item(
            menu,
            self.t("paste"),
            self.store.data.app.keybindings.get("paste", ""),
            lambda: self.paste_terminal_clipboard(popover, terminal),
        )
        if session.server_id is not None:
            server = find_server(self.store.data.servers, session.server_id)
            if server is not None:
                self.add_context_menu_item(
                    menu,
                    self.t("send_files_to_server"),
                    lambda: self.on_send_files_to_server(popover, server),
                )
        self.add_context_menu_item(menu, self.t("configure_terminal"), lambda: self.configure_terminal_from_menu(popover))
        self.add_context_menu_item(menu, self.t("session_statistics"), lambda: self.show_session_statistics(popover, session))
        self.add_context_menu_separator(menu)
        self.add_terminal_split_menu(menu, popover, session, terminal, active_submenu)
        self.add_terminal_tab_menu(menu, popover, session, active_submenu)
        popover.set_child(menu)
        popover.popup()

    def add_terminal_shortcut_menu_item(
        self,
        menu: Gtk.ListBox,
        label_text: str,
        accelerator: str,
        callback: Any,
    ) -> None:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_hexpand(True)
        shortcut = Gtk.Label(label=keybinding_label(accelerator, self.t("keybinding_disabled")))
        shortcut.add_css_class("dim-label")
        shortcut.set_xalign(1)
        box.append(label)
        box.append(shortcut)
        row.set_child(box)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", lambda *_args: callback())
        row.add_controller(click)
        menu.append(row)

    def add_terminal_split_menu(
        self,
        menu: Gtk.ListBox,
        parent_popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
        active_submenu: dict[str, Gtk.Popover | None],
    ) -> None:
        submenu_items = [
            (self.t("split_up"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "up")),
            (self.t("split_down"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "down")),
            (self.t("split_right"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "right")),
            (self.t("split_left"), lambda: self.split_terminal_from_menu(parent_popover, session, terminal, "left")),
        ]
        self.add_terminal_nested_menu(menu, self.t("split"), submenu_items, active_submenu)

    def add_terminal_tab_menu(
        self,
        menu: Gtk.ListBox,
        parent_popover: Gtk.Popover,
        session: TerminalSession,
        active_submenu: dict[str, Gtk.Popover | None],
    ) -> None:
        submenu_items = [
            (self.t("rename_tab"), lambda: self.show_rename_tab_dialog(parent_popover, session)),
            (self.t("duplicate_tab"), lambda: self.duplicate_tab(parent_popover, session)),
            (self.t("new_tab"), lambda: self.new_tab_from_terminal_menu(parent_popover)),
            (self.t("close_tab"), lambda: self.close_tab_from_terminal_menu(parent_popover, session)),
        ]
        self.add_terminal_nested_menu(menu, self.t("tab"), submenu_items, active_submenu)

    def add_terminal_nested_menu(
        self,
        menu: Gtk.ListBox,
        label_text: str,
        submenu_items: list[tuple[str, Any]],
        active_submenu: dict[str, Gtk.Popover | None],
    ) -> None:
        # All terminal context-menu submenus must go through this helper so
        # hover/open/close behavior stays consistent when new submenus are added.
        row = Gtk.ListBoxRow()
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label_box.set_margin_top(8)
        label_box.set_margin_bottom(8)
        label_box.set_margin_start(12)
        label_box.set_margin_end(12)
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_hexpand(True)
        arrow = Gtk.Label(label=">")
        arrow.add_css_class("dim-label")
        label_box.append(label)
        label_box.append(arrow)
        row.set_child(label_box)

        submenu = Gtk.Popover()
        submenu.add_css_class("termia-menu-popover")
        submenu.set_has_arrow(False)
        submenu.set_autohide(False)
        submenu.set_position(Gtk.PositionType.RIGHT)
        submenu.set_parent(row)
        submenu_box = Gtk.ListBox()
        submenu_box.add_css_class("termia-menu-panel")
        submenu_box.set_selection_mode(Gtk.SelectionMode.NONE)
        submenu_box.set_margin_top(6)
        submenu_box.set_margin_bottom(6)
        submenu_box.set_margin_start(6)
        submenu_box.set_margin_end(6)
        for item_label, callback in submenu_items:
            self.add_context_menu_item(submenu_box, item_label, callback)
        submenu.set_child(submenu_box)

        row_motion = Gtk.EventControllerMotion.new()
        row_motion.connect("motion", lambda *_args: self.set_terminal_submenu_row_hover(active_submenu, submenu, True))
        row_motion.connect("leave", lambda *_args: self.set_terminal_submenu_row_hover(active_submenu, submenu, False))
        row.add_controller(row_motion)

        submenu_motion = Gtk.EventControllerMotion.new()
        submenu_motion.connect("motion", lambda *_args: self.set_terminal_submenu_panel_hover(active_submenu, submenu, True))
        submenu_motion.connect("leave", lambda *_args: self.set_terminal_submenu_panel_hover(active_submenu, submenu, False))
        submenu_box.add_controller(submenu_motion)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", lambda *_args: self.set_terminal_submenu_row_hover(active_submenu, submenu, True))
        row.add_controller(click)

        menu.append(row)

    def close_active_terminal_submenu(self, active_submenu: dict[str, Gtk.Popover | None]) -> None:
        close_id = active_submenu.get("close_id")
        if close_id is not None:
            GLib.source_remove(close_id)
            active_submenu["close_id"] = None
        submenu = active_submenu.get("popover")
        if submenu is not None:
            submenu.popdown()
        active_submenu["popover"] = None
        active_submenu["row_hover"] = False
        active_submenu["panel_hover"] = False

    def popup_terminal_submenu(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
    ) -> None:
        close_id = active_submenu.get("close_id")
        if close_id is not None:
            GLib.source_remove(close_id)
            active_submenu["close_id"] = None
        current = active_submenu.get("popover")
        if current is not submenu:
            if current is not None:
                current.popdown()
            active_submenu["popover"] = submenu
            active_submenu["row_hover"] = False
            active_submenu["panel_hover"] = False
        submenu.popup()

    def set_terminal_submenu_row_hover(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
        hovered: bool,
    ) -> None:
        if hovered:
            self.popup_terminal_submenu(active_submenu, submenu)
            active_submenu["row_hover"] = True
            return
        if active_submenu.get("popover") is submenu:
            active_submenu["row_hover"] = False
            self.schedule_terminal_submenu_close(active_submenu, submenu)

    def set_terminal_submenu_panel_hover(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
        hovered: bool,
    ) -> None:
        if hovered:
            self.popup_terminal_submenu(active_submenu, submenu)
            active_submenu["panel_hover"] = True
            return
        if active_submenu.get("popover") is submenu:
            active_submenu["panel_hover"] = False
            self.schedule_terminal_submenu_close(active_submenu, submenu)

    def schedule_terminal_submenu_close(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
    ) -> None:
        close_id = active_submenu.get("close_id")
        if close_id is not None:
            GLib.source_remove(close_id)
        active_submenu["close_id"] = GLib.timeout_add(
            120,
            self.close_terminal_submenu_if_inactive,
            active_submenu,
            submenu,
        )

    def close_terminal_submenu_if_inactive(
        self,
        active_submenu: dict[str, Gtk.Popover | None],
        submenu: Gtk.Popover,
    ) -> bool:
        active_submenu["close_id"] = None
        if active_submenu.get("popover") is not submenu:
            return GLib.SOURCE_REMOVE
        if active_submenu.get("row_hover") or active_submenu.get("panel_hover"):
            return GLib.SOURCE_REMOVE
        submenu.popdown()
        active_submenu["popover"] = None
        active_submenu["row_hover"] = False
        active_submenu["panel_hover"] = False
        return GLib.SOURCE_REMOVE
