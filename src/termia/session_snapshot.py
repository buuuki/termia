# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persist the safe, restorable part of the last open Termia session."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .workspace_layout import MAX_WORKSPACE_PANES, workspace_tab_layouts, workspace_total_pane_count

SESSION_SNAPSHOT_SCHEMA_VERSION = 1


class SessionSnapshotStore:
    """Store connection references and split geometry, never terminal state."""

    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = path
        self.read_only = read_only

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict) or payload.get("schema_version") != SESSION_SNAPSHOT_SCHEMA_VERSION:
            return []
        tabs = payload.get("tabs")
        if workspace_total_pane_count(tabs) > MAX_WORKSPACE_PANES:
            return []
        return [{"layout": layout} for layout in workspace_tab_layouts(tabs)]

    def save(self, tabs: object) -> None:
        if self.read_only:
            return
        layouts = workspace_tab_layouts(tabs)
        if not layouts:
            self.clear()
            return
        payload = {
            "schema_version": SESSION_SNAPSHOT_SCHEMA_VERSION,
            "tabs": [{"layout": layout} for layout in layouts],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)
        self.path.chmod(0o600)

    def clear(self) -> None:
        if self.read_only:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return
