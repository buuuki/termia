# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
import shlex

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from .constants import DEFAULT_PROMPT_COLOR
from .models import TerminalSettings

SPLIT_LAYOUT_NONE = "none"
SPLIT_LAYOUT_COLUMNS = "columns"
SPLIT_LAYOUT_ROWS = "rows"
SPLIT_LAYOUT_LEFT_ROWS = "left_rows"
SPLIT_LAYOUT_RIGHT_ROWS = "right_rows"
SPLIT_LAYOUT_TOP_COLUMNS = "top_columns"
SPLIT_LAYOUT_BOTTOM_COLUMNS = "bottom_columns"
SPLIT_LAYOUT_GRID = "grid"

SPLIT_LAYOUT_CHOICES: list[tuple[str, str]] = [
    (SPLIT_LAYOUT_NONE, "split_layout_none"),
    (SPLIT_LAYOUT_COLUMNS, "split_layout_columns"),
    (SPLIT_LAYOUT_ROWS, "split_layout_rows"),
    (SPLIT_LAYOUT_LEFT_ROWS, "split_layout_left_rows"),
    (SPLIT_LAYOUT_RIGHT_ROWS, "split_layout_right_rows"),
    (SPLIT_LAYOUT_TOP_COLUMNS, "split_layout_top_columns"),
    (SPLIT_LAYOUT_BOTTOM_COLUMNS, "split_layout_bottom_columns"),
    (SPLIT_LAYOUT_GRID, "split_layout_grid"),
]

SPLIT_LAYOUT_PLANS: dict[str, list[tuple[str, str, str]]] = {
    SPLIT_LAYOUT_NONE: [],
    SPLIT_LAYOUT_COLUMNS: [("root", "right", "right")],
    SPLIT_LAYOUT_ROWS: [("root", "down", "bottom")],
    SPLIT_LAYOUT_LEFT_ROWS: [("root", "right", "right"), ("root", "down", "left_bottom")],
    SPLIT_LAYOUT_RIGHT_ROWS: [("root", "right", "right"), ("right", "down", "right_bottom")],
    SPLIT_LAYOUT_TOP_COLUMNS: [("root", "down", "bottom"), ("root", "right", "top_right")],
    SPLIT_LAYOUT_BOTTOM_COLUMNS: [("root", "down", "bottom"), ("bottom", "right", "bottom_right")],
    SPLIT_LAYOUT_GRID: [
        ("root", "right", "right"),
        ("root", "down", "left_bottom"),
        ("right", "down", "right_bottom"),
    ],
}


def parse_color(value: str, fallback: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    if not color.parse(value):
        color.parse(fallback)
    return color


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    red = max(0, min(round(rgba.red * 255), 255))
    green = max(0, min(round(rgba.green * 255), 255))
    blue = max(0, min(round(rgba.blue * 255), 255))
    return f"#{red:02x}{green:02x}{blue:02x}"


def build_terminal_environment(ls_colors: str, password: str = "") -> list[str]:
    env = dict(os.environ)
    env["LS_COLORS"] = ls_colors
    if password:
        env["SSHPASS"] = password
    env.setdefault("COLORTERM", "truecolor")
    env.setdefault("TERM", "xterm-256color")
    return [f"{key}={value}" for key, value in env.items()]


def normalized_prompt_template(template: str) -> str:
    value = template if template.strip() else r"\u@\h:\w\$ "
    if value == r"\w \$ ":
        return r"\u@\h:\w\$ "
    return value


def build_prompt_ps1(settings: TerminalSettings) -> str:
    color = parse_color(settings.prompt_color, DEFAULT_PROMPT_COLOR)
    red = max(0, min(round(color.red * 255), 255))
    green = max(0, min(round(color.green * 255), 255))
    blue = max(0, min(round(color.blue * 255), 255))
    template = normalized_prompt_template(settings.prompt_template)
    return f"\\[\\033[38;2;{red};{green};{blue}m\\]{template}\\[\\033[0m\\]"


def build_bash_rcfile_shell_command(
    bash_path: str,
    shell_arguments: list[str] | None = None,
    rcfile_lines: list[str] | None = None,
) -> list[str]:
    quoted_shell = shlex.quote(bash_path)
    quoted_arguments = " ".join(shlex.quote(argument) for argument in (shell_arguments or []))
    argument_text = f" {quoted_arguments}" if quoted_arguments else ""
    quoted_rcfile_lines = " ".join(shlex.quote(line) for line in (rcfile_lines or []))
    script = f"exec {quoted_shell}{argument_text} --rcfile <(printf '%s\\n' {quoted_rcfile_lines}) -i"
    return [bash_path, "-lc", script]


def build_local_prompt_shell_command(
    settings: TerminalSettings,
    bash_path: str,
    shell_arguments: list[str] | None = None,
) -> list[str]:
    quoted_ps1 = shlex.quote(build_prompt_ps1(settings))
    rcfile_lines = [
        "test -r ~/.bashrc && . ~/.bashrc",
        'PS1="$TERMIA_PS1"',
        "export PS1",
    ]
    command = build_bash_rcfile_shell_command(bash_path, shell_arguments, rcfile_lines)
    script = f"export TERMIA_PS1={quoted_ps1}; {command[-1]}"
    return [bash_path, "-lc", script]


def split_prompt_datetime_template(template: str) -> tuple[str, str]:
    prefixes = [
        ("both", r"[\d \A] "),
        ("date", r"[\d] "),
        ("time_seconds", r"[\t] "),
        ("time", r"[\A] "),
    ]
    for option_id, prefix in prefixes:
        if template.startswith(prefix):
            return option_id, template[len(prefix):]
    return "none", template


def prompt_template_with_datetime(template: str, option_id: str) -> str:
    base_template = normalized_prompt_template(template)
    prefixes = {
        "time": r"[\A] ",
        "time_seconds": r"[\t] ",
        "date": r"[\d] ",
        "both": r"[\d \A] ",
    }
    return f"{prefixes.get(option_id, '')}{base_template}"


def render_prompt_preview(template: str) -> str:
    text = normalized_prompt_template(template)
    replacements = {
        r"\u": "usuario",
        r"\h": "servidor",
        r"\H": "servidor.local",
        r"\w": "~/proyecto",
        r"\W": "proyecto",
        r"\$": "$",
        r"\A": "14:35",
        r"\t": "14:35:08",
        r"\d": "dom jun 07",
        r"\n": "\n",
    }
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    return text


def normalize_split_layout(layout: str) -> str:
    if layout in SPLIT_LAYOUT_PLANS:
        return layout
    return SPLIT_LAYOUT_NONE


def split_layout_plan(layout: str) -> list[tuple[str, str, str]]:
    return SPLIT_LAYOUT_PLANS[normalize_split_layout(layout)]
