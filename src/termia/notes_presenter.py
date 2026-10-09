# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Note filtering and ordering without GTK dependencies."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Note, Server


@dataclass(frozen=True)
class NoteListItem:
    note: Note
    server_name: str


class NotesPresenter:
    def __init__(
        self,
        notes: Callable[[], list[Note]],
        categories: Callable[[], list[str]],
        servers: Callable[[], list[Server]],
    ) -> None:
        self._notes = notes
        self._categories = categories
        self._servers = servers

    def items(
        self,
        query: str = "",
        category: str | None = None,
        server_id: str | None = None,
    ) -> list[NoteListItem]:
        query = query.strip().casefold()
        servers = {server.id: server.name for server in self._servers()}
        items: list[NoteListItem] = []
        for note in self._notes():
            if category is not None and note.category != category:
                continue
            if server_id is not None and note.server_id != server_id:
                continue
            server_name = servers.get(note.server_id or "", "")
            haystack = " ".join((note.title, note.content, note.category, server_name)).casefold()
            if query and query not in haystack:
                continue
            items.append(NoteListItem(note, server_name))
        return sorted(items, key=lambda item: (item.note.modified_at, item.note.title.casefold()), reverse=True)

    def categories(self) -> list[tuple[str, int]]:
        counts = {
            name: sum(note.category == name for note in self._notes())
            for name in self._categories()
        }
        return sorted(counts.items(), key=lambda item: item[0].casefold())
