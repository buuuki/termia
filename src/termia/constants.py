# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
from pathlib import Path

from gi.repository import GLib

APP_ID = "local.termia"
APP_DIR = Path(__file__).resolve().parent
CONFIG_DIR = Path(GLib.get_user_config_dir()) / "termia"
DATA_FILE = CONFIG_DIR / "connections.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
STATISTICS_FILE = STATE_DIR / "termia" / "statistics.json"
ABOUT_IMAGE = APP_DIR / "assets" / "termia.svg"
ISSUES_URL = "https://github.com/buuuki/termia/issues"

LEGACY_ANSI_PALETTE = [
    "#2e3436",
    "#cc0000",
    "#4e9a06",
    "#c4a000",
    "#3465a4",
    "#75507b",
    "#06989a",
    "#d3d7cf",
    "#555753",
    "#ef2929",
    "#8ae234",
    "#fce94f",
    "#729fcf",
    "#ad7fa8",
    "#34e2e2",
    "#eeeeec",
]

TERMINAL_PALETTES = {
    "Ubuntu": ("#eeeeec", "#300a24"),
    "Polaris": ("#d8dee9", "#1f2430"),
    "Solarized": ("#839496", "#002b36"),
    "Tango": ("#eeeeec", "#2e3436"),
    "Claro": ("#2e3436", "#f6f5f4"),
}

PROMPT_PRESETS = {
    "Verde": (r"\u@\h:\w\$ ", "#8ae234"),
    "Azul": (r"\u@\h:\w\$ ", "#729fcf"),
    "Ambar": (r"\u@\h:\w\$ ", "#fce94f"),
    "Rojo": (r"\u@\h \W \$ ", "#ef2929"),
    "Blanco": (r"\u@\h:\w\$ ", "#eeeeec"),
}

APP_THEMES = {"system": "Sistema", "light": "Claro", "dark": "Oscuro"}
