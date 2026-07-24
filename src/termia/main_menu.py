# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from .constants import ABOUT_IMAGE, ISSUES_URL
from . import __version__
from .main_menu_actions import MainMenuActions


class MainMenuMixin:
    POPOVER_CALLBACK_DELAY_MS = 100

    def build_main_menu(self, actions: MainMenuActions) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_child(self.build_main_menu_content(popover, actions))
        return popover

    def build_main_menu_content(
        self,
        popover: Gtk.Popover,
        actions: MainMenuActions,
    ) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        general = Gtk.Button(label=self.t("general"))
        general.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            general, popover, actions.general_preferences
        )
        self.configure_write_action(general)
        menu.append(general)

        terminal = Gtk.Button(label=self.t("terminal"))
        terminal.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            terminal, popover, actions.terminal_settings
        )
        self.configure_write_action(terminal)
        menu.append(terminal)

        prompt = Gtk.Button(label=self.t("prompt"))
        prompt.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(prompt, popover, actions.prompt_settings)
        self.configure_write_action(prompt)
        menu.append(prompt)

        keybindings = Gtk.Button(label=self.t("keybindings"))
        keybindings.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            keybindings, popover, actions.keybinding_settings
        )
        self.configure_write_action(keybindings)
        menu.append(keybindings)

        security = Gtk.Button(label=self.t("security"))
        security.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            security, popover, actions.security_settings
        )
        self.configure_write_action(security)
        menu.append(security)

        statistics = Gtk.Button(label=self.t("statistics"))
        statistics.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(statistics, popover, actions.statistics)
        menu.append(statistics)

        history = Gtk.Button(label=self.t("connection_history"))
        history.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            history, popover, actions.connection_history
        )
        menu.append(history)

        data_locations = Gtk.Button(label=self.t("data_locations"))
        data_locations.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            data_locations, popover, actions.data_locations
        )
        menu.append(data_locations)

        connections_file = Gtk.Button(label=self.t("connections_file"))
        connections_file.set_halign(Gtk.Align.FILL)
        connections_file.connect(
            "clicked",
            lambda _button: popover.set_child(
                self.build_main_connections_menu(popover, actions)
            ),
        )
        menu.append(connections_file)

        help_btn = Gtk.Button(label=self.t("help"))
        help_btn.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(help_btn, popover, actions.help)
        menu.append(help_btn)

        about_btn = Gtk.Button(label=self.t("about"))
        about_btn.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(about_btn, popover, actions.about)
        menu.append(about_btn)
        return menu

    def build_main_connections_menu(
        self,
        popover: Gtk.Popover,
        actions: MainMenuActions,
    ) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        back = Gtk.Button(label=self.t("main_menu"))
        back.set_halign(Gtk.Align.FILL)
        back.connect(
            "clicked",
            lambda _button: popover.set_child(
                self.build_main_menu_content(popover, actions)
            ),
        )
        menu.append(back)

        export_config = Gtk.Button(label=self.t("export_config"))
        export_config.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            export_config, popover, actions.export_config
        )
        menu.append(export_config)

        import_config = Gtk.Button(label=self.t("import_config"))
        import_config.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            import_config, popover, actions.import_config
        )
        self.configure_write_action(import_config)
        menu.append(import_config)

        import_asbru = Gtk.Button(label=self.t("import_asbru"))
        import_asbru.set_halign(Gtk.Align.FILL)
        self.connect_main_menu_action(
            import_asbru, popover, actions.import_asbru_config
        )
        self.configure_write_action(import_asbru)
        menu.append(import_asbru)

        clear_config = Gtk.Button(label=self.t("clear_config"))
        clear_config.set_halign(Gtk.Align.FILL)
        clear_config.add_css_class("destructive-action")
        self.connect_main_menu_action(
            clear_config, popover, actions.clear_config
        )
        self.configure_write_action(clear_config)
        menu.append(clear_config)
        return menu

    def connect_main_menu_action(
        self,
        button: Gtk.Button,
        popover: Gtk.Popover,
        callback: Callable[[], None],
    ) -> None:
        button.connect(
            "clicked",
            lambda _button: self.run_action_after_popover_closed(
                popover, callback
            ),
        )

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
