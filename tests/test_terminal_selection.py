# SPDX-License-Identifier: GPL-3.0-or-later
import gc
import tempfile
import unittest
import weakref
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import GLib, Gtk, Vte

from termia.general_preferences import GeneralPreferencesMixin
from termia.i18n import translate_key
from termia.models import AppSettings
from termia.stores import ConnectionStore, normalize_app_settings
from termia.terminal_sessions import TerminalSessionsMixin


class CopyHost(TerminalSessionsMixin):
    t = staticmethod(lambda key: translate_key(key, "es"))

    def __init__(self):
        self.store = SimpleNamespace(data=SimpleNamespace(app=AppSettings(copy_on_selection=True)))
        self.toast_label = Mock()


class CopyPane:
    def __init__(self, terminal):
        self.terminal = terminal
        self.retired = False


class AutomaticSelectionCopyTests(unittest.TestCase):
    def setUp(self):
        self.host = CopyHost()
        self.terminal = Mock(spec=Vte.Terminal)
        self.terminal.get_has_selection.return_value = True
        self.terminal.get_text_selected.return_value = "synthetic text"
        self.clipboard = self.terminal.get_clipboard.return_value
        self.clipboard.set_content.return_value = True
        self.pane = CopyPane(self.terminal)
        self.session = Mock()
        self.session.pane_for_terminal.return_value = self.pane
        idle_patch = patch("termia.terminal_sessions.GLib.idle_add")
        self.idle = idle_patch.start()
        self.addCleanup(idle_patch.stop)

    def schedule(self):
        self.host.on_terminal_selection_changed(self.terminal, self.session)
        self.clipboard.set_content.assert_not_called()
        return self.idle.call_args.args[0]

    def test_disabled_and_empty_selection_leave_clipboard_unchanged(self):
        self.host.store.data.app.copy_on_selection = False
        self.host.on_terminal_selection_changed(self.terminal, self.session)
        self.host.store.data.app.copy_on_selection = True
        self.terminal.get_has_selection.return_value = False
        self.host.on_terminal_selection_changed(self.terminal, self.session)
        self.idle.assert_not_called()
        self.terminal.get_clipboard.assert_not_called()

    def test_counts_unicode_spaces_and_newlines_without_exposing_text(self):
        self.terminal.get_text_selected.return_value = "á🙂 \n"
        self.assertFalse(self.schedule()())
        self.terminal.get_text_selected.assert_called_once_with(Vte.Format.TEXT)
        self.clipboard.set_content.assert_called_once()
        self.host.toast_label.set_success.assert_called_once_with("Copiados 4 caracteres al portapapeles")
        self.host.toast_label.set_error.assert_not_called()

    def test_single_character_uses_singular_notification(self):
        self.terminal.get_text_selected.return_value = "é"
        self.schedule()()
        self.host.toast_label.set_success.assert_called_once_with("Copiado 1 carácter al portapapeles")

    def test_clipboard_rejection_never_reports_success(self):
        self.clipboard.set_content.return_value = False
        self.schedule()()
        self.host.toast_label.set_error.assert_called_once_with("No se pudo copiar el texto seleccionado al portapapeles")
        self.host.toast_label.set_success.assert_not_called()

    def test_deselection_or_disabled_setting_before_idle_cancels_copy(self):
        callback = self.schedule()
        self.terminal.get_has_selection.return_value = False
        callback()
        self.terminal.get_has_selection.return_value = True
        callback = self.schedule()
        self.host.store.data.app.copy_on_selection = False
        callback()
        self.clipboard.set_content.assert_not_called()

    def test_removed_or_retired_pane_does_not_copy(self):
        self.session.pane_for_terminal.return_value = None
        self.host.on_terminal_selection_changed(self.terminal, self.session)
        self.idle.assert_not_called()
        self.session.pane_for_terminal.return_value = self.pane
        callback = self.schedule()
        self.pane.retired = True
        callback()
        self.clipboard.set_content.assert_not_called()

    def test_idle_does_not_keep_owner_alive(self):
        callback = self.schedule()
        reference = weakref.ref(self.host)
        del self.host
        gc.collect()
        self.assertIsNone(reference())
        self.assertFalse(callback())
        self.clipboard.set_content.assert_not_called()

    def test_no_selected_text_does_not_report_success(self):
        self.terminal.get_text_selected.return_value = None
        self.schedule()()
        self.clipboard.set_content.assert_not_called()
        self.host.toast_label.set_success.assert_not_called()


