# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Server
from .ui_state import TerminalSession

MenuPopover = object
TerminalWidget = object


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
    session_statistics: Callable[[MenuPopover, TerminalSession, TerminalWidget], None]
    split: Callable[[MenuPopover, TerminalSession, TerminalWidget, str], None]
    split_connection: Callable[[MenuPopover, TerminalSession, TerminalWidget], None]
    rename_tab: Callable[[MenuPopover, TerminalSession], None]
    duplicate_tab: Callable[[MenuPopover, TerminalSession], None]
    new_tab: Callable[[MenuPopover], None]
    close_tab: Callable[[MenuPopover, TerminalSession], None]
