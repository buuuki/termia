# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass

from .connection_utils import group_matches_query, server_matches_query
from .models import Group, LocalTerminalProfile, Server


@dataclass(frozen=True)
class SidebarRow:
    kind: str
    item_id: str
    title: str
    subtitle: str = ""


@dataclass
class SidebarProjection:
    rows: list[SidebarRow]
    children_by_parent: dict[str | None, list[Group]]
    servers_by_group: dict[str | None, list[Server]]
    local_terminal_profiles: list[LocalTerminalProfile]
    recent_servers: list[Server]
    favorite_servers: list[Server]
    root_groups: list[Group]
    ungrouped_servers: list[Server]


def server_connection_text(server: Server) -> str:
    return f"{server.user}@{server.host}:{server.port}" if server.user else f"{server.host}:{server.port}"


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


def build_sidebar_projection(
    groups: list[Group],
    servers: list[Server],
    local_terminal_profiles: list[LocalTerminalProfile],
    recent_server_ids: list[str],
    query: str,
    expanded_groups: dict[str, bool],
    collapse_groups_on_startup: bool,
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

    def is_expanded(group_id: str) -> bool:
        if query:
            return True
        default = True if group_id in {"__recent__", "__favorites__", "__local_terminals__"} else not collapse_groups_on_startup
        return expanded_groups.get(group_id, default)

    def server_row(server: Server, kind: str = "server") -> SidebarRow:
        return SidebarRow(kind, server.id, server.name, server_connection_text(server))

    def collect_group_rows(group: Group) -> list[SidebarRow]:
        child_rows: list[SidebarRow] = []
        if is_expanded(group.id):
            for child in sorted(children_by_parent.get(group.id, []), key=lambda item: item.name.lower()):
                child_rows.extend(collect_group_rows(child))
            for server in sorted(servers_by_group.get(group.id, []), key=lambda item: item.name.lower()):
                child_rows.append(server_row(server))
        if query and not group_matches_query(group, query) and not child_rows:
            return []
        descendant_servers = sum(1 for row in child_rows if row.kind == "server")
        return [SidebarRow("group", group.id, group.name, f"{descendant_servers} servidor(es)"), *child_rows]

    rows = [SidebarRow("local_terminal", profile.id, profile.name or "Local terminal") for profile in profiles]
    if is_expanded("__recent__"):
        rows.extend(server_row(server, "recent") for server in recent)
    if is_expanded("__favorites__"):
        rows.extend(server_row(server, "favorite") for server in favorites)
    for group in root_groups:
        rows.extend(collect_group_rows(group))
    rows.extend(server_row(server) for server in sorted(ungrouped, key=lambda item: item.name.lower()))

    return SidebarProjection(
        rows=rows,
        children_by_parent=children_by_parent,
        servers_by_group=servers_by_group,
        local_terminal_profiles=profiles,
        recent_servers=recent,
        favorite_servers=favorites,
        root_groups=root_groups,
        ungrouped_servers=ungrouped,
    )
