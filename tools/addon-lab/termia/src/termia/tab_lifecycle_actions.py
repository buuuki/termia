# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ui_state import TerminalSession

SessionAction = Callable[[TerminalSession], None]
ConfirmedAction = Callable[[], None]
ConfirmationAction = Callable[
    [TerminalSession, str, str, str, ConfirmedAction],
    None,
]


@dataclass(frozen=True)
class TabLifecycleActions:
    """Terminal lifecycle callbacks exposed to tab management."""

    duplicate_session: SessionAction
    disconnect_session: SessionAction
    terminate_split_processes: SessionAction
    confirm_session_action: ConfirmationAction
