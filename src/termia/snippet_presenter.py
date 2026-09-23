# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .connection_utils import find_server, group_path_labels
from .models import CommandSnippet, Group, Server
from .snippets import available_snippets


@dataclass(frozen=True)
class SnippetListItem:
    id: str
    label: str


@dataclass(frozen=True)
class SnippetTargetItem:
    id: str
    label: str


class SnippetPresenter:
    """Pure presentation logic for snippet manager and runner views."""

    def __init__(
        self,
        snippets: Callable[[], list[CommandSnippet]],
        groups: Callable[[], list[Group]],
        servers: Callable[[], list[Server]],
    ) -> None:
        self._snippets = snippets
        self._groups = groups
        self._servers = servers

    @staticmethod
    def label(snippet: CommandSnippet) -> str:
        return f"{snippet.category} · {snippet.name}" if snippet.category else snippet.name

    def snippet(self, snippet_id: str | None) -> CommandSnippet | None:
        return next((item for item in self._snippets() if item.id == snippet_id), None)

    def manager_items(self) -> list[SnippetListItem]:
        snippets = sorted(
            self._snippets(),
            key=lambda item: (item.category.lower(), item.name.lower()),
        )
        return [SnippetListItem(item.id, self.label(item)) for item in snippets]

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
