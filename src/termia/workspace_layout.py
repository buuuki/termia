# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture and validate the safe, persistent part of terminal layouts."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .ui_state import TerminalPane, TerminalSession

WorkspaceNode = dict[str, Any]
WORKSPACE_OPEN_CONFIRMATION_PANES = 8
MAX_WORKSPACE_PANES = 16


def pane_workspace_node(pane: TerminalPane) -> WorkspaceNode:
    if pane.server_id is not None:
        return {"type": "pane", "connection_type": "server", "connection_id": pane.server_id}
    return {
        "type": "pane",
        "connection_type": "local",
        "connection_id": pane.local_profile_id or "",
    }


def capture_workspace_tab(session: TerminalSession) -> dict[str, WorkspaceNode] | None:
    root = session.page.get_first_child()
    if root is None:
        return None
    layout = capture_workspace_node(root, session)
    return {"layout": layout} if layout is not None else None


def capture_workspace_tabs(sessions: Iterable[TerminalSession]) -> list[dict[str, WorkspaceNode]]:
    return [tab for session in sessions if (tab := capture_workspace_tab(session)) is not None]


def capture_workspace_node(widget: Gtk.Widget, session: TerminalSession) -> WorkspaceNode | None:
    if isinstance(widget, Gtk.Paned):
        start = widget.get_start_child()
        end = widget.get_end_child()
        if start is None or end is None:
            return None
        start_node = capture_workspace_node(start, session)
        end_node = capture_workspace_node(end, session)
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
    return pane_workspace_node(pane) if pane is not None else None


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
        return {
            "type": "pane",
            "connection_type": node["connection_type"],
            "connection_id": node["connection_id"],
        }
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
    if not isinstance(tabs, list):
        return []
    layouts: list[WorkspaceNode] = []
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        layout = normalized_workspace_node(tab.get("layout"))
        if layout is not None:
            layouts.append(layout)
    return layouts


def workspace_total_pane_count(tabs: object) -> int:
    """Count panes across every valid tab in a saved workspace."""

    return sum(workspace_pane_count(layout) for layout in workspace_tab_layouts(tabs))
