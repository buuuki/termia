import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from termia.constants import DEFAULT_TERMINAL_BACKGROUND, DEFAULT_TERMINAL_FOREGROUND
from termia.migrations import CURRENT_SCHEMA_VERSION, migrate_settings_payload
from termia.stores import ConnectionStore, SettingsStore


class MigrationTests(unittest.TestCase):
    def test_future_schema_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            migrate_settings_payload({"schema_version": CURRENT_SCHEMA_VERSION + 1})

    def test_settings_migrate_legacy_terminal_palette_and_colors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "app": {"keybindings": {"copy": "<Control><Shift>c"}},
                        "terminal": {
                            "font_family": "Ubuntu Mono",
                            "font_size": 13,
                            "foreground": "#839496",
                            "background": "#002b36",
                            "split_separator_thickness": 999,
                            "split_separator_color": "not-a-color",
                        },
                    }
                ),
                encoding="utf-8",
            )

            store = SettingsStore(path)

        self.assertEqual(store.app.keybindings["copy"], "Ctrl+Shift+C")
        self.assertEqual(store.terminal.foreground, DEFAULT_TERMINAL_FOREGROUND)
        self.assertEqual(store.terminal.background, DEFAULT_TERMINAL_BACKGROUND)
        self.assertEqual(store.terminal.split_separator_thickness, 32)
        self.assertEqual(store.terminal.split_separator_color, "#008712")

        store.save()
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["schema_version"], CURRENT_SCHEMA_VERSION)

    def test_statistics_and_connections_get_schema_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connections_path = root / "connections.json"
            settings_path = root / "settings.json"
            statistics_path = root / "statistics.json"
            lock_path = root / "instance.lock"
            store = ConnectionStore(connections_path, settings_path, statistics_path, lock_path)
            try:
                store.data.app.debug_enabled = True
                store.save()
                store.save_statistics()
            finally:
                store.close()

            self.assertEqual(json.loads(connections_path.read_text())["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertEqual(json.loads(settings_path.read_text())["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertEqual(json.loads(statistics_path.read_text())["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertTrue(SettingsStore(settings_path).app.debug_enabled)

    def test_connection_store_migrates_embedded_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connections_path = root / "connections.json"
            settings_path = root / "settings.json"
            statistics_path = root / "statistics.json"
            lock_path = root / "instance.lock"
            connections_path.write_text(
                json.dumps(
                    {
                        "groups": [{"id": "g", "name": "Legacy"}],
                        "servers": [],
                        "local_terminals": [],
                        "app": {"theme": "light"},
                        "terminal": {"font_size": 18},
                    }
                ),
                encoding="utf-8",
            )

            with patch("termia.stores.HISTORY_FILE", root / "history.jsonl"):
                store = ConnectionStore(connections_path, settings_path, statistics_path, lock_path)
                try:
                    self.assertEqual(store.data.app.theme, "light")
                    self.assertEqual(store.data.terminal.font_size, 18)
                    self.assertTrue(settings_path.exists())
                finally:
                    store.close()

    def test_invalid_settings_are_backed_up_with_recovery_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")

            store = SettingsStore(path)

            backups = list(path.parent.glob("settings.json.invalid-*"))

        self.assertEqual(len(store.recovery_messages), 1)
        self.assertEqual(len(backups), 1)
