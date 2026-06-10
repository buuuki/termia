# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
import shlex

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from .models import TerminalSettings


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
    color = parse_color(settings.prompt_color, "#8ae234")
    red = max(0, min(round(color.red * 255), 255))
    green = max(0, min(round(color.green * 255), 255))
    blue = max(0, min(round(color.blue * 255), 255))
    template = normalized_prompt_template(settings.prompt_template)
    return f"\\[\\033[38;2;{red};{green};{blue}m\\]{template}\\[\\033[0m\\]"


def build_local_prompt_shell_command(settings: TerminalSettings, bash_path: str) -> list[str]:
    quoted_ps1 = shlex.quote(build_prompt_ps1(settings))
    script = (
        f"export TERMIA_PS1={quoted_ps1}; "
        "exec bash --rcfile <(printf '%s\\n' "
        "'test -r ~/.bashrc && . ~/.bashrc' "
        "'PS1=\"$TERMIA_PS1\"' "
        "'export PS1') -i"
    )
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
