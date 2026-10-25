import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia.builtin_tools import BuiltInTools
from termia.models import AppSettings, StatisticsSettings
from termia.session_observer import NoOpSessionObserver
from termia.statistics_collector import StatisticsCollector
from termia.stores import ConnectionStore, SettingsStore


class BuiltInToolsTests(unittest.TestCase):
    def test_legacy_settings_keep_previous_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"app": {"statistics_enabled": True}}), encoding="utf-8")
            settings = SettingsStore(path).app

        self.assertEqual(BuiltInTools.from_settings(settings), BuiltInTools(True, True))
        self.assertEqual(BuiltInTools.from_settings(AppSettings()), BuiltInTools(False, True))

    def test_optional_tool_choice_persists_without_removing_statistics_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(
                root / "connections.json",
                settings_path=root / "settings.json",
                statistics_path=root / "statistics.json",
                lock_path=root / "instance.lock",
                history_path=root / "history.jsonl",
                notes_path=root / "notes.json",
            )
            try:
                store.data.statistics.connections = 4
                store.save_statistics()
                initial = BuiltInTools.from_settings(store.data.app)
                store.update_optional_tools(statistics_enabled=True, sftp_enabled=False)
                self.assertEqual(initial, BuiltInTools(False, True))
                self.assertEqual(BuiltInTools.from_settings(store.data.app), BuiltInTools(True, False))
                store.update_app_settings(AppSettings(theme="system"))
                self.assertEqual(BuiltInTools.from_settings(store.data.app), BuiltInTools(True, False))
            finally:
                store.close()

            reloaded = SettingsStore(root / "settings.json").app
            saved_statistics = json.loads((root / "statistics.json").read_text(encoding="utf-8"))

        self.assertEqual(BuiltInTools.from_settings(reloaded), BuiltInTools(True, False))
        self.assertEqual(saved_statistics["connections"], 4)

    def test_disabled_observer_never_records_or_writes(self) -> None:
        observer = NoOpSessionObserver()
        observer.connection_started("synthetic-server")
        observer.pane_finished(SimpleNamespace())
        observer.flush()
        observer.shutdown(())
        self.assertEqual(observer.run_connections, 0)


class StatisticsCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SimpleNamespace(
            data=SimpleNamespace(statistics=StatisticsSettings()),
            save_statistics=Mock(),
        )

    @patch("termia.statistics_collector.GLib.timeout_add_seconds", return_value=10)
    def test_records_connections_and_duration_once(self, timer: Mock) -> None:
        collector = StatisticsCollector(
            lambda: self.store.data.statistics, self.store.save_statistics
        )
        pane = SimpleNamespace(
            child_pid=42,
            duration_recorded=False,
            started_at=100.0,
        )
        with patch("termia.statistics_collector.time.monotonic", return_value=105.0):
            collector.connection_started("synthetic-server")
            collector.pane_finished(pane)
            collector.pane_finished(pane)

        stats = self.store.data.statistics
        self.assertEqual((stats.connections, collector.run_connections), (1, 1))
        self.assertEqual(stats.server_connections, {"synthetic-server": 1})
        self.assertEqual(stats.completed_sessions, 1)
        self.assertEqual(stats.duration_total, 5.0)
        timer.assert_called_once_with(30, collector._on_save_timeout)

    @patch("termia.statistics_collector.GLib.source_remove")
    @patch("termia.statistics_collector.GLib.timeout_add_seconds", return_value=10)
    def test_shutdown_flushes_active_root_and_split_without_double_counting(
        self, timer: Mock, remove: Mock
    ) -> None:
        collector = StatisticsCollector(
            lambda: self.store.data.statistics, self.store.save_statistics
        )
        root_terminal = object()
        split_terminal = object()
        split = SimpleNamespace(
            terminal=split_terminal,
            child_pid=43,
            duration_recorded=False,
            started_at=101.0,
        )
        session = SimpleNamespace(
            terminal=root_terminal,
            child_pid=42,
            duration_recorded=False,
            started_at=100.0,
            panes={id(split_terminal): split},
        )
        with patch("termia.statistics_collector.time.monotonic", return_value=106.0):
            collector.shutdown((session,))
            collector.pane_finished(session)

        self.assertEqual(self.store.data.statistics.completed_sessions, 2)
        self.assertEqual(self.store.data.statistics.duration_total, 11.0)
        self.store.save_statistics.assert_called_once_with()
        timer.assert_called_once()
        remove.assert_called_once_with(10)


if __name__ == "__main__":
    unittest.main()
