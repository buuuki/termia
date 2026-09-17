# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""About-owned update UI. No release parsing or package manager commands."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from . import __version__
from .update_controller import CheckResult, UpdateController


class UpdateDialog(Gtk.Window):
    def __init__(self, parent, translate, controller_factory=UpdateController):
        super().__init__(title=translate("update_title"), transient_for=parent, modal=True)
        self.t = translate
        self.set_default_size(460, -1)
        self.set_destroy_with_parent(True)
        self.controller = controller_factory(__version__, GLib.idle_add, self.completed)
        self.result = None
        self.installed = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(18)
        self.set_child(box)
        box.append(Gtk.Label(label=self.t("update_current").format(version=__version__), xalign=0))
        self.status = Gtk.Label(label=self.t("update_intro"), xalign=0, wrap=True)
        self.status.set_max_width_chars(60)
        box.append(self.status)
        self.notes = Gtk.LinkButton(label=self.t("update_notes"), uri="https://github.com/buuuki/termia/releases")
        self.notes.set_visible(False)
        box.append(self.notes)
        self.spinner = Gtk.Spinner()
        box.append(self.spinner)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.append(actions)
        self.check_button = Gtk.Button(label=self.t("update_check"))
        self.check_button.connect("clicked", self.check)
        actions.append(self.check_button)
        self.install_button = Gtk.Button(label=self.t("update_install"))
        self.install_button.set_visible(False)
        self.install_button.connect("clicked", self.confirm_install)
        actions.append(self.install_button)
        self.close_button = Gtk.Button(label=self.t("close"))
        self.close_button.connect("clicked", self.close_or_cancel)
        actions.append(self.close_button)
        self.connect("close-request", self.close_requested)
        self.connect("unrealize", lambda *_: self.controller.close())

    def working(self, key):
        self.status.set_text(self.t(key))
        self.spinner.start()
        self.check_button.set_sensitive(False)
        self.install_button.set_sensitive(False)
        self.close_button.set_label(self.t("cancel"))

    def check(self, _button=None):
        self.result = None
        self.install_button.set_visible(False)
        self.notes.set_visible(False)
        self.working("update_checking")
        self.controller.check()

    def completed(self, state, payload):
        if state == "applying":
            self.status.set_text(self.t("update_applying"))
            self.close_button.set_sensitive(False)
            return
        self.spinner.stop()
        self.close_button.set_sensitive(True)
        self.close_button.set_label(self.t("close"))
        self.check_button.set_sensitive(not self.installed)
        if state == "error":
            self.status.set_text(self.t(payload))
            self.install_button.set_visible(False)
        elif isinstance(payload, CheckResult):
            self.result = payload
            release = payload.release
            reason = payload.installation.reason
            if release is None:
                message = self.t("update_current_latest")
            else:
                message = self.t("update_available").format(version=release.label)
                self.notes.set_uri(release.url)
                self.notes.set_visible(True)
                adapter = payload.installation.adapter
                if adapter is not None and adapter.kind == "update_debian" and release.asset is None:
                    reason = "update_no_verified_asset"
                self.install_button.set_visible(adapter is not None and not reason)
                self.install_button.set_sensitive(not reason)
            if reason:
                message += "\n\n" + self.t(reason)
            self.status.set_text(message)
        else:
            self.installed = True
            self.check_button.set_sensitive(False)
            self.install_button.set_visible(False)
            key = "update_installed_source" if self.result.installation.adapter.kind == "update_source" else "update_installed"
            self.status.set_text(self.t(key))

    def confirm_install(self, _button):
        if self.result is None or self.controller.busy:
            return
        confirmation = Gtk.Dialog(title=self.t("update_install"), transient_for=self, modal=True)
        confirmation.set_destroy_with_parent(True)
        confirmation.add_button(self.t("cancel"), Gtk.ResponseType.CANCEL)
        confirmation.add_button(self.t("update_install"), Gtk.ResponseType.OK)
        confirmation.set_default_response(Gtk.ResponseType.CANCEL)
        label = Gtk.Label(label=self.t("update_confirm").format(version=self.result.release.label), wrap=True)
        label.set_max_width_chars(55)
        for side in ("top", "bottom", "start", "end"):
            getattr(label, f"set_margin_{side}")(16)
        confirmation.get_content_area().append(label)

        def response(dialog, response_id):
            dialog.destroy()
            if response_id == Gtk.ResponseType.OK and not self.controller.closed:
                self.working("update_preparing")
                self.controller.install(self.result)

        confirmation.connect("response", response)
        confirmation.present()

    def close_or_cancel(self, _button):
        if self.controller.busy:
            if self.controller.stop():
                self.status.set_text(self.t("update_cancelling"))
        else:
            self.close()

    def close_requested(self, _window):
        if self.controller.applying:
            return True
        self.controller.close()
        return False


def attach_updates(about: Gtk.AboutDialog, translate) -> None:
    """Extend the public header-bar API without traversing About's internals."""
    header = about.get_titlebar()
    if not isinstance(header, Gtk.HeaderBar):
        header = Gtk.HeaderBar()
        about.set_titlebar(header)
    button = Gtk.Button(label=translate("update_check"))
    header.pack_start(button)
    dialogs = []

    def show(_button):
        if dialogs and not dialogs[0].controller.closed:
            dialogs[0].present()
            return
        dialog = UpdateDialog(about, translate)
        dialogs[:] = [dialog]
        dialog.present()
        dialog.check()

    button.connect("clicked", show)
    about.connect("close-request", lambda *_: bool(dialogs and dialogs[0].controller.applying))
