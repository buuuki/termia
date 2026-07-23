# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .models import Server, StatisticsSettings
from .statistics_utils import (
    TopServerStat,
    average_session_duration,
    format_duration,
    top_server_statistics,
)

StatisticsProvider = Callable[[], StatisticsSettings]
ServersProvider = Callable[[], Sequence[Server]]
RunConnectionsProvider = Callable[[], int]
Translator = Callable[[str], str]


@dataclass(frozen=True)
class StatisticCard:
    title: str
    value: str
    subtitle: str


@dataclass(frozen=True)
class StatisticsDashboard:
    cards: tuple[StatisticCard, ...]
    top_servers: tuple[TopServerStat, ...]
    max_server_count: int


class StatisticsPresenter:
    """Prepare statistics dashboard content without depending on GTK."""

    def __init__(
        self,
        statistics: StatisticsProvider,
        servers: ServersProvider,
        run_connections: RunConnectionsProvider,
        translate: Translator,
    ) -> None:
        self._statistics = statistics
        self._servers = servers
        self._run_connections = run_connections
        self._translate = translate

    def dashboard(self) -> StatisticsDashboard:
        stats = self._statistics()
        average_duration = average_session_duration(stats)
        cards = (
            StatisticCard(
                self._translate("connections"),
                str(stats.connections),
                f"{self._translate('current_run')} {self._run_connections()}",
            ),
            StatisticCard(
                self._translate("sessions"),
                str(stats.completed_sessions),
                self._translate("global"),
            ),
            StatisticCard(
                self._translate("average_duration"),
                format_duration(average_duration),
                self._translate("duration"),
            ),
            StatisticCard(
                self._translate("longest_duration"),
                format_duration(stats.duration_max if stats.completed_sessions else None),
                f"{self._translate('shortest_duration')}: {format_duration(stats.duration_min)}",
            ),
        )
        top_servers = tuple(
            top_server_statistics(stats, list(self._servers()))
        )
        return StatisticsDashboard(
            cards=cards,
            top_servers=top_servers,
            max_server_count=max(
                (item.count for item in top_servers),
                default=1,
            ),
        )
