# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import gi
import yaml

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk, Pango

from .asbru_import import extract_asbru_connections, merge_asbru_connections
from .config_io import (
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    export_connections_file,
    load_store_data_from_json,
    write_connections_file,
)
from .constants import (
    CONFIG_DIR,
    DATA_FILE,
    HISTORY_FILE,
    INSTANCE_LOCK_FILE,
    NOTES_FILE,
    SETTINGS_FILE,
    STATE_DIR,
    STATISTICS_FILE,
)
from .dialog_window import DialogWindow


class ConfigActionsMixin:
    def on_data_locations(self) -> None:
        dialog = DialogWindow(title=self.t("data_locations_title"), transient_for=self, modal=True)
        dialog.set_default_size(680, -1)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE)
        dialog.connect("response", lambda source, _response: source.destroy())

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        intro = Gtk.Label(label=self.t("data_locations_detail"))
        intro.set_xalign(0)
        intro.set_wrap(True)
        intro.set_max_width_chars(80)
        content.append(intro)

        grid = Gtk.Grid(column_spacing=16, row_spacing=10)
        grid.set_margin_top(6)
        grid.set_margin_bottom(6)
        grid.set_margin_start(6)
        grid.set_margin_end(6)

        for row, (label_key, path) in enumerate(self.data_location_paths()):
            label = Gtk.Label(label=self.t(label_key))
            label.set_xalign(0)
            label.set_valign(Gtk.Align.START)
            label.add_css_class("dim-label")
            grid.attach(label, 0, row, 1, 1)

            path_label = Gtk.Label(label=str(path))
            path_label.set_xalign(0)
            path_label.set_selectable(True)
            path_label.set_wrap(True)
            path_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            path_label.set_width_chars(40)
            path_label.set_max_width_chars(56)
            attributes = Pango.AttrList()
            attributes.insert(Pango.attr_family_new("monospace"))
            path_label.set_attributes(attributes)
            path_label.set_hexpand(True)
            grid.attach(path_label, 1, row, 1, 1)

            state = Gtk.Label(label=self.t("path_exists") if path.exists() else self.t("path_missing"))
            state.set_xalign(0)
            state.set_valign(Gtk.Align.START)
            state.add_css_class("dim-label")
            grid.attach(state, 2, row, 1, 1)

        content.append(grid)
        dialog.present()

    def data_location_paths(self) -> list[tuple[str, Path]]:
        return [
            ("config_directory", CONFIG_DIR),
            ("connections_file_path", DATA_FILE),
            ("notes_file_path", NOTES_FILE),
            ("settings_file_path", SETTINGS_FILE),
            ("instance_lock_file_path", INSTANCE_LOCK_FILE),
            ("state_directory", STATE_DIR / "termia"),
            ("statistics_file_path", STATISTICS_FILE),
            ("connection_history_file_path", HISTORY_FILE),
        ]

    def on_request_clear_config(self) -> None:
        dialog = Gtk.AlertDialog(message=self.t("clear_config"), detail=self.t("clear_confirm"))
        dialog.set_buttons([self.t("cancel"), self.t("clear_config")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_clear_config_confirmed)

    def on_clear_config_confirmed(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        if not self.ensure_writable():
            return
        self.store.data.groups = []
        self.store.data.servers = []
        self.store.data.local_terminals = []
        self.store.data.workspaces = []
        self.store.data.snippets = []
        self.store.data.snippet_categories = []
        self.store.detach_orphaned_notes()
        self.store.save_connections()
        self.selected = None
        self.refresh_list()
        self.toast_label.set_label(self.t("clear_config"))

    def on_export_config(self) -> None:
        dialog = Gtk.FileDialog(title=self.t("export_config"))
        dialog.set_initial_name("termia.json")
        dialog.save(self, None, self.on_export_config_selected)

    def on_export_config_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if file and file.get_path():
            if self.store.encryption_locked:
                self.toast_label.set_label(self.t("connections_locked"))
                return
            destination = Path(file.get_path())
            if self.store.read_only or not self.store.path.exists():
                write_connections_file(
                    destination,
                    self.store.data.groups,
                    self.store.data.servers,
                    self.store.data.local_terminals,
                    self.store.data.app.connection_storage_mode,
                    self.store.master_password,
                    self.store.data.workspaces,
                    self.store.data.snippets,
                    self.store.data.snippet_categories,
                )
            else:
                self.store.save_connections()
                export_connections_file(self.store.path, destination)
            self.toast_label.set_label(self.t("export_config_success"))

    def on_import_config(self) -> None:
        dialog = Gtk.FileDialog(title=self.t("import_config"))
        dialog.open(self, None, self.on_import_config_selected)

    def on_import_config_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file and file.get_path():
            if not self.ensure_writable():
                return
            try:
                self.import_connection_file(Path(file.get_path()))
            except MissingMasterPasswordError:
                self.present_connection_import_password(Path(file.get_path()))
            except (OSError, ValueError, TypeError) as exc:
                self.toast_label.set_error(self.t("import_config_failed").format(error=exc))

    def import_connection_file(self, path: Path, password: str | None = None) -> bool:
        if not self.ensure_writable():
            return False
        imported = load_store_data_from_json(path, self.store.data, password)
        if not self.ensure_writable():
            return False
        self.store.data = imported
        self.store.detach_orphaned_notes()
        self.store.save_connections()
        self.apply_app_theme()
        self.refresh_list()
        self.toast_label.set_label(self.t("import_config_success"))
        return True

    def present_connection_import_password(self, path: Path) -> None:
        dialog = DialogWindow(title=self.t("import_config_unlock_title"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        self.add_dialog_action_buttons(dialog, self.t("import_config"))
        content = dialog.get_content_area()
        content.set_spacing(12)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{side}")(16)
        detail = Gtk.Label(label=self.t("import_config_unlock_detail"), wrap=True, xalign=0)
        content.append(detail)
        entry = Gtk.PasswordEntry(show_peek_icon=True)
        entry.connect("activate", lambda _entry: dialog.response(Gtk.ResponseType.OK))
        content.append(entry)
        error = Gtk.Label(wrap=True, xalign=0)
        content.append(error)
        dialog.connect("response", self.on_connection_import_password_response, path, entry, error)
        dialog.present()
        entry.grab_focus()

    def on_connection_import_password_response(
        self, dialog: DialogWindow, response: Gtk.ResponseType, path: Path,
        entry: Gtk.PasswordEntry, error: Gtk.Label,
    ) -> None:
        if response != Gtk.ResponseType.OK or not self.ensure_writable():
            entry.set_text("")
            dialog.destroy()
            return
        password = entry.get_text()
        entry.set_text("")
        if not password:
            error.set_label(self.t("import_config_unlock_required"))
            entry.grab_focus()
            return
        try:
            self.import_connection_file(path, password)
        except InvalidMasterPasswordError:
            error.set_label(self.t("import_config_unlock_wrong"))
            entry.grab_focus()
            return
        except (OSError, ValueError, TypeError) as exc:
            self.toast_label.set_error(self.t("import_config_failed").format(error=exc))
        dialog.destroy()

    def on_import_asbru_config(self) -> None:
        dialog = Gtk.FileDialog(title=self.t("import_asbru"))
        dialog.open(self, None, self.on_import_asbru_config_selected)

    def on_import_asbru_config_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if not file or not file.get_path():
            return
        try:
            payload = yaml.safe_load(Path(file.get_path()).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.toast_label.set_error(self.t("import_asbru_failed").format(error=exc))
            return
        if not isinstance(payload, dict):
            self.toast_label.set_error(self.t("import_asbru_invalid"))
            return
        if "__PAC__EXPORTED__PARTIAL_CONF" in payload:
            payload = payload["__PAC__EXPORTED__PARTIAL_CONF"]
        if not self.ensure_writable():
            return
        imported_groups, imported_servers = extract_asbru_connections(payload)
        added_groups, added_servers = merge_asbru_connections(self.store.data, imported_groups, imported_servers)
        self.store.save_connections()
        self.refresh_list()
        self.toast_label.set_label(self.t("import_asbru_success").format(groups=added_groups, servers=added_servers))
