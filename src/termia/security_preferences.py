# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .config_io import CONNECTION_STORAGE_ENCRYPTED, CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_PLAIN
from .stores import ReadOnlyStoreError


class SecurityPreferencesMixin:
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

    def on_security_settings_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType,
                                      storage_combo: Gtk.ComboBoxText) -> None:
        if response == Gtk.ResponseType.OK:
            target_mode = storage_combo.get_active_id() or CONNECTION_STORAGE_PLAIN
            if target_mode == CONNECTION_STORAGE_ENCRYPTED and self.store.data.app.connection_storage_mode != CONNECTION_STORAGE_ENCRYPTED:
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
        dialog = Gtk.AlertDialog(message=self.t("enable_connection_encryption_title"), detail=self.t("enable_connection_encryption_detail"))
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

    def on_master_password_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType,
                                    password_entry: Gtk.PasswordEntry, confirm_entry: Gtk.PasswordEntry,
                                    error: Gtk.Label) -> None:
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
