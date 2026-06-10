# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any
from uuid import uuid4

from .models import Group, Server, StoreData


def normalize_asbru_name(value: str) -> str:
    name = value.strip()
    suffix = " - copy"
    while name.lower().endswith(suffix):
        name = name[:-len(suffix)].rstrip()
    return name


def extract_asbru_connections(
    payload: Any,
) -> tuple[list[tuple[str, str, str | None]], list[tuple[str, str, str, int, str | None, str]]]:
    environments = payload.get("environments", payload) if isinstance(payload, dict) else {}
    if not isinstance(environments, dict):
        return [], []

    groups: list[tuple[str, str, str | None]] = []
    servers: list[tuple[str, str, str, int, str | None, str]] = []
    group_uuids = {
        str(uuid)
        for uuid, node in environments.items()
        if isinstance(node, dict) and bool(node.get("_is_group"))
    }

    for uuid, node in environments.items():
        if not isinstance(node, dict):
            continue
        node_id = str(uuid)
        name = normalize_asbru_name(str(node.get("name") or node.get("description") or node_id))
        parent_uuid = str(node.get("parent")) if node.get("parent") in group_uuids else None
        if node_id in group_uuids:
            groups.append((node_id, name, parent_uuid))
            continue

        method = str(node.get("method") or node.get("protocol") or "ssh").lower()
        host = str(node.get("ip") or node.get("host") or node.get("hostname") or "").strip()
        if not host or method not in ("", "ssh"):
            continue
        user = str(node.get("user") or node.get("username") or node.get("passphrase user") or "").strip()
        if "@" in host and not user:
            user, host = host.split("@", 1)
        try:
            port = int(node.get("port") or node.get("ssh_port") or 22)
        except (TypeError, ValueError):
            port = 22
        public_key = str(node.get("public key") or "").strip()
        servers.append((name, host, user, port, parent_uuid, public_key))
    return groups, servers


def merge_asbru_connections(
    data: StoreData,
    groups: list[tuple[str, str, str | None]],
    servers: list[tuple[str, str, str, int, str | None, str]],
) -> tuple[int, int]:
    groups_by_path: dict[tuple[str | None, str], Group] = {
        (group.parent_id, group.name): group for group in data.groups
    }
    imported_ids: dict[str, str] = {}
    pending = groups.copy()
    added_groups = 0
    while pending:
        progressed = False
        for source_id, name, source_parent in pending[:]:
            if source_parent and source_parent not in imported_ids:
                continue
            parent_id = imported_ids.get(source_parent)
            key = (parent_id, name)
            group = groups_by_path.get(key)
            if group is None:
                group = Group(id=str(uuid4()), name=name, parent_id=parent_id)
                data.groups.append(group)
                groups_by_path[key] = group
                added_groups += 1
            imported_ids[source_id] = group.id
            pending.remove((source_id, name, source_parent))
            progressed = True
        if not progressed:
            source_id, name, _source_parent = pending.pop(0)
            key = (None, name)
            group = groups_by_path.get(key)
            if group is None:
                group = Group(id=str(uuid4()), name=name)
                data.groups.append(group)
                groups_by_path[key] = group
                added_groups += 1
            imported_ids[source_id] = group.id

    existing = {(server.host, server.user, server.port, server.group_id) for server in data.servers}
    added_servers = 0
    for name, host, user, port, source_group_id, public_key in servers:
        group_id = imported_ids.get(source_group_id)
        key = (host, user, port, group_id)
        if key in existing:
            continue
        data.servers.append(
            Server(
                id=str(uuid4()),
                name=normalize_asbru_name(name),
                host=host,
                user=user,
                port=port,
                group_id=group_id,
                public_key=public_key,
            )
        )
        existing.add(key)
        added_servers += 1
    return added_groups, added_servers
