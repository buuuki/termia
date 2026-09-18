# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-snippet domain rules, independent from GTK and VTE."""
from __future__ import annotations

import re
import shlex

from .models import CommandSnippet, Group, Server

SNIPPET_SCOPES = {"global", "group", "server"}
VARIABLE_PATTERN = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]*)\}\}")


class SnippetError(ValueError):
    """A translation key for invalid snippet data or variable input."""


def normalize_snippet(
    snippet_id: str, name: str, content: str, category: str = "",
    scope: str = "global", target_id: str = "",
) -> CommandSnippet:
    name, content, category = name.strip(), content.strip(), category.strip()
    scope, target_id = scope.strip(), target_id.strip()
    if not name:
        raise SnippetError("snippet_name_required")
    if not content:
        raise SnippetError("snippet_content_required")
    if scope not in SNIPPET_SCOPES:
        raise SnippetError("snippet_scope_invalid")
    if scope == "global":
        target_id = ""
    elif not target_id:
        raise SnippetError("snippet_scope_target_required")
    return CommandSnippet(snippet_id, name, content, category, scope, target_id)


def snippet_variables(content: str) -> list[str]:
    return list(dict.fromkeys(VARIABLE_PATTERN.findall(content)))


def render_snippet(content: str, values: dict[str, str]) -> str:
    variables = snippet_variables(content)
    if any(not values.get(variable, "").strip() for variable in variables):
        raise SnippetError("snippet_variable_required")
    return VARIABLE_PATTERN.sub(lambda match: shlex.quote(values[match.group(1)]), content)


def server_group_ids(server: Server, groups: list[Group]) -> set[str]:
    groups_by_id = {group.id: group for group in groups}
    group_ids: set[str] = set()
    group_id = server.group_id
    while group_id and group_id not in group_ids:
        group_ids.add(group_id)
        group = groups_by_id.get(group_id)
        group_id = group.parent_id if group is not None else None
    return group_ids


def snippet_applies(
    snippet: CommandSnippet,
    server: Server | None,
    groups: list[Group] | None = None,
) -> bool:
    if snippet.scope == "global":
        return True
    if server is None:
        return False
    if snippet.scope == "server":
        return snippet.target_id == server.id
    return (
        snippet.scope == "group"
        and snippet.target_id in server_group_ids(server, groups or [])
    )


def available_snippets(
    snippets: list[CommandSnippet],
    server: Server | None,
    query: str = "",
    groups: list[Group] | None = None,
) -> list[CommandSnippet]:
    query = query.strip().lower()
    return sorted(
        (
            snippet for snippet in snippets
            if snippet_applies(snippet, server, groups)
            and (not query or query in " ".join((snippet.name, snippet.category)).lower())
        ),
        key=lambda snippet: (snippet.category.lower(), snippet.name.lower()),
    )


def snippet_target_exists(
    snippet: CommandSnippet,
    groups: list[Group],
    servers: list[Server],
) -> bool:
    if snippet.scope == "global":
        return True
    if snippet.scope == "group":
        return any(group.id == snippet.target_id for group in groups)
    return any(server.id == snippet.target_id for server in servers)
