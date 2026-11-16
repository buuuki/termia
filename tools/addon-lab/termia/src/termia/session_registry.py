# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit ownership and lookup for open terminal sessions."""

from __future__ import annotations

from collections.abc import Iterable

from .ui_state import TerminalSession


class SessionRegistry:
    """Own the sessions whose terminal processes are managed by the window."""

    def __init__(self, sessions: Iterable[TerminalSession] = ()) -> None:
        self._sessions: dict[str, TerminalSession] = {}
        for session in sessions:
            self.register(session)

    def register(self, session: TerminalSession) -> None:
        if session.id in self._sessions:
            raise ValueError(f"Session is already registered: {session.id}")
        self._sessions[session.id] = session

    def get(self, session_id: str) -> TerminalSession | None:
        return self._sessions.get(session_id)

    def contains(self, session_id: str) -> bool:
        return session_id in self._sessions

    def remove(self, session_id: str) -> TerminalSession | None:
        return self._sessions.pop(session_id, None)

    def sessions(self) -> tuple[TerminalSession, ...]:
        return tuple(self._sessions.values())

    def __bool__(self) -> bool:
        return bool(self._sessions)
