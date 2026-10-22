import signal
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia.terminal_processes import (
    SessionProcessIdentity,
    TerminalProcess,
    signal_terminal_process,
    snapshot_terminal_process,
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
    @patch(
        "termia.terminal_processes.os.getsid",
        return_value=500,
    )
    @patch("termia.terminal_processes.os.getpgid", return_value=99)
    @patch("termia.terminal_processes.process_session_members", return_value=(
        SessionProcessIdentity(42, 99, "42"),
        SessionProcessIdentity(43, 99, "child"),
    ))
    @patch("termia.terminal_processes.process_start_time", side_effect=["42", "42", "42", "child"])
    def test_terminal_process_is_active_while_a_session_group_remains(
        self, _start_time, members, _getpgid, _getsid
    ) -> None:
        process = TerminalProcess(42, 99, 500, "42")

        self.assertTrue(terminal_process_is_active(process))

        members.assert_called_once_with(500)

    @patch("termia.terminal_processes.process_start_time", return_value=None)
    @patch("termia.terminal_processes.process_session_members", return_value=())
    def test_terminal_process_is_inactive_after_every_session_process_exits(
        self, members, start_time
    ) -> None:
        process = TerminalProcess(42, 99, 500, "42")

        self.assertFalse(terminal_process_is_active(process))

        members.assert_called_once_with(500)
        self.assertEqual(start_time.call_count, 2)

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

    @patch("termia.terminal_processes.process_start_time", side_effect=["42", "42", "42", "43"])
    @patch("termia.terminal_processes.os.getsid", return_value=500)
    @patch("termia.terminal_processes.os.getpgid", side_effect=[99, 100])
    @patch("termia.terminal_processes.process_session_members", return_value=(
        SessionProcessIdentity(42, 99, "42"),
        SessionProcessIdentity(43, 100, "43"),
    ))
    @patch("termia.terminal_processes.os.killpg")
    @patch("termia.terminal_processes.os.getpgrp", return_value=1)
    def test_signals_every_group_in_the_captured_terminal_session(
        self, getpgrp, killpg, members, getpgid, getsid, _start_time
    ) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="42")

        self.assertTrue(signal_terminal_process(process, signal.SIGTERM))
        self.assertCountEqual(
            killpg.call_args_list,
            [
                ((99, signal.SIGTERM),),
                ((100, signal.SIGTERM),),
            ],
        )

    def test_signals_snapshot_groups_after_leader_exits(self) -> None:
        process = TerminalProcess(
            pid=42,
            process_group_id=42,
            session_id=500,
            start_time="leader",
            session_members=(SessionProcessIdentity(43, 99, "child"),),
        )
        with (
            patch("termia.terminal_processes.process_start_time", return_value="child"),
            patch("termia.terminal_processes.os.getpgid", return_value=99),
            patch("termia.terminal_processes.os.getsid", return_value=500),
            patch("termia.terminal_processes.os.getpgrp", return_value=1),
            patch("termia.terminal_processes.os.killpg") as killpg,
            patch("termia.terminal_processes.process_session_members") as live_members,
        ):
            self.assertTrue(signal_terminal_process(process, signal.SIGKILL))

        killpg.assert_called_once_with(99, signal.SIGKILL)
        live_members.assert_not_called()

    def test_session_pid_reuse_rejects_unrelated_live_groups(self) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="old")
        with (
            patch("termia.terminal_processes.process_start_time", side_effect=["new", "new"]),
            patch(
                "termia.terminal_processes.process_session_members",
                return_value=(SessionProcessIdentity(43, 99, "unrelated"),),
            ) as groups,
            patch("termia.terminal_processes.os.killpg") as killpg,
            patch("termia.terminal_processes.os.kill") as kill,
        ):
            self.assertFalse(signal_terminal_process(process, signal.SIGTERM))

        groups.assert_called_once_with(500)
        killpg.assert_not_called()
        kill.assert_not_called()

    def test_snapshot_does_not_adopt_a_reused_session_id(self) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="old")
        with (
            patch("termia.terminal_processes.process_start_time", return_value="new"),
            patch("termia.terminal_processes.process_session_members", return_value=()) as members,
        ):
            snapshot = snapshot_terminal_process(process)

        self.assertEqual(snapshot.session_members, ())
        self.assertFalse(snapshot.session_unverified)
        members.assert_called_once_with(500)

    def test_snapshot_marks_live_groups_unverified_when_the_leader_identity_changed(self) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="old")
        members = (SessionProcessIdentity(43, 99, "new"),)
        with (
            patch("termia.terminal_processes.process_start_time", return_value="reused"),
            patch("termia.terminal_processes.process_session_members", return_value=members),
        ):
            snapshot = snapshot_terminal_process(process)

        self.assertTrue(snapshot.session_unverified)
        self.assertEqual(snapshot.session_members, ())
        with patch("termia.terminal_processes.process_session_members", return_value=members):
            self.assertTrue(terminal_process_is_active(snapshot))

    def test_unverified_session_stops_pending_when_its_members_disappear(self) -> None:
        process = TerminalProcess(42, 42, 42, "leader", session_unverified=True)
        members = (SessionProcessIdentity(43, 43, "child"),)
        with patch(
            "termia.terminal_processes.process_session_members",
            side_effect=[members, ()],
        ):
            self.assertTrue(terminal_process_is_active(process))
            self.assertFalse(terminal_process_is_active(process))

        with patch("termia.terminal_processes.os.killpg") as killpg:
            self.assertFalse(signal_terminal_process(process, signal.SIGKILL))
        killpg.assert_not_called()

    def test_child_exit_reuses_shutdown_snapshot_without_false_pending_identity(self) -> None:
        process = TerminalProcess(42, 42, 42, "leader")
        terminal = object()
        pane = SimpleNamespace(child_pid=42, child_process=process)
        session = SimpleNamespace(
            id="session", terminal=terminal, child_pid=42, child_process=process,
            split_child_pids={}, split_processes={}, panes={id(terminal): pane},
        )
        host = TerminalSessionsMixin()
        host.shutdown_in_progress = True
        host.orphaned_terminal_processes = set()
        host.session_registry = SessionRegistry([session])
        live = {42: "leader", 43: "child"}

        with (
            patch("termia.terminal_processes.process_start_time", side_effect=live.get),
            patch(
                "termia.terminal_processes.process_session_members",
                side_effect=lambda _sid: tuple(
                    SessionProcessIdentity(pid, pid, birth) for pid, birth in live.items()
                ),
            ),
            patch("termia.terminal_processes.os.getpgid", side_effect=lambda pid: pid),
            patch("termia.terminal_processes.os.getsid", return_value=42),
        ):
            host.prepare_terminal_sessions_for_shutdown()
            snapshot, = host.shutdown_terminal_processes
            del live[42]
            host.clear_terminal_process_state(session, terminal, pane)

            self.assertEqual(host.orphaned_terminal_processes, {snapshot})
            self.assertEqual(host.pending_shutdown_terminal_processes(), (snapshot,))
            live.clear()
            self.assertEqual(host.pending_shutdown_terminal_processes(), ())

    def test_child_exit_does_not_restart_pending_forced_cleanup(self) -> None:
        terminal = object()
        process = TerminalProcess(42, 42, 42, "leader")
        snapshot = TerminalProcess(
            42, 42, 42, "leader", (SessionProcessIdentity(43, 43, "child"),)
        )
        pane = SimpleNamespace(child_pid=42, child_process=process)
        session = SimpleNamespace(
            terminal=terminal, child_pid=42, child_process=process,
            split_child_pids={}, split_processes={},
        )
        host = TerminalSessionsMixin()
        host.orphaned_terminal_processes = {snapshot}
        host.terminate_terminal_process = Mock()

        with patch("termia.terminal_sessions.terminal_process_is_active", return_value=True):
            host.clear_terminal_process_state(session, terminal, pane)

        host.terminate_terminal_process.assert_not_called()
        self.assertEqual(host.orphaned_terminal_processes, {snapshot})

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

    @patch("termia.terminal_sessions.terminal_process_is_active", return_value=True)
    @patch(
        "termia.terminal_sessions.snapshot_terminal_process",
        side_effect=lambda process: TerminalProcess(
            process.pid,
            process.process_group_id,
            process.session_id,
            process.start_time,
            (SessionProcessIdentity(process.pid + 1, process.pid + 1, "child"),),
        ),
    )
    def test_shutdown_retains_process_identity_after_terminal_state_is_cleared(
        self, _snapshot, _active
    ) -> None:
        process = TerminalProcess(42, 99, 500, "leader")
        session = SimpleNamespace(
            id="session",
            child_process=process,
            split_processes={},
            panes={},
            disconnect_requested=False,
            pending_reconnect=False,
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.shutdown_in_progress = True
                self.terminated = []

            def terminate_terminal_process(self, current, *, force=False):
                self.terminated.append((current, force))
                return True

        host = Host()
        host.prepare_terminal_sessions_for_shutdown()
        host.terminate_open_terminal_processes()
        session.child_process = None

        host.terminate_open_terminal_processes(force=True)

        self.assertEqual(len(host.terminated), 2)
        for captured, _forced in host.terminated:
            self.assertEqual(captured.session_members[0].pid, 43)
        self.assertEqual([forced for _captured, forced in host.terminated], [False, True])

    @patch("termia.terminal_sessions.GLib.timeout_add")
    @patch("termia.terminal_sessions.signal_terminal_process", return_value=True)
    @patch("termia.terminal_sessions.snapshot_terminal_process", side_effect=lambda process: process)
    def test_shutdown_uses_only_the_global_forced_termination_pass(self, snapshot, signal_process, timeout_add) -> None:
        process = TerminalProcess(pid=42, process_group_id=99, session_id=500, start_time="42")
        host = TerminalSessionsMixin()
        host.shutdown_in_progress = True

        self.assertTrue(host.terminate_terminal_process(process))

        snapshot.assert_called_once_with(process)
        signal_process.assert_called_once_with(process, signal.SIGTERM)
        timeout_add.assert_not_called()

    def test_forced_cleanup_retains_the_snapshot_used_for_soft_termination(self) -> None:
        process = TerminalProcess(42, 42, 42, "leader")
        snapshot = TerminalProcess(
            42, 42, 42, "leader", (SessionProcessIdentity(43, 43, "child"),)
        )
        host = TerminalSessionsMixin()

        with (
            patch("termia.terminal_sessions.snapshot_terminal_process", return_value=snapshot),
            patch("termia.terminal_sessions.signal_terminal_process", return_value=True) as signal_process,
            patch("termia.terminal_sessions.GLib.timeout_add") as timeout_add,
        ):
            self.assertTrue(host.terminate_terminal_process(process))

        signal_process.assert_called_once_with(snapshot, signal.SIGTERM)
        timeout_add.assert_called_once_with(500, host.force_terminate_terminal_process, snapshot)
        self.assertEqual(host.orphaned_terminal_processes, {snapshot})

    def test_forced_cleanup_does_not_signal_a_reused_snapshot_child_pid(self) -> None:
        process = TerminalProcess(
            42, 42, 42, "leader", (SessionProcessIdentity(43, 43, "old-child"),)
        )
        host = TerminalSessionsMixin()
        with (
            patch("termia.terminal_processes.process_start_time", side_effect=lambda pid: "new-child" if pid == 43 else None),
            patch("termia.terminal_processes.os.killpg") as killpg,
            patch("termia.terminal_processes.os.kill") as kill,
        ):
            host.force_terminate_terminal_process(process)

        killpg.assert_not_called()
        kill.assert_not_called()

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

    def test_ssh_clean_exit_accepts_remote_nonzero_statuses_but_not_transport_failures(self) -> None:
        host = TerminalSessionsMixin()

        self.assertTrue(host.ssh_status_is_clean_exit(0))
        self.assertTrue(host.ssh_status_is_clean_exit(256))
        self.assertTrue(host.ssh_status_is_clean_exit(254 << 8))
        self.assertFalse(host.ssh_status_is_clean_exit(255 << 8))
        self.assertFalse(host.ssh_status_is_clean_exit(signal.SIGTERM))

    def test_ssh_remote_nonzero_exit_closes_the_root_session(self) -> None:
        terminal = object()
        pane = SimpleNamespace(
            id="pane",
            connected=True,
            disconnect_requested=False,
            disconnect_button=Mock(),
        )
        session = SimpleNamespace(
            id="session",
            title="Example",
            terminal=terminal,
            page=object(),
            active_terminal_ids=set(),
            status_label=Mock(),
            connected=True,
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.shutdown_in_progress = False
                self.store = SimpleNamespace(record_history_end=Mock())
                self.session_observer = Mock()
                self.toast_label = Mock()
                self.closed = []
                self.reconnect_requested = False

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def pane_state(self, _session, _terminal):
                return pane

            def clear_terminal_process_state(self, *_args) -> None:
                pass

            def should_close_tab_after_terminal_exit(self, _session) -> bool:
                return True

            def close_tab(self, *args, **kwargs) -> None:
                self.closed.append((args, kwargs))

            def mark_session_for_reconnect(self, *_args) -> None:
                self.reconnect_requested = True

            def t(self, key):
                return {
                    "session_closed_toast": "Closed: {title}",
                }[key]

        host = Host()
        host.on_terminal_exited(terminal, 256, SimpleNamespace(name="Example"), session)

        host.store.record_history_end.assert_called_once_with(session, "closed")
        self.assertEqual(len(host.closed), 1)
        self.assertFalse(host.reconnect_requested)

    def test_ssh_remote_nonzero_exit_closes_a_split_pane(self) -> None:
        terminal = object()
        pane = SimpleNamespace(
            id="split-pane",
            title="Example",
            server_id="server",
            connected=True,
            disconnect_requested=False,
            disconnect_button=Mock(),
            status_label=Mock(),
        )
        session = SimpleNamespace(
            id="session",
            title="Example",
            page=object(),
            active_terminal_ids=set(),
            connected=True,
            pane_for_terminal=lambda current: pane if current is terminal else None,
            split_terminals=[terminal],
            status_label=Mock(),
            disconnect_button=Mock(),
        )

        class Host(TerminalSessionsMixin):
            def __init__(self) -> None:
                self.shutdown_in_progress = False
                self.store = SimpleNamespace(record_history_end=Mock())
                self.session_observer = Mock()
                self.closed = []
                self.reconnect_requested = False

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def clear_terminal_process_state(self, *_args) -> None:
                pass

            def should_close_tab_after_terminal_exit(self, _session) -> bool:
                return True

            def close_tab(self, *args, **kwargs) -> None:
                self.closed.append((args, kwargs))

            def mark_pane_for_reconnect(self, *_args) -> None:
                self.reconnect_requested = True

            def t(self, key):
                return {
                    "session_closed_status": "Closed: {title}",
                    "connection_failed_toast": "Failed: {title}",
                }[key]

        host = Host()
        host.on_split_terminal_exited(terminal, 256, session)

        host.store.record_history_end.assert_called_once_with(pane, "closed")
        self.assertEqual(len(host.closed), 1)
        self.assertFalse(host.reconnect_requested)

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
                self.session_observer = Mock()
                self.toast_label = Mock()
                self.reconnect_requested = False

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def pane_state(self, _session, _terminal):
                return pane

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
                self.session_observer = Mock()
                self.toast_label = Mock()

            def mark_terminal_inactive(self, _terminal, _session) -> None:
                pass

            def pane_state(self, _session, _terminal):
                return pane

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
                self.session_observer = Mock()
                self.reconnect_requested = False

            def mark_terminal_inactive(self, _terminal, _session) -> None:
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
