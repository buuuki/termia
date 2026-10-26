# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""About-owned update UI. No release parsing or package manager commands."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from . import __version__
from .dialog_actions import add_dialog_action_button, configure_action_area
from .update_controller import CheckResult, PreparedUpdate, UpdateController


class UpdateDialog(Gtk.Window):
    def __init__(self, parent, translate, controller_factory=UpdateController):
        super().__init__(title=translate("update_title"), transient_for=parent, modal=True)
        self.t = translate
        self.set_default_size(460, -1)
        self.set_destroy_with_parent(True)
        self.controller = controller_factory(__version__, GLib.idle_add, self.completed)
        self.result = None
        self.installed = False
        self.prepared = None
        self.manual_mode = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(18)
        self.set_child(box)
        box.append(Gtk.Label(label=self.t("update_current").format(version=__version__), xalign=0))
        self.installation_label = Gtk.Label(label=self.t("update_type_detecting"), xalign=0, wrap=True)
        box.append(self.installation_label)
        self.status = Gtk.Label(label=self.t("update_intro"), xalign=0, wrap=True)
        self.status.set_max_width_chars(60)
        box.append(self.status)
        self.notes = Gtk.LinkButton(label=self.t("update_notes"), uri="https://github.com/buuuki/termia/releases")
        self.notes.set_visible(False)
        box.append(self.notes)
        self.plan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.plan_box.set_visible(False)
        box.append(self.plan_box)
        self.dependency_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.dependency_label.set_max_width_chars(60)
        dependency_scroller = Gtk.ScrolledWindow()
        dependency_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        dependency_scroller.set_min_content_height(100)
        dependency_scroller.set_max_content_height(200)
        dependency_scroller.set_propagate_natural_height(True)
        dependency_scroller.set_child(self.dependency_label)
        self.plan_box.append(dependency_scroller)
        self.manual_label = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.manual_label.set_max_width_chars(60)
        self.manual_label.set_visible(False)
        self.plan_box.append(self.manual_label)
        self.copy_button = Gtk.Button(label=self.t("update_copy_commands"))
        self.copy_button.connect("clicked", self.copy_commands)
        self.copy_button.set_visible(False)
        self.plan_box.append(self.copy_button)
        self.assisted_button = Gtk.Button(label=self.t("update_assisted"))
        self.assisted_button.connect("clicked", lambda *_: self.apply_prepared(True))
        self.plan_box.append(self.assisted_button)
        self.manual_button = Gtk.Button(label=self.t("update_manual"))
        self.manual_button.connect("clicked", self.show_manual)
        self.plan_box.append(self.manual_button)
        self.continue_button = Gtk.Button(label=self.t("update_recheck_continue"))
        self.continue_button.connect("clicked", lambda *_: self.apply_prepared(False))
        self.plan_box.append(self.continue_button)
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
        configure_action_area(actions)
        self.connect("close-request", self.close_requested)
        self.connect("unrealize", lambda *_: self.controller.close())

    def working(self, key):
        self.status.set_text(self.t(key))
        self.spinner.start()
        self.check_button.set_sensitive(False)
        self.install_button.set_sensitive(False)
        self.close_button.set_label(self.t("cancel"))
        for button in (self.assisted_button, self.manual_button, self.continue_button):
            button.set_sensitive(False)

    def check(self, _button=None):
        self.result = None
        self.prepared = None
        self.manual_mode = False
        self.manual_label.set_visible(False)
        self.copy_button.set_visible(False)
        self.plan_box.set_visible(False)
        self.install_button.set_visible(False)
        self.notes.set_visible(False)
        self.working("update_checking")
        self.controller.check()

    def completed(self, state, payload):
        if state == "installation":
            self.show_installation(payload)
            return
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
            self.plan_box.set_visible(False)
        elif isinstance(payload, PreparedUpdate):
            self.show_plan(payload)
        elif isinstance(payload, CheckResult):
            self.show_installation(payload.installation)
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
            self.prepared = None
            self.plan_box.set_visible(False)
            self.check_button.set_sensitive(False)
            self.install_button.set_visible(False)
            key = "update_installed_source" if self.result.installation.adapter.kind == "update_source" else "update_installed"
            self.status.set_text(self.t(key))

    def confirm_install(self, _button):
        if self.result is None or self.controller.busy:
            return
        confirmation = Gtk.Dialog(title=self.t("update_install"), transient_for=self, modal=True)
        confirmation.set_destroy_with_parent(True)
        add_dialog_action_button(
            confirmation, self.t("cancel"), Gtk.ResponseType.CANCEL,
        )
        add_dialog_action_button(
            confirmation, self.t("update_install"), Gtk.ResponseType.OK,
        )
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
                self.controller.prepare_update(self.result)

        confirmation.connect("response", response)
        confirmation.present()

    def show_installation(self, installation):
        kind = installation.adapter.kind if installation.adapter is not None else "unknown"
        key = {"update_source": "update_type_source", "update_debian": "update_type_debian"}.get(
            kind, "update_type_unknown")
        self.installation_label.set_text(self.t(key))

    def show_plan(self, prepared):
        self.prepared = prepared
        self.result = prepared.result
        self.show_installation(self.result.installation)
        plan = prepared.dependencies
        none = self.t("update_dependency_none")
        added = "\n".join(plan.added) or none
        missing = "\n".join(plan.missing) or none
        self.dependency_label.set_text(self.t("update_dependency_summary").format(
            added=added, missing=missing))
        self.status.set_text(self.t("update_dependency_warning") if plan.missing
                             else self.t("update_dependencies_ready"))
        if self.result.installation.adapter.kind == "update_debian":
            self.status.set_text(self.status.get_text() + "\n\n" + self.t("update_debian_dependencies"))
        self.install_button.set_visible(False)
        self.plan_box.set_visible(True)
        self.assisted_button.set_visible(bool(plan.missing) and plan.assisted_available)
        self.manual_button.set_visible(bool(plan.missing))
        self.continue_button.set_visible(not plan.missing or self.manual_mode)
        for button in (self.assisted_button, self.manual_button, self.continue_button):
            button.set_sensitive(True)
        if self.manual_mode:
            self.show_manual()

    def show_manual(self, _button=None):
        if self.prepared is None:
            return
        self.manual_mode = True
        commands = self.prepared.dependencies.manual_commands
        self.manual_label.set_text(self.t("update_manual_steps").format(commands=commands)
                                   if commands else self.t("update_dependencies_ready"))
        self.manual_label.set_visible(True)
        self.copy_button.set_visible(bool(commands))
        self.continue_button.set_visible(True)

    def copy_commands(self, _button=None):
        if self.prepared is not None:
            self.get_clipboard().set(self.prepared.dependencies.manual_commands)

    def apply_prepared(self, assisted):
        if self.prepared is None or self.controller.busy:
            return
        self.working("update_dependencies_checking")
        self.controller.install(self.prepared, assisted=assisted)

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
