import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from termia.file_transfer import DESTINATION, FileTransferController, build_scp_commands
from termia.models import Server


class FileTransferTests(unittest.TestCase):
    def test_builds_ssh_and_scp_commands_for_files_and_directories(self) -> None:
        server = Server(
            id="server-1",
            name="Web",
            host="example.test",
            user="admin",
            port=2200,
            public_key="~/.ssh/id_ed25519",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "file with spaces.txt"
            file_path.touch()
            folder = root / "folder"
            folder.mkdir()

            ssh_command, scp_command = build_scp_commands(
                server,
                [file_path, folder],
                "/usr/bin/ssh",
                "/usr/bin/scp",
            )

        self.assertEqual(ssh_command[:5], ["/usr/bin/ssh", "-p", "2200", "-i", str(Path("~/.ssh/id_ed25519").expanduser())])
        self.assertEqual(ssh_command[-4:], ["admin@example.test", "mkdir", "-p", DESTINATION])
        self.assertIn("-r", scp_command)
        self.assertEqual(scp_command[-1], f"admin@example.test:{DESTINATION}/")
        self.assertIn(str(file_path), scp_command)

    def test_wraps_commands_with_sshpass_without_shell_interpolation(self) -> None:
        server = Server(id="server-1", name="Web", host="example.test", user="admin")

        ssh_command, scp_command = build_scp_commands(
            server,
            [Path("file;touch compromised")],
            "/usr/bin/ssh",
            "/usr/bin/scp",
            sshpass_path="/usr/bin/sshpass",
        )

        self.assertEqual(ssh_command[:2], ["/usr/bin/sshpass", "-e"])
        self.assertEqual(scp_command[:2], ["/usr/bin/sshpass", "-e"])
        self.assertIn("file;touch compromised", scp_command)

    def test_defers_upload_until_known_host_check_finishes(self) -> None:
        inspect_known_host = Mock()
        toast = Mock()
        controller = FileTransferController(object(), lambda key: key, toast, Mock(), inspect_known_host)
        controller.show_transfer_dialog = Mock()

        with patch(
            "termia.file_transfer.GLib.find_program_in_path",
            side_effect=lambda program: f"/usr/bin/{program}",
        ):
            controller.start_upload(
                Server(id="server-1", name="Web", host="example.test", user="admin"),
                [Path("report.txt")],
            )

        inspect_known_host.assert_called_once()
        controller.show_transfer_dialog.assert_not_called()
        callback = inspect_known_host.call_args.args[2]
        callback(False)
        toast.set_label.assert_called_once_with("send_files_to_server_fingerprint")
        controller.show_transfer_dialog.assert_not_called()
