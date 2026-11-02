# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, plain-text installer output. No credentials or terminal input."""
from __future__ import annotations

import re
from collections.abc import Callable

MAX_LOG_CHARS = 65536
MAX_LINE_CHARS = 8192
_ESCAPE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]")
_URL = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+")


class OutputLines:
    """Buffer complete lines so URLs cannot leak across pipe-read boundaries."""

    def __init__(self, notify: Callable[[str], None]):
        self.notify = notify
        self.pending = ""
        self.omitting = False

    def feed(self, text: str) -> None:
        self.pending += text.replace("\r", "\n")
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            if self.omitting or len(line) > MAX_LINE_CHARS:
                self.omitting = False
                self.notify("[…]\n")
            else:
                self.write(line + "\n")
        if len(self.pending) > MAX_LINE_CHARS:
            self.pending = ""
            self.omitting = True

    def write(self, text: str) -> None:
        text = _URL.sub("[URL]", _ESCAPE.sub("", text))
        self.notify("".join(char for char in text if char.isprintable() or char in "\n\t"))

    def finish(self) -> None:
        if self.omitting:
            self.notify("[…]\n")
        elif self.pending:
            self.write(self.pending + "\n")
        self.pending = ""
        self.omitting = False
