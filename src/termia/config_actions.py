# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import yaml
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .asbru_import import extract_asbru_connections, merge_asbru_connections
from .config_io import export_connections_file, load_store_data_from_json, write_connections_file


class ConfigActionsMixin:
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
            destination = Path(file.get_path())
            if self.store.read_only or not self.store.path.exists():
                write_connections_file(
                    destination,
                    self.store.data.groups,
                    self.store.data.servers,
                    self.store.data.app.connection_storage_mode,
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
                imported = load_store_data_from_json(Path(file.get_path()), self.store.data)
            except (OSError, ValueError, TypeError) as exc:
                self.toast_label.set_label(self.t("import_config_failed").format(error=exc))
                return
            self.store.data = imported
            self.store.save_connections()
            self.apply_app_theme()
            self.refresh_list()
            self.toast_label.set_label(self.t("import_config_success"))

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
            self.toast_label.set_label(self.t("import_asbru_failed").format(error=exc))
            return
        if not isinstance(payload, dict):
            self.toast_label.set_label(self.t("import_asbru_invalid"))
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
