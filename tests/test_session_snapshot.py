import json
import tempfile
import unittest
from pathlib import Path

from termia.session_snapshot import SessionSnapshotStore


class SessionSnapshotStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "last-session.json"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_round_trip_keeps_only_safe_layout_references(self) -> None:
        store = SessionSnapshotStore(self.path)
        store.save(
            [
                {
                    "layout": {
                        "type": "pane",
                        "connection_type": "server",
                        "connection_id": "server-1",
                        "extra_field": "discarded-field",
                        "pid": 1234,
                    }
                }
            ]
        )

        self.assertEqual(
            store.load(),
            [
                {
                    "layout": {
                        "type": "pane",
                        "connection_type": "server",
                        "connection_id": "server-1",
                    }
                }
            ],
        )
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        content = self.path.read_text(encoding="utf-8")
        self.assertNotIn("discarded-field", content)
        self.assertNotIn("1234", content)

    def test_read_only_store_never_writes_or_removes_snapshot(self) -> None:
        self.path.write_text(
            json.dumps({
                "schema_version": 1,
                "tabs": [{"layout": {"type": "pane", "connection_type": "local", "connection_id": ""}}],
            }),
            encoding="utf-8",
        )
        store = SessionSnapshotStore(self.path, read_only=True)
        store.save([])
        store.clear()

        self.assertTrue(self.path.exists())
        self.assertEqual(len(store.load()), 1)

    def test_invalid_snapshot_is_ignored(self) -> None:
        self.path.write_text("not json", encoding="utf-8")

        self.assertEqual(SessionSnapshotStore(self.path).load(), [])


if __name__ == "__main__":
    unittest.main()
