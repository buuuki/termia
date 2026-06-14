# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .connection_utils import group_descendant_ids, group_path_labels
from .models import Group, Server
from .stores import ReadOnlyStoreError


class ConnectionDialogsMixin:
    def show_group_dialog(self, group: Group | None = None) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("edit_group") if group else self.t("new_group"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(360, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        entry = Gtk.Entry()
        entry.set_placeholder_text(self.t("name"))
        parent_combo = Gtk.ComboBoxText()
        parent_combo.append("", self.t("no_parent_group"))
        excluded_ids = group_descendant_ids(self.store.data.groups, group.id) | {group.id} if group else set()
        for candidate, path_label in group_path_labels(self.store.data.groups):
            if candidate.id not in excluded_ids:
                parent_combo.append(candidate.id, path_label)
        parent_combo.set_active_id(group.parent_id if group and group.parent_id not in excluded_ids else "")
        if group:
            entry.set_text(group.name)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.attach(Gtk.Label(label=self.t("name"), xalign=0), 0, 0, 1, 1)
        grid.attach(entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=self.t("parent_group"), xalign=0), 0, 1, 1, 1)
        grid.attach(parent_combo, 1, 1, 1, 1)
        entry.set_hexpand(True)
        parent_combo.set_hexpand(True)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.append(grid)

        dialog.connect("response", self.on_group_dialog_response, entry, parent_combo, group)
        dialog.present()

    def on_group_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        entry: Gtk.Entry,
        parent_combo: Gtk.ComboBoxText,
        group: Group | None,
    ) -> None:
        name = entry.get_text().strip()
        parent_id = parent_combo.get_active_id() or None
        if response == Gtk.ResponseType.OK and name:
            try:
                if group:
                    self.store.update_group(group.id, name, parent_id)
                else:
                    self.store.add_group(name, parent_id)
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.refresh_list()
        dialog.destroy()

    def build_form_label(self, label_text: str, required: bool = False) -> Gtk.Label:
        label = Gtk.Label()
        label.set_xalign(0)
        if required:
            escaped = GLib.markup_escape_text(label_text)
            label.set_markup(f"{escaped} <span foreground='#ff5f57' size='large'><b>*</b></span>")
        else:
            label.set_text(label_text)
        return label

    def build_required_hint(self) -> Gtk.Label:
        label = Gtk.Label()
        label.set_xalign(0)
        label.set_markup(
            f"<span size='medium' foreground='#ff5f57'><b>{GLib.markup_escape_text(self.t('required_field'))}</b></span>"
        )
        return label

    def show_server_dialog(self, server: Server | None = None) -> None:
        if not self.ensure_writable():
            return
        dialog = Gtk.Dialog(title=self.t("edit_server") if server else self.t("new_server"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        name_entry = Gtk.Entry()
        host_entry = Gtk.Entry()
        user_entry = Gtk.Entry()
        port_spin = Gtk.SpinButton.new_with_range(1, 65535, 1)
        group_combo = Gtk.ComboBoxText()
        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        public_key_entry = Gtk.Entry()
        for widget in (name_entry, host_entry, user_entry, port_spin, group_combo, password_entry, public_key_entry):
            widget.set_hexpand(True)
            widget.set_size_request(260, -1)

        group_combo.append("", self.t("no_group"))
        for group, path_label in group_path_labels(self.store.data.groups):
            group_combo.append(group.id, path_label)
        group_combo.set_active_id("")

        if server:
            name_entry.set_text(server.name)
            host_entry.set_text(server.host)
            user_entry.set_text(server.user)
            port_spin.set_value(server.port)
            group_combo.set_active_id(server.group_id or "")
            password_entry.set_text(server.password)
            public_key_entry.set_text(server.public_key)
        else:
            port_spin.set_value(22)

        rows: list[tuple[str, Gtk.Widget, bool]] = [
            (self.t("name"), name_entry, True),
            (self.t("host"), host_entry, True),
            (self.t("ssh_user"), user_entry, True),
            (self.t("ssh_port"), port_spin, False),
            (self.t("group"), group_combo, False),
            (self.t("password"), password_entry, False),
            (self.t("public_key"), public_key_entry, False),
        ]
        for index, (label_text, widget, required) in enumerate(rows):
            grid.attach(self.build_form_label(label_text, required), 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)
        grid.attach(self.build_required_hint(), 1, len(rows), 1, 1)

        dialog.get_content_area().append(grid)
        warning = Gtk.Label()
        warning.set_markup(f"<i>{GLib.markup_escape_text(self.t('password_warning'))}</i>")
        warning.set_wrap(True)
        warning.set_xalign(0)
        warning.set_margin_start(16)
        warning.set_margin_end(16)
        warning.set_margin_bottom(14)
        warning.add_css_class("warning")
        dialog.get_content_area().append(warning)
        dialog.connect(
            "response",
            self.on_server_dialog_response,
            {
                "name": name_entry,
                "host": host_entry,
                "user": user_entry,
                "port": port_spin,
                "group": group_combo,
                "password": password_entry,
                "public_key": public_key_entry,
            },
            server,
        )
        dialog.present()

    def on_server_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        widgets: dict[str, Any],
        server: Server | None,
    ) -> None:
        name = widgets["name"].get_text().strip()
        host = widgets["host"].get_text().strip()
        user = widgets["user"].get_text().strip()
        port = int(widgets["port"].get_value())
        group_id = widgets["group"].get_active_id() or None
        password = widgets["password"].get_text()
        public_key = widgets["public_key"].get_text().strip()

        if response == Gtk.ResponseType.OK:
            if not name or not host or not user:
                self.toast_label.set_label(self.t("server_required_fields"))
                for widget in (widgets["name"], widgets["host"], widgets["user"]):
                    if not widget.get_text().strip():
                        widget.grab_focus()
                        break
                return
            try:
                if server:
                    self.store.update_server(server.id, name, host, user, port, group_id, password, public_key)
                else:
                    self.store.add_server(name, host, user, port, group_id, password, public_key)
            except ReadOnlyStoreError:
                self.toast_label.set_label(self.t("read_only_mode_enabled"))
                dialog.destroy()
                return
            self.refresh_list()
        dialog.destroy()
