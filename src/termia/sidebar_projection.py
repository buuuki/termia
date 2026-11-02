# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass

from .connection_utils import server_matches_query
from .models import Group, LocalTerminalProfile, Server, Workspace


@dataclass(frozen=True)
class SidebarRow:
    kind: str
    item_id: str
    title: str
    subtitle: str = ""


@dataclass
class SidebarProjection:
    children_by_parent: dict[str | None, list[Group]]
    servers_by_group: dict[str | None, list[Server]]
    local_terminal_profiles: list[LocalTerminalProfile]
    workspaces: list[Workspace]
    recent_servers: list[Server]
    favorite_servers: list[Server]
    root_groups: list[Group]
    ungrouped_servers: list[Server]


def local_terminal_profile_matches_query(profile: LocalTerminalProfile, query: str) -> bool:
    haystack = " ".join(
        str(value)
        for value in (
            profile.name,
            profile.working_directory,
            profile.shell,
            profile.arguments,
            profile.command_on_start,
            profile.tab_title,
        )
        if value
    ).casefold()
    return query in haystack


def workspace_matches_query(workspace: Workspace, query: str) -> bool:
    return query in workspace.name.casefold()


def build_sidebar_projection(
    groups: list[Group],
    servers: list[Server],
    local_terminal_profiles: list[LocalTerminalProfile],
    workspaces: list[Workspace],
    recent_server_ids: list[str],
    query: str,
) -> SidebarProjection:
    children_by_parent: dict[str | None, list[Group]] = {}
    for group in groups:
        children_by_parent.setdefault(group.parent_id, []).append(group)

    filtered_servers = [server for server in servers if server_matches_query(server, query)]
    servers_by_group: dict[str | None, list[Server]] = {}
    for server in filtered_servers:
        servers_by_group.setdefault(server.group_id, []).append(server)

    profiles = sorted(local_terminal_profiles, key=lambda item: item.name.lower())
    if query:
        profiles = [profile for profile in profiles if local_terminal_profile_matches_query(profile, query)]

    visible_workspaces = sorted(workspaces, key=lambda item: item.name.casefold())
    if query:
        visible_workspaces = [workspace for workspace in visible_workspaces if workspace_matches_query(workspace, query)]

    servers_by_id = {server.id: server for server in filtered_servers}
    recent: list[Server] = []
    seen: set[str] = set()
    for server_id in recent_server_ids:
        if server_id in seen:
            continue
        server = servers_by_id.get(server_id)
        if server is not None:
            seen.add(server_id)
            recent.append(server)

    favorites = sorted(
        [server for server in filtered_servers if server.favorite],
        key=lambda item: (item.name.lower(), item.host.lower(), item.user.lower(), item.port),
    )
    root_groups = sorted(children_by_parent.get(None, []), key=lambda item: item.name.lower())
    ungrouped = servers_by_group.get(None, [])

    return SidebarProjection(
        children_by_parent=children_by_parent,
        servers_by_group=servers_by_group,
        local_terminal_profiles=profiles,
        workspaces=visible_workspaces,
        recent_servers=recent,
        favorite_servers=favorites,
        root_groups=root_groups,
        ungrouped_servers=ungrouped,
    )
