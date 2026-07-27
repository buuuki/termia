# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gio, Gtk, Pango

from .connection_history_presenter import ConnectionHistoryPresenter
from .models import ConnectionHistoryEntry


class ConnectionHistoryDialog:
    """Builds the connection history dialog from explicit dependencies."""

    def __init__(
        self,
        parent: Gtk.Window,
        presenter: ConnectionHistoryPresenter,
        translate: Callable[[str], str],
        clear_history: Callable[[], None],
        configure_write_action: Callable[[Gtk.Widget], Gtk.Widget],
        show_toast: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.presenter = presenter
        self.translate = translate
        self.clear_history = clear_history
        self.configure_write_action = configure_write_action
        self.show_toast = show_toast

    def show(self) -> None:
        dialog = Gtk.Dialog(title=self.translate("connection_history_title"), transient_for=self.parent, modal=True)
        dialog.set_resizable(True)
        dialog.set_default_size(760, 520)
        state = {"show_local_terminals": True}
        clear_button = dialog.add_button(self.translate("clear_history"), Gtk.ResponseType.REJECT)
        clear_button.set_margin_end(6)
        clear_button.set_margin_bottom(12)
        clear_button.add_css_class("destructive-action")
        self.configure_write_action(clear_button)
        close_button = dialog.add_button(self.translate("close"), Gtk.ResponseType.CLOSE)
        close_button.set_margin_end(12)
        close_button.set_margin_bottom(12)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_hexpand(True)
        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text(self.translate("search_history"))
        actions.append(search_entry)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        if hasattr(list_box, "set_show_separators"):
            list_box.set_show_separators(False)
        scroller.set_child(list_box)
        search_entry.connect(
            "search-changed",
            lambda _entry: self.refresh_connection_history(state, list_box, search_entry),
        )

        local_toggle = Gtk.ToggleButton(label=self.translate("hide_local_terminals"))
        local_toggle.set_active(False)
        local_toggle.connect("toggled", self.on_toggle_local_terminals, state, list_box, search_entry)
        actions.append(local_toggle)
        content.append(actions)
        content.append(scroller)

        self.refresh_connection_history(state, list_box, search_entry)
        dialog.connect("response", self.on_connection_history_response, state, list_box, search_entry, local_toggle)
        dialog.present()

    def on_toggle_local_terminals(
        self,
        button: Gtk.ToggleButton,
        state: dict[str, bool],
        list_box: Gtk.ListBox,
        search_entry: Gtk.SearchEntry,
    ) -> None:
        state["show_local_terminals"] = not button.get_active()
        button.set_label(
            self.translate("show_local_terminals")
            if button.get_active()
            else self.translate("hide_local_terminals")
        )
        self.refresh_connection_history(state, list_box, search_entry)

    def on_connection_history_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        state: dict[str, bool],
        list_box: Gtk.ListBox,
        search_entry: Gtk.SearchEntry,
        local_toggle: Gtk.ToggleButton,
    ) -> None:
        if response == Gtk.ResponseType.REJECT:
            self.confirm_clear_connection_history(dialog, state, list_box, search_entry, local_toggle)
            return
        dialog.destroy()

    def confirm_clear_connection_history(
        self,
        dialog: Gtk.Dialog,
        state: dict[str, bool],
        list_box: Gtk.ListBox,
        search_entry: Gtk.SearchEntry,
        local_toggle: Gtk.ToggleButton,
    ) -> None:
        alert = Gtk.AlertDialog(
            message=self.translate("clear_history"),
            detail=self.translate("clear_history_confirm"),
        )
        alert.set_buttons([self.translate("cancel"), self.translate("clear_history")])
        alert.set_cancel_button(0)
        alert.set_default_button(0)
        alert.choose(
            self.parent,
            None,
            self.on_clear_connection_history_confirmed,
            (dialog, state, list_box, search_entry, local_toggle, alert),
        )

    def on_clear_connection_history_confirmed(
        self,
        _alert: Gtk.AlertDialog,
        result: Gio.AsyncResult,
        data: tuple[Gtk.Dialog, dict[str, bool], Gtk.ListBox, Gtk.SearchEntry, Gtk.ToggleButton, Gtk.AlertDialog],
    ) -> None:
        dialog, state, list_box, search_entry, local_toggle, alert = data
        try:
            response = alert.choose_finish(result)
        except Exception:
            return
        if response != 1:
            return
        self.clear_history()
        self.refresh_connection_history(state, list_box, search_entry)
        local_toggle.set_sensitive(False)
        self.show_toast(self.translate("history_cleared"))
        dialog.present()

    def refresh_connection_history(
        self,
        state: dict[str, bool],
        list_box: Gtk.ListBox,
        search_entry: Gtk.SearchEntry,
    ) -> None:
        child = list_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            list_box.remove(child)
            child = next_child

        query = search_entry.get_text()
        show_local_terminals = state.get("show_local_terminals", True)
        entries = self.presenter.filter_entries(query, show_local_terminals)
        if not entries:
            row = Gtk.ListBoxRow()
            label_key = (
                "no_matching_history"
                if query.strip() or not show_local_terminals
                else "no_connection_history"
            )
            label = Gtk.Label(label=self.translate(label_key))
            label.set_xalign(0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.set_child(label)
            list_box.append(row)
            return

        for entry in entries:
            list_box.append(self.build_history_row(entry))

    def build_history_row(self, entry: ConnectionHistoryEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(0)
        box.set_margin_bottom(0)
        box.set_margin_start(12)
        box.set_margin_end(12)

        label = Gtk.Label(label=self.presenter.build_line(entry))
        label.set_xalign(0)
        label.set_wrap(False)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(label)
        row.set_child(box)
        return row
