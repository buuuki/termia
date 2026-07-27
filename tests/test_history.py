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

    def test_unfinished_entries_are_finalized_once_when_writable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "session_id": "unfinished",
                        "kind": "ssh",
                        "event": "started",
                        "timestamp": "2026-07-23T10:00:00+02:00",
                        "title": "Web",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            store = ConnectionHistoryStore(path)

            self.assertEqual(store.finalize_unfinished_entries(timestamp="2026-07-27T10:00:00+02:00"), 1)
            self.assertEqual(store.finalize_unfinished_entries(timestamp="2026-07-27T10:00:01+02:00"), 0)

        self.assertEqual(store.entries[0].result, "interrupted")
        self.assertEqual(store.entries[0].ended_at, "2026-07-27T10:00:00+02:00")
        self.assertIsNone(store.entries[0].duration_seconds)

    def test_read_only_history_does_not_finalize_unfinished_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            path.write_text(
                json.dumps({"session_id": "unfinished", "event": "started", "timestamp": "2026-07-23T10:00:00+02:00"})
                + "\n",
                encoding="utf-8",
            )
            store = ConnectionHistoryStore(path, read_only=True)

            self.assertEqual(store.finalize_unfinished_entries(timestamp="2026-07-27T10:00:00+02:00"), 0)

        self.assertFalse(store.entries[0].ended_at)

    def test_writable_connection_store_finalizes_history_from_an_earlier_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history_path = root / "history.jsonl"
            history_path.write_text(
                json.dumps({"session_id": "unfinished", "event": "started", "timestamp": "2026-07-23T10:00:00+02:00"})
                + "\n",
                encoding="utf-8",
            )
            store = ConnectionStore(
                root / "connections.json",
                settings_path=root / "settings.json",
                statistics_path=root / "statistics.json",
                lock_path=root / "instance.lock",
                history_path=history_path,
            )
            try:
                self.assertFalse(store.read_only)
                self.assertEqual(store.history_store.entries[0].result, "interrupted")
                self.assertTrue(store.history_store.entries[0].ended_at)
            finally:
                store.close()

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
