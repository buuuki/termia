# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small lifecycle contract used by optional session observers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .ui_state import TerminalPane, TerminalSession

Pane = TerminalPane | TerminalSession


class SessionObserver(Protocol):
    run_connections: int

    def connection_started(self, server_id: str) -> None: ...

    def pane_finished(self, pane: Pane) -> None: ...

    def flush(self) -> None: ...

    def shutdown(self, sessions: Iterable[TerminalSession]) -> None: ...


class NoOpSessionObserver:
    run_connections = 0

    def connection_started(self, server_id: str) -> None:
        pass

    def pane_finished(self, pane: Pane) -> None:
        pass

    def flush(self) -> None:
        pass

    def shutdown(self, sessions: Iterable[TerminalSession]) -> None:
        pass
