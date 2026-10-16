import shlex
import unittest
from pathlib import Path

from termia.models import Server
from termia.session_commands import build_ssh_command


class SessionCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = Server(
            id="server-1",
            name="Web",
            host="example.test",
            user="admin",
            port=2200,
            public_key="~/.ssh/id_ed25519",
        )

    def test_builds_ssh_command_with_identity_file(self) -> None:
        command = build_ssh_command(self.server, "/usr/bin/ssh")

        self.assertEqual(
            command,
            [
                "/usr/bin/ssh",
                "-p",
                "2200",
                "-i",
                str(Path("~/.ssh/id_ed25519").expanduser()),
                "admin@example.test",
            ],
        )

    def test_wraps_ssh_command_with_sshpass_as_argv(self) -> None:
        command = build_ssh_command(self.server, "/usr/bin/ssh", sshpass_path="/usr/bin/sshpass")

        self.assertEqual(command[:2], ["/usr/bin/sshpass", "-e"])
        self.assertEqual(command[-1], "admin@example.test")

    def test_runs_saved_startup_command_after_auth_and_keeps_interactive_shell(self) -> None:
        self.server.command_on_start = "cd /srv/app && ./start.sh"

        command = build_ssh_command(self.server, "/usr/bin/ssh")

        self.assertIn("-t", command)
        self.assertEqual(command[-2], "admin@example.test")
        remote_argv = shlex.split(command[-1])
        self.assertEqual(remote_argv[:2], ["sh", "-c"])
        login_argv = shlex.split(remote_argv[2])
        self.assertEqual(login_argv[0], "remote_shell=${SHELL:-/bin/sh};")
        self.assertEqual(login_argv[1:3], ["export", "SHELL=$remote_shell;"])
        self.assertEqual(login_argv[3:8], ["exec", "$remote_shell", "-l", "-i", "-c"])
        self.assertEqual(login_argv[-1], 'cd /srv/app && ./start.sh\nexec "$SHELL" -i')

    def test_startup_command_is_not_in_connection_banner_command(self) -> None:
        self.server.command_on_start = "printf 'private startup text'"

        command = build_ssh_command(self.server, "/usr/bin/ssh", include_startup_command=False)

        self.assertNotIn("-t", command)
        self.assertEqual(command[-1], "admin@example.test")
        self.assertNotIn("private startup text", " ".join(command))
