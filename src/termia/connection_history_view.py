# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import datetime
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from .statistics_utils import format_duration


class ConnectionHistoryViewMixin:
    def on_connection_history(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("connection_history_title"), transient_for=self, modal=True)
        dialog.set_resizable(True)
        dialog.set_default_size(760, 520)
        clear_button = self.add_dialog_action_button(dialog, self.t("clear_history"), Gtk.ResponseType.REJECT)
        clear_button.add_css_class("destructive-action")
        self.configure_write_action(clear_button)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE, last=True)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)

        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text(self.t("search_history"))
        search_entry.connect("search-changed", lambda _entry: self.refresh_connection_history(list_box, search_entry))
        content.append(search_entry)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scroller.set_child(list_box)
        content.append(scroller)

        self.refresh_connection_history(list_box, search_entry)
        dialog.connect("response", self.on_connection_history_response, list_box, search_entry)
        dialog.present()

    def on_connection_history_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        list_box: Gtk.ListBox,
        search_entry: Gtk.SearchEntry,
    ) -> None:
        if response == Gtk.ResponseType.REJECT:
            self.confirm_clear_connection_history(dialog, list_box, search_entry)
            return
        dialog.destroy()

    def confirm_clear_connection_history(
        self,
        dialog: Gtk.Dialog,
        list_box: Gtk.ListBox,
        search_entry: Gtk.SearchEntry,
    ) -> None:
        alert = Gtk.AlertDialog(message=self.t("clear_history"), detail=self.t("clear_history_confirm"))
        alert.set_buttons([self.t("cancel"), self.t("clear_history")])
        alert.set_cancel_button(0)
        alert.set_default_button(0)
        alert.choose(self, None, self.on_clear_connection_history_confirmed, (dialog, list_box, search_entry, alert))

    def on_clear_connection_history_confirmed(
        self,
        _alert: Gtk.AlertDialog,
        result: Gio.AsyncResult,
        data: tuple[Gtk.Dialog, Gtk.ListBox, Gtk.SearchEntry, Gtk.AlertDialog],
    ) -> None:
        dialog, list_box, search_entry, alert = data
        try:
            response = alert.choose_finish(result)
        except Exception:
            return
        if response != 1:
            return
        self.store.clear_history()
        self.refresh_connection_history(list_box, search_entry)
        self.toast_label.set_label(self.t("history_cleared"))
        dialog.present()

    def refresh_connection_history(self, list_box: Gtk.ListBox, search_entry: Gtk.SearchEntry) -> None:
        child = list_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            list_box.remove(child)
            child = next_child

        query = search_entry.get_text().strip().casefold()
        entries = self.filter_connection_history_entries(query)
        if not entries:
            row = Gtk.ListBoxRow()
            label_key = "no_matching_history" if query else "no_connection_history"
            label = Gtk.Label(label=self.t(label_key))
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

    def filter_connection_history_entries(self, query: str) -> list[Any]:
        entries = self.store.history_store.entries
        if not query:
            return entries
        return [entry for entry in entries if self.connection_history_entry_matches(entry, query)]

    def connection_history_entry_matches(self, entry: Any, query: str) -> bool:
        haystack = " ".join(
            str(value)
            for value in (
                entry.kind,
                entry.title,
                entry.server_name,
                entry.host,
                entry.user,
                entry.result,
                entry.detail,
                entry.started_at,
                entry.ended_at,
                format_duration(entry.duration_seconds),
            )
            if value
        ).casefold()
        return query in haystack

    def build_history_row(self, entry: Any) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        top_line = Gtk.Label(label=self.build_history_heading(entry))
        top_line.set_xalign(0)
        top_line.set_wrap(True)
        top_line.add_css_class("heading")

        subtitle = Gtk.Label(label=self.build_history_subtitle(entry))
        subtitle.set_xalign(0)
        subtitle.set_wrap(True)
        subtitle.add_css_class("dim-label")

        box.append(top_line)
        box.append(subtitle)
        row.set_child(box)
        return row

    def build_history_heading(self, entry) -> str:
        timestamp = self.format_history_timestamp(entry.ended_at or entry.started_at)
        result = self.format_history_result(entry.result, entry.ended_at)
        duration = format_duration(entry.duration_seconds)
        parts = [part for part in (timestamp, result, duration) if part]
        return " · ".join(parts)

    def build_history_subtitle(self, entry) -> str:
        kind = self.format_history_kind(entry.kind)
        target = entry.server_name or entry.title or self.t("local_terminal")
        details = [part for part in (kind, target) if part]
        endpoint = self.format_history_endpoint(entry.user, entry.host, entry.port)
        if endpoint:
            details.append(endpoint)
        if entry.detail:
            details.append(entry.detail)
        return " · ".join(details)

    def format_history_timestamp(self, value: str) -> str:
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return value
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def format_history_result(self, result: str, ended_at: str) -> str:
        if not ended_at:
            return self.t("history_result_running")
        if result == "failed":
            return self.t("history_result_failed")
        if result == "disconnected":
            return self.t("history_result_disconnected")
        return self.t("history_result_closed")

    def format_history_kind(self, kind: str) -> str:
        if kind == "ssh":
            return self.t("history_kind_ssh")
        if kind == "local":
            return self.t("history_kind_local")
        return kind

    def format_history_endpoint(self, user: str, host: str, port: int) -> str:
        if not host:
            return ""
        endpoint = host
        if port:
            endpoint = f"{endpoint}:{port}"
        if user:
            endpoint = f"{user}@{endpoint}"
        return endpoint
