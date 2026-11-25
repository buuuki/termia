# SPDX-License-Identifier: GPL-3.0-or-later
"""Profile-scoped aggregate data exposed to a trusted statistics plugin."""
from dataclasses import asdict

from .models import StatisticsSettings


class StatisticsData:
    def __init__(self, store):
        self._store = store

    def snapshot(self):
        return asdict(self._store.data.statistics)

    def servers(self):
        return [
            {key: getattr(server, key) for key in ("id", "name", "user", "host", "port")}
            for server in self._store.data.servers
        ]

    def update(self, values):
        if not self._store.read_only and not self._store.encryption_locked:
            self._store.data.statistics = StatisticsSettings(
                **{**values, "server_connections": dict(values["server_connections"])}
            )

    def flush(self):
        if not self._store.read_only and not self._store.encryption_locked:
            self._store.save_statistics()
