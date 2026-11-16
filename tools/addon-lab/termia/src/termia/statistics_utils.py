# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass

from .models import Server, StatisticsSettings


@dataclass(frozen=True)
class TopServerStat:
    index: int
    name: str
    subtitle: str
    count: int


def average_session_duration(stats: StatisticsSettings) -> float | None:
    if not stats.completed_sessions:
        return None
    return stats.duration_total / stats.completed_sessions


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--:--:--"
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def top_server_statistics(
    stats: StatisticsSettings, servers: list[Server], limit: int = 10
) -> list[TopServerStat]:
    servers_by_id = {server.id: server for server in servers}
    ranked = sorted(stats.server_connections.items(), key=lambda item: item[1], reverse=True)[:limit]
    rows: list[TopServerStat] = []
    for index, (server_id, count) in enumerate(ranked, start=1):
        server = servers_by_id.get(server_id)
        rows.append(
            TopServerStat(
                index=index,
                name=server.name if server is not None else server_id,
                subtitle=f"{server.user}@{server.host}:{server.port}" if server is not None else "",
                count=count,
            )
        )
    return rows
