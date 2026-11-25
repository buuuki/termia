# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import StatisticsSettings
from termia.statistics_data import StatisticsData


class StatisticsDataTests(unittest.TestCase):
    def test_existing_counts_survive_a_read_only_or_locked_update(self):
        for read_only, locked in ((True, False), (False, True), (False, False)):
            with self.subTest(read_only=read_only, locked=locked):
                store = SimpleNamespace(
                    read_only=read_only, encryption_locked=locked, save_statistics=Mock(),
                    data=SimpleNamespace(statistics=StatisticsSettings(server_connections={"s": 3})),
                )
                api = StatisticsData(store)
                update = api.snapshot()
                update["server_connections"]["s"] += 1
                self.assertEqual(store.data.statistics.server_connections["s"], 3)
                api.update(update)
                api.flush()
                writable = not read_only and not locked
                self.assertEqual(store.data.statistics.server_connections["s"], 4 if writable else 3)
                self.assertEqual(store.save_statistics.call_count, int(writable))
