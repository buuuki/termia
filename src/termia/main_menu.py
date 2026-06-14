# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from .constants import ABOUT_IMAGE, ISSUES_URL
from . import __version__


class MainMenuMixin:
    def build_configuration_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        general = Gtk.Button(label=self.t("general"))
        general.set_halign(Gtk.Align.FILL)
        general.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_app_preferences))
        self.configure_write_action(general)
        menu.append(general)

        terminal = Gtk.Button(label=self.t("terminal"))
        terminal.set_halign(Gtk.Align.FILL)
        terminal.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_terminal_settings))
        self.configure_write_action(terminal)
        menu.append(terminal)

        prompt = Gtk.Button(label=self.t("prompt"))
        prompt.set_halign(Gtk.Align.FILL)
        prompt.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_prompt_settings))
        self.configure_write_action(prompt)
        menu.append(prompt)

        keybindings = Gtk.Button(label=self.t("keybindings"))
        keybindings.set_halign(Gtk.Align.FILL)
        keybindings.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_keybindings_settings))
        self.configure_write_action(keybindings)
        menu.append(keybindings)

        connections_file = Gtk.MenuButton(label=self.t("connections_file"))
        connections_file.set_halign(Gtk.Align.FILL)
        connections_file.set_popover(self.build_connections_file_menu())
        menu.append(connections_file)
        popover.set_child(menu)
        return popover

    def build_main_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_child(self.build_main_menu_content(popover))
        return popover

    def build_main_menu_content(self, popover: Gtk.Popover) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        general = Gtk.Button(label=self.t("general"))
        general.set_halign(Gtk.Align.FILL)
        general.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_app_preferences))
        self.configure_write_action(general)
        menu.append(general)

        terminal = Gtk.Button(label=self.t("terminal"))
        terminal.set_halign(Gtk.Align.FILL)
        terminal.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_terminal_settings))
        self.configure_write_action(terminal)
        menu.append(terminal)

        prompt = Gtk.Button(label=self.t("prompt"))
        prompt.set_halign(Gtk.Align.FILL)
        prompt.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_prompt_settings))
        self.configure_write_action(prompt)
        menu.append(prompt)

        keybindings = Gtk.Button(label=self.t("keybindings"))
        keybindings.set_halign(Gtk.Align.FILL)
        keybindings.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_keybindings_settings))
        self.configure_write_action(keybindings)
        menu.append(keybindings)

        security = Gtk.Button(label=self.t("security"))
        security.set_halign(Gtk.Align.FILL)
        security.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_security_settings))
        self.configure_write_action(security)
        menu.append(security)

        connections_file = Gtk.Button(label=self.t("connections_file"))
        connections_file.set_halign(Gtk.Align.FILL)
        connections_file.connect("clicked", lambda _button: popover.set_child(self.build_main_connections_menu(popover)))
        menu.append(connections_file)

        statistics = Gtk.Button(label=self.t("statistics"))
        statistics.set_halign(Gtk.Align.FILL)
        statistics.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_statistics_dashboard))
        menu.append(statistics)

        help_btn = Gtk.Button(label=self.t("help"))
        help_btn.set_halign(Gtk.Align.FILL)
        help_btn.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_help))
        menu.append(help_btn)

        about_btn = Gtk.Button(label=self.t("about"))
        about_btn.set_halign(Gtk.Align.FILL)
        about_btn.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_about))
        menu.append(about_btn)
        return menu

    def build_main_connections_menu(self, popover: Gtk.Popover) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        back = Gtk.Button(label=self.t("main_menu"))
        back.set_halign(Gtk.Align.FILL)
        back.connect("clicked", lambda _button: popover.set_child(self.build_main_menu_content(popover)))
        menu.append(back)

        export_config = Gtk.Button(label=self.t("export_config"))
        export_config.set_halign(Gtk.Align.FILL)
        export_config.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_export_config))
        menu.append(export_config)

        import_config = Gtk.Button(label=self.t("import_config"))
        import_config.set_halign(Gtk.Align.FILL)
        import_config.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_import_config))
        self.configure_write_action(import_config)
        menu.append(import_config)

        import_asbru = Gtk.Button(label=self.t("import_asbru"))
        import_asbru.set_halign(Gtk.Align.FILL)
        import_asbru.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_import_asbru_config))
        self.configure_write_action(import_asbru)
        menu.append(import_asbru)

        clear_config = Gtk.Button(label=self.t("clear_config"))
        clear_config.set_halign(Gtk.Align.FILL)
        clear_config.add_css_class("destructive-action")
        clear_config.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_request_clear_config))
        self.configure_write_action(clear_config)
        menu.append(clear_config)
        return menu

    def run_after_popover_closed(self, popover: Gtk.Popover, callback: Any) -> None:
        popover.popdown()

        def run_callback() -> bool:
            callback(None)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(run_callback)

    def run_action_after_popover_closed(self, popover: Gtk.Popover, callback: Any) -> None:
        popover.popdown()

        def run_callback() -> bool:
            callback()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(run_callback)

    def add_dialog_action_button(
        self, dialog: Gtk.Dialog, label: str, response: Gtk.ResponseType, *, last: bool = False
    ) -> Gtk.Button:
        button = dialog.add_button(label, response)
        button.set_margin_end(12 if last else 6)
        button.set_margin_bottom(12)
        return button

    def add_dialog_action_buttons(
        self, dialog: Gtk.Dialog, confirm_label: str, confirm_response: Gtk.ResponseType = Gtk.ResponseType.OK
    ) -> tuple[Gtk.Button, Gtk.Button]:
        cancel = self.add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
        confirm = self.add_dialog_action_button(dialog, confirm_label, confirm_response, last=True)
        return cancel, confirm

    def on_help(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("help_title"), transient_for=self, modal=True)
        dialog.set_default_size(620, 440)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE, last=True)
        dialog.connect("response", lambda source, _response: source.destroy())

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        label = Gtk.Label(label=self.t("help_content"))
        label.set_xalign(0)
        label.set_yalign(0)
        label.set_wrap(True)
        label.set_selectable(True)
        scroller.set_child(label)
        content.append(scroller)
        dialog.present()

    def on_about(self, _button: Gtk.Button) -> None:
        dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        dialog.set_program_name("Termia")
        dialog.set_version(__version__)
        dialog.set_copyright("Copyright © 2026 Jordi Pons")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.set_comments(self.t("about_content"))
        dialog.set_website(ISSUES_URL)
        dialog.set_website_label(self.t("report_issue"))
        if ABOUT_IMAGE.exists():
            dialog.set_logo(Gdk.Texture.new_from_filename(str(ABOUT_IMAGE)))
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

    def build_connections_file_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("export_config"), self.on_export_config)
        self.add_context_menu_item(menu, self.t("import_config"), self.on_import_config, enabled=not self.store.read_only)
        self.add_context_menu_item(menu, self.t("import_asbru"), self.on_import_asbru_config, enabled=not self.store.read_only)
        self.add_context_menu_item(menu, self.t("clear_config"), self.on_request_clear_config, destructive=True, enabled=not self.store.read_only)
        popover.set_child(menu)
        return popover
