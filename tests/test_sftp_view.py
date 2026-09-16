import time
import os
import unittest
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
    def test_window_lists_files_without_changing_parent_and_closes_backend(self):
        try:
            parent = Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))
        backend = Mock()
        backend.connect.return_value = "/home/synthetic"
        backend.list_directory.return_value = [RemoteEntry("test.txt", 4, 0, 0o100600)]
        closed = Mock()
        window = SFTPWindow(parent, Endpoint("example.test", 22, "test"), "Synthetic",
                            lambda key: translate_key(key, "en"), closed,
                            owner_session_id="session-1", backend_factory=lambda _: backend)
        self.addCleanup(parent.destroy)
        self.addCleanup(window.destroy)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if window.rows.get_first_child() is not None:
                break
            time.sleep(0.005)
        self.assertEqual(window.path, "/home/synthetic")
        self.assertEqual(window.rows.get_first_child().entry.name, "test.txt")
        self.assertIsNone(parent.get_child())
        window.cancel_active_transfer(close_dialog=True)
        self.assertTrue(window.disposed)
        backend.close.assert_called_once()
        closed.assert_called_once_with(window)
