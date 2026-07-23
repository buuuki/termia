import unittest

from termia.connection_history_presenter import ConnectionHistoryPresenter
from termia.models import ConnectionHistoryEntry


class ConnectionHistoryPresenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = [
            ConnectionHistoryEntry(
                session_id="ssh-1",
                kind="ssh",
                server_name="Production",
                host="example.test",
                port=2222,
                user="admin",
                started_at="2026-07-22T10:00:00+02:00",
                ended_at="2026-07-22T10:01:05+02:00",
                result="failed",
                duration_seconds=65,
                detail="Connection refused",
            ),
            ConnectionHistoryEntry(
                session_id="local-1",
                kind="local",
                title="Local shell",
                started_at="2026-07-22T11:00:00+02:00",
                duration_seconds=None,
            ),
        ]
        self.presenter = ConnectionHistoryPresenter(
            lambda: self.entries,
            lambda key: f"<{key}>",
        )

    def test_filter_normalizes_query_and_can_hide_local_entries(self) -> None:
        self.assertEqual(
            [entry.session_id for entry in self.presenter.filter_entries("  PRODUCTION  ")],
            ["ssh-1"],
        )
        self.assertEqual(
            [entry.session_id for entry in self.presenter.filter_entries("", False)],
            ["ssh-1"],
        )
        self.assertEqual(
            [entry.session_id for entry in self.presenter.filter_entries("00:01:05")],
            ["ssh-1"],
        )

    def test_build_line_combines_translated_status_target_and_endpoint(self) -> None:
        line = self.presenter.build_line(self.entries[0])

        self.assertIn("<history_result_failed>", line)
        self.assertIn("<history_kind_ssh>", line)
        self.assertIn("Production", line)
        self.assertIn("admin@example.test:2222", line)
        self.assertIn("Connection refused", line)

    def test_running_local_entry_uses_running_and_local_labels(self) -> None:
        line = self.presenter.build_line(self.entries[1])

        self.assertIn("<history_result_running>", line)
        self.assertIn("<history_kind_local>", line)
        self.assertIn("Local shell", line)

    def test_format_helpers_preserve_invalid_timestamp_and_unknown_kind(self) -> None:
        self.assertEqual(self.presenter.format_timestamp("invalid"), "invalid")
        self.assertEqual(self.presenter.format_kind("other"), "other")
        self.assertEqual(self.presenter.format_endpoint("", "", 0), "")
