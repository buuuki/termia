import time
import os
import unittest
from threading import Event
from unittest.mock import Mock

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from termia.i18n import translate_key
from termia.sftp_service import Endpoint, RemoteEntry
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
        self.assertTrue(window.disposed)
        backend.close.assert_called_once()
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
        self.assertTrue(window.disposed)
        backend.close.assert_called_once()
        closed.assert_called_once_with(window)

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
        window.service.worker.join(2)
        self.assertFalse(window.service.worker.is_alive())
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        self.assertTrue(window.disposed)
        backend.close.assert_called_once()
        backend.list_directory.assert_not_called()
        closed.assert_called_once_with(window)
