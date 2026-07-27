import signal
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from termia.terminal_processes import TerminalProcess, signal_terminal_process, spawn_terminal_process
from termia.terminal_sessions import TerminalSessionsMixin


class FakeTerminal:
    def spawn_sync(self, *args: object) -> tuple[bool, int]:
        self.args = args
        return True, 4242


class TerminalProcessTests(unittest.TestCase):
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
                self.open_tabs = {
                    "session": SimpleNamespace(
                        child_process=main_process,
                        split_processes={"split": split_process},
                    )
                }
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
