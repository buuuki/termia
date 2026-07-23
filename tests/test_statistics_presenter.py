import unittest

from termia.models import Server, StatisticsSettings
from termia.statistics_presenter import StatisticsPresenter


class StatisticsPresenterTests(unittest.TestCase):
    def test_dashboard_prepares_cards_and_ranked_servers(self) -> None:
        stats = StatisticsSettings(
            connections=7,
            completed_sessions=2,
            duration_total=130,
            duration_min=30,
            duration_max=100,
            server_connections={"web": 4, "db": 2},
        )
        servers = [
            Server(id="web", name="Web", host="web.test", user="admin", port=22),
            Server(id="db", name="Database", host="db.test", user="dba", port=2200),
        ]
        presenter = StatisticsPresenter(
            lambda: stats,
            lambda: servers,
            lambda: 3,
            lambda key: f"<{key}>",
        )

        dashboard = presenter.dashboard()

        self.assertEqual(
            [(card.title, card.value, card.subtitle) for card in dashboard.cards],
            [
                ("<connections>", "7", "<current_run> 3"),
                ("<sessions>", "2", "<global>"),
                ("<average_duration>", "00:01:05", "<duration>"),
                ("<longest_duration>", "00:01:40", "<shortest_duration>: 00:00:30"),
            ],
        )
        self.assertEqual(
            [(row.name, row.subtitle, row.count) for row in dashboard.top_servers],
            [
                ("Web", "admin@web.test:22", 4),
                ("Database", "dba@db.test:2200", 2),
            ],
        )
        self.assertEqual(dashboard.max_server_count, 4)

    def test_empty_dashboard_uses_duration_placeholders(self) -> None:
        presenter = StatisticsPresenter(
            StatisticsSettings,
            list,
            lambda: 0,
            lambda key: key,
        )

        dashboard = presenter.dashboard()

        self.assertEqual(dashboard.cards[2].value, "--:--:--")
        self.assertEqual(dashboard.cards[3].value, "--:--:--")
        self.assertEqual(dashboard.top_servers, ())
        self.assertEqual(dashboard.max_server_count, 1)
