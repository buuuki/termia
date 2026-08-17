# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class NotificationSeverity(IntEnum):
    INFORMATION = 0
    SUCCESS = 1
    WARNING = 2
    ERROR = 3


NOTIFICATION_ICONS = {
    NotificationSeverity.INFORMATION: "dialog-information-symbolic",
    NotificationSeverity.SUCCESS: "emblem-default-symbolic",
    NotificationSeverity.WARNING: "dialog-warning-symbolic",
    NotificationSeverity.ERROR: "dialog-error-symbolic",
}


class GroupedNotificationLabel(Gtk.Label):
    def __init__(self) -> None:
        super().__init__()
        self._notification_handler: Callable[[str, NotificationSeverity], None] | None = None
        self._setting_grouped_text = False

    def set_notification_handler(
        self,
        handler: Callable[[str, NotificationSeverity], None],
    ) -> None:
        self._notification_handler = handler

    def set_label(self, text: str) -> None:
        self.set_notification(text, NotificationSeverity.INFORMATION)

    def set_success(self, text: str) -> None:
        self.set_notification(text, NotificationSeverity.SUCCESS)

    def set_warning(self, text: str) -> None:
        self.set_notification(text, NotificationSeverity.WARNING)

    def set_error(self, text: str) -> None:
        self.set_notification(text, NotificationSeverity.ERROR)

    def set_notification(self, text: str, severity: NotificationSeverity) -> None:
        if self._notification_handler is None or self._setting_grouped_text:
            super().set_label(text)
            return
        self._notification_handler(text, severity)

    def set_grouped_text(self, text: str) -> None:
        self._setting_grouped_text = True
        try:
            super().set_label(text)
        finally:
            self._setting_grouped_text = False
