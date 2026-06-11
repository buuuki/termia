# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
from pathlib import Path

from .models import Group, Server, StoreData


def export_connections_file(source: Path, destination: Path) -> None:
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    destination.chmod(0o600)


def load_store_data_from_json(path: Path, current: StoreData) -> StoreData:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return StoreData(
        groups=[Group(**item) for item in payload.get("groups", [])],
        servers=[Server(**item) for item in payload.get("servers", [])],
        terminal=current.terminal,
        app=current.app,
        statistics=current.statistics,
    )
