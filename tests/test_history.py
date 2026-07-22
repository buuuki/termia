import json
import tempfile
import unittest
from pathlib import Path

from termia.models import ConnectionHistoryEvent
from termia.stores import ConnectionHistoryStore, ConnectionStore


class HistoryPersistenceTests(unittest.TestCase):
    def test_missing_and_empty_history_are_valid_empty_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = ConnectionHistoryStore(root / "missing.jsonl")
            empty_path = root / "empty.jsonl"
            empty_path.touch()
            empty = ConnectionHistoryStore(empty_path)

        for store in (missing, empty):
            self.assertEqual(store.events, [])
            self.assertEqual(store.entries, [])
            self.assertEqual(store.recovery_messages, [])

    def test_unreadable_history_reports_recovery_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.mkdir()

            store = ConnectionHistoryStore(path)

        self.assertEqual(store.events, [])
        self.assertEqual(store.recovery_messages, [str(path)])

    def test_malformed_lines_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text("not json\n[]\n{\"session_id\": \"valid\", \"event\": \"started\"}\n", encoding="utf-8")

            store = ConnectionHistoryStore(path)

        self.assertEqual([event.session_id for event in store.events], ["valid"])
        self.assertEqual(store.recovery_messages, [])

    def test_partially_valid_history_rebuilds_entries(self) -> None:
        event = ConnectionHistoryEvent(
            session_id="session-1",
            event="ended",
            timestamp="2026-07-22T10:00:00+02:00",
            title="Web",
            server_id="server-1",
            server_name="Web",
            host="example.test",
            user="admin",
            port=22,
            result="success",
            duration_seconds=3.5,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"session_id": "session-1", "event": "started", "timestamp": "2026-07-22T09:59:56+02:00"}),
                        "invalid line",
                        json.dumps(event.__dict__),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            store = ConnectionHistoryStore(path)

        self.assertEqual(len(store.events), 2)
        self.assertEqual(len(store.entries), 1)
        self.assertEqual(store.entries[0].result, "success")
        self.assertEqual(store.entries[0].duration_seconds, 3.5)

    def test_connection_store_uses_injected_history_and_aggregates_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history_path = root / "history.jsonl"
            history_path.mkdir()
            store = ConnectionStore(
                root / "connections.json",
                settings_path=root / "settings.json",
                statistics_path=root / "statistics.json",
                lock_path=root / "instance.lock",
                history_path=history_path,
            )
            try:
                self.assertIs(store.history_store.path, history_path)
                self.assertIn(str(history_path), store.recovery_messages)
            finally:
                store.close()
