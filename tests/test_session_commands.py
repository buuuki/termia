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
