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


def _configure_submenu_dismissal(popover: Gtk.PopoverMenu) -> None:
    """Let the main menu own dismissal while preserving submenu keyboard focus."""
    def configure_submenu_focus(panel: Gtk.Popover) -> None:
        focus_root: Gtk.Window | None = None
        focus_handler: int | None = None

        def focus_changed(root, _pspec) -> None:
            focused = root.get_focus()
            if focused is None or not focused.is_ancestor(panel):
                return

            def clear_stale_selection(widget: Gtk.Widget) -> None:
                if widget.get_css_name() == "modelbutton":
                    if widget is not focused and not focused.is_ancestor(widget):
                        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
                    return
                child = widget.get_first_child()
                while child is not None:
                    clear_stale_selection(child)
                    child = child.get_next_sibling()

            # GTK's pointer-selected item can outlive keyboard focus on it.
            clear_stale_selection(panel)

        def clear_highlight() -> bool:
            if panel.get_visible():
                _clear_initial_menu_selection(panel)
            return GLib.SOURCE_REMOVE

        def mapped(_panel) -> None:
            nonlocal focus_root, focus_handler
            focus_root = panel.get_root()
            if isinstance(focus_root, Gtk.Window):
                focus_handler = focus_root.connect("notify::focus-widget", focus_changed)
                focused = focus_root.get_focus()
                if focused is None or not focused.is_ancestor(panel):
                    panel.child_focus(Gtk.DirectionType.TAB_FORWARD)
            GLib.idle_add(clear_highlight)

        def unmapped(_panel) -> None:
            nonlocal focus_root, focus_handler
            if focus_root is not None and focus_handler is not None:
                focus_root.disconnect(focus_handler)
            focus_root = None
            focus_handler = None

        panel.connect("map", mapped)
        panel.connect("unmap", unmapped)

    def restore_parent_focus(panel: Gtk.Popover) -> None:
        parent = panel.get_parent()
        root = parent.get_ancestor(Gtk.Popover) if parent is not None else None
        if root is not None and root.get_visible():
            parent.grab_focus()

    def watch_submenu(panel: Gtk.Popover) -> None:
        hovered: set[Gtk.Widget] = set()
        pending: int | None = None

        def cancel_pending(*_args) -> None:
            nonlocal pending
            if pending is not None:
                GLib.source_remove(pending)
                pending = None
            hovered.clear()

        def changed(_controller, entered: bool, widget: Gtk.Widget) -> None:
            nonlocal pending
            if entered:
                hovered.add(widget)
            else:
                hovered.discard(widget)
            if pending is not None:
                GLib.source_remove(pending)
                pending = None
            if not hovered and panel.get_visible() and popover.get_visible():
                def close_if_outside() -> bool:
                    nonlocal pending
                    pending = None
                    if not hovered and popover.get_visible():
                        panel.popdown()
                    return GLib.SOURCE_REMOVE

                # Allow crossing the gap between the row and its native panel.
                pending = GLib.timeout_add(120, close_if_outside)

        for widget in (panel.get_parent(), panel):
            if widget is None:
                continue
            motion = Gtk.EventControllerMotion()
            motion.set_name("termia-main-submenu-leave")
            motion.connect("enter", lambda source, _x, _y, target: changed(source, True, target), widget)
            motion.connect("leave", lambda source, target: changed(source, False, target), widget)
            widget.add_controller(motion)
        panel.connect("closed", cancel_pending)
        popover.connect("closed", cancel_pending)

    def visit(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Popover) and widget is not popover:
            widget.set_has_arrow(True)
            # A separate grab can leave the root open after this panel closes.
            widget.set_autohide(False)
            configure_submenu_focus(widget)
            widget.connect("closed", restore_parent_focus)
            watch_submenu(widget)
        child = widget.get_first_child()
        while child is not None:
            visit(child)
            child = child.get_next_sibling()

    visit(popover)


class MainMenuMixin:
    POPOVER_CALLBACK_DELAY_MS = 100

    def build_main_menu(
        self, actions: MainMenuActions, *, write_allowed: bool
    ) -> Gtk.PopoverMenu:
        """Present injected commands without accessing stores or feature implementations."""
        model = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        popover = Gtk.PopoverMenu.new_from_model_full(model, Gtk.PopoverMenuFlags.NESTED)
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(True)
        popover.set_cascade_popdown(False)

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
        _configure_submenu_dismissal(popover)
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
