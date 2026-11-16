# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Searchable saved-connection choices for split panes."""

from __future__ import annotations

from dataclasses import dataclass

from .models import LocalTerminalProfile, Server


@dataclass(frozen=True)
class SplitConnectionChoice:
    """A saved SSH server or local profile that can be opened in a split."""

    connection_id: str
    kind: str
    name: str
    detail: str
    search_text: str


def build_split_connection_choices(
    servers: list[Server],
    local_terminal_profiles: list[LocalTerminalProfile],
) -> list[SplitConnectionChoice]:
    """Return saved connection choices sorted by their user-visible name."""

    choices = [
        SplitConnectionChoice(
            connection_id=f"server:{server.id}",
            kind="server",
            name=server.name,
            detail=_server_detail(server),
            search_text=" ".join(
                str(value)
                for value in (server.name, server.host, server.user, server.port)
                if value
            ).casefold(),
        )
        for server in servers
    ]
    choices.extend(
        SplitConnectionChoice(
            connection_id=f"local:{profile.id}",
            kind="local",
            name=profile.name,
            detail=_local_profile_detail(profile),
            search_text=" ".join(
                str(value)
                for value in (
                    profile.name,
                    profile.tab_title,
                    profile.working_directory,
                    profile.shell,
                    profile.arguments,
                    profile.command_on_start,
                )
                if value
            ).casefold(),
        )
        for profile in local_terminal_profiles
    )
    return sorted(choices, key=lambda choice: (choice.name.casefold(), choice.detail.casefold()))


def filter_split_connection_choices(
    choices: list[SplitConnectionChoice],
    query: str,
) -> list[SplitConnectionChoice]:
    """Filter choices case-insensitively using all connection details."""

    normalized_query = query.strip().casefold()
    if not normalized_query:
        return choices
    return [choice for choice in choices if normalized_query in choice.search_text]


def _server_detail(server: Server) -> str:
    endpoint = f"{server.host}:{server.port}" if server.host else ""
    return f"{server.user}@{endpoint}" if server.user else endpoint


def _local_profile_detail(profile: LocalTerminalProfile) -> str:
    return profile.working_directory or profile.shell or profile.tab_title
