# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .connection_utils import find_server, group_path_labels
from .models import CommandSnippet, Group, Server
from .snippets import available_snippets, normalized_categories


@dataclass(frozen=True)
class SnippetListItem:
    id: str
    label: str


@dataclass(frozen=True)
class SnippetTargetItem:
    id: str
    label: str


@dataclass(frozen=True)
class SnippetCategoryItem:
    key: str
    label: str
    count: int
    icon_name: str


class SnippetPresenter:
    """Pure presentation logic for snippet manager and runner views."""

    def __init__(
        self,
        snippets: Callable[[], list[CommandSnippet]],
        groups: Callable[[], list[Group]],
        servers: Callable[[], list[Server]],
        categories: Callable[[], list[str]] | None = None,
    ) -> None:
        self._snippets = snippets
        self._groups = groups
        self._servers = servers
        self._categories = categories or (lambda: [])

    @staticmethod
    def label(snippet: CommandSnippet) -> str:
        return f"{snippet.category} · {snippet.name}" if snippet.category else snippet.name

    def snippet(self, snippet_id: str | None) -> CommandSnippet | None:
        return next((item for item in self._snippets() if item.id == snippet_id), None)

    def categories(self) -> list[SnippetCategoryItem]:
        counts = {
            name: 0 for name in normalized_categories(self._categories(), self._snippets())
        }
        for snippet in self._snippets():
            counts[snippet.category] = counts.get(snippet.category, 0) + 1
        return [
            SnippetCategoryItem(
                key=category,
                label=category,
                count=count,
                icon_name="folder-open-symbolic" if not category else "folder-symbolic",
            )
            for category, count in sorted(
                counts.items(),
                key=lambda item: (not item[0], item[0].lower()),
            )
        ]

    def manager_items(
        self,
        category: str | None = None,
        query: str = "",
    ) -> list[SnippetListItem]:
        query = query.strip().lower()
        snippets = sorted(
            (
                item for item in self._snippets()
                if (category is None or item.category == category)
                and (
                    not query
                    or query in " ".join((item.name, item.category, item.content)).lower()
                )
            ),
            key=lambda item: (item.category.lower(), item.name.lower()),
        )
        return [
            SnippetListItem(item.id, item.name if category is not None else self.label(item))
            for item in snippets
        ]

    def run_items(self, server_id: str | None, query: str) -> list[SnippetListItem]:
        server = find_server(self._servers(), server_id) if server_id else None
        return [
            SnippetListItem(item.id, self.label(item))
            for item in available_snippets(
                self._snippets(),
                server,
                query,
                self._groups(),
            )
        ]

    def targets(self, scope: str) -> list[SnippetTargetItem]:
        if scope == "group":
            return [
                SnippetTargetItem(group.id, label)
                for group, label in group_path_labels(self._groups())
            ]
        if scope == "server":
            return [
                SnippetTargetItem(server.id, server.name)
                for server in sorted(self._servers(), key=lambda item: item.name.lower())
            ]
        return []
