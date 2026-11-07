# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from functools import partial

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .choice_widgets import (
    append_choice,
    choice_id,
    select_choice,
    text_choice,
)
from .constants import APP_THEMES, DEBUG_LOG_FILE, DEFAULT_DARK_GLOW_BORDER_COLOR
from .debug import configure_debug_logging
from .dialog_window import DialogWindow
from .i18n import LANGUAGES, detect_system_language
from .models import AppSettings
from .stores import ReadOnlyStoreError
from .terminal_config import parse_color, rgba_to_hex
from .theme_styles import DARK_GLOW_THEME

GENERAL_PREFERENCE_FIELDS = (
    ("theme", "theme"),
    ("language", "language"),
    ("close_tab_on_disconnect", "close_tab_on_disconnect"),
    ("close_tab_on_ssh_exit", "close_tab_on_ssh_exit"),
    ("open_local_terminal_on_startup", "open_local_terminal_on_startup"),
    ("restore_sessions_on_startup", "restore_sessions_on_startup"),
    ("show_sidebar_on_startup", "show_sidebar_on_startup"),
    ("show_session_status_bar", "show_session_status_bar"),
    ("audible_bell", "audible_bell"),
    ("confirm_multiline_paste", "confirm_multiline_paste"),
    ("copy_on_selection", "copy_on_selection"),
    ("confirm_disconnect", "confirm_disconnect"),
    ("confirm_close_app", "confirm_close_app"),
    ("send_credential_shortcut", "send_password_shortcut"),
    ("send_credential_enter", "send_password_enter"),
    ("debug_mode", "debug_enabled"),
)


def password_preference_sensitivity(
    keybindings: dict[str, str], shortcut_active: bool
) -> tuple[bool, bool]:
    """Return sensitivity for the permission and trailing-Enter options."""
    shortcut_configured = bool(keybindings.get("send_password", "").strip())
    return shortcut_configured, shortcut_configured and shortcut_active


def password_preference_hint_visibility(
    keybindings: dict[str, str], shortcut_active: bool
) -> tuple[bool, bool]:
    """Return visibility for the shortcut and dependent-option explanations."""
    shortcut_sensitive, _enter_sensitive = password_preference_sensitivity(
        keybindings, shortcut_active
    )
    return not shortcut_sensitive, shortcut_sensitive and not shortcut_active


