# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preferences for bundled tools, applied on the next Termia start."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .stores import ConnectionStore, ReadOnlyStoreError


class OptionalToolsDialog:
    def __init__(
        self,
        parent: Gtk.Window,
        store: ConnectionStore,
        translate: Callable[[str], str],
        notify: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.store = store
        self.translate = translate
        self.notify = notify

    def show(self) -> None:
        dialog = Gtk.Dialog(
            title=self.translate("optional_tools"),
            transient_for=self.parent,
            modal=True,
        )
        dialog.set_resizable(False)
        dialog.set_default_size(420, -1)
        dialog.add_button(self.translate("cancel"), Gtk.ResponseType.CANCEL)
        save = dialog.add_button(self.translate("save"), Gtk.ResponseType.OK)
        save.set_sensitive(not self.store.read_only and not self.store.encryption_locked)

        content = dialog.get_content_area()
        content.set_spacing(12)
        for side in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{side}")(16)

        statistics = Gtk.CheckButton(label=self.translate("statistics_enabled"))
        statistics.set_active(self.store.data.app.statistics_enabled)
        content.append(statistics)

        sftp = Gtk.CheckButton(label=self.translate("sftp_tool"))
        sftp.set_active(self.store.data.app.sftp_enabled)
        content.append(sftp)

        hint = Gtk.Label(label=self.translate("optional_tools_restart"), xalign=0)
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        content.append(hint)

        def on_response(current: Gtk.Dialog, response: Gtk.ResponseType) -> None:
            if response == Gtk.ResponseType.OK:
                try:
                    self.store.update_optional_tools(
                        statistics_enabled=statistics.get_active(),
                        sftp_enabled=sftp.get_active(),
                    )
                except ReadOnlyStoreError:
                    self.notify(self.translate("read_only_mode_enabled"))
                else:
                    self.notify(self.translate("optional_tools_restart"))
            current.destroy()

        dialog.connect("response", on_response)
        dialog.present()
