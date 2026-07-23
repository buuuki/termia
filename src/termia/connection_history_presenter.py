# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from .models import ConnectionHistoryEntry
from .statistics_utils import format_duration

HistoryEntriesProvider = Callable[[], Sequence[ConnectionHistoryEntry]]
Translator = Callable[[str], str]


class ConnectionHistoryPresenter:
    """Prepare connection-history data without depending on GTK or the window."""

    def __init__(self, entries: HistoryEntriesProvider, translate: Translator) -> None:
        self._entries = entries
        self._translate = translate

    def filter_entries(
        self,
        query: str,
        show_local_terminals: bool = True,
    ) -> list[ConnectionHistoryEntry]:
        normalized_query = query.strip().casefold()
        entries = [
            entry
            for entry in self._entries()
            if show_local_terminals or entry.kind != "local"
        ]
        if not normalized_query:
            return entries
        return [
            entry
            for entry in entries
            if self.entry_matches(entry, normalized_query)
        ]

    def entry_matches(self, entry: ConnectionHistoryEntry, query: str) -> bool:
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

    def build_line(self, entry: ConnectionHistoryEntry) -> str:
        return " · ".join(
            part
            for part in (self.build_heading(entry), self.build_subtitle(entry))
            if part
        )

    def build_heading(self, entry: ConnectionHistoryEntry) -> str:
        timestamp = self.format_timestamp(entry.ended_at or entry.started_at)
        result = self.format_result(entry.result, entry.ended_at)
        duration = format_duration(entry.duration_seconds)
        return " · ".join(part for part in (timestamp, result, duration) if part)

    def build_subtitle(self, entry: ConnectionHistoryEntry) -> str:
        kind = self.format_kind(entry.kind)
        target = entry.server_name or entry.title or self._translate("local_terminal")
        details = [part for part in (kind, target) if part]
        endpoint = self.format_endpoint(entry.user, entry.host, entry.port)
        if endpoint:
            details.append(endpoint)
        if entry.detail:
            details.append(entry.detail)
        return " · ".join(details)

    def format_timestamp(self, value: str) -> str:
        if not value:
            return ""
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return value
        return timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def format_result(self, result: str, ended_at: str) -> str:
        if not ended_at:
            return self._translate("history_result_running")
        if result == "failed":
            return self._translate("history_result_failed")
        if result == "disconnected":
            return self._translate("history_result_disconnected")
        return self._translate("history_result_closed")

    def format_kind(self, kind: str) -> str:
        if kind == "ssh":
            return self._translate("history_kind_ssh")
        if kind == "local":
            return self._translate("history_kind_local")
        return kind

    def format_endpoint(self, user: str, host: str, port: int) -> str:
        if not host:
            return ""
        endpoint = f"{host}:{port}" if port else host
        return f"{user}@{endpoint}" if user else endpoint