class ClipboardPreferenceTests(unittest.TestCase):
    def test_auto_copy_is_opt_in_for_old_or_invalid_settings(self):
        self.assertFalse(AppSettings().copy_on_selection)
        for value in (None, 0, 1, "true", False):
            with self.subTest(value=value):
                self.assertFalse(normalize_app_settings(AppSettings(copy_on_selection=value)).copy_on_selection)
        self.assertTrue(normalize_app_settings(AppSettings(copy_on_selection=True)).copy_on_selection)

    def test_copy_and_paste_preferences_persist_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(root / "connections.json", root / "settings.json",
                                    root / "statistics.json", root / "lock", root / "history")
            self.addCleanup(store.close)
            for copy, confirm in ((True, True), (True, False), (False, True), (False, False)):
                with self.subTest(copy=copy, confirm=confirm):
                    store.update_app_settings(replace(store.data.app, copy_on_selection=copy,
                                                      confirm_multiline_paste=confirm))
                    store.update_notes_editor({"size": 14})
                    store.settings_store.load()
                    self.assertEqual(store.settings_store.app.copy_on_selection, copy)
                    self.assertEqual(store.settings_store.app.confirm_multiline_paste, confirm)

    def test_general_preferences_save_keeps_copy_paste_and_debug_distinct(self):
        data = SimpleNamespace(app=AppSettings(language="en"), groups=[])
        host = Mock()
        host.store.data = data
        host.general_preference_values = GeneralPreferencesMixin.general_preference_values
        host.store.update_app_settings.side_effect = lambda app: setattr(data, "app", app)
        values = [False, False, True, False, True, False, False,
                  True, False, False, False, False, True, True]
        checks = [Mock(get_active=Mock(return_value=value)) for value in values]
        with patch("termia.general_preferences.choice_id", side_effect=["dark", "en"]):
            GeneralPreferencesMixin.on_app_preferences_response(host, Mock(), Gtk.ResponseType.OK,
                                                                Mock(), Mock(), *checks)
        self.assertFalse(data.app.confirm_multiline_paste)
        self.assertTrue(data.app.copy_on_selection)
        self.assertTrue(data.app.debug_enabled)


@unittest.skipUnless(Gtk.init_check(), "GTK display unavailable")
class NativeSelectionCopyTests(unittest.TestCase):
    def test_native_selection_copies_and_deselection_preserves_clipboard(self):
        host = CopyHost()
        terminal = Vte.Terminal()
        pane = CopyPane(terminal)
        session = Mock()
        session.pane_for_terminal.return_value = pane
        window = Gtk.Window()
        self.addCleanup(window.destroy)
        window.set_child(terminal)
        window.present()
        terminal.connect("selection-changed", host.on_terminal_selection_changed, session)

        def settle():
            loop = GLib.MainLoop()
            GLib.timeout_add(50, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
            loop.run()

        terminal.feed(b"synthetic first\r\nsynthetic second")
        settle()
        terminal.select_all()
        expected = terminal.get_text_selected(Vte.Format.TEXT)
        self.assertTrue(expected)
        settle()
        terminal.unselect_all()
        settle()
        self.assertFalse(terminal.get_has_selection())
        received = []
        loop = GLib.MainLoop()

        def read(clipboard, result):
            received.append(clipboard.read_text_finish(result))
            loop.quit()

        terminal.get_clipboard().read_text_async(None, read)
        timeout = GLib.timeout_add(2000, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
        loop.run()
        if received:
            GLib.source_remove(timeout)
        self.assertEqual(received, [expected])
        host.toast_label.set_success.assert_called_once()
