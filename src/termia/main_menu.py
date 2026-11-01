# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from . import __version__
from .constants import ABOUT_IMAGE, ISSUES_URL
from .dialog_actions import add_dialog_action_button as add_shared_dialog_action_button
from .dialog_window import DialogWindow
from .keybindings import KEYBINDING_ACTIONS, keybinding_label
from .main_menu_actions import MainMenuActions


def _clear_initial_menu_selection(widget: Gtk.Widget) -> bool:
    """Clear the initial native menu highlight once, preserving later navigation."""
    if widget.get_css_name() == "modelbutton":
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
        return GLib.SOURCE_REMOVE
    child = widget.get_first_child()
    while child is not None:
        if child.get_css_name() == "modelbutton":
            child.unset_state_flags(Gtk.StateFlags.SELECTED)
            return GLib.SOURCE_REMOVE
        _clear_initial_menu_selection(child)
        child = child.get_next_sibling()
    return GLib.SOURCE_REMOVE


class MainMenuMixin:
    POPOVER_CALLBACK_DELAY_MS = 100

    def build_main_menu(
        self, actions: MainMenuActions, *, write_allowed: bool
    ) -> Gtk.PopoverMenu:
        """Present injected commands without accessing stores or feature implementations."""
        model = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(True)

        def append_command(
            menu: Gio.Menu, label: str, name: str, *, requires_write: bool = False
        ) -> None:
            callback = getattr(actions, name)
            if callback is None:
                return
            action = Gio.SimpleAction.new(name, None)
            action.set_enabled(write_allowed or not requires_write)
            action.connect(
                "activate",
                lambda _action, _parameter: self.run_action_after_popover_closed(
                    popover, callback
                ),
            )
            action_group.add_action(action)
            menu.append(self.t(label), f"main-menu.{name}")

        preferences = Gio.Menu()
        for label, name in (
            ("general", "general_preferences"),
            ("terminal", "terminal_settings"),
            ("keybindings", "keybinding_settings"),
            ("security", "security_settings"),
        ):
            append_command(preferences, label, name, requires_write=True)
        append_command(preferences, "optional_tools", "optional_tools")
        model.append_section(None, preferences)

        tools = Gio.Menu()
        append_command(tools, "manage_snippets", "manage_snippets", requires_write=True)
        append_command(tools, "manage_notes", "manage_notes")
        append_command(tools, "statistics", "statistics")
        append_command(tools, "connection_history", "connection_history")
        model.append_section(None, tools)

        data = Gio.Menu()
        append_command(data, "data_locations", "data_locations")
        connections = Gio.Menu()
        append_command(connections, "export_config", "export_config")
        append_command(connections, "import_config", "import_config", requires_write=True)
        append_command(
            connections, "import_asbru", "import_asbru_config", requires_write=True
        )
        append_command(connections, "clear_config", "clear_config", requires_write=True)
        data.append_submenu(self.t("connections_file"), connections)
        model.append_section(None, data)

        help_menu = Gio.Menu()
        append_command(help_menu, "help", "help")
        append_command(help_menu, "about", "about")
        model.append_section(None, help_menu)

        popover.insert_action_group("main-menu", action_group)
        popover.set_menu_model(model)
        popover.connect("show", lambda source: GLib.idle_add(_clear_initial_menu_selection, source))
        popover.connect("closed", lambda *_args: self.reset_main_menu(popover))
        return popover

    def reset_main_menu(self, popover: Gtk.PopoverMenu) -> None:
        popover.set_property("visible-submenu", "main")

    def run_action_after_popover_closed(
        self,
        popover: Gtk.Popover,
        callback: Callable[[], None],
    ) -> None:
        popover.popdown()

        def run_callback() -> bool:
            callback()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(self.POPOVER_CALLBACK_DELAY_MS, run_callback)

    def add_dialog_action_button(
        self, dialog: DialogWindow, label: str, response: Gtk.ResponseType
    ) -> Gtk.Button:
        return add_shared_dialog_action_button(
            dialog, label, response,
        )

    def add_dialog_action_buttons(
        self, dialog: DialogWindow, confirm_label: str, confirm_response: Gtk.ResponseType = Gtk.ResponseType.OK
    ) -> tuple[Gtk.Button, Gtk.Button]:
        cancel = self.add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
        confirm = self.add_dialog_action_button(dialog, confirm_label, confirm_response)
        return cancel, confirm

    def on_help(self, _button: Gtk.Button) -> None:
        dialog = DialogWindow(title=self.t("help_title"), transient_for=self, modal=True)
        dialog.set_default_size(760, 620)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE)
        dialog.connect("response", lambda source, _response: source.destroy())

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        sections = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

        def add_section(title_key: str, body_key: str) -> None:
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            title = Gtk.Label(label=self.t(title_key), xalign=0, wrap=True)
            title.add_css_class("heading")
            section.append(title)
            body = Gtk.Label(label=self.t(body_key), xalign=0, wrap=True, selectable=True)
            body.set_max_width_chars(80)
            section.append(body)
            sections.append(section)

        for title_key, body_key in (
            ("help_start", "help_start_body"),
            ("help_terminals", "help_terminals_body"),
            ("workspaces", "help_workspaces_body"),
            ("manage_notes", "help_notes_body"),
            ("manage_snippets", "help_snippets_body"),
            ("optional_tools", "help_addons_body"),
            ("security", "help_security_body"),
            ("update_title", "help_updates_body"),
        ):
            add_section(title_key, body_key)
        add_section("help_shortcuts", "help_shortcuts_body")
        shortcuts = Gtk.Grid(column_spacing=24, row_spacing=8)
        for row, (action, label_key) in enumerate(KEYBINDING_ACTIONS):
            name = Gtk.Label(label=self.t(label_key), xalign=0, wrap=True, hexpand=True)
            value = Gtk.Label(
                label=keybinding_label(
                    self.store.data.app.keybindings.get(action, ""), self.t("keybinding_disabled")
                ),
                xalign=0, selectable=True,
            )
            value.add_css_class("monospace")
            shortcuts.attach(name, 0, row, 1, 1)
            shortcuts.attach(value, 1, row, 1, 1)
        sections.append(shortcuts)
        scroller.set_child(sections)
        content.append(scroller)
        dialog.present()

    def on_about(self, _button: Gtk.Button) -> None:
        dialog = Gtk.AboutDialog(modal=False)
        dialog.set_program_name("Termia")
        dialog.set_version(__version__)
        dialog.set_copyright("Copyright © 2026 Jordi Pons")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.set_comments(self.t("about_content"))
        dialog.set_website(ISSUES_URL)
        dialog.set_website_label(self.t("report_issue"))
        if ABOUT_IMAGE.exists():
            dialog.set_logo(Gdk.Texture.new_from_filename(str(ABOUT_IMAGE)))
        from .update_view import attach_updates
        attach_updates(dialog, self.t)
        dialog.present()
        GLib.idle_add(self.clear_about_dialog_selection, dialog)

    def clear_about_dialog_selection(self, widget: Gtk.Widget) -> bool:
        if isinstance(widget, Gtk.Label):
            widget.set_selectable(False)
        child = widget.get_first_child()
        while child is not None:
            self.clear_about_dialog_selection(child)
            child = child.get_next_sibling()
        return GLib.SOURCE_REMOVE
