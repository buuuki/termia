# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""SFTP window: GTK presentation, with an injected backend factory."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import posixpath
import stat

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .known_hosts import ScannedHostKey, append_scanned_host_key
from .sftp_backend import ParamikoBackend
from .sftp_service import (
    AuthenticationRequired, Cancelled, Endpoint, HostKeyChanged, SFTPService,
    UnknownHost, child_path,
)


class SFTPWindow(Gtk.Window):
    def __init__(self, parent, endpoint: Endpoint, title, translate, on_closed,
                 owner_session_id=None, backend_factory=ParamikoBackend):
        super().__init__(title=f"SFTP — {title}", transient_for=parent)
        self.t = translate
        self.endpoint = endpoint
        self.backend_factory = backend_factory
        self.on_closed = on_closed
        self.owner_session_id = owner_session_id
        self.service = None
        self.disposed = False
        self.dialogs = set()
        self.path = "."
        self.set_default_size(820, 560)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(12)
        self.set_child(box)
        self.toolbar = Gtk.Box(spacing=6)
        box.append(self.toolbar)
        self.button("sftp_up", lambda: self.navigate(posixpath.dirname(self.path) or "/"))
        self.location = Gtk.Entry(text=self.path, hexpand=True)
        self.location.connect("activate", lambda *_: self.navigate(self.location.get_text()))
        self.toolbar.append(self.location)
        self.button("sftp_refresh", lambda: self.navigate(self.path))
        self.actions = Gtk.Box(spacing=6)
        box.append(self.actions)
        self.button("sftp_upload", lambda: self.choose_upload(False), self.actions)
        self.button("sftp_upload_folder", lambda: self.choose_upload(True), self.actions)
        self.button("sftp_download", self.choose_download, self.actions)
        self.button("sftp_mkdir", lambda: self.prompt("sftp_mkdir", self.make_directory), self.actions)
        self.button("sftp_rename", self.rename_selected, self.actions)
        self.button("sftp_delete", self.delete_selected, self.actions)
        self.rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.rows.connect("row-activated", self.activate_row)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.rows)
        box.append(scroll)
        self.progress = Gtk.ProgressBar(show_text=True)
        box.append(self.progress)
        self.status = Gtk.Label(xalign=0, wrap=True)
        box.append(self.status)
        controls = Gtk.Box(spacing=6)
        box.append(controls)
        self.cancel_button = self.button("cancel", self.cancel, controls)
        self.reconnect_button = self.button("sftp_reconnect", self.connect_backend, controls)
        self.connect("close-request", self.close_requested)
        self.connect_backend()

    def button(self, key, callback, box=None):
        button = Gtk.Button(label=self.t(key))
        button.connect("clicked", lambda *_: callback())
        (box if box is not None else self.toolbar).append(button)
        return button

    def set_busy(self, busy):
        self.toolbar.set_sensitive(not busy)
        self.actions.set_sensitive(not busy)
        self.rows.set_sensitive(not busy)
        self.cancel_button.set_sensitive(busy)
        self.reconnect_button.set_sensitive(not busy)

    def connect_backend(self):
        if self.disposed:
            return
        if self.service:
            self.service.close()
        self.service = SFTPService(self.backend_factory(self.endpoint), GLib.idle_add)
        self.run(lambda backend, _: backend.connect(), self.navigate)

    def run(self, operation, done=None):
        if self.disposed or self.service.busy:
            return
        if self.service.cancelled.is_set():
            self.status.set_text(self.t("sftp_reconnect_required"))
            return
        self.set_busy(True)
        self.status.set_text(self.t("sftp_working"))
        self.progress.set_fraction(0)

        def completed(value):
            self.set_busy(False)
            self.status.set_text(self.t("sftp_done"))
            if done:
                done(value)

        self.service.submit(operation, completed, self.failed, self.show_progress)

    def show_progress(self, current, total):
        self.progress.set_fraction(min(current / total, 1) if total else 0)
        self.progress.set_text(f"{current:,} / {total:,} B")

    def failed(self, error):
        self.set_busy(False)
        if isinstance(error, UnknownHost):
            self.confirm(
                f"{self.endpoint.host}:{self.endpoint.port}\n{error.key_type}\n{error.fingerprint}\n" + self.t("sftp_trust"),
                lambda: self.accept_host(error),
            )
        elif isinstance(error, AuthenticationRequired):
            self.prompt("sftp_password", self.use_password, secret=True)
        elif isinstance(error, HostKeyChanged):
            self.status.set_text(self.t("sftp_key_changed"))
        elif isinstance(error, Cancelled):
            self.status.set_text(self.t("sftp_cancelled"))
        else:
            self.status.set_text(self.t("sftp_failed"))

    def accept_host(self, error):
        key = ScannedHostKey(error.hostname, error.key_type, error.key_data, error.fingerprint)
        if append_scanned_host_key(key):
            self.connect_backend()
        else:
            self.status.set_text(self.t("sftp_failed"))

    def use_password(self, password):
        self.endpoint = replace(self.endpoint, password=password)
        self.connect_backend()

    def navigate(self, path):
        if not path or any(ord(c) < 32 for c in path):
            return
        def display(entries):
            self.path = path
            self.location.set_text(path)
            while self.rows.get_first_child():
                self.rows.remove(self.rows.get_first_child())
            for entry in entries:
                row = Gtk.ListBoxRow()
                row.entry = entry
                line = Gtk.Box(spacing=12)
                icon = "folder-symbolic" if stat.S_ISDIR(entry.mode) else "text-x-generic-symbolic"
                line.append(Gtk.Image.new_from_icon_name(icon))
                name = Gtk.Label(label=entry.name, xalign=0, hexpand=True,
                                 ellipsize=3, max_width_chars=50)
                name.set_tooltip_text(entry.name)
                line.append(name)
                line.append(Gtk.Label(label=f"{entry.size:,} B"))
                try:
                    date = datetime.fromtimestamp(entry.modified).strftime("%Y-%m-%d %H:%M")
                except (ValueError, OverflowError, OSError):
                    date = "—"
                line.append(Gtk.Label(label=date))
                line.append(Gtk.Label(label=stat.filemode(entry.mode)))
                row.set_child(line)
                self.rows.append(row)
        self.run(lambda backend, _: backend.list_directory(path), display)

    def activate_row(self, _rows, row):
        if stat.S_ISDIR(row.entry.mode):
            self.navigate(child_path(self.path, row.entry.name))

    def selected(self):
        row = self.rows.get_selected_row()
        return child_path(self.path, row.entry.name) if row else None

    def refresh_after(self, _result):
        self.navigate(self.path)

    def make_directory(self, name):
        try:
            path = child_path(self.path, name)
        except ValueError:
            self.status.set_text(self.t("sftp_invalid_name"))
            return
        self.run(lambda backend, _: backend.mkdir(path), self.refresh_after)

    def rename_selected(self):
        source = self.selected()
        if source:
            def rename(name):
                try:
                    target = child_path(self.path, name)
                except ValueError:
                    self.status.set_text(self.t("sftp_invalid_name"))
                    return
                self.run(lambda backend, _: backend.rename(source, target), self.refresh_after)
            self.prompt("sftp_rename", rename)

    def delete_selected(self):
        source = self.selected()
        if source:
            self.confirm(self.t("sftp_delete_confirm") + "\n" + source,
                         lambda: self.run(lambda backend, _: backend.delete(source), self.refresh_after))

    def choose_upload(self, directory):
        self.choose_local(directory, lambda paths: self.upload_paths(paths))

    def upload_paths(self, paths):
        destination = self.path
        def upload(backend, progress):
            for path in paths:
                backend.upload(path, child_path(destination, path.name), progress)
        self.run(upload, self.refresh_after)

    def choose_download(self):
        source = self.selected()
        if source:
            self.choose_local(True, lambda paths: self.run(
                lambda backend, progress: backend.download(source, paths[0] / posixpath.basename(source), progress)))

    def choose_local(self, directory, callback):
        action = Gtk.FileChooserAction.SELECT_FOLDER if directory else Gtk.FileChooserAction.OPEN
        dialog = Gtk.FileChooserDialog(title=self.t("sftp_select"), transient_for=self, modal=True, action=action)
        dialog.add_button(self.t("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.t("sftp_select"), Gtk.ResponseType.OK)
        dialog.set_select_multiple(not directory)
        self.dialogs.add(dialog)
        def response(current, result):
            paths = []
            if result == Gtk.ResponseType.OK:
                files = current.get_files()
                paths = [Path(files.get_item(i).get_path()) for i in range(files.get_n_items())
                         if files.get_item(i).get_path()]
            self.dialogs.discard(current)
            current.destroy()
            if paths and not self.disposed:
                callback(paths)
        dialog.connect("response", response)
        dialog.present()

    def prompt(self, key, callback, secret=False):
        entry = Gtk.Entry(visibility=not secret, activates_default=True)
        self.dialog(self.t(key), callback, entry)

    def confirm(self, message, callback):
        self.dialog(message, lambda _value: callback())

    def dialog(self, message, callback, entry=None):
        dialog = Gtk.Dialog(transient_for=self, modal=True, title="SFTP")
        dialog.add_button(self.t("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.t("sftp_continue"), Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.append(Gtk.Label(label=message, wrap=True, selectable=True))
        if entry is not None:
            content.append(entry)
        self.dialogs.add(dialog)
        def response(current, result):
            value = entry.get_text() if entry is not None else ""
            if entry is not None:
                entry.set_text("")
            self.dialogs.discard(current)
            current.destroy()
            if result == Gtk.ResponseType.OK and not self.disposed:
                callback(value)
            elif not self.disposed:
                self.status.set_text(self.t("sftp_reconnect_required"))
        dialog.connect("response", response)
        dialog.present()

    def cancel(self):
        self.service.cancel()
        self.status.set_text(self.t("sftp_cancelled"))

    def cancel_active_transfer(self, *, close_dialog=False):
        if close_dialog:
            self.close_requested()
            self.destroy()
        else:
            self.cancel()

    def close_requested(self, *_args):
        if not self.disposed:
            self.disposed = True
            self.service.close()
            for dialog in tuple(self.dialogs):
                dialog.destroy()
            self.dialogs.clear()
            self.endpoint = replace(self.endpoint, password="")
            self.on_closed(self)
        return False
