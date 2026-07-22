# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Pango", "1.0")
gi.require_version("Vte", "3.91")
from gi.repository import Pango, Vte

from .constants import DEFAULT_TERMINAL_BACKGROUND, DEFAULT_TERMINAL_FOREGROUND
from .models import DEFAULT_ANSI_PALETTE, TerminalSettings
from .terminal_config import parse_color


class TerminalViewFactory:
    def __init__(self, resolve_font_family: Callable[[str], str]) -> None:
        self.resolve_font_family = resolve_font_family

    def create(self, settings: TerminalSettings) -> Vte.Terminal:
        terminal = Vte.Terminal()
        terminal.set_hexpand(True)
        terminal.set_vexpand(True)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        terminal.set_scrollback_lines(10000)
        self.apply_settings(terminal, settings)
        return terminal

    def apply_settings(self, terminal: Vte.Terminal, settings: TerminalSettings) -> None:
        font_family = self.resolve_font_family(settings.font_family)
        font = Pango.FontDescription(f"{font_family} {settings.font_size}")
        foreground = parse_color(settings.foreground, DEFAULT_TERMINAL_FOREGROUND)
        background = parse_color(settings.background, DEFAULT_TERMINAL_BACKGROUND)
        palette_values = settings.ansi_palette or DEFAULT_ANSI_PALETTE
        palette = [parse_color(color, fallback) for color, fallback in zip(palette_values, DEFAULT_ANSI_PALETTE)]
        terminal.set_font(font)
        terminal.set_colors(foreground, background, palette)
