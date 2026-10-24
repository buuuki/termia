# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""SFTP window: GTK presentation, with an injected backend factory."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import posixpath
import stat
from time import monotonic

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from .dialog_actions import add_dialog_action_button, configure_action_area
from .debug import log_event
from .known_hosts import ScannedHostKey, append_scanned_host_key
from .sftp_backend import ParamikoBackend, failure_details
from .sftp_service import (
    AuthenticationRequired, Cancelled, Endpoint, HostKeyChanged, SFTPService,
    UnknownHost, child_path,
)
from .ui_state import SignalConnections


def format_file_size(size: int) -> str:
    amount = float(size)
    for unit in ("B", "kB", "MB", "GB"):
        if amount < 1000 or unit == "GB":
            return f"{size} B" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1000


class SFTPWindow(Gtk.Window):
    def __init__(self, parent, endpoint: Endpoint, title, translate, on_closed,
                 owner_session_id=None, backend_factory=ParamikoBackend):
        super().__init__(title=f"SFTP — {title}", application=parent.get_application())
        self.set_modal(False)
        # A modal SFTP prompt must not grab unrelated Termia windows.
        self.window_group = Gtk.WindowGroup()
        self.window_group.add_window(self)
        self.t = translate
        self.endpoint = endpoint
        self.backend_factory = backend_factory
        self.on_closed = on_closed
        self.owner_session_id = owner_session_id
        self.service = None
        self.disposed = False
        self.ui_released = False
        self.ui_signals = SignalConnections()
        self.dialogs = set()
        self.dialog_signals = {}
        self.transfer_active = False
        self.connection_ready = False
        self.stop_source = 0
        self.reconnect_pending = False
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
        self.ui_signals.connect(self.location, "activate", lambda *_: self.navigate(self.location.get_text()))
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
        self.rows.set_activate_on_single_click(False)
        self.ui_signals.connect(self.rows, "row-activated", self.activate_row)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.rows)
        box.append(scroll)
        self.progress = Gtk.ProgressBar(show_text=True)
        self.progress.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        box.append(self.progress)
        self.status = Gtk.Label(xalign=0, wrap=True)
        box.append(self.status)
        controls = Gtk.Box()
        configure_action_area(controls)
        controls.set_halign(Gtk.Align.END)
        box.append(controls)
        self.cancel_button = self.button("cancel", self.cancel, controls)
        self.reconnect_button = self.button("sftp_reconnect", self.connect_backend, controls)
        self.disconnect_button = self.button("disconnect", self.disconnect, controls)
        self.ui_signals.connect(self, "close-request", self.close_requested)
        self.connect_backend()

    def button(self, key, callback, box=None):
        button = Gtk.Button(label=self.t(key))
        self.ui_signals.connect(button, "clicked", lambda *_: callback())
        (box if box is not None else self.toolbar).append(button)
        return button

    def set_busy(self, busy):
        stopping = bool(self.service and self.service.cancelled.is_set() and not self.service.stopped)
        busy = busy or stopping
        self.toolbar.set_sensitive(not busy and self.connection_ready)
        self.actions.set_sensitive(not busy and self.connection_ready)
        self.rows.set_sensitive(not busy and self.connection_ready)
        self.cancel_button.set_sensitive(busy and not stopping)
        self.reconnect_button.set_sensitive(not busy)

    def connect_backend(self):
        if self.disposed or self.reconnect_pending:
            return
        if self.service and self.service.busy and not self.service.cancelled.is_set():
            return
        if self.service:
            self.service.close()
            if not self.service.stopped or self.stop_source:
                self.connection_ready = False
                self.reconnect_pending = True
                self.status.set_text(self.t("sftp_stopping"))
                self.monitor_stop()
                return
        self.connection_ready = False
        self.service = SFTPService(self.backend_factory(self.endpoint), GLib.idle_add)
        def connected(path):
            self.connection_ready = True
            self.navigate(path)
        self.run(lambda backend, _: backend.connect(), connected)

    def run(self, operation, done=None, *, transfer=False):
        if self.disposed or self.service.busy:
            return
        if self.service.cancelled.is_set():
            self.status.set_text(self.t("sftp_reconnect_required"))
            return
        self.set_busy(True)
        self.transfer_active = transfer
        self.status.set_text(self.t("sftp_working"))
        if transfer:
            self.progress.set_fraction(0)
            self.progress.set_text("")
            self.progress.set_tooltip_text(None)

        def completed(value):
            self.transfer_active = False
            self.set_busy(False)
            if transfer:
                self.progress.set_fraction(1)
            self.status.set_text(self.t("sftp_done"))
            if done:
                done(value)

        self.service.submit(operation, completed, self.failed, self.show_progress)

    def show_progress(self, value):
        mb = 1000 * 1000
        if value.total is None:
            self.progress.pulse()
            size = f"{value.current / mb:.1f} MB"
        else:
            self.progress.set_fraction(min(value.current / value.total, 1) if value.total else 1)
            size = f"{value.current / mb:.1f} / {value.total / mb:.1f} MB"
        text = self.t("sftp_progress").format(
            name=value.name, size=size, files=value.files_completed,
            speed=f"{value.bytes_per_second / mb:.2f}")
        self.progress.set_text(text)
        self.progress.set_tooltip_text(text + "\n" + self.t("sftp_progress_total").format(
            transferred=f"{value.bytes_transferred / mb:.1f}"))

    def failed(self, error):
        transfer = self.transfer_active
        self.transfer_active = False
        self.set_busy(False)
        if self.service.cleanup_failed:
            self.status.set_text(self.t("sftp_cleanup_failed"))
            return
        if isinstance(error, UnknownHost):
            self.status.set_text(self.t("sftp_reconnect_required"))
            self.confirm(
                f"{self.endpoint.host}:{self.endpoint.port}\n{error.key_type}\n{error.fingerprint}\n" + self.t("sftp_trust"),
                lambda: self.accept_host(error),
            )
        elif isinstance(error, AuthenticationRequired):
            self.status.set_text(self.t("sftp_reconnect_required"))
            self.prompt("sftp_credential", self.use_password, secret=True)
        elif isinstance(error, HostKeyChanged):
            self.status.set_text(self.t("sftp_key_changed"))
        elif isinstance(error, Cancelled):
            self.status.set_text(self.t("sftp_cancelled"))
        else:
            key, reconnect = failure_details(error)
            message = self.t(key)
            if reconnect:
                self.connection_ready = False
                self.service.cancel()
                self.monitor_stop()
                message += " " + self.t("sftp_reconnect_required")
            if transfer:
                message += " " + self.t("sftp_partial")
            self.status.set_text(message)

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
                line.append(Gtk.Label(label=format_file_size(entry.size)))
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
        self.run(upload, self.refresh_after, transfer=True)

    def choose_download(self):
        source = self.selected()
        if source:
            self.choose_local(True, lambda paths: self.run(
                lambda backend, progress: backend.download(source, paths[0] / posixpath.basename(source), progress),
                transfer=True))

    def choose_local(self, directory, callback):
        action = Gtk.FileChooserAction.SELECT_FOLDER if directory else Gtk.FileChooserAction.OPEN
        dialog = Gtk.FileChooserDialog(title=self.t("sftp_select"), transient_for=self, modal=True, action=action)
        add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
        add_dialog_action_button(
            dialog, self.t("sftp_select"), Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(not directory)
        self.dialogs.add(dialog)
        signals = self.dialog_signals[dialog] = SignalConnections()
        def response(current, result):
            paths = []
            if result == Gtk.ResponseType.OK:
                files = current.get_files()
                paths = [Path(files.get_item(i).get_path()) for i in range(files.get_n_items())
                         if files.get_item(i).get_path()]
            self.release_dialog(current)
            if paths and not self.disposed:
                callback(paths)
        signals.connect(dialog, "response", response)
        dialog.present()

    def prompt(self, key, callback, secret=False):
        entry = Gtk.Entry(visibility=not secret, activates_default=True)
        self.dialog(self.t(key), callback, entry)

    def confirm(self, message, callback):
        self.dialog(message, lambda _value: callback())

    def dialog(self, message, callback, entry=None):
        previous_status = self.status.get_text()
        dialog = Gtk.Dialog(transient_for=self, modal=True, title="SFTP")
        add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
        add_dialog_action_button(
            dialog, self.t("sftp_continue"), Gtk.ResponseType.OK,
        )
        content = dialog.get_content_area()
        content.append(Gtk.Label(label=message, wrap=True, selectable=True))
        if entry is not None:
            content.append(entry)
        self.dialogs.add(dialog)
        signals = self.dialog_signals[dialog] = SignalConnections()
        def response(current, result):
            value = entry.get_text() if entry is not None else ""
            if entry is not None:
                entry.set_text("")
            self.release_dialog(current)
            if result == Gtk.ResponseType.OK and not self.disposed:
                callback(value)
            elif not self.disposed:
                self.status.set_text(previous_status)
        signals.connect(dialog, "response", response)
        dialog.present()

    def release_dialog(self, dialog):
        self.dialogs.discard(dialog)
        signals = self.dialog_signals.pop(dialog, None)
        if signals is not None:
            signals.disconnect()
        dialog.destroy()

    def release_closed_ui(self):
        """Retire UI handlers only after the service has verifiably stopped."""
        if self.ui_released:
            return
        if not self.disposed or not self.service.stopped:
            return
        self.ui_released = True
        self.ui_signals.disconnect()
        for dialog in tuple(self.dialogs):
            self.release_dialog(dialog)
        self.window_group.remove_window(self)
        on_closed, self.on_closed = self.on_closed, None
        try:
            if on_closed is not None:
                on_closed(self)
        finally:
            self.destroy()

    def cancel(self):
        self.reconnect_pending = False
        self.connection_ready = False
        self.service.cancel()
        self.status.set_text(self.t("sftp_cancelled"))
        self.monitor_stop()

    def monitor_stop(self):
        """Observe actual worker/closer exit without blocking the GTK thread."""
        if self.stop_source:
            return
        started = monotonic()
        service = self.service

        def check():
            if service.stopped:
                self.stop_source = 0
                if self.disposed:
                    self.release_closed_ui()
                elif self.reconnect_pending:
                    self.reconnect_pending = False
                    self.connect_backend()
                else:
                    self.set_busy(False)
                return GLib.SOURCE_REMOVE
            if service.cleanup_failed:
                self.stop_source = 0
                self.reconnect_pending = False
                self.status.set_text(self.t("sftp_cleanup_failed"))
                log_event("sftp.cleanup_failed", window_disposed=self.disposed)
                # Keep ownership in the host registry for shutdown observation,
                # but do not poll a terminal failure forever or replace it.
                return GLib.SOURCE_REMOVE
            if monotonic() - started >= 30:
                # Keep observing; a deadline is not proof that cleanup succeeded.
                self.status.set_text(self.t("sftp_stopping"))
            return GLib.SOURCE_CONTINUE

        self.set_busy(True)
        self.cancel_button.set_sensitive(False)
        self.stop_source = GLib.timeout_add(50, check)

    def disconnect(self):
        self.close_requested()

    def cancel_active_transfer(self, *, close_dialog=False):
        if close_dialog:
            self.close_requested()
        else:
            self.cancel()

    def shutdown_cleanup_state(self):
        if self.service.stopped:
            return "stopped"
        workers_alive = any(
            worker is not None and worker.is_alive()
            for worker in (self.service.worker, self.service.close_worker)
        )
        if self.service.cleanup_failed and not workers_alive:
            return "failed"
        return "pending"

    def close_requested(self, *_args):
        if not self.disposed:
            self.disposed = True
            self.reconnect_pending = False
            self.service.close()
            for dialog in tuple(self.dialogs):
                self.release_dialog(dialog)
            self.endpoint = replace(self.endpoint, password="")
            self.set_visible(False)
            self.monitor_stop()
        return True
