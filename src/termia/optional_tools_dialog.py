# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Manage external tools and apply their preferences on Save."""

from __future__ import annotations

import logging
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .dialog_actions import add_dialog_action_button
from .dialog_window import DialogWindow
from .stores import ConnectionStore

logger = logging.getLogger(__name__)


class OptionalToolsDialog:
    def __init__(
        self,
        parent: Gtk.Window,
        store: ConnectionStore,
        translate: Callable[[str], str],
        notify: Callable[[str], None],
        *, external_options=None, external_apply=None,
    ) -> None:
        self.parent = parent
        self.store = store
        self.translate = translate
        self.notify = notify
        self.external_options = external_options or list
        self.external_apply = external_apply

    def show(self) -> None:
        dialog = DialogWindow(
            title=self.translate("optional_tools"),
            transient_for=self.parent,
            modal=True,
        )
        dialog.set_resizable(False)
        dialog.set_default_size(420, -1)
        add_dialog_action_button(
            dialog, self.translate("cancel"), Gtk.ResponseType.CANCEL,
        )
        save = add_dialog_action_button(
            dialog, self.translate("save"), Gtk.ResponseType.OK,
        )
        save.set_sensitive(not self.store.read_only and not self.store.encryption_locked)

        content = dialog.get_content_area()
        content.set_spacing(12)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{side}")(16)

        external_rows = {}
        for identifier, title, problem, enabled, available in self.external_options():
            switch = self.add_switch_row(
                content, self.translate("addon_external_title").format(name=title), enabled
            )
            switch.set_sensitive(
                available and not self.store.read_only and not self.store.encryption_locked
            )
            status = Gtk.Label(label=self.translate(problem) if problem else "", xalign=0, wrap=True)
            status.set_visible(bool(problem))
            content.append(status)
            external_rows[identifier] = (title, switch, status)
        hint = Gtk.Label(xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        content.append(hint)

        def external_changes():
            active = {item[0]: item[3] for item in self.external_options()}
            return [
                (identifier, title, switch, status)
                for identifier, (title, switch, status) in external_rows.items()
                if switch.get_sensitive() and switch.get_active() != active.get(identifier)
            ]

        def refresh_hint(*_args):
            messages = []
            changed = external_changes()
            if changed:
                messages.append(self.translate("addon_external_pending").format(
                    addons=", ".join(item[1] for item in changed)
                ))
            hint.set_text("\n".join(messages))
            hint.set_visible(bool(messages))

        for _title, switch, _status in external_rows.values():
            switch.connect("notify::active", refresh_hint)
        refresh_hint()

        def on_response(current: DialogWindow, response: Gtk.ResponseType) -> None:
            if response != Gtk.ResponseType.OK:
                current.destroy()
                return
            changed = external_changes()
            if not changed:
                current.destroy()
                return
            if self.store.read_only or self.store.encryption_locked:
                self.notify(self.translate("read_only_mode_enabled"))
                return
            messages = []
            applied = []
            for identifier, title, switch, status in changed:
                try:
                    self.external_apply(identifier, switch.get_active())
                except Exception:
                    logger.exception("Cannot apply plugin preference: %s", identifier)
                    option = next(item for item in self.external_options() if item[0] == identifier)
                    message = (f"{title}: {self.translate(option[2])}" if option[2]
                               else self.translate("addon_external_failed").format(name=title))
                    switch.set_active(option[3])
                    switch.set_sensitive(
                        option[4] and not self.store.read_only and not self.store.encryption_locked
                    )
                    status.set_text(message)
                    status.set_visible(True)
                    if applied:
                        messages.append(self.translate("addon_external_applied").format(
                            addons=", ".join(applied)
                        ))
                    messages.append(message)
                    self.notify("\n".join(messages))
                    refresh_hint()
                    return
                else:
                    applied.append(title)
                    option = next(item for item in self.external_options() if item[0] == identifier)
                    status.set_text(self.translate(option[2]) if option[2] else "")
                    status.set_visible(bool(option[2]))
            if applied:
                messages.append(self.translate("addon_external_applied").format(addons=", ".join(applied)))
            self.notify("\n".join(messages))
            current.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    @staticmethod
    def add_switch_row(content: Gtk.Box, title: str, active: bool) -> Gtk.Switch:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label=title, xalign=0)
        label.set_hexpand(True)
        switch = Gtk.Switch()
        switch.set_active(active)
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_tooltip_text(title)
        label.set_mnemonic_widget(switch)
        row.append(label)
        row.append(switch)
        content.append(row)
        return switch
