# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .constants import APP_THEMES
from .debug import configure_debug_logging
from .i18n import LANGUAGES, detect_system_language
from .models import AppSettings
from .stores import ReadOnlyStoreError


class GeneralPreferencesMixin:
    def on_app_preferences(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("general"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(380, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        for margin in ("top", "bottom", "start", "end"):
            getattr(grid, f"set_margin_{margin}")(16)

        theme_combo = Gtk.ComboBoxText()
        for theme_id in APP_THEMES:
            theme_combo.append(theme_id, self.t(f"theme_{theme_id}"))
        theme_combo.set_active_id(self.store.data.app.theme)
        language_combo = Gtk.ComboBoxText()
        for language_id, label in LANGUAGES.items():
            language_combo.append(language_id, label)
        language_combo.set_active_id(self.store.data.app.language)

        checks = [
            ("close_tab_on_disconnect", self.store.data.app.close_tab_on_disconnect),
            ("close_tab_on_ssh_exit", self.store.data.app.close_tab_on_ssh_exit),
            ("open_local_terminal_on_startup", self.store.data.app.open_local_terminal_on_startup),
            ("show_sidebar_on_startup", self.store.data.app.show_sidebar_on_startup),
            ("show_session_status_bar", self.store.data.app.show_session_status_bar),
            ("statistics_enabled", self.store.data.app.statistics_enabled),
            ("confirm_disconnect", self.store.data.app.confirm_disconnect),
            ("confirm_close_app", self.store.data.app.confirm_close_app),
            ("sudo_password_shortcut", self.store.data.app.sudo_password_shortcut),
            ("sudo_password_enter", self.store.data.app.sudo_password_enter),
            ("debug_mode", self.store.data.app.debug_enabled),
        ]
        check_buttons = [Gtk.CheckButton(label=self.t(key)) for key, _ in checks]
        for button, (_, active) in zip(check_buttons, checks):
            button.set_active(active)
            button.set_halign(Gtk.Align.START)
        sudo_password_shortcut, sudo_password_enter = check_buttons[-2:]
        sudo_password_enter.set_sensitive(sudo_password_shortcut.get_active())
        sudo_password_shortcut.connect("toggled", lambda current: sudo_password_enter.set_sensitive(current.get_active()))

        rows: list[tuple[str, Gtk.Widget]] = [(self.t("theme"), theme_combo), (self.t("language"), language_combo)]
        rows.extend(("", button) for button in check_buttons)
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            widget.set_hexpand(True)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)
        dialog.get_content_area().append(grid)
        dialog.connect("response", self.on_app_preferences_response, theme_combo, language_combo, *check_buttons)
        dialog.present()

    def on_app_preferences_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType, theme_combo: Gtk.ComboBoxText,
                                    language_combo: Gtk.ComboBoxText, *check_buttons: Gtk.CheckButton) -> None:
        if response == Gtk.ResponseType.OK:
            previous_language = self.store.data.app.language
            values = [button.get_active() for button in check_buttons]
            try:
                self.store.update_app_settings(AppSettings(
                    theme=theme_combo.get_active_id() or "system",
                    language=language_combo.get_active_id() or detect_system_language(),
                    close_tab_on_disconnect=values[0], close_tab_on_ssh_exit=values[1],
                    open_local_terminal_on_startup=values[2], show_sidebar_on_startup=values[3],
                    show_session_status_bar=values[4], statistics_enabled=values[5],
                    confirm_disconnect=values[6], confirm_close_app=values[7],
                    sudo_password_shortcut=values[8], sudo_password_enter=values[9],
                    connection_storage_mode=self.store.data.app.connection_storage_mode,
                    debug_enabled=values[10],
                    keybindings=self.store.data.app.keybindings,
                ))
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.apply_app_theme()
            self.install_tree_styles()
            self.apply_session_status_bar_visibility_to_open_tabs()
            self.set_sidebar_visible(self.store.data.app.show_sidebar_on_startup)
            self.collapse_groups_on_startup = True
            self.group_expanded_state = {group.id: False for group in self.store.data.groups}
            self.group_expanded_state["__ungrouped__"] = False
            self.refresh_list()
            configure_debug_logging(self.store.data.app.debug_enabled)
            self.toast_label.set_label(
                self.t("debug_mode_enabled" if self.store.data.app.debug_enabled else "debug_mode_disabled")
            )
            if previous_language != self.store.data.app.language:
                self.refresh_translated_chrome()
                self.toast_label.set_label(self.t("language_settings_saved"))
        dialog.destroy()
