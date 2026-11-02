# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, GLib, Gtk

from termia.dialog_window import DialogWindow
from termia.i18n import translate_key
from termia.keybinding_preferences import (
    KeybindingCaptureRow,
    KeybindingPreferencesMixin,
)
from termia.keybindings import DEFAULT_KEYBINDINGS, snippet_action
from termia.snippet_dialogs import SnippetDialogs
from termia.snippet_presenter import SnippetPresenter
from termia.stores import ConnectionStore, ReadOnlyStoreError, SettingsStore
from termia.terminal_sessions import TerminalSessionsMixin


class PreferencesHost(KeybindingPreferencesMixin, Gtk.Window):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.toast_label = Mock()

    def t(self, key):
        return translate_key(key, "en")

    def ensure_writable(self):
        return True

    def add_dialog_action_button(self, dialog, label, response, **_kwargs):
        return dialog.add_button(label, response)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "GTK display unavailable")
class SnippetShortcutTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.store = ConnectionStore(root / "connections.json", root / "settings.json",
                                     root / "statistics.json", root / "lock", root / "history")
        self.addCleanup(self.store.close)
        self.parent = Gtk.Window()
        self.addCleanup(self.parent.destroy)
        self.dialogs = SnippetDialogs(
            self.parent, self.store,
            SnippetPresenter(lambda: self.store.data.snippets, lambda: self.store.data.groups,
                             lambda: self.store.data.servers, lambda: self.store.data.snippet_categories),
            lambda key: translate_key(key, "en"), lambda: True, Mock(), Mock(),
        )
        self.addCleanup(self.dialogs.shutdown)
        self.terminal = Mock()
        self.terminal.has_focus.return_value = True
        self.pane = SimpleNamespace(server_id=None, connected=True, pending_reconnect=False)
        self.session = SimpleNamespace(
            detached_window=None, active_terminal_ids={id(self.terminal)}, terminal=self.terminal,
            pane_for_terminal=lambda terminal: self.pane if terminal is self.terminal else None,
        )

    def press(self, key=Gdk.KEY_d, modifiers=Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
        return self.dialogs.on_terminal_shortcut(key, modifiers, self.session, self.terminal)

    @staticmethod
    def settle_activation():
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(0.01)

    def test_capture_clear_and_escape(self):
        row = KeybindingCaptureRow("Ctrl+Alt+D", "Disabled", "Press", "Clear")
        row.on_capture_clicked(Mock())
        self.assertTrue(row.on_key_pressed(Mock(), Gdk.KEY_Escape, 0, Gdk.ModifierType(0)))
        self.assertEqual(row.get_accelerator(), "Ctrl+Alt+D")
        row.on_capture_clicked(Mock())
        row.on_key_pressed(Mock(), Gdk.KEY_e, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertEqual(row.get_accelerator(), "Ctrl+E")
        row.on_clear_clicked(Mock())
        self.assertEqual(row.get_accelerator(), "")

    def test_preferences_lists_snippets_and_restore_defaults_is_cancellable(self):
        snippet = self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        host = PreferencesHost(self.store)
        self.addCleanup(host.destroy)
        host.on_keybindings_settings(None)
        dialog = next(window for window in Gtk.Window.list_toplevels()
                      if isinstance(window, DialogWindow) and window.get_transient_for() is host)
        self.addCleanup(dialog.destroy)
        content = dialog.get_content_area()
        grid = content.get_last_child().get_child()
        if isinstance(grid, Gtk.Viewport):
            grid = grid.get_child()
        labels = []
        rows = []
        child = grid.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label):
                labels.append(child.get_label())
            elif isinstance(child, KeybindingCaptureRow):
                rows.append(child)
            child = child.get_next_sibling()
        self.assertIn("Snippets", labels)
        self.assertIn("Example", labels)
        row = rows[-1]
        self.assertEqual(row.get_accelerator(), "Ctrl+Alt+D")
        dialog.response(Gtk.ResponseType.APPLY)
        self.assertEqual(row.get_accelerator(), "")
        dialog.response(Gtk.ResponseType.CANCEL)
        action = snippet_action(snippet.id)
        self.assertEqual(self.store.data.app.keybindings[action], "Ctrl+Alt+D")
        host.on_keybindings_settings(None)
        dialog = next(window for window in Gtk.Window.list_toplevels()
                      if isinstance(window, DialogWindow) and window.get_transient_for() is host)
        self.addCleanup(dialog.destroy)
        dialog.response(Gtk.ResponseType.APPLY)
        dialog.response(Gtk.ResponseType.OK)
        self.assertEqual(self.store.data.app.keybindings.get(action, ""), "")
        for action, shortcut in DEFAULT_KEYBINDINGS.items():
            self.assertEqual(self.store.data.app.keybindings[action], shortcut)

    def test_editor_preferences_and_persistence_share_one_assignment(self):
        snippet = self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        state = self.dialogs.show_manager()
        self.dialogs.show_editor(state, snippet.id, False)
        self.assertEqual(state.shortcut.get_accelerator(), "Ctrl+Alt+D")
        state.shortcut.set_accelerator("Ctrl+Alt+E")
        self.dialogs.on_editor_save(Mock(), state)
        action = snippet_action(snippet.id)
        self.assertEqual(self.store.data.app.keybindings[action], "Ctrl+Alt+E")
        previous = self.store.data.app.keybindings.copy()
        row = KeybindingCaptureRow("Ctrl+Alt+F", "Disabled", "Press", "Clear")
        host = SimpleNamespace(store=self.store, toast_label=Mock(), t=lambda key: translate_key(key, "en"),
                               duplicate_keybinding=lambda values: "")
        dialog = Mock()
        KeybindingPreferencesMixin.on_keybindings_settings_response(
            host, dialog, Gtk.ResponseType.OK, [(action, row)], previous,
        )
        self.dialogs.show_editor(state, snippet.id, False)
        self.assertEqual(state.shortcut.get_accelerator(), "Ctrl+Alt+F")
        self.assertEqual(SettingsStore(self.store.settings_store.path).app.keybindings[action], "Ctrl+Alt+F")
        self.dialogs.show_editor(state, snippet.id, True)
        self.assertEqual(state.shortcut.get_accelerator(), "")

    def test_conflicts_and_read_only_do_not_change_snippet_or_shortcut(self):
        snippet = self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        state = self.dialogs.show_manager()
        self.dialogs.show_editor(state, snippet.id, False)
        state.name.set_text("Changed")
        state.shortcut.set_accelerator("Ctrl+Shift+C")
        self.dialogs.on_editor_save(Mock(), state)
        self.assertTrue(state.editor_error.get_visible())
        self.assertEqual(state.stack.get_visible_child_name(), "editor")
        self.assertEqual(self.store.data.snippets[0].name, "Example")
        self.assertEqual(self.store.data.app.keybindings[snippet_action(snippet.id)], "Ctrl+Alt+D")
        self.store.read_only = True
        with self.assertRaises(ReadOnlyStoreError):
            self.store.update_keybindings({snippet_action(snippet.id): "Ctrl+Alt+E"})
        self.dialogs.on_editor_save(Mock(), state)
        self.dialogs.show_error.assert_called()
        self.store.read_only = False

    def test_stale_form_preserves_newer_assignment_when_unchanged(self):
        snippet = self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        state = self.dialogs.show_manager()
        self.dialogs.show_editor(state, snippet.id, False)
        self.store.update_keybindings({snippet_action(snippet.id): "Ctrl+Alt+E"})
        state.name.set_text("Renamed")
        self.dialogs.on_editor_save(Mock(), state)
        self.assertEqual(self.store.data.app.keybindings[snippet_action(snippet.id)], "Ctrl+Alt+E")
        self.dialogs.show_editor(state, snippet.id, False)
        self.store.update_keybindings({snippet_action(snippet.id): "Ctrl+Alt+F"})
        state.shortcut.set_accelerator("Ctrl+Alt+G")
        self.dialogs.on_editor_save(Mock(), state)
        self.assertTrue(state.editor_error.get_visible())
        self.assertEqual(self.store.data.app.keybindings[snippet_action(snippet.id)], "Ctrl+Alt+F")

    def test_shortcut_opens_preview_without_sending_and_cancel_is_safe(self):
        self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        self.assertTrue(self.press())
        state = self.dialogs.picker_state
        self.assertEqual(state.stack.get_visible_child_name(), "preview")
        self.terminal.feed_child.assert_not_called()
        self.dialogs.hide_picker(state)
        self.terminal.feed_child.assert_not_called()
        self.assertTrue(self.press())
        self.assertIs(self.dialogs.picker_state, state)
        self.dialogs.on_preview_send(Mock(), state)
        self.terminal.feed_child.assert_called_once_with(b"true\n")

    def test_variables_are_quoted_and_detached_split_is_the_owner(self):
        self.store.add_snippet("Example", "printf %s {{value}}", shortcut="Ctrl+Alt+D")
        detached = Gtk.Window()
        self.addCleanup(detached.destroy)
        self.session.detached_window = detached
        self.session.terminal = Mock()  # The focused terminal is a different split pane.
        self.assertTrue(self.press())
        state = self.dialogs.picker_state
        self.assertIs(state.window.get_transient_for(), detached)
        self.assertEqual(state.stack.get_visible_child_name(), "variables")
        state.variable_entries["value"].set_text("a b; echo example")
        self.dialogs.on_variables_preview(Mock(), state)
        self.terminal.feed_child.assert_not_called()
        self.dialogs.on_preview_send(Mock(), state)
        self.terminal.feed_child.assert_called_once_with(b"printf %s 'a b; echo example'\n")

    def test_enter_advances_variables_then_sends_preview_only_once(self):
        self.store.add_snippet("Example", "printf %s {{value}}", shortcut="Ctrl+Alt+D")
        self.assertTrue(self.press())
        self.settle_activation()
        state = self.dialogs.picker_state
        entry = state.variable_entries["value"]
        entry.set_text("synthetic value")
        entry.emit("activate")
        self.settle_activation()
        self.assertEqual(state.stack.get_visible_child_name(), "preview")
        self.terminal.feed_child.assert_not_called()
        self.assertIs(state.window.get_focus(), state.window.get_default_widget())
        state.window.emit("activate-default")
        self.settle_activation()
        self.terminal.feed_child.assert_called_once_with(b"printf %s 'synthetic value'\n")
        self.assertIsNone(state.window.get_default_widget())
        state.window.emit("activate-default")
        self.terminal.feed_child.assert_called_once()

    def test_search_enter_requires_selection_and_reopening_restores_default(self):
        self.store.add_snippet("Example", "true")
        state = self.dialogs.prepare_picker(self.session, self.terminal)
        state.window.present()
        state.search.emit("activate")
        self.assertEqual(state.stack.get_visible_child_name(), "picker")
        self.terminal.feed_child.assert_not_called()
        state.listing.select_row(state.listing.get_row_at_index(0))
        state.search.emit("activate")
        self.settle_activation()
        self.assertEqual(state.stack.get_visible_child_name(), "preview")
        self.terminal.feed_child.assert_not_called()
        self.dialogs.hide_picker(state)
        self.assertIsNone(state.window.get_default_widget())
        self.assertIs(self.dialogs.prepare_picker(self.session, self.terminal), state)
        self.assertIs(state.window.get_default_widget(), state.preview_button)

    def test_scope_connected_focus_locked_and_deleted_guards(self):
        group = self.store.add_group("Example")
        server = self.store.add_server("Example", "example.invalid", "example", 22, group.id)
        snippet = self.store.add_snippet("Scoped", "true", scope="group", target_id=group.id, shortcut="Ctrl+Alt+D")
        self.assertFalse(self.press())  # Local terminal is outside the group.
        self.pane.server_id = server.id
        self.assertTrue(self.press())
        state = self.dialogs.picker_state
        for guard in ("focus", "connected", "locked", "removed"):
            self.terminal.has_focus.return_value = guard != "focus"
            self.pane.connected = guard != "connected"
            self.store.encryption_locked = guard == "locked"
            self.session.active_terminal_ids = set() if guard == "removed" else {id(self.terminal)}
            self.assertFalse(self.press())
        self.terminal.has_focus.return_value = True
        self.pane.connected = True
        self.store.encryption_locked = False
        self.session.active_terminal_ids = {id(self.terminal)}
        self.store.delete_snippet(snippet.id)
        self.dialogs.on_preview_send(Mock(), state)
        self.terminal.feed_child.assert_not_called()
        self.assertFalse(self.press())

    def test_changed_connection_cannot_receive_an_old_preview(self):
        self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        server = self.store.add_server("Example", "example.invalid", "example", 22, None)
        self.assertTrue(self.press())
        state = self.dialogs.picker_state
        self.pane.server_id = server.id
        self.dialogs.on_preview_send(Mock(), state)
        self.terminal.feed_child.assert_not_called()
        self.assertTrue(self.press())
        self.store.delete_server(server.id)
        self.dialogs.on_preview_send(Mock(), state)
        self.terminal.feed_child.assert_not_called()

    def test_nested_group_scope_and_deleted_target_assignment(self):
        parent = self.store.add_group("Parent")
        child = self.store.add_group("Child", parent.id)
        server = self.store.add_server("Example", "example.invalid", "example", 22, child.id)
        snippet = self.store.add_snippet("Scoped", "true", scope="group", target_id=parent.id,
                                         shortcut="Ctrl+Alt+D")
        self.pane.server_id = server.id
        self.assertTrue(self.press())
        state = self.dialogs.picker_state
        self.store.delete_group(parent.id)
        self.assertNotIn(snippet_action(snippet.id), self.store.data.app.keybindings)
        self.dialogs.on_preview_send(Mock(), state)
        self.terminal.feed_child.assert_not_called()

    def test_dispatch_preserves_builtin_shortcuts_and_function_keys(self):
        host = SimpleNamespace(
            pane_state=lambda session, terminal: self.pane, store=self.store,
            terminal_shortcut_handler=self.dialogs.on_terminal_shortcut,
        )
        self.store.add_snippet("Example", "true", shortcut="Ctrl+Alt+D")
        dispatch = lambda key, mods: TerminalSessionsMixin.on_terminal_key_pressed(
            host, Mock(), key, 0, mods, self.session, self.terminal,
        )
        self.assertTrue(dispatch(Gdk.KEY_c, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK))
        self.terminal.copy_clipboard_format.assert_called_once()
        self.assertFalse(dispatch(Gdk.KEY_F8, Gdk.ModifierType(0)))
        self.assertFalse(dispatch(Gdk.KEY_x, Gdk.ModifierType(0)))
        self.assertTrue(dispatch(Gdk.KEY_d, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK))
        self.terminal.feed_child.assert_not_called()