class GeneralPreferencesMixin:
    def on_app_preferences(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = DialogWindow(title=self.t("general"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(380, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        for margin in ("top", "bottom", "start", "end"):
            getattr(grid, f"set_margin_{margin}")(16)

        theme_combo = text_choice()
        for theme_id in APP_THEMES:
            append_choice(theme_combo, theme_id, self.t(f"theme_{theme_id}"))
        select_choice(theme_combo, self.store.data.app.theme)
        language_combo = text_choice()
        for language_id, label in LANGUAGES.items():
            append_choice(language_combo, language_id, label)
        select_choice(language_combo, self.store.data.app.language)

        border_color_button = Gtk.ColorButton()
        border_color_button.set_title(self.t("border_color"))
        border_color_button.set_use_alpha(False)
        border_color_button.set_rgba(parse_color(
            self.store.data.app.dark_glow_border_color, DEFAULT_DARK_GLOW_BORDER_COLOR,
        ))
        reset_border_button = Gtk.Button(label=self.t("reset_border_color"))
        reset_border_button.connect(
            "clicked", lambda _button: border_color_button.set_rgba(
                parse_color(DEFAULT_DARK_GLOW_BORDER_COLOR, DEFAULT_DARK_GLOW_BORDER_COLOR)
            ),
        )
        border_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        border_controls.append(border_color_button)
        border_controls.append(reset_border_button)

        checks = [
            ("close_tab_on_disconnect", self.store.data.app.close_tab_on_disconnect),
            ("close_tab_on_ssh_exit", self.store.data.app.close_tab_on_ssh_exit),
            ("open_local_terminal_on_startup", self.store.data.app.open_local_terminal_on_startup),
            ("restore_sessions_on_startup", self.store.data.app.restore_sessions_on_startup),
            ("show_sidebar_on_startup", self.store.data.app.show_sidebar_on_startup),
            ("show_session_status_bar", self.store.data.app.show_session_status_bar),
            ("audible_bell", self.store.data.app.audible_bell),
            ("confirm_disconnect", self.store.data.app.confirm_disconnect),
            ("confirm_close_app", self.store.data.app.confirm_close_app),
            ("send_credential_shortcut", self.store.data.app.send_password_shortcut),
            ("send_credential_enter", self.store.data.app.send_password_enter),
            ("confirm_multiline_paste", self.store.data.app.confirm_multiline_paste),
            ("copy_on_selection", self.store.data.app.copy_on_selection),
            ("debug_mode", self.store.data.app.debug_enabled),
        ]
        check_buttons = [Gtk.CheckButton(label=self.t(key)) for key, _ in checks]
        for button, (_, active) in zip(check_buttons, checks):
            button.set_active(active)
            button.set_halign(Gtk.Align.START)
        send_password_shortcut = check_buttons[9]
        send_password_enter = check_buttons[10]
        shortcut_sensitive, enter_sensitive = password_preference_sensitivity(
            self.store.data.app.keybindings,
            send_password_shortcut.get_active(),
        )
        if not shortcut_sensitive:
            send_password_shortcut.set_active(False)
            enter_sensitive = False
        send_password_shortcut.set_sensitive(shortcut_sensitive)
        send_password_enter.set_sensitive(enter_sensitive)
        shortcut_hint = Gtk.Label(
            label=self.t("send_credential_shortcut_unavailable"), xalign=0
        )
        shortcut_hint.set_wrap(True)
        shortcut_hint.add_css_class("dim-label")
        enter_hint = Gtk.Label(
            label=self.t("send_credential_enter_unavailable"), xalign=0
        )
        enter_hint.set_wrap(True)
        enter_hint.add_css_class("dim-label")

        shortcut_hint_visible, enter_hint_visible = password_preference_hint_visibility(
            self.store.data.app.keybindings,
            send_password_shortcut.get_active(),
        )
        shortcut_hint.set_visible(shortcut_hint_visible)
        enter_hint.set_visible(enter_hint_visible)

        def update_password_preference_help(current: Gtk.CheckButton) -> None:
            active = current.get_active()
            send_password_enter.set_sensitive(shortcut_sensitive and active)
            shortcut_hint.set_visible(not shortcut_sensitive)
            enter_hint.set_visible(shortcut_sensitive and not active)

        send_password_shortcut.connect("toggled", update_password_preference_help)
        check_buttons[-1].set_tooltip_text(
            self.t("debug_log_path").format(path=DEBUG_LOG_FILE)
        )

        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("theme"), theme_combo), (self.t("border_color"), border_controls),
            (self.t("language"), language_combo),
        ]
        rows.extend(("", button) for button in check_buttons[:9])
        shortcut_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        shortcut_box.set_hexpand(True)
        shortcut_box.append(send_password_shortcut)
        shortcut_box.append(shortcut_hint)
        enter_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        enter_box.set_hexpand(True)
        enter_box.append(send_password_enter)
        enter_box.append(enter_hint)
        rows.extend((("", shortcut_box), ("", enter_box), ("", check_buttons[11]), ("", check_buttons[12]), ("", check_buttons[-1])))
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            if widget is border_controls:
                def update_border_visibility(_combo, _spec, label=label):
                    visible = choice_id(theme_combo) == DARK_GLOW_THEME
                    label.set_visible(visible)
                    border_controls.set_visible(visible)

                theme_combo.connect("notify::selected", update_border_visibility)
                update_border_visibility(theme_combo, None)
            widget.set_hexpand(True)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)
        dialog.get_content_area().append(grid)
        dialog.connect(
            "response", partial(self.on_app_preferences_response, border_color_button=border_color_button),
            theme_combo, language_combo, *check_buttons,
        )
        dialog.present()

    @staticmethod
    def general_preference_values(settings: AppSettings) -> dict[str, str | bool]:
        return {
            setting_key: getattr(settings, attribute)
            for setting_key, attribute in GENERAL_PREFERENCE_FIELDS
        }

    def on_app_preferences_response(self, dialog: DialogWindow, response: Gtk.ResponseType, theme_combo: Gtk.DropDown,
                                    language_combo: Gtk.DropDown, *check_buttons: Gtk.CheckButton,
                                    border_color_button: Gtk.ColorButton | None = None) -> None:
        if response == Gtk.ResponseType.OK:
            previous_values = self.general_preference_values(self.store.data.app)
            values = [button.get_active() for button in check_buttons]
            color_options = (
                {"dark_glow_border_color": rgba_to_hex(border_color_button.get_rgba())}
                if border_color_button is not None else {}
            )
            try:
                self.store.update_app_settings(AppSettings(
                    theme=choice_id(theme_combo) or "system",
                    language=choice_id(language_combo) or detect_system_language(),
                    close_tab_on_disconnect=values[0], close_tab_on_ssh_exit=values[1],
                    open_local_terminal_on_startup=values[2], show_sidebar_on_startup=values[4],
                    restore_sessions_on_startup=values[3],
                    show_session_status_bar=values[5], audible_bell=values[6],
                    statistics_enabled=self.store.data.app.statistics_enabled,
                    confirm_disconnect=values[7], confirm_close_app=values[8],
                    send_password_shortcut=values[9], send_password_enter=values[10],
                    connection_storage_mode=self.store.data.app.connection_storage_mode,
                    confirm_multiline_paste=values[11],
                    copy_on_selection=values[12],
                    debug_enabled=values[13],
                    keybindings=self.store.data.app.keybindings,
                ), **color_options)
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            if previous_values["restore_sessions_on_startup"] != self.store.data.app.restore_sessions_on_startup:
                if self.store.data.app.restore_sessions_on_startup:
                    self.pending_session_snapshot = self.session_snapshot_store.load()
                else:
                    self.pending_session_snapshot = []
                    self.session_snapshot_store.clear()
            self.apply_app_theme()
            if (
                previous_values["audible_bell"] != self.store.data.app.audible_bell
                or previous_values["theme"] != self.store.data.app.theme
            ):
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
