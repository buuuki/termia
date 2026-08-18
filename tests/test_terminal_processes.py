import signal
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia.terminal_processes import (
    TerminalProcess,
    signal_terminal_process,
    spawn_terminal_process,
    terminal_process_is_active,
)
from termia.terminal_sessions import TerminalSessionsMixin
from termia.session_registry import SessionRegistry


class FakeTerminal:
    def spawn_sync(self, *args: object) -> tuple[bool, int]:
        self.args = args
        return True, 4242


class TerminalProcessTests(unittest.TestCase):
    @patch("termia.terminal_processes.process_groups_in_session", return_value={99})
    def test_terminal_process_is_active_while_a_session_group_remains(self, groups) -> None:
        process = TerminalProcess(42, 99, 500, "42")

        self.assertTrue(terminal_process_is_active(process))

        groups.assert_called_once_with(500)

    @patch("termia.terminal_processes.process_start_time", return_value=None)
    @patch("termia.terminal_processes.process_groups_in_session", return_value=set())
    def test_terminal_process_is_inactive_after_every_session_process_exits(
        self,
        groups,
        start_time,
    ) -> None:
        process = TerminalProcess(42, 99, 500, "42")

        self.assertFalse(terminal_process_is_active(process))

        groups.assert_called_once_with(500)
        start_time.assert_called_once_with(42)

    def test_spawn_helper_centralizes_vte_arguments(self) -> None:
        terminal = FakeTerminal()
        environment = ["TERM=xterm-256color"]

        process = spawn_terminal_process(terminal, "/tmp", ["/bin/bash", "-l"], environment)

        self.assertEqual(process.pid, 4242)
        self.assertEqual(terminal.args[1:5], ("/tmp", ["/bin/bash", "-l"], environment, 0))
        self.assertEqual(terminal.args[5:], (None, None, None))

    @patch("termia.terminal_processes.process_start_time", return_value="42")
    @patch("termia.terminal_processes.os.killpg")
    @patch("termia.terminal_processes.os.getpgrp", return_value=1)
    @patch("termia.terminal_processes.os.getpgid", return_value=99)
    def test_signals_the_captured_process_group(self, getpgid, getpgrp, killpg, start_time) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=None, start_time="42")

        self.assertTrue(signal_terminal_process(process, signal.SIGTERM))
        killpg.assert_called_once_with(99, signal.SIGTERM)
        getpgid.assert_called_once_with(42)

    @patch("termia.terminal_processes.os.kill")
    @patch("termia.terminal_processes.process_start_time", return_value="new")
    def test_reused_pid_is_never_signalled(self, start_time, kill) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=None, start_time="old")

        self.assertFalse(signal_terminal_process(process, signal.SIGTERM))
        kill.assert_not_called()

    @patch("termia.terminal_processes.os.killpg")
    @patch("termia.terminal_processes.os.getpgrp", return_value=1)
    @patch("termia.terminal_processes.process_groups_in_session", return_value={99, 100})
    def test_signals_every_group_in_the_captured_terminal_session(self, groups, getpgrp, killpg) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="42")

        self.assertTrue(signal_terminal_process(process, signal.SIGTERM))
        self.assertCountEqual(
            killpg.call_args_list,
            [
                ((99, signal.SIGTERM),),
                ((100, signal.SIGTERM),),
            ],
        )

    def test_terminates_main_and_split_processes_for_every_open_session(self) -> None:
        main_process = TerminalProcess(pid=1, process_group_id=10, session_id=100, start_time="1")
        split_process = TerminalProcess(pid=2, process_group_id=20, session_id=200, start_time="2")

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry(
                    [
                        SimpleNamespace(
                            id="session",
                        child_process=main_process,
                        split_processes={"split": split_process},
                        )
                    ]
                )
                self.terminated = []

            def terminate_terminal_process(self, process, *, force=False) -> bool:
                self.terminated.append((process, force))
                return True

        host = Host()
        host.terminate_open_terminal_processes()
        host.terminate_open_terminal_processes(force=True)

        self.assertEqual(
            host.terminated,
            [
                (main_process, False),
                (split_process, False),
                (main_process, True),
                (split_process, True),
            ],
        )

    def test_shutdown_marks_every_session_and_pane_as_intentional(self) -> None:
        root_pane = SimpleNamespace(disconnect_requested=False, pending_reconnect=True)
        split_pane = SimpleNamespace(disconnect_requested=False, pending_reconnect=True)
        session = SimpleNamespace(
            id="session",
            disconnect_requested=False,
            pending_reconnect=True,
            panes={"root": root_pane, "split": split_pane},
        )
        host = TerminalSessionsMixin()
        host.session_registry = SessionRegistry([session])

        host.prepare_terminal_sessions_for_shutdown()

        self.assertTrue(session.disconnect_requested)
        self.assertFalse(session.pending_reconnect)
        self.assertTrue(root_pane.disconnect_requested)
        self.assertFalse(root_pane.pending_reconnect)
        self.assertTrue(split_pane.disconnect_requested)
        self.assertFalse(split_pane.pending_reconnect)

    @patch("termia.terminal_sessions.GLib.timeout_add")
    @patch("termia.terminal_sessions.signal_terminal_process", return_value=True)
    def test_shutdown_uses_only_the_global_forced_termination_pass(self, signal_process, timeout_add) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="42")
        host = TerminalSessionsMixin()
        host.shutdown_in_progress = True

        self.assertTrue(host.terminate_terminal_process(process))

        signal_process.assert_called_once_with(process, signal.SIGTERM)
        timeout_add.assert_not_called()

    @patch("termia.terminal_sessions.log_event")
    @patch("termia.terminal_sessions.terminal_process_is_active", return_value=False)
    def test_forced_cleanup_skips_a_process_that_already_exited(
        self,
        is_active,
        log_event,
    ) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="42")
        host = TerminalSessionsMixin()
        host.terminate_terminal_process = Mock()

        host.force_terminate_terminal_process(process)

        is_active.assert_called_once_with(process)
        host.terminate_terminal_process.assert_not_called()
        log_event.assert_called_once_with(
            "process.force_termination_skipped",
            pid=42,
            reason="already_exited",
        )

    @patch("termia.terminal_sessions.terminal_process_is_active", return_value=True)
    def test_forced_cleanup_still_kills_remaining_session_processes(self, is_active) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="42")
        host = TerminalSessionsMixin()
        host.terminate_terminal_process = Mock()

        host.force_terminate_terminal_process(process)

        is_active.assert_called_once_with(process)
        host.terminate_terminal_process.assert_called_once_with(process, force=True)

    def test_ssh_exit_during_shutdown_does_not_reconnect_or_notify(self) -> None:
        terminal = object()
        pane = SimpleNamespace(
            id="pane",
            connected=True,
            disconnect_requested=False,
            pending_reconnect=True,
            disconnect_button=Mock(),
            child_pid=42,
            child_process=object(),
        )
        session = SimpleNamespace(
            id="session",
            terminal=terminal,
            child_pid=42,
            child_process=pane.child_process,
            disconnect_requested=False,
            pending_reconnect=True,
            panes={id(terminal): pane},
            split_child_pids={},
            split_processes={},
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.shutdown_in_progress = True
                self.session_registry = SessionRegistry([session])
                self.store = SimpleNamespace(record_history_end=Mock())
                self.toast_label = Mock()
                self.reconnect_requested = False

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def pane_state(self, _session, _terminal):
                return pane

            def record_session_duration(self, _session) -> None:
                pass

            def save_statistics_now(self) -> None:
                pass

            def mark_session_for_reconnect(self, *_args) -> None:
                self.reconnect_requested = True

        host = Host()
        host.prepare_terminal_sessions_for_shutdown()
        host.on_terminal_exited(
            terminal,
            65280,
            SimpleNamespace(name="Example"),
            session,
        )

        host.store.record_history_end.assert_called_once_with(session, "disconnected")
        self.assertFalse(host.reconnect_requested)
        host.toast_label.set_label.assert_not_called()

    def test_ssh_exit_after_requested_disconnect_does_not_notify_twice(self) -> None:
        terminal = object()
        pane = SimpleNamespace(
            id="pane",
            connected=True,
            disconnect_requested=True,
            disconnect_button=Mock(),
            child_pid=42,
            child_process=object(),
        )
        session = SimpleNamespace(
            id="session",
            title="Example",
            terminal=terminal,
            child_pid=42,
            child_process=pane.child_process,
            panes={id(terminal): pane},
            active_terminal_ids=set(),
            split_child_pids={},
            split_processes={},
            status_label=Mock(),
            connected=True,
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.shutdown_in_progress = False
                self.store = SimpleNamespace(record_history_end=Mock())
                self.toast_label = Mock()

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def pane_state(self, _session, _terminal):
                return pane

            def record_session_duration(self, _session) -> None:
                pass

            def save_statistics_now(self) -> None:
                pass

            def t(self, key):
                return {
                    "session_disconnected_status": "Disconnected: {title}",
                }[key]

        host = Host()
        host.on_terminal_exited(
            terminal,
            0,
            SimpleNamespace(name="Example"),
            session,
        )

        host.store.record_history_end.assert_called_once_with(session, "disconnected")
        session.status_label.set_label.assert_called_once_with("Disconnected: Example")
        host.toast_label.set_label.assert_not_called()

    def test_split_exit_during_shutdown_does_not_reconnect_or_touch_widgets(self) -> None:
        terminal = object()
        pane = SimpleNamespace(
            id="split-pane",
            terminal=terminal,
            server_id="server",
            connected=True,
            disconnect_requested=False,
            pending_reconnect=True,
            disconnect_button=Mock(),
            status_label=Mock(),
            child_pid=42,
            child_process=object(),
        )
        session = SimpleNamespace(
            id="session",
            terminal=object(),
            disconnect_requested=False,
            pending_reconnect=True,
            panes={id(terminal): pane},
            pane_for_terminal=lambda current: pane if current is terminal else None,
            split_child_pids={id(terminal): 42},
            split_processes={id(terminal): object()},
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.shutdown_in_progress = True
                self.session_registry = SessionRegistry([session])
                self.store = SimpleNamespace(record_history_end=Mock())
                self.reconnect_requested = False

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def record_pane_duration(self, _pane) -> None:
                pass

            def save_statistics_now(self) -> None:
                pass

            def mark_pane_for_reconnect(self, *_args) -> None:
                self.reconnect_requested = True

        host = Host()
        host.prepare_terminal_sessions_for_shutdown()
        host.on_split_terminal_exited(terminal, 65280, session)

        host.store.record_history_end.assert_called_once_with(pane, "disconnected")
        self.assertFalse(host.reconnect_requested)
        pane.disconnect_button.set_sensitive.assert_not_called()
        pane.status_label.set_label.assert_not_called()
