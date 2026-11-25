import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from termia.builtin_tools import BuiltInTools
from termia.models import AppSettings
from termia.session_observer import MetricsSessionObserver
from termia.stores import ConnectionStore, SettingsStore


class BuiltInToolsTests(unittest.TestCase):
    def test_legacy_settings_keep_previous_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"app": {"statistics_enabled": True}}), encoding="utf-8")
            settings = SettingsStore(path).app

        self.assertTrue(settings.statistics_enabled)
        self.assertEqual(BuiltInTools.from_settings(settings), BuiltInTools(True))
        self.assertEqual(BuiltInTools.from_settings(AppSettings()), BuiltInTools(True))

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
                self.assertEqual(initial, BuiltInTools(True))
                self.assertEqual(BuiltInTools.from_settings(store.data.app), BuiltInTools(False))
                store.update_app_settings(AppSettings(theme="system"))
                self.assertEqual(BuiltInTools.from_settings(store.data.app), BuiltInTools(False))
            finally:
                store.close()

            reloaded = SettingsStore(root / "settings.json").app
            saved_statistics = json.loads((root / "statistics.json").read_text(encoding="utf-8"))

        self.assertEqual(BuiltInTools.from_settings(reloaded), BuiltInTools(False))
        self.assertTrue(reloaded.statistics_enabled)
        self.assertEqual(saved_statistics["connections"], 4)

class SessionObserverTests(unittest.TestCase):
    def test_shutdown_finishes_root_and_split_once(self):
        publish = Mock()
        observer = MetricsSessionObserver(publish)
        root = SimpleNamespace(terminal=object(), child_pid=42, duration_recorded=False, started_at=100.0)
        split = SimpleNamespace(terminal=object(), child_pid=43, duration_recorded=False, started_at=101.0)
        root.panes = {1: root, 2: split}
        with patch("termia.session_observer.time.monotonic", return_value=106.0):
            observer.connection_started("synthetic")
            observer.pane_finished(root)
            observer.shutdown([root])
            observer.pane_finished(split)
        self.assertEqual(publish.call_args_list, [
            call("connection_started", "synthetic"), call("duration_finished", 6.0),
            call("duration_finished", 5.0), call("flush", None),
        ])


if __name__ == "__main__":
    unittest.main()
