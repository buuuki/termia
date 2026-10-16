import time
import os
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from termia.i18n import translate_key
from termia.sftp_service import Endpoint, RemoteEntry, TransferProgress
from termia.sftp_view import SFTPWindow


@unittest.skipUnless(
    os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"),
    "GTK display unavailable",
)
class SFTPViewTests(unittest.TestCase):
    def make_window(self, backend):
        try:
            parent = Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))
        closed = Mock()
        window = SFTPWindow(parent, Endpoint("example.test", 22, "test"), "Synthetic",
                            lambda key: translate_key(key, "en"), closed,
                            owner_session_id="session-1", backend_factory=lambda _: backend)
        self.addCleanup(parent.destroy)
        self.addCleanup(window.destroy)
        return parent, window, closed

    def drain_window(self, window):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if window.rows.get_first_child() is not None:
                break
            time.sleep(0.005)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for isolated SFTP operation")

    def test_window_lists_files_without_changing_parent_and_closes_backend(self):
        backend = Mock()
        backend.connect.return_value = "/home/synthetic"
        backend.list_directory.return_value = [RemoteEntry("test.txt", 4, 0, 0o100600)]
        parent, window, closed = self.make_window(backend)
        self.drain_window(window)
        self.assertEqual(window.path, "/home/synthetic")
        self.assertEqual(window.rows.get_first_child().entry.name, "test.txt")
        self.assertIsNone(parent.get_child())
        window.cancel_active_transfer(close_dialog=True)
        self.wait_for(lambda: closed.called)
        self.assertTrue(window.disposed)
        backend.close.assert_called()
        closed.assert_called_once_with(window)

    def test_actions_are_right_aligned_and_disconnect_closes_idle_window(self):
        backend = Mock()
        backend.connect.return_value = "/home/synthetic"
        backend.list_directory.return_value = []
        _parent, window, closed = self.make_window(backend)
        window.service.worker.join(2)
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        controls = window.cancel_button.get_parent()
        self.assertEqual(controls.get_halign(), Gtk.Align.END)
        self.assertIs(controls.get_first_child(), window.cancel_button)
        self.assertIs(window.cancel_button.get_next_sibling(), window.reconnect_button)
        self.assertIs(window.reconnect_button.get_next_sibling(), window.disconnect_button)
        self.assertFalse(window.cancel_button.get_sensitive())
        self.assertTrue(window.reconnect_button.get_sensitive())
        self.assertTrue(window.disconnect_button.get_sensitive())

        window.disconnect_button.emit("clicked")
        self.wait_for(lambda: closed.called)
        self.assertTrue(window.disposed)
        backend.close.assert_called()
        closed.assert_called_once_with(window)

    def test_file_list_uses_readable_decimal_sizes_and_preserves_byte_counts(self):
        cases = ((0, "0 B"), (999, "999 B"), (1000, "1.0 kB"),
                 (1500, "1.5 kB"), (1000 ** 2, "1.0 MB"),
                 (128 * 1000 ** 2, "128.0 MB"), (1000 ** 3, "1.0 GB"),
                 (5 * 1000 ** 3 // 2, "2.5 GB"))
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = [
            RemoteEntry(f"file-{index}", size, 0, 0o100600)
            for index, (size, _label) in enumerate(cases)
        ]
        _parent, window, closed = self.make_window(backend)
        self.drain_window(window)
        row = window.rows.get_first_child()
        for size, label in cases:
            with self.subTest(size=size):
                size_label = row.get_child().get_first_child().get_next_sibling().get_next_sibling()
                self.assertEqual(size_label.get_text(), label)
                self.assertEqual(row.entry.size, size)
                row = row.get_next_sibling()
        self.assertIsNone(row)
        window.disconnect()
        self.wait_for(lambda: closed.called)

    def test_selected_directory_can_be_downloaded_without_navigating(self):
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = [RemoteEntry("folder", 0, 0, 0o040700)]
        _parent, window, closed = self.make_window(backend)
        self.drain_window(window)
        self.assertFalse(window.rows.get_activate_on_single_click())
        row = window.rows.get_first_child()
        window.rows.select_row(row)
        self.assertEqual(window.path, "/synthetic")
        self.assertEqual(window.selected(), "/synthetic/folder")
        backend.list_directory.assert_called_once_with("/synthetic")
        destination = Path("/synthetic-downloads")
        with patch.object(window, "choose_local", side_effect=lambda directory, callback: callback([destination])) as chooser:
            window.choose_download()
            self.wait_for(lambda: not window.service.busy)
        chooser.assert_called_once()
        self.assertTrue(chooser.call_args.args[0])
        self.assertEqual(backend.download.call_args.args[:2],
                         ("/synthetic/folder", destination / "folder"))
        self.assertEqual(window.path, "/synthetic")
        window.disconnect()
        self.wait_for(lambda: closed.called)

    def test_row_activation_opens_directory_and_keeps_file_navigation_unchanged(self):
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = [RemoteEntry("folder", 0, 0, 0o040700),
                                               RemoteEntry("file.txt", 1, 0, 0o100600)]
        _parent, window, closed = self.make_window(backend)
        self.drain_window(window)
        folder = window.rows.get_first_child()
        file_row = folder.get_next_sibling()
        window.rows.select_row(file_row)
        file_row.emit("activate")
        self.assertEqual(window.path, "/synthetic")
        backend.list_directory.assert_called_once_with("/synthetic")
        folder.emit("activate")
        self.wait_for(lambda: window.path == "/synthetic/folder")
        backend.list_directory.assert_called_with("/synthetic/folder")
        window.disconnect()
        self.wait_for(lambda: closed.called)

    def test_keyboard_activation_still_opens_focused_directory(self):
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = [RemoteEntry("folder", 0, 0, 0o040700)]
        _parent, window, closed = self.make_window(backend)
        self.drain_window(window)
        window.present()
        self.wait_for(window.get_mapped)
        row = window.rows.get_first_child()
        self.assertTrue(row.grab_focus())
        window.rows.emit("activate-cursor-row")
        self.wait_for(lambda: window.path == "/synthetic/folder")
        window.disconnect()
        self.wait_for(lambda: closed.called)

    def test_disconnect_during_connection_closes_backend_and_suppresses_completion(self):
        started, released = Event(), Event()
        backend = Mock()

        def connect():
            started.set()
            released.wait(2)
            return "/home/synthetic"

        backend.connect.side_effect = connect
        backend.close.side_effect = released.set
        _parent, window, closed = self.make_window(backend)
        self.assertTrue(started.wait(2))
        self.assertTrue(window.cancel_button.get_sensitive())
        self.assertFalse(window.reconnect_button.get_sensitive())
        self.assertTrue(window.disconnect_button.get_sensitive())

        window.disconnect_button.emit("clicked")
        self.wait_for(lambda: closed.called)
        window.service.worker.join(2)
        self.assertFalse(window.service.worker.is_alive())
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        self.assertTrue(window.disposed)
        backend.close.assert_called()
        backend.list_directory.assert_not_called()
        closed.assert_called_once_with(window)

    def test_independent_window_and_modal_prompts_leave_parent_in_separate_group(self):
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = []
        parent, window, closed = self.make_window(backend)
        self.wait_for(lambda: not window.service.busy)
        self.assertIsNone(window.get_transient_for())
        self.assertFalse(window.get_modal())
        self.assertIsNot(window.get_group(), parent.get_group())
        previous = window.status.get_text()
        action = Mock()
        window.confirm("Synthetic confirmation", action)
        dialog = next(iter(window.dialogs))
        self.assertIs(dialog.get_group(), window.get_group())
        dialog.response(Gtk.ResponseType.CANCEL)
        action.assert_not_called()
        self.assertEqual(window.status.get_text(), previous)
        self.assertFalse(window.service.cancelled.is_set())
        window.disconnect()
        self.wait_for(lambda: closed.called)

    def test_transfer_and_slow_cancel_leave_main_loop_responsive(self):
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = []
        _parent, window, closed = self.make_window(backend)
        self.wait_for(lambda: not window.service.busy)
        started, release, closing = Event(), Event(), Event()
        def transfer(*_):
            started.set()
            release.wait(2)
        def close():
            closing.set()
            release.wait(2)
        backend.close.side_effect = close
        try:
            window.run(transfer, transfer=True)
            self.assertTrue(started.wait(1))
            heartbeat = Mock(return_value=GLib.SOURCE_REMOVE)
            GLib.idle_add(heartbeat)
            self.wait_for(lambda: heartbeat.called)
            window.cancel()
            self.assertTrue(closing.wait(1))
            GLib.idle_add(heartbeat)
            self.wait_for(lambda: heartbeat.call_count == 2)
            self.assertFalse(window.reconnect_button.get_sensitive())
        finally:
            release.set()
        self.wait_for(lambda: window.service.stopped)
        window.disconnect()
        self.wait_for(lambda: closed.called)

    def test_transfer_progress_final_empty_directory_and_safe_error(self):
        backend = Mock()
        backend.connect.return_value = "/synthetic"
        backend.list_directory.return_value = []
        _parent, window, closed = self.make_window(backend)
        self.wait_for(lambda: not window.service.busy)
        mb = 1000 * 1000
        value = TransferProgress("synthetic.txt", 64 * mb, 128 * mb, 2, 192 * mb, 12.5 * mb)
        window.show_progress(value)
        self.assertEqual(window.progress.get_fraction(), 0.5)
        self.assertIn("synthetic.txt", window.progress.get_text())
        self.assertIn("2 files completed", window.progress.get_text())
        self.assertIn("64.0 / 128.0 MB", window.progress.get_text())
        self.assertIn("12.50 MB/s", window.progress.get_text())
        self.assertNotIn("192.0", window.progress.get_text())
        self.assertIn("192.0 MB transferred", window.progress.get_tooltip_text())
        window.run(lambda _backend, report: report(0, None, name="empty-directory"), transfer=True)
        self.wait_for(lambda: not window.service.busy)
        self.assertEqual(window.progress.get_fraction(), 1)
        self.assertIn("empty-directory", window.progress.get_text())
        window.failed(PermissionError(13, "sensitive backend path"))
        self.assertNotIn("sensitive", window.status.get_text())
        self.assertIn("Permission denied", window.status.get_text())
        window.disconnect()
        self.wait_for(lambda: closed.called)
