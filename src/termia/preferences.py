# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .config_io import CONNECTION_STORAGE_ENCRYPTED, CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_PLAIN
from .constants import (
    APP_THEMES,
)
from .i18n import LANGUAGES, detect_system_language
from .keybindings import (
    DEFAULT_KEYBINDINGS,
    KEYBINDING_ACTIONS,
    keybinding_from_event,
    keybinding_label,
    normalize_keybinding,
)
from .models import AppSettings
from .prompt_preferences import PromptPreferencesMixin
from .stores import ReadOnlyStoreError
from .terminal_preferences import TerminalPreferencesMixin


class KeybindingCaptureRow(Gtk.Box):
    def __init__(self, accelerator: str, disabled_label: str, capture_prompt: str, clear_label: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_hexpand(True)

        self._disabled_label = disabled_label
        self._capture_prompt = capture_prompt
        self._clear_label = clear_label
        self._accelerator = normalize_keybinding(accelerator)
        self._capturing = False

        self._capture_button = Gtk.Button()
        self._capture_button.set_hexpand(True)
        self._capture_button.set_halign(Gtk.Align.FILL)
        self._capture_button.connect("clicked", self.on_capture_clicked)
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self._capture_button.add_controller(key_controller)
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect("leave", self.on_focus_leave)
        self._capture_button.add_controller(focus_controller)

        self._clear_button = Gtk.Button(label=self._clear_label)
        self._clear_button.connect("clicked", self.on_clear_clicked)

        self.append(self._capture_button)
        self.append(self._clear_button)
        self.update_label()

    def get_accelerator(self) -> str:
        return self._accelerator

    def set_accelerator(self, accelerator: str) -> None:
        self._accelerator = normalize_keybinding(accelerator)
        self._capturing = False
        self.update_label()

    def update_label(self) -> None:
        if self._capturing:
            self._capture_button.set_label(self._capture_prompt)
            self._capture_button.add_css_class("suggested-action")
        else:
            self._capture_button.set_label(keybinding_label(self._accelerator, self._disabled_label))
            self._capture_button.remove_css_class("suggested-action")

    def on_capture_clicked(self, _button: Gtk.Button) -> None:
        self._capturing = True
        self.update_label()
        self._capture_button.grab_focus()

    def on_clear_clicked(self, _button: Gtk.Button) -> None:
        self.set_accelerator("")

    def on_focus_leave(self, _controller: Gtk.EventControllerFocus) -> None:
        if not self._capturing:
            return
        self._capturing = False
        self.update_label()

    def on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: object,
    ) -> bool:
        if not self._capturing:
            return False
        accelerator = keybinding_from_event(keyval, state)
        if not accelerator:
            return True
        self._accelerator = accelerator
        self._capturing = False
        self.update_label()
        return True


