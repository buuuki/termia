import unittest

from termia.terminal_processes import spawn_terminal_process


class FakeTerminal:
    def spawn_sync(self, *args: object) -> tuple[bool, int]:
        self.args = args
        return True, 4242


class TerminalProcessTests(unittest.TestCase):
    def test_spawn_helper_centralizes_vte_arguments(self) -> None:
        terminal = FakeTerminal()
        environment = ["TERM=xterm-256color"]

        child_pid = spawn_terminal_process(terminal, "/tmp", ["/bin/bash", "-l"], environment)

        self.assertEqual(child_pid, 4242)
        self.assertEqual(terminal.args[1:5], ("/tmp", ["/bin/bash", "-l"], environment, 0))
        self.assertEqual(terminal.args[5:], (None, None, None))
