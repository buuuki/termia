# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Note filtering and ordering without GTK dependencies."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Note, NoteCategory, Server


@dataclass(frozen=True)
class NoteListItem:
    note: Note
    server_name: str


@dataclass(frozen=True)
class NoteTreeCategory:
    name: str
    items: tuple[NoteListItem, ...]


@dataclass(frozen=True)
class NoteTreeServer:
    id: str
    name: str
    categories: tuple[NoteTreeCategory, ...]


@dataclass(frozen=True)
class NoteTree:
    personal_categories: tuple[NoteTreeCategory, ...]
    servers: tuple[NoteTreeServer, ...]


class NotesPresenter:
    def __init__(
        self,
        notes: Callable[[], list[Note]],
        categories: Callable[[], list[NoteCategory]],
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
        personal_only: bool = False,
        server_only: bool = False,
    ) -> list[NoteListItem]:
        query = query.strip().casefold()
        if server_only and server_id is None:
            return []
        servers = {server.id: server.name for server in self._servers()}
        items: list[NoteListItem] = []
        for note in self._notes():
            if category is not None and note.category != category:
                continue
            if server_id is not None and note.server_id != server_id:
                continue
            if personal_only and note.server_id is not None:
                continue
            if server_only and note.server_id != server_id:
                continue
            server_name = servers.get(note.server_id or "", "")
            haystack = " ".join((note.title, note.content, note.category, server_name)).casefold()
            if query and query not in haystack:
                continue
            items.append(NoteListItem(note, server_name))
        return sorted(items, key=lambda item: (item.note.modified_at, item.note.title.casefold()), reverse=True)

    def categories(self, server_id: str | None = None) -> list[tuple[str, int]]:
        counts = {
            category.name: sum(
                note.category == category.name and note.server_id == (server_id or None)
                for note in self._notes()
            )
            for category in self._categories()
            if category.server_id == (server_id or None)
        }
        return sorted(counts.items(), key=lambda item: item[0].casefold())

    def tree(
        self, query: str = "", include_server_ids: set[str] | None = None,
    ) -> NoteTree:
        """Build the notes tree, retaining servers with categories or drafts."""
        items = self.items(query)
        categories = self._categories()
        personal_items = [item for item in items if item.note.server_id is None]
        items_by_server: dict[str, list[NoteListItem]] = {}
        server_names = {server.id: server.name for server in self._servers()}
        category_names_by_scope: dict[str | None, list[str]] = {}
        for category in categories:
            category_names_by_scope.setdefault(category.server_id, []).append(category.name)
        for item in items:
            if item.note.server_id is not None:
                items_by_server.setdefault(item.note.server_id, []).append(item)

        def categories_for(
            scope_id: str | None, scoped_items: list[NoteListItem],
        ) -> tuple[NoteTreeCategory, ...]:
            grouped: dict[str, list[NoteListItem]] = {}
            for item in scoped_items:
                grouped.setdefault(item.note.category, []).append(item)
            if not query:
                for name in category_names_by_scope.get(scope_id, ()):
                    grouped.setdefault(name, [])
            return tuple(
                NoteTreeCategory(name, tuple(grouped[name]))
                for name in sorted(grouped, key=lambda value: (value != "", value.casefold()))
            )

        personal_categories = categories_for(None, personal_items)
        server_ids = set(items_by_server)
        if not query:
            server_ids.update(
                server_id for server_id in category_names_by_scope
                if server_id is not None and server_id in server_names
            )
        server_ids.update((include_server_ids or set()) & server_names.keys())
        servers = tuple(
            NoteTreeServer(
                server_id,
                server_names.get(server_id, ""),
                categories_for(server_id, items_by_server.get(server_id, [])),
            )
            for server_id in sorted(
                server_ids,
                key=lambda server_id: (server_names.get(server_id, "").casefold(), server_id),
            )
        )
        return NoteTree(personal_categories, servers)
