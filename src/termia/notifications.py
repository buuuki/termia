# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class GroupedNotificationLabel(Gtk.Label):
    def __init__(self) -> None:
        super().__init__()
        self._notification_handler: Callable[[str], None] | None = None
        self._setting_grouped_text = False

    def set_notification_handler(self, handler: Callable[[str], None]) -> None:
        self._notification_handler = handler

    def set_label(self, text: str) -> None:
        if self._notification_handler is None or self._setting_grouped_text:
            super().set_label(text)
            return
        self._notification_handler(text)

    def set_grouped_text(self, text: str) -> None:
        self._setting_grouped_text = True
        try:
            super().set_label(text)
        finally:
            self._setting_grouped_text = False
