import tempfile
import unittest
import signal
from pathlib import Path
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from termia.file_transfer import DESTINATION, FileTransferController, build_scp_commands
from termia.models import Server
from termia.terminal_processes import TerminalProcess


class FileTransferTests(unittest.TestCase):
    def build_controller(self):
        parent = Mock()
        toast = Mock()
        controller = FileTransferController(parent, lambda key: key, toast, Mock(), Mock())
        return controller, parent, toast

    @staticmethod
    def build_state(**overrides):
        state = {
            "cancel": Mock(),
            "cancellable": Gio.Cancellable(),
            "cancelled": False,
            "completed": False,
            "dialog": Mock(),
            "dialog_destroyed": False,
            "force_termination_id": None,
            "parent_close_id": None,
            "phase": "copy",
            "process": None,
            "process_identity": None,
            "progress": Mock(),
            "pulse_id": None,
            "status": Mock(),
        }
        state.update(overrides)
        return state

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

    def test_run_command_uses_an_isolated_session_and_captures_identity(self) -> None:
        controller, _parent, _toast = self.build_controller()
        state = self.build_state(phase="prepare")
        launcher = Mock()
        process = Mock()
        process.get_identifier.return_value = "321"
        launcher.spawnv.return_value = process
        identity = TerminalProcess(321, 321, 321, "start")

        with (
            patch("termia.file_transfer.GLib.find_program_in_path", return_value="/usr/bin/setsid"),
            patch("termia.file_transfer.Gio.SubprocessLauncher.new", return_value=launcher),
            patch("termia.file_transfer.capture_terminal_process", return_value=identity),
        ):
            controller.run_command(["/usr/bin/scp", "source", "target"], "secret", state, Mock())

        launcher.setenv.assert_called_once_with("SSHPASS", "secret", True)
        launcher.spawnv.assert_called_once_with(
            ["/usr/bin/setsid", "--wait", "/usr/bin/scp", "source", "target"]
        )
        self.assertIs(state["process"], process)
        self.assertEqual(state["process_identity"], identity)
        process.communicate_utf8_async.assert_called_once()

    def test_cancel_requests_bounded_process_tree_termination_once(self) -> None:
        controller, _parent, toast = self.build_controller()
        identity = TerminalProcess(321, 321, 321, "start")
        state = self.build_state(process=Mock(), process_identity=identity)

        with (
            patch.object(controller, "refresh_process_identity", return_value=identity),
            patch("termia.file_transfer.signal_terminal_process", return_value=True) as terminate,
            patch("termia.file_transfer.GLib.timeout_add", return_value=77) as timeout_add,
        ):
            controller.cancel_transfer(state)
            controller.cancel_transfer(state)

        self.assertTrue(state["cancellable"].is_cancelled())
        self.assertTrue(state["cancelled"])
        self.assertTrue(state["completed"])
        terminate.assert_called_once_with(identity, signal.SIGTERM)
        timeout_add.assert_called_once_with(500, controller.force_process_termination, state, identity)
        toast.set_label.assert_called_once_with("send_files_to_server_cancelled")
        toast.set_error.assert_not_called()

    def test_force_termination_kills_only_a_still_active_captured_session(self) -> None:
        controller, _parent, _toast = self.build_controller()
        identity = TerminalProcess(321, 321, 321, "start")
        state = self.build_state(force_termination_id=77)

        with (
            patch.object(controller, "refresh_process_identity", return_value=identity),
            patch("termia.file_transfer.terminal_process_is_active", return_value=True),
            patch("termia.file_transfer.signal_terminal_process", return_value=True) as terminate,
        ):
            result = controller.force_process_termination(state, identity)

        self.assertEqual(result, GLib.SOURCE_REMOVE)
        self.assertIsNone(state["force_termination_id"])
        terminate.assert_called_once_with(identity, signal.SIGKILL)

    def test_window_close_cancels_transfer_and_destroys_dialog(self) -> None:
        controller, _parent, _toast = self.build_controller()
        dialog = Mock()
        state = self.build_state(dialog=dialog)
        controller.cancel_transfer = Mock()

        controller.on_dialog_response(dialog, Gtk.ResponseType.DELETE_EVENT, state)

        controller.cancel_transfer.assert_called_once_with(state)
        dialog.destroy.assert_called_once_with()

    def test_registered_owner_can_cancel_the_active_transfer(self) -> None:
        controller, _parent, _toast = self.build_controller()
        state = self.build_state()
        controller.active_state = state
        controller.cancel_transfer = Mock()

        controller.cancel_active_transfer()

        controller.cancel_transfer.assert_called_once_with(state)

    def test_owner_close_cancels_and_destroys_transfer_dialog_once(self) -> None:
        controller, _parent, _toast = self.build_controller()
        dialog = Mock()
        state = self.build_state(dialog=dialog)
        controller.active_state = state

        controller.cancel_active_transfer(close_dialog=True)
        controller.destroy_transfer_dialog(state)

        self.assertTrue(state["completed"])
        self.assertTrue(state["dialog_destroyed"])
        dialog.destroy.assert_called_once_with()

    def test_late_success_callback_does_not_continue_after_cancellation(self) -> None:
        controller, _parent, _toast = self.build_controller()
        process = Mock()
        process.communicate_utf8_finish.return_value = (True, "", "")
        state = self.build_state(process=process, completed=True, cancelled=True)
        on_success = Mock()

        controller.on_command_finished(process, Mock(), state, on_success)

        on_success.assert_not_called()
        self.assertIsNone(state["process"])

    def test_known_host_callback_cannot_start_transfer_after_owner_shutdown(self) -> None:
        controller, _parent, _toast = self.build_controller()
        controller.cancel_active_transfer()
        controller.show_transfer_dialog = Mock()

        controller._start_upload_after_known_host_check(
            Server(id="server-1", name="Web", host="example.test", user="admin"),
            [Path("report.txt")],
            "/usr/bin/ssh",
            "/usr/bin/scp",
            True,
        )

        controller.show_transfer_dialog.assert_not_called()

    def test_failed_and_successful_outcomes_use_distinct_notifications(self) -> None:
        controller, _parent, toast = self.build_controller()
        failed_state = self.build_state()
        successful_state = self.build_state()

        controller.finish_dialog(failed_state, "failed", outcome="failed")
        controller.finish_dialog(successful_state, "finished", outcome="success")

        toast.set_error.assert_called_once_with("failed")
        toast.set_success.assert_called_once_with("finished")
        failed_state["progress"].set_fraction.assert_called_once_with(0.0)
        successful_state["progress"].set_fraction.assert_called_once_with(1.0)
