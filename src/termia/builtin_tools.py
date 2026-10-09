# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup snapshot of Termia's bundled optional tools.

This is deliberately not a third-party plugin loader or a public API.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import AppSettings


@dataclass(frozen=True)
class BuiltInTools:
    statistics: bool
    sftp: bool

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "BuiltInTools":
        return cls(
            statistics=settings.statistics_enabled,
            sftp=settings.sftp_enabled,
        )