class PreferencesMixin(TerminalPreferencesMixin, PromptPreferencesMixin):
    def on_app_preferences(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("general"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(380, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        theme_combo = Gtk.ComboBoxText()
        for theme_id in APP_THEMES:
            theme_combo.append(theme_id, self.t(f"theme_{theme_id}"))
        theme_combo.set_active_id(self.store.data.app.theme)

        language_combo = Gtk.ComboBoxText()
        for language_id, label in LANGUAGES.items():
            language_combo.append(language_id, label)
        language_combo.set_active_id(self.store.data.app.language)

        close_tab_on_disconnect = Gtk.CheckButton(label=self.t("close_tab_on_disconnect"))
        close_tab_on_disconnect.set_active(self.store.data.app.close_tab_on_disconnect)
        close_tab_on_disconnect.set_halign(Gtk.Align.START)
        close_tab_on_ssh_exit = Gtk.CheckButton(label=self.t("close_tab_on_ssh_exit"))
        close_tab_on_ssh_exit.set_active(self.store.data.app.close_tab_on_ssh_exit)
        close_tab_on_ssh_exit.set_halign(Gtk.Align.START)
        open_local_terminal_on_startup = Gtk.CheckButton(label=self.t("open_local_terminal_on_startup"))
        open_local_terminal_on_startup.set_active(self.store.data.app.open_local_terminal_on_startup)
        open_local_terminal_on_startup.set_halign(Gtk.Align.START)
        show_sidebar_on_startup = Gtk.CheckButton(label=self.t("show_sidebar_on_startup"))
        show_sidebar_on_startup.set_active(self.store.data.app.show_sidebar_on_startup)
        show_sidebar_on_startup.set_halign(Gtk.Align.START)
        show_session_status_bar = Gtk.CheckButton(label=self.t("show_session_status_bar"))
        show_session_status_bar.set_active(self.store.data.app.show_session_status_bar)
        show_session_status_bar.set_halign(Gtk.Align.START)
        confirm_disconnect = Gtk.CheckButton(label=self.t("confirm_disconnect"))
        confirm_disconnect.set_active(self.store.data.app.confirm_disconnect)
        confirm_disconnect.set_halign(Gtk.Align.START)
        confirm_close_app = Gtk.CheckButton(label=self.t("confirm_close_app"))
        confirm_close_app.set_active(self.store.data.app.confirm_close_app)
        confirm_close_app.set_halign(Gtk.Align.START)
        sudo_password_shortcut = Gtk.CheckButton(label=self.t("sudo_password_shortcut"))
        sudo_password_shortcut.set_active(self.store.data.app.sudo_password_shortcut)
        sudo_password_shortcut.set_halign(Gtk.Align.START)
        sudo_password_enter = Gtk.CheckButton(label=self.t("sudo_password_enter"))
        sudo_password_enter.set_active(self.store.data.app.sudo_password_enter)
        sudo_password_enter.set_halign(Gtk.Align.START)
        sudo_password_enter.set_sensitive(sudo_password_shortcut.get_active())
        sudo_password_shortcut.connect(
            "toggled", lambda current: sudo_password_enter.set_sensitive(current.get_active())
        )
        statistics_enabled = Gtk.CheckButton(label=self.t("statistics_enabled"))
        statistics_enabled.set_active(self.store.data.app.statistics_enabled)
        statistics_enabled.set_halign(Gtk.Align.START)
        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("theme"), theme_combo),
            (self.t("language"), language_combo),
            ("", close_tab_on_disconnect),
            ("", close_tab_on_ssh_exit),
            ("", open_local_terminal_on_startup),
            ("", show_sidebar_on_startup),
            ("", show_session_status_bar),
            ("", statistics_enabled),
            ("", confirm_disconnect),
            ("", confirm_close_app),
            ("", sudo_password_shortcut),
            ("", sudo_password_enter),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            widget.set_hexpand(True)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        dialog.get_content_area().append(grid)
        dialog.connect(
            "response", self.on_app_preferences_response, theme_combo, language_combo,
            close_tab_on_disconnect, close_tab_on_ssh_exit, open_local_terminal_on_startup,
            show_sidebar_on_startup, show_session_status_bar, confirm_disconnect, confirm_close_app,
            sudo_password_shortcut, sudo_password_enter, statistics_enabled
        )
        dialog.present()

    def on_app_preferences_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        theme_combo: Gtk.ComboBoxText,
        language_combo: Gtk.ComboBoxText,
        close_tab_on_disconnect: Gtk.CheckButton,
        close_tab_on_ssh_exit: Gtk.CheckButton,
        open_local_terminal_on_startup: Gtk.CheckButton,
        show_sidebar_on_startup: Gtk.CheckButton,
        show_session_status_bar: Gtk.CheckButton,
        confirm_disconnect: Gtk.CheckButton,
        confirm_close_app: Gtk.CheckButton,
        sudo_password_shortcut: Gtk.CheckButton,
        sudo_password_enter: Gtk.CheckButton,
        statistics_enabled: Gtk.CheckButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            previous_language = self.store.data.app.language
            try:
                self.store.update_app_settings(
                    AppSettings(
                        theme=theme_combo.get_active_id() or "system",
                        language=language_combo.get_active_id() or detect_system_language(),
                        close_tab_on_disconnect=close_tab_on_disconnect.get_active(),
                        close_tab_on_ssh_exit=close_tab_on_ssh_exit.get_active(),
                        open_local_terminal_on_startup=open_local_terminal_on_startup.get_active(),
                        show_sidebar_on_startup=show_sidebar_on_startup.get_active(),
                        show_session_status_bar=show_session_status_bar.get_active(),
                        confirm_disconnect=confirm_disconnect.get_active(),
                        confirm_close_app=confirm_close_app.get_active(),
                        sudo_password_shortcut=sudo_password_shortcut.get_active(),
                        sudo_password_enter=sudo_password_enter.get_active(),
                        connection_storage_mode=self.store.data.app.connection_storage_mode,
                        statistics_enabled=statistics_enabled.get_active(),
                        keybindings=self.store.data.app.keybindings,
                    )
                )
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
            if previous_language != self.store.data.app.language:
                self.refresh_translated_chrome()
                self.toast_label.set_label(self.t("language_settings_saved"))
        dialog.destroy()


    def on_security_settings(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("security"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        storage_combo = Gtk.ComboBoxText()
        storage_combo.append(CONNECTION_STORAGE_PLAIN, self.t("connection_storage_plain"))
        storage_combo.append(CONNECTION_STORAGE_OBFUSCATED, self.t("connection_storage_obfuscated"))
        storage_combo.append(CONNECTION_STORAGE_ENCRYPTED, self.t("connection_storage_encrypted"))
        storage_combo.set_active_id(self.store.data.app.connection_storage_mode)
        storage_combo.set_hexpand(True)

        label = Gtk.Label(label=self.t("connection_storage_mode"))
        label.set_xalign(0)
        grid.attach(label, 0, 0, 1, 1)
        grid.attach(storage_combo, 1, 0, 1, 1)
        content.append(grid)

        warning = Gtk.Label(label=self.t("connection_storage_obfuscated_warning"))
        warning.set_xalign(0)
        warning.set_wrap(True)
        warning.add_css_class("dim-label")
        content.append(warning)

        dialog.connect("response", self.on_security_settings_response, storage_combo)
        dialog.present()

    def on_security_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        storage_combo: Gtk.ComboBoxText,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            target_mode = storage_combo.get_active_id() or CONNECTION_STORAGE_PLAIN
            if (
                target_mode == CONNECTION_STORAGE_ENCRYPTED
                and self.store.data.app.connection_storage_mode != CONNECTION_STORAGE_ENCRYPTED
            ):
                dialog.destroy()
                self.confirm_enable_connection_encryption()
                return
            try:
                self.store.update_connection_storage_mode(target_mode)
            except (ReadOnlyStoreError, ValueError):
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.toast_label.set_label(self.t("security_settings_saved"))
        dialog.destroy()

    def confirm_enable_connection_encryption(self) -> None:
        dialog = Gtk.AlertDialog(
            message=self.t("enable_connection_encryption_title"),
            detail=self.t("enable_connection_encryption_detail"),
        )
        dialog.set_buttons([self.t("cancel"), self.t("continue")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_enable_connection_encryption_confirmed)

    def on_enable_connection_encryption_confirmed(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            self.present_master_password_dialog()

    def present_master_password_dialog(self) -> None:
        dialog = Gtk.Dialog(title=self.t("master_password_title"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        dialog.add_button(self.t("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.t("enable_encryption"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        detail = Gtk.Label(label=self.t("master_password_detail"))
        detail.set_xalign(0)
        detail.set_wrap(True)
        content.append(detail)

        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        password_entry.connect("activate", lambda _entry: dialog.response(Gtk.ResponseType.OK))
        confirm_entry = Gtk.PasswordEntry()
        confirm_entry.set_show_peek_icon(True)
        confirm_entry.connect("activate", lambda _entry: dialog.response(Gtk.ResponseType.OK))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        password_label = Gtk.Label(label=self.t("master_password"))
        password_label.set_xalign(0)
        confirm_label = Gtk.Label(label=self.t("confirm_master_password"))
        confirm_label.set_xalign(0)
        grid.attach(password_label, 0, 0, 1, 1)
        grid.attach(password_entry, 1, 0, 1, 1)
        grid.attach(confirm_label, 0, 1, 1, 1)
        grid.attach(confirm_entry, 1, 1, 1, 1)
        content.append(grid)

        error = Gtk.Label()
        error.set_xalign(0)
        error.set_wrap(True)
        error.add_css_class("error")
        content.append(error)

        dialog.connect("response", self.on_master_password_response, password_entry, confirm_entry, error)
        dialog.present()
        password_entry.grab_focus()

    def on_master_password_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        password_entry: Gtk.PasswordEntry,
        confirm_entry: Gtk.PasswordEntry,
        error: Gtk.Label,
    ) -> None:
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        password = password_entry.get_text()
        if len(password) < 8:
            error.set_label(self.t("master_password_too_short"))
            password_entry.grab_focus()
            return
        if password != confirm_entry.get_text():
            error.set_label(self.t("master_password_mismatch"))
            confirm_entry.set_text("")
            confirm_entry.grab_focus()
            return
        try:
            self.store.update_connection_storage_mode(CONNECTION_STORAGE_ENCRYPTED, password)
        except ReadOnlyStoreError:
            self.toast_label.set_label(self.t("read_only_mode_enabled"))
            dialog.destroy()
            return
        dialog.destroy()
        self.toast_label.set_label(self.t("security_settings_saved"))

    def on_keybindings_settings(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("keybindings"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(520, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        self.add_dialog_action_button(dialog, self.t("keybindings_restore_defaults"), Gtk.ResponseType.APPLY)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        description = Gtk.Label(label=self.t("keybindings_description"))
        description.set_xalign(0)
        description.set_wrap(True)
        description.add_css_class("dim-label")
        content.append(description)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        rows: list[tuple[str, KeybindingCaptureRow]] = []
        for index, (action, label_key) in enumerate(KEYBINDING_ACTIONS):
            label = Gtk.Label(label=self.t(label_key))
            label.set_xalign(0)
            row = KeybindingCaptureRow(
                self.store.data.app.keybindings.get(action, DEFAULT_KEYBINDINGS[action]),
                self.t("keybinding_disabled"),
                self.t("keybinding_capture_prompt"),
                self.t("keybinding_clear"),
            )
            rows.append((action, row))
            grid.attach(label, 0, index, 1, 1)
            grid.attach(row, 1, index, 1, 1)
        content.append(grid)

        dialog.connect("response", self.on_keybindings_settings_response, rows)
        dialog.present()

    def on_keybindings_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        rows: list[tuple[str, KeybindingCaptureRow]],
    ) -> None:
        if response == Gtk.ResponseType.APPLY:
            for action, row in rows:
                row.set_accelerator(DEFAULT_KEYBINDINGS[action])
            return
        if response == Gtk.ResponseType.OK:
            keybindings = {action: row.get_accelerator() for action, row in rows}
            conflict = self.duplicate_keybinding(keybindings)
            if conflict:
                self.toast_label.set_label(self.t("keybindings_conflict").format(shortcut=conflict))
                return
            try:
                self.store.update_keybindings(keybindings)
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.toast_label.set_label(self.t("keybindings_settings_saved"))
        dialog.destroy()

    def duplicate_keybinding(self, keybindings: dict[str, str]) -> str:
        seen: set[str] = set()
        for shortcut in keybindings.values():
            normalized = normalize_keybinding(shortcut)
            if not normalized:
                continue
            if normalized in seen:
                return normalized
            seen.add(normalized)
        return ""
