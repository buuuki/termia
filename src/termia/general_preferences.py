# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .constants import APP_THEMES, DEBUG_LOG_FILE
from .debug import configure_debug_logging
from .i18n import LANGUAGES, detect_system_language
from .models import AppSettings
from .stores import ReadOnlyStoreError

GENERAL_PREFERENCE_FIELDS = (
    ("theme", "theme"),
    ("language", "language"),
    ("close_tab_on_disconnect", "close_tab_on_disconnect"),
    ("close_tab_on_ssh_exit", "close_tab_on_ssh_exit"),
    ("open_local_terminal_on_startup", "open_local_terminal_on_startup"),
    ("show_sidebar_on_startup", "show_sidebar_on_startup"),
    ("show_session_status_bar", "show_session_status_bar"),
    ("audible_bell", "audible_bell"),
    ("statistics_enabled", "statistics_enabled"),
    ("confirm_disconnect", "confirm_disconnect"),
    ("confirm_close_app", "confirm_close_app"),
    ("send_password_shortcut", "send_password_shortcut"),
    ("send_password_enter", "send_password_enter"),
    ("debug_mode", "debug_enabled"),
)


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
            ("audible_bell", self.store.data.app.audible_bell),
            ("statistics_enabled", self.store.data.app.statistics_enabled),
            ("confirm_disconnect", self.store.data.app.confirm_disconnect),
            ("confirm_close_app", self.store.data.app.confirm_close_app),
            ("send_password_shortcut", self.store.data.app.send_password_shortcut),
            ("send_password_enter", self.store.data.app.send_password_enter),
            ("debug_mode", self.store.data.app.debug_enabled),
        ]
        check_buttons = [Gtk.CheckButton(label=self.t(key)) for key, _ in checks]
        for button, (_, active) in zip(check_buttons, checks):
            button.set_active(active)
            button.set_halign(Gtk.Align.START)
        send_password_shortcut, send_password_enter = check_buttons[9:11]
        send_password_enter.set_sensitive(send_password_shortcut.get_active())
        send_password_shortcut.connect("toggled", lambda current: send_password_enter.set_sensitive(current.get_active()))
        check_buttons[-1].set_tooltip_text(
            self.t("debug_log_path").format(path=DEBUG_LOG_FILE)
        )

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

    @staticmethod
    def general_preference_values(settings: AppSettings) -> dict[str, str | bool]:
        return {
            setting_key: getattr(settings, attribute)
            for setting_key, attribute in GENERAL_PREFERENCE_FIELDS
        }

    def on_app_preferences_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType, theme_combo: Gtk.ComboBoxText,
                                    language_combo: Gtk.ComboBoxText, *check_buttons: Gtk.CheckButton) -> None:
        if response == Gtk.ResponseType.OK:
            previous_values = self.general_preference_values(self.store.data.app)
            values = [button.get_active() for button in check_buttons]
            try:
                self.store.update_app_settings(AppSettings(
                    theme=theme_combo.get_active_id() or "system",
                    language=language_combo.get_active_id() or detect_system_language(),
                    close_tab_on_disconnect=values[0], close_tab_on_ssh_exit=values[1],
                    open_local_terminal_on_startup=values[2], show_sidebar_on_startup=values[3],
                    show_session_status_bar=values[4], audible_bell=values[5], statistics_enabled=values[6],
                    confirm_disconnect=values[7], confirm_close_app=values[8],
                    send_password_shortcut=values[9], send_password_enter=values[10],
                    connection_storage_mode=self.store.data.app.connection_storage_mode,
                    debug_enabled=values[11],
                    keybindings=self.store.data.app.keybindings,
                ))
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.apply_app_theme()
            self.install_tree_styles()
            if previous_values["audible_bell"] != self.store.data.app.audible_bell:
                self.apply_terminal_settings_to_open_tabs()
            self.apply_session_status_bar_visibility_to_open_tabs()
            self.set_sidebar_visible(self.store.data.app.show_sidebar_on_startup)
            self.collapse_groups_on_startup = True
            self.group_expanded_state = {group.id: False for group in self.store.data.groups}
            self.group_expanded_state["__ungrouped__"] = False
            self.refresh_list()
            if previous_values["language"] != self.store.data.app.language:
                self.refresh_translated_chrome()
            self.notify_general_preference_changes(previous_values)
        dialog.destroy()

    def notify_general_preference_changes(
        self,
        previous_values: dict[str, str | bool],
    ) -> None:
        current_values = GeneralPreferencesMixin.general_preference_values(
            self.store.data.app
        )
        if previous_values["debug_mode"] != current_values["debug_mode"]:
            configure_debug_logging(bool(current_values["debug_mode"]))
        for setting_key, _attribute in GENERAL_PREFERENCE_FIELDS:
            value = current_values[setting_key]
            if previous_values[setting_key] == value:
                continue
            if setting_key == "theme":
                value_label = self.t(f"theme_{value}")
            elif setting_key == "language":
                value_label = LANGUAGES.get(str(value), str(value))
            else:
                value_label = self.t("setting_enabled" if value else "setting_disabled")
            self.toast_label.set_label(
                self.t("setting_changed").format(
                    setting=self.t(setting_key),
                    value=value_label,
                )
            )
