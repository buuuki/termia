# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from .constants import DEFAULT_PROMPT_COLOR
from .terminal_config import (
    parse_color,
    prompt_template_with_datetime,
    render_prompt_preview,
)


def combined_terminal_preview_markup(
    *,
    prompt_enabled: bool,
    prompt_template: str,
    prompt_datetime_id: str,
    prompt_color: str,
    command_text: str,
    output_text: str,
    ansi_palette: list[str],
) -> str:
    template = (
        prompt_template_with_datetime(prompt_template, prompt_datetime_id)
        if prompt_enabled
        else r"\u@\h:\w\$ "
    )
    prompt_text = render_prompt_preview(template)
    escaped_prompt = GLib.markup_escape_text(prompt_text)
    if prompt_enabled:
        prompt_markup = f'<span foreground="{prompt_color}">{escaped_prompt}</span>'
    else:
        prompt_markup = escaped_prompt
    command_markup = GLib.markup_escape_text(command_text)
    output_markup = GLib.markup_escape_text(output_text)
    ansi_markup = " ".join(
        f'<span foreground="{GLib.markup_escape_text(color)}">●</span>'
        for color in ansi_palette[:8]
    )
    return f"{prompt_markup}{command_markup}\n{output_markup}\nANSI  {ansi_markup}"


class PromptPreferencesMixin:
    def on_prompt_preset_clicked(
        self,
        _button: Gtk.Button,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
        template: str,
        color: str,
    ) -> None:
        prompt_template_entry.set_text(template)
        prompt_color_button.set_rgba(parse_color(color, DEFAULT_PROMPT_COLOR))
