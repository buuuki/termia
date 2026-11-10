# SPDX-License-Identifier: GPL-3.0-or-later
import shutil
import subprocess
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import GLib, Gtk, Vte

from termia.dialog_actions import add_dialog_action_button
from termia.i18n import translate_key
from termia.models import AppSettings
from termia.stores import ConnectionStore, normalize_app_settings
from termia.terminal_sessions import TerminalSessionsMixin


class PasteHost(TerminalSessionsMixin):
    t = staticmethod(lambda key: translate_key(key, "en"))

    def __init__(self):
        self.store = SimpleNamespace(data=SimpleNamespace(app=AppSettings()))
        self.toast_label = Mock()

    def add_dialog_action_buttons(self, dialog, label):
        return (
            add_dialog_action_button(dialog, "Cancel", Gtk.ResponseType.CANCEL),
            add_dialog_action_button(dialog, label, Gtk.ResponseType.OK),
        )


class PastePane:
    def __init__(self, terminal):
        self.terminal = terminal
        self.child_process = object()
        self.connected = True
        self.retired = False
        self.pending_reconnect = False


class PasteSettingsTests(unittest.TestCase):
    def test_default_and_invalid_values_keep_protection_enabled(self):
        self.assertTrue(AppSettings().confirm_multiline_paste)
        for value in (None, 0, 1, "false", True):
            with self.subTest(value=value):
                settings = AppSettings(confirm_multiline_paste=value)
                self.assertTrue(normalize_app_settings(settings).confirm_multiline_paste)
        self.assertFalse(normalize_app_settings(AppSettings(confirm_multiline_paste=False)).confirm_multiline_paste)

    def test_preference_survives_settings_save_reload_and_other_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(
                root / "connections.json", root / "settings.json",
                root / "statistics.json", root / "lock", root / "history",
            )
            self.addCleanup(store.close)
            for enabled in (False, True):
                with self.subTest(enabled=enabled):
                    store.update_app_settings(replace(store.data.app, confirm_multiline_paste=enabled))
                    store.update_notes_editor({"size": 14})
                    store.settings_store.load()
                    self.assertEqual(store.settings_store.app.confirm_multiline_paste, enabled)


