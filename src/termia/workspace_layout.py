# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture and validate the safe, persistent part of terminal layouts."""
from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .ui_state import TerminalPane, TerminalSession

WorkspaceNode = dict[str, Any]
MAX_WORKSPACE_PANES = 32


def pane_workspace_node(
    pane: TerminalPane,
    *,
    include_local_context: bool = True,
) -> WorkspaceNode:
    if pane.server_id is not None:
        return {"type": "pane", "connection_type": "server", "connection_id": pane.server_id}
    node: WorkspaceNode = {
        "type": "pane",
        "connection_type": "local",
        "connection_id": pane.local_profile_id or "",
    }
    working_directory = local_pane_working_directory(pane) if include_local_context else None
    if working_directory is not None:
        node["working_directory"] = working_directory
    return node


def local_pane_working_directory(pane: TerminalPane) -> str | None:
    if pane.server_id is not None or pane.child_pid is None:
        return None
    try:
        path = Path(os.readlink(f"/proc/{pane.child_pid}/cwd"))
    except OSError:
        return None
    return str(path) if path.is_absolute() else None


def capture_workspace_tab(
    session: TerminalSession,
    *,
    include_local_context: bool = True,
) -> dict[str, WorkspaceNode | str] | None:
    root = session.page.get_first_child()
    if root is None:
        return None
    layout = capture_workspace_node(
        root,
        session,
        include_local_context=include_local_context,
    )
    if layout is None:
        return None
    tab: dict[str, WorkspaceNode | str] = {"layout": layout}
    if include_local_context and session.title_locked and session.title.strip():
        tab["title"] = session.title.strip()
    return tab


def capture_workspace_tabs(
    sessions: Iterable[TerminalSession],
    *,
    include_local_context: bool = True,
) -> list[dict[str, WorkspaceNode | str]]:
    return [
        tab
        for session in sessions
        if (
            tab := capture_workspace_tab(
                session,
                include_local_context=include_local_context,
            )
        )
        is not None
    ]


def capture_workspace_node(
    widget: Gtk.Widget,
    session: TerminalSession,
    *,
    include_local_context: bool = True,
) -> WorkspaceNode | None:
    if isinstance(widget, Gtk.Paned):
        start = widget.get_start_child()
        end = widget.get_end_child()
        if start is None or end is None:
            return None
        start_node = capture_workspace_node(
            start,
            session,
            include_local_context=include_local_context,
        )
        end_node = capture_workspace_node(
            end,
            session,
            include_local_context=include_local_context,
        )
        if start_node is None or end_node is None:
            return None
        orientation = "horizontal" if widget.get_orientation() == Gtk.Orientation.HORIZONTAL else "vertical"
        size = widget.get_width() if orientation == "horizontal" else widget.get_height()
        ratio = widget.get_position() / size if size > 0 else 0.5
        return {
            "type": "split",
            "orientation": orientation,
            "position": max(0.1, min(ratio, 0.9)),
            "start": start_node,
            "end": end_node,
        }
    pane = next((item for item in session.panes.values() if item.container is widget), None)
    return (
        pane_workspace_node(pane, include_local_context=include_local_context)
        if pane is not None
        else None
    )


def workspace_layout_is_valid(node: object) -> bool:
    if not isinstance(node, dict):
        return False
    node_type = node.get("type")
    if node_type == "pane":
        connection_type = node.get("connection_type")
        connection_id = node.get("connection_id")
        return (
            connection_type in {"server", "local"}
            and isinstance(connection_id, str)
            and (connection_type == "local" or bool(connection_id))
        )
    if node_type == "split":
        return (
            node.get("orientation") in {"horizontal", "vertical"}
            and isinstance(node.get("position", 0.5), (int, float))
            and workspace_layout_is_valid(node.get("start"))
            and workspace_layout_is_valid(node.get("end"))
        )
    return False


def normalized_workspace_node(node: object) -> WorkspaceNode | None:
    if not workspace_layout_is_valid(node) or not isinstance(node, dict):
        return None
    if node["type"] == "pane":
        normalized = {
            "type": "pane",
            "connection_type": node["connection_type"],
            "connection_id": node["connection_id"],
        }
        working_directory = node.get("working_directory")
        if (
            node["connection_type"] == "local"
            and isinstance(working_directory, str)
            and Path(working_directory).is_absolute()
        ):
            normalized["working_directory"] = working_directory
        return normalized
    start = normalized_workspace_node(node["start"])
    end = normalized_workspace_node(node["end"])
    if start is None or end is None:
        return None
    return {
        "type": "split",
        "orientation": node["orientation"],
        "position": max(0.1, min(float(node.get("position", 0.5)), 0.9)),
        "start": start,
        "end": end,
    }


def workspace_root_pane(node: WorkspaceNode) -> WorkspaceNode | None:
    current: object = node
    while isinstance(current, dict) and current.get("type") == "split":
        current = current.get("start")
    return current if workspace_layout_is_valid(current) else None


def workspace_pane_count(node: object) -> int:
    if not isinstance(node, dict):
        return 0
    if node.get("type") == "pane":
        return 1
    if node.get("type") == "split":
        return workspace_pane_count(node.get("start")) + workspace_pane_count(node.get("end"))
    return 0


def workspace_tab_layouts(tabs: object) -> list[WorkspaceNode]:
    return [tab["layout"] for tab in normalized_workspace_tabs(tabs)]


def normalized_workspace_tabs(tabs: object) -> list[dict[str, Any]]:
    if not isinstance(tabs, list):
        return []
    normalized_tabs: list[dict[str, Any]] = []
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        layout = normalized_workspace_node(tab.get("layout"))
        if layout is not None:
            normalized_tab: dict[str, Any] = {"layout": layout}
            title = tab.get("title")
            if isinstance(title, str) and title.strip():
                normalized_tab["title"] = title.strip()
            normalized_tabs.append(normalized_tab)
    return normalized_tabs


def workspace_total_pane_count(tabs: object) -> int:
    """Count panes across every valid tab in a saved workspace."""

    return sum(workspace_pane_count(layout) for layout in workspace_tab_layouts(tabs))
