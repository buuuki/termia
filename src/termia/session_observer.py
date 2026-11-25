# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small lifecycle contract used by optional session observers."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from .ui_state import TerminalPane, TerminalSession

Pane = TerminalPane | TerminalSession


class MetricsSessionObserver:
    def __init__(self, publish: Callable[[str, str | float | None], None]) -> None:
        self.publish = publish

    def connection_started(self, server_id: str) -> None:
        self.publish("connection_started", server_id)

    def pane_finished(self, pane: Pane) -> None:
        if pane.duration_recorded or pane.child_pid is None:
            return
        pane.duration_recorded = True
        duration = max(0.0, time.monotonic() - pane.started_at)
        self.publish("duration_finished", duration)

    def flush(self) -> None:
        self.publish("flush", None)

    def shutdown(self, sessions: Iterable[TerminalSession]) -> None:
        for session in sessions:
            self.pane_finished(session)
            for pane in session.panes.values():
                if pane.terminal is not session.terminal:
                    self.pane_finished(pane)
        self.flush()
