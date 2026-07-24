# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .models import Server
from .ui_state import TerminalSession

MenuPopover = object
TerminalWidget = object


@dataclass(frozen=True)
class TerminalMenuActions:
    """Callbacks exposed to terminal context menus by the composition root."""

    disconnect: Callable[[MenuPopover, TerminalSession], None]
    show_status_bar: Callable[[MenuPopover, TerminalSession], None]
    copy: Callable[[MenuPopover, TerminalWidget], None]
    paste: Callable[[MenuPopover, TerminalWidget], None]
    send_files: Callable[[MenuPopover, Server], None]
    configure: Callable[[MenuPopover], None]
    session_statistics: Callable[[MenuPopover, TerminalSession], None]
    split: Callable[[MenuPopover, TerminalSession, TerminalWidget, str], None]
    rename_tab: Callable[[MenuPopover, TerminalSession], None]
    duplicate_tab: Callable[[MenuPopover, TerminalSession], None]
    new_tab: Callable[[MenuPopover], None]
    close_tab: Callable[[MenuPopover, TerminalSession], None]