@unittest.skipUnless(Gtk.init_check(), "GTK display unavailable")
class ProtectedPasteTests(unittest.TestCase):
    def setUp(self):
        self.host = PasteHost()
        self.root = Gtk.Window()
        self.terminal = Mock(spec=Vte.Terminal)
        self.terminal.get_root.return_value = self.root
        self.terminal.get_input_enabled.return_value = True
        self.clipboard = self.terminal.get_clipboard.return_value
        self.pane = PastePane(self.terminal)
        self.session = Mock()
        self.session.pane_for_terminal.return_value = self.pane
        self.state = {}

    def tearDown(self):
        self.host.on_terminal_paste_unrealize(self.terminal, self.state)
        self.root.destroy()
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

    def request(self, text, *, primary=False):
        self.host.request_protected_terminal_paste(
            self.terminal, self.session, self.state, primary=primary,
        )
        clipboard = self.terminal.get_primary_clipboard.return_value if primary else self.clipboard
        callback = clipboard.read_text_async.call_args.args[1]
        clipboard.read_text_finish.return_value = text
        callback(clipboard, Mock())

    def test_single_line_pastes_without_dialog(self):
        self.request("synthetic text")
        self.terminal.paste_text.assert_called_once_with("synthetic text")
        self.assertFalse(self.state)

    def test_line_breaks_require_confirmation_including_trailing_break(self):
        for text in ("one\ntwo", "one\rtwo", "one\r\ntwo", "one\n"):
            with self.subTest(text=text):
                self.request(text)
                self.terminal.paste_text.assert_not_called()
                self.state["dialog"].response(Gtk.ResponseType.CANCEL)
                self.assertFalse(self.state)

    def test_cancel_escape_response_and_window_close_never_send_text(self):
        for response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
            with self.subTest(response=response):
                self.request("one\ntwo")
                dialog = self.state["dialog"]
                dialog.get_content_area().get_last_child().get_child().get_buffer().set_text("edited\ntext")
                dialog.response(response)
                self.terminal.paste_text.assert_not_called()
                self.assertFalse(self.state)

    def test_confirmation_uses_snapshot_and_original_target(self):
        self.request("one\ntwo")
        self.clipboard.read_text_finish.return_value = "different clipboard"
        self.state["dialog"].response(Gtk.ResponseType.OK)
        self.terminal.paste_text.assert_called_once_with("one\ntwo")
        self.terminal.grab_focus.assert_called_once_with()

    def test_preview_is_editable_with_compact_footer_and_paste_focus(self):
        self.request("one\ntwo")
        dialog = self.state["dialog"]
        content = dialog.get_content_area()
        scroller = content.get_last_child()
        preview = scroller.get_child()
        self.assertTrue(preview.get_editable())
        self.assertTrue(preview.get_cursor_visible())
        self.assertFalse(preview.get_accepts_tab())
        self.assertTrue(scroller.has_css_class("termia-terminal-paste-preview"))
        self.assertEqual(content.get_margin_bottom(), 0)
        cancel = dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
        paste = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        self.assertIs(dialog.get_default_widget(), paste)
        self.assertIs(dialog.get_focus(), paste)
        self.assertEqual(cancel.get_parent().get_margin_top(), 8)
        buffer = preview.get_buffer()
        self.assertEqual(buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True), "one\ntwo")

    def test_confirmation_sends_edited_text_once_without_rewriting_clipboards(self):
        for primary in (False, True):
            for edited in ("updated\ncommand", "updated\rcommand", "updated\r\ncommand",
                           "single line", "  synthetic\tαβ\n", ""):
                with self.subTest(primary=primary, edited=edited):
                    self.terminal.paste_text.reset_mock()
                    self.request("original\ntext", primary=primary)
                    dialog = self.state["dialog"]
                    preview = dialog.get_content_area().get_last_child().get_child()
                    preview.get_buffer().set_text(edited)
                    dialog.response(Gtk.ResponseType.OK)
                    dialog.response(Gtk.ResponseType.OK)
                    if edited:
                        self.terminal.paste_text.assert_called_once_with(edited)
                    else:
                        self.terminal.paste_text.assert_not_called()
                    self.clipboard.set.assert_not_called()
                    self.terminal.get_primary_clipboard.return_value.set.assert_not_called()
                    self.assertFalse(self.state)

    def test_native_editor_enter_inserts_newline_and_tab_reaches_actions(self):
        xdotool = shutil.which("xdotool")
        if xdotool is None:
            self.skipTest("Native keyboard test requires xdotool")
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11

        self.root.present()
        self.request("one\ntwo")
        dialog = self.state["dialog"]
        if not isinstance(dialog.get_display(), GdkX11.X11Display):
            self.skipTest("Native keyboard test requires the private X11 display")

        def wait_until(predicate):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                GLib.MainContext.default().iteration(False)
                if predicate():
                    return
                time.sleep(0.005)
            self.fail("Timed out waiting for paste dialog keyboard interaction")

        wait_until(dialog.get_mapped)
        xid = str(GdkX11.X11Surface.get_xid(dialog.get_surface()))
        subprocess.run([xdotool, "windowfocus", "--sync", xid], check=True)
        preview = dialog.get_content_area().get_last_child().get_child()
        paste = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        wait_until(lambda: dialog.is_active() and preview.get_width() > 0
                   and paste.get_mapped() and paste.get_width() > 0)
        buffer = preview.get_buffer()
        preview.grab_focus()
        buffer.place_cursor(buffer.get_end_iter())
        subprocess.run([xdotool, "key", "Return"], check=True)
        wait_until(lambda: buffer.get_text(*buffer.get_bounds(), True) == "one\ntwo\n")
        self.assertIs(self.state["dialog"], dialog)
        self.terminal.paste_text.assert_not_called()
        subprocess.run([xdotool, "key", "Tab"], check=True)
        wait_until(lambda: not preview.has_focus())
        self.assertIsInstance(dialog.get_focus(), Gtk.Button)
        paste.grab_focus()
        subprocess.run([xdotool, "key", "Return"], check=True)
        wait_until(lambda: not self.state)
        self.terminal.paste_text.assert_called_once_with("one\ntwo\n")

    def test_duplicate_requests_do_not_read_or_create_another_dialog(self):
        self.request("one\ntwo")
        dialog = self.state["dialog"]
        self.host.request_protected_terminal_paste(self.terminal, self.session, self.state)
        self.clipboard.read_text_async.assert_called_once()
        self.assertIs(self.state["dialog"], dialog)

    def test_closed_disconnected_reconnected_or_reparented_target_is_not_used(self):
        for change in ("retired", "disconnected", "process", "root", "input"):
            with self.subTest(change=change):
                self.request("one\ntwo")
                preview = self.state["dialog"].get_content_area().get_last_child().get_child()
                preview.get_buffer().set_text("edited\ntext")
                if change == "retired":
                    self.pane.retired = True
                elif change == "disconnected":
                    self.pane.connected = False
                elif change == "process":
                    self.pane.child_process = object()
                elif change == "root":
                    self.terminal.get_root.return_value = None
                else:
                    self.terminal.get_input_enabled.return_value = False
                self.state["dialog"].response(Gtk.ResponseType.OK)
                self.terminal.paste_text.assert_not_called()
                self.pane.retired = False
                self.pane.connected = True
                self.terminal.get_root.return_value = self.root
                self.terminal.get_input_enabled.return_value = True

    def test_unrealize_cancels_pending_read(self):
        self.host.request_protected_terminal_paste(self.terminal, self.session, self.state)
        cancellable = self.state["cancellable"]
        self.host.on_terminal_paste_unrealize(self.terminal, self.state)
        self.assertTrue(cancellable.is_cancelled())
        self.clipboard.read_text_finish.return_value = "one\ntwo"
        self.clipboard.read_text_async.call_args.args[1](self.clipboard, Mock())
        self.terminal.paste_text.assert_not_called()
        self.assertFalse(self.state)

    def test_clipboard_error_and_empty_text_do_not_paste(self):
        self.host.request_protected_terminal_paste(self.terminal, self.session, self.state)
        self.clipboard.read_text_finish.side_effect = GLib.Error("synthetic clipboard failure")
        self.clipboard.read_text_async.call_args.args[1](self.clipboard, Mock())
        self.host.toast_label.set_error.assert_called_once()
        self.assertFalse(self.state)
        self.clipboard.read_text_finish.side_effect = None
        self.request(None)
        self.terminal.paste_text.assert_not_called()

    def test_disabled_preference_preserves_native_paste_signal(self):
        self.host.store.data.app.confirm_multiline_paste = False
        self.host.on_terminal_paste_requested(self.terminal, self.session, self.state)
        self.terminal.stop_emission_by_name.assert_not_called()
        self.clipboard.read_text_async.assert_not_called()

    def test_enabled_preference_stops_native_paste_before_read(self):
        self.host.on_terminal_paste_requested(self.terminal, self.session, self.state)
        self.terminal.stop_emission_by_name.assert_called_once_with("paste-clipboard")
        self.clipboard.read_text_async.assert_called_once()
        self.terminal.paste_text.assert_not_called()

    def test_middle_button_reads_primary_selection_and_requires_confirmation(self):
        gesture = Mock()
        self.host.on_terminal_primary_paste_requested(gesture, 1, 0, 0, self.session, self.terminal, self.state)
        gesture.set_state.assert_called_once_with(Gtk.EventSequenceState.CLAIMED)
        primary = self.terminal.get_primary_clipboard.return_value
        primary.read_text_finish.return_value = "one\ntwo"
        primary.read_text_async.call_args.args[1](primary, Mock())
        self.clipboard.read_text_async.assert_not_called()
        self.terminal.paste_text.assert_not_called()
        self.state["dialog"].response(Gtk.ResponseType.OK)
        self.terminal.paste_text.assert_called_once_with("one\ntwo")

    def test_native_vte_paste_signal_waits_for_confirmation(self):
        terminal = Vte.Terminal()
        self.root.set_child(terminal)
        self.root.present()
        self.pane = PastePane(terminal)
        self.session.pane_for_terminal.return_value = self.pane
        terminal.connect("paste-clipboard", self.host.on_terminal_paste_requested, self.session, self.state)
        terminal.get_clipboard().set("one\ntwo")
        with patch.object(terminal, "paste_text") as paste:
            terminal.paste_clipboard()
            deadline = time.monotonic() + 2
            while "dialog" not in self.state and time.monotonic() < deadline:
                GLib.MainContext.default().iteration(False)
                time.sleep(0.001)
            self.assertIn("dialog", self.state)
            paste.assert_not_called()
            self.state["dialog"].response(Gtk.ResponseType.OK)
            paste.assert_called_once_with("one\ntwo")
