# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from .models import Group, LocalTerminalProfile, Server


def find_server(servers: list[Server], server_id: str) -> Server | None:
    return next((server for server in servers if server.id == server_id), None)


def find_group(groups: list[Group], group_id: str | None) -> Group | None:
    return next((group for group in groups if group.id == group_id), None)


def find_local_terminal_profile(
    profiles: list[LocalTerminalProfile], profile_id: str
) -> LocalTerminalProfile | None:
    return next((profile for profile in profiles if profile.id == profile_id), None)


def unique_server_clone_name(servers: list[Server], name: str) -> str:
    existing_names = {server.name for server in servers}
    base_name = f"{name}-clone"
    if base_name not in existing_names:
        return base_name
    index = 2
    while f"{base_name}-{index}" in existing_names:
        index += 1
    return f"{base_name}-{index}"


def server_matches_query(server: Server, query: str) -> bool:
    if not query:
        return True
    return query in " ".join([server.name, server.host, server.user]).lower()


def group_matches_query(group: Group, query: str) -> bool:
    if not query:
        return True
    return query in group.name.lower()


def group_descendant_ids(groups: list[Group], group_id: str) -> set[str]:
    descendants: set[str] = set()
    pending = [group_id]
    while pending:
        parent_id = pending.pop()
        children = [group.id for group in groups if group.parent_id == parent_id]
        descendants.update(children)
        pending.extend(children)
    return descendants


def group_path_labels(groups: list[Group]) -> list[tuple[Group, str]]:
    groups_by_id = {group.id: group for group in groups}

    def path_label(group: Group) -> str:
        names = [group.name]
        visited = {group.id}
        parent_id = group.parent_id
        while parent_id and parent_id in groups_by_id and parent_id not in visited:
            parent = groups_by_id[parent_id]
            names.append(parent.name)
            visited.add(parent_id)
            parent_id = parent.parent_id
        return " / ".join(reversed(names))

    return sorted(((group, path_label(group)) for group in groups), key=lambda item: item[1].lower())
