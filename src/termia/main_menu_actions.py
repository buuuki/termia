# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

MenuAction = Callable[[], None]


@dataclass(frozen=True)
class MainMenuActions:
    """Callbacks exposed to the main menu by the application composition root."""

    general_preferences: MenuAction
    terminal_settings: MenuAction
    prompt_settings: MenuAction
    keybinding_settings: MenuAction
    security_settings: MenuAction
    statistics: MenuAction
    connection_history: MenuAction
    data_locations: MenuAction
    export_config: MenuAction
    import_config: MenuAction
    import_asbru_config: MenuAction
    clear_config: MenuAction
    help: MenuAction
    about: MenuAction
