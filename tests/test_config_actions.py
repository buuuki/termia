import json
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

from termia import config_io
from termia.config_actions import ConfigActionsMixin, Gio, GLib, Gtk
from termia.config_io import read_connections_payload, write_connections_file
from termia.dialog_actions import add_dialog_action_button
from termia.dialog_window import DialogWindow
from termia.i18n import translate_key
from termia.models import Server
from termia.stores import ConnectionStore


class DataLocationsTests(unittest.TestCase):
    def test_all_locations_fit_without_scrolling_in_each_language(self):
        if not Gtk.init_check():
            self.skipTest("GTK display unavailable")
        paths = ConfigActionsMixin.data_location_paths(None)
        for language in ("en", "es", "ca"):
            for long_path in (False, True):
                with self.subTest(language=language, long_path=long_path):
                    host = Gtk.Window()
                    host.t = lambda key, lang=language: translate_key(key, lang)
                    locations = [(key, Path("/synthetic") / ("nested-directory/" * 5 if long_path else "")
                                  / path.name) for key, path in paths]
                    host.data_location_paths = lambda values=locations: values
                    host.add_dialog_action_button = add_dialog_action_button
                    dialog = None
                    try:
                        ConfigActionsMixin.on_data_locations(host)
                        dialog = next(window for window in Gtk.Window.list_toplevels()
                                      if window.get_transient_for() == host)
                        loop = GLib.MainLoop()
                        GLib.timeout_add(200, lambda active_loop=loop: (active_loop.quit(), False)[1])
                        loop.run()
                        content = dialog.get_content_area()
                        grid = content.get_first_child().get_next_sibling()
                        self.assertIsInstance(grid, Gtk.Grid)
                        for row, (_key, path) in enumerate(locations):
                            label, path_label, status = (grid.get_child_at(column, row)
                                                         for column in range(3))
                            self.assertEqual(path_label.get_text(), str(path))
                            self.assertTrue(path_label.get_selectable())
                            self.assertIn("monospace", path_label.get_attributes().to_string())
                            self.assertEqual(label.get_valign(), Gtk.Align.START)
                            self.assertEqual(status.get_valign(), Gtk.Align.START)
                            for widget in (label, path_label, status):
                                valid, bounds = widget.compute_bounds(dialog)
                                self.assertTrue(valid)
                                self.assertGreater(bounds.get_width(), 0)
                                self.assertGreaterEqual(bounds.get_y(), 0)
                                self.assertLessEqual(bounds.get_y() + bounds.get_height(), dialog.get_height())
                                self.assertLessEqual(bounds.get_x() + bounds.get_width(), dialog.get_width())
                        self.assertLess(dialog.get_height(), 760)
                        dialog.get_widget_for_response(Gtk.ResponseType.CLOSE).emit("clicked")
                        closing = GLib.MainLoop()
                        GLib.timeout_add(100, lambda active_loop=closing: (active_loop.quit(), False)[1])
                        closing.run()
                        self.assertNotIn(dialog, Gtk.Window.list_toplevels())
                    finally:
                        if dialog is not None:
                            dialog.destroy()
                        host.destroy()


class ConnectionImportTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gtk.Settings.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = ConnectionStore(
            self.root / "connections.json", self.root / "settings.json",
            self.root / "statistics.json", self.root / "lock", self.root / "history",
        )
        self.store.add_server("Existing", "existing.test", "synthetic", 22, None)
        self.note = self.store.add_note("Synthetic note", "Keep this note")
        self.incoming = self.root / "import.json"
        write_connections_file(
            self.incoming, [], [Server("incoming", "Incoming", "example.test", "synthetic")],
            [], "encrypted", "synthetic-file-password",
        )
        self.host = Gtk.Window()
        self.host.store = self.store
        self.host.t = lambda key: key
        self.host.toast_label = SimpleNamespace(set_error=Mock(), set_label=Mock())
        self.host.ensure_writable = lambda: not (self.store.read_only or self.store.encryption_locked)
        self.host.apply_app_theme = Mock()
        self.host.refresh_list = Mock()
        for name in (
            "on_import_config_selected", "import_connection_file",
            "present_connection_import_password", "on_connection_import_password_response",
        ):
            setattr(self.host, name, MethodType(getattr(ConfigActionsMixin, name), self.host))
        self.host.add_dialog_action_buttons = self.add_buttons
        self.original = self.store.path.read_bytes()

    @staticmethod
    def add_buttons(dialog, label):
        add_dialog_action_button(dialog, "Cancel", Gtk.ResponseType.CANCEL)
        add_dialog_action_button(dialog, label, Gtk.ResponseType.OK)

    def tearDown(self):
        for window in Gtk.Window.list_toplevels():
            if window.get_transient_for() == self.host:
                window.destroy()
        self.host.destroy()
        self.store.close()
        self.temporary.cleanup()

    def select(self):
        chooser = SimpleNamespace(open_finish=lambda _: Gio.File.new_for_path(str(self.incoming)))
        self.host.on_import_config_selected(chooser, None)

    def prompt(self):
        self.select()
        dialog = next(window for window in Gtk.Window.list_toplevels()
                      if isinstance(window, DialogWindow) and window.get_transient_for() == self.host)
        entry = dialog.get_content_area().get_first_child().get_next_sibling()
        return dialog, entry, entry.get_next_sibling()

    def test_wrong_password_can_retry_without_changing_data(self):
        dialog, entry, error = self.prompt()
        entry.set_text("synthetic-wrong")
        dialog.response(Gtk.ResponseType.OK)
        self.assertEqual(error.get_label(), "import_config_unlock_wrong")
        self.assertEqual(entry.get_text(), "")
        self.assertTrue(dialog.get_visible())
        self.assertEqual(self.store.path.read_bytes(), self.original)
        entry.set_text("synthetic-file-password")
        dialog.get_widget_for_response(Gtk.ResponseType.OK).emit("clicked")
        self.assertEqual(self.store.data.servers[0].id, "incoming")
        self.assertEqual(self.store.data.notes, [self.note])
        self.assertIsNone(self.store.master_password)
        self.host.toast_label.set_label.assert_called_with("import_config_success")

    def test_import_retains_current_profile_encryption_password(self):
        self.store.update_connection_storage_mode("encrypted", "synthetic-profile-password")
        dialog, entry, _ = self.prompt()
        entry.set_text("synthetic-file-password")
        dialog.response(Gtk.ResponseType.OK)
        self.assertEqual(self.store.master_password, "synthetic-profile-password")
        self.assertEqual(read_connections_payload(self.store.path, "synthetic-profile-password")
                         ["servers"][0]["id"], "incoming")
        self.assertEqual(self.store.data.notes, [self.note])

    def test_cancel_preserves_data_and_clears_entry(self):
        dialog, entry, _ = self.prompt()
        entry.set_text("synthetic-file-password")
        dialog.get_widget_for_response(Gtk.ResponseType.CANCEL).emit("clicked")
        self.assertEqual(entry.get_text(), "")
        self.assertEqual(self.store.path.read_bytes(), self.original)
        self.assertEqual(self.store.data.servers[0].name, "Existing")

    def test_empty_password_keeps_prompt_open(self):
        dialog, _entry, error = self.prompt()
        dialog.response(Gtk.ResponseType.OK)
        self.assertTrue(dialog.get_visible())
        self.assertEqual(error.get_label(), "import_config_unlock_required")
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_write_lock_changed_while_prompt_open_preserves_data(self):
        dialog, entry, _ = self.prompt()
        entry.set_text("synthetic-file-password")
        self.store.read_only = True
        dialog.response(Gtk.ResponseType.OK)
        self.assertEqual(entry.get_text(), "")
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_read_only_import_never_prompts(self):
        self.store.read_only = True
        with patch.object(self.host, "present_connection_import_password") as prompt:
            self.select()
            prompt.assert_not_called()
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_resource_budget_rejected_before_prompt(self):
        self.incoming.write_text(json.dumps({
            "format": config_io.ENCRYPTED_CONNECTIONS_FORMAT,
            "iterations": config_io.MAX_KDF_ITERATIONS + 1,
        }))
        with patch.object(self.host, "present_connection_import_password") as prompt:
            self.select()
            prompt.assert_not_called()
        self.host.toast_label.set_error.assert_called_once()
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_file_is_revalidated_after_password_prompt(self):
        dialog, entry, _ = self.prompt()
        self.incoming.write_bytes(b" " * 65)
        entry.set_text("synthetic-file-password")
        with patch.object(config_io, "MAX_STORAGE_BYTES", 64):
            dialog.response(Gtk.ResponseType.OK)
        self.host.toast_label.set_error.assert_called_once()
        self.assertEqual(self.store.path.read_bytes(), self.original)

    def test_plain_import_does_not_prompt(self):
        write_connections_file(self.incoming, [], [], [], "plain")
        with patch.object(self.host, "present_connection_import_password") as prompt:
            self.select()
            prompt.assert_not_called()
        self.assertEqual(self.store.data.servers, [])
        self.assertEqual(self.store.data.notes, [self.note])
