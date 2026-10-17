import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia.app import TermiaWindow
from termia.terminal_processes import TerminalProcess
from termia.transfer_lifecycle import ManagedTransfer


class AppShutdownTests(unittest.TestCase):
    def make_host(self, transfer_states, *, deadline=20.0):
        transfer = Mock(spec=ManagedTransfer)
        transfer.shutdown_cleanup_state.side_effect = transfer_states
        application = Mock()
        host = SimpleNamespace(
            shutdown_force_sent=False,
            shutdown_deadline=deadline,
            shutdown_transfers=(transfer,),
            terminate_open_terminal_processes=Mock(),
            pending_shutdown_terminal_processes=Mock(return_value=()),
            get_application=Mock(return_value=application),
        )
        return host, transfer, application

    def test_shutdown_waits_for_transfers_after_one_forced_process_pass(self) -> None:
        host, transfer, application = self.make_host(["pending", "stopped"])

        with patch("termia.app.monotonic", return_value=10.0), patch("termia.app.log_event") as log_event:
            first = TermiaWindow.finish_main_window_shutdown(host)
            second = TermiaWindow.finish_main_window_shutdown(host)

        self.assertEqual(first, 1)
        self.assertTrue(host.shutdown_force_sent)
        host.terminate_open_terminal_processes.assert_called_once_with(force=True)
        self.assertEqual(transfer.shutdown_cleanup_state.call_count, 2)
        self.assertEqual(second, 0)
        application.quit.assert_called_once_with()
        log_event.assert_any_call("application.shutdown_finished", cleanup="stopped")

    def test_shutdown_logs_failed_cleanup_without_claiming_success(self) -> None:
        host, _transfer, application = self.make_host(["failed"])

        with patch("termia.app.monotonic", return_value=10.0), patch("termia.app.log_event") as log_event:
            result = TermiaWindow.finish_main_window_shutdown(host)

        self.assertEqual(result, 0)
        application.quit.assert_called_once_with()
        log_event.assert_any_call(
            "application.shutdown_cleanup_unverified",
            outcome="failed",
            terminal_processes=0,
            transfers_pending=0,
            transfers_failed=1,
        )
        log_event.assert_any_call("application.shutdown_finished", cleanup="failed")

    def test_shutdown_deadline_logs_pending_resources_as_timed_out(self) -> None:
        host, _transfer, application = self.make_host(["pending"], deadline=9.0)
        process = TerminalProcess(42, 42, 42, "old")
        host.pending_shutdown_terminal_processes = Mock(return_value=(process,))

        with patch("termia.app.monotonic", return_value=10.0), patch("termia.app.log_event") as log_event:
            result = TermiaWindow.finish_main_window_shutdown(host)

        self.assertEqual(result, 0)
        application.quit.assert_called_once_with()
        log_event.assert_any_call(
            "application.shutdown_cleanup_unverified",
            outcome="timed_out",
            terminal_processes=1,
            transfers_pending=1,
            transfers_failed=0,
        )
        log_event.assert_any_call("application.shutdown_finished", cleanup="timed_out")

    def test_shutdown_without_optional_transfers_finishes_cleanly(self) -> None:
        application = Mock()
        host = SimpleNamespace(
            shutdown_force_sent=False,
            shutdown_deadline=20.0,
            shutdown_transfers=(),
            terminate_open_terminal_processes=Mock(),
            pending_shutdown_terminal_processes=Mock(return_value=()),
            get_application=Mock(return_value=application),
        )

        with patch("termia.app.monotonic", return_value=10.0), patch("termia.app.log_event") as log_event:
            result = TermiaWindow.finish_main_window_shutdown(host)

        self.assertEqual(result, 0)
        application.quit.assert_called_once_with()
        log_event.assert_any_call("application.shutdown_finished", cleanup="stopped")


if __name__ == "__main__":
    unittest.main()
