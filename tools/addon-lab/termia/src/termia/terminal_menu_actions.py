# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Server
from .ui_state import TerminalPane, TerminalSession

MenuPopover = object
TerminalWidget = object


def can_reopen_terminal(session: TerminalSession, pane: TerminalPane) -> bool:
    return (
        len(session.panes) == 1
        and not pane.retired
        and pane.disconnect_requested
        and not pane.connected
        and pane.child_process is None
    )


def terminal_action_label_key(session: TerminalSession, pane: TerminalPane) -> str:
    if can_reopen_terminal(session, pane):
        return "connect" if pane.server_id is not None else "open_local_terminal"
    return "disconnect" if pane.server_id is not None else "end_local_terminal"


def status_bar_action_label_key(status_bar_visible: bool) -> str:
    return (
        "hide_session_status_bar"
        if status_bar_visible
        else "show_session_status_bar"
    )


@dataclass(frozen=True)
class TerminalMenuActions:
    """Callbacks exposed to terminal context menus by the composition root."""

    disconnect: Callable[[MenuPopover, TerminalSession, TerminalWidget], None]
    toggle_status_bar: Callable[[MenuPopover, TerminalSession, TerminalWidget], None]
    copy: Callable[[MenuPopover, TerminalWidget], None]
    paste: Callable[[MenuPopover, TerminalWidget], None]
    send_files: Callable[[MenuPopover, TerminalSession, Server], None]
    configure: Callable[[MenuPopover, TerminalSession], None]
    session_statistics: Callable[[MenuPopover, TerminalSession, TerminalWidget], None] | None
    split: Callable[[MenuPopover, TerminalSession, TerminalWidget, str], None]
    split_connection: Callable[[MenuPopover, TerminalSession, TerminalWidget], None]
    rename_tab: Callable[[MenuPopover, TerminalSession], None]
    reattach_tab: Callable[[MenuPopover, TerminalSession], None]
    duplicate_tab: Callable[[MenuPopover, TerminalSession], None]
    new_tab: Callable[[MenuPopover], None]
    close_tab: Callable[[MenuPopover, TerminalSession], None]
    browse_files: Callable[[MenuPopover, TerminalSession, Server], None] | None = None
    run_snippet: Callable[[MenuPopover, TerminalSession, TerminalWidget], None] | None = None
