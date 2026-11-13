# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from gi.repository import GLib

from termia.app import TermiaApp, TermiaWindow
from termia.i18n import translate_key
from termia.stores import ConnectionStore


class StartupSidebarTests(unittest.TestCase):
    @contextmanager
    def window(self, startup_visible=True, theme="dark"):
        app = TermiaApp()
        app.set_application_id(f"local.termia.SidebarTests.t{uuid4().hex}")
        self.assertTrue(app.register(None))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConnectionStore(root / "connections.json", root / "settings.json",
                                    root / "statistics.json", root / "lock", root / "history")
            store.data.app.open_local_terminal_on_startup = False
            store.data.app.restore_sessions_on_startup = False
            store.data.app.show_sidebar_on_startup = startup_visible
            store.data.app.theme = theme
            with (patch("termia.app.ConnectionStore", return_value=store),
                  patch("termia.app.RETRON_PROFILE_FILE", root / "retron.json"),
                  patch("termia.app.SESSION_SNAPSHOT_FILE", root / "session.json")):
                window = TermiaWindow(app)
            try:
                yield window
            finally:
                window.shutdown_in_progress = True
                window.prepare_terminal_sessions_for_shutdown()
                window.snippet_dialogs.shutdown()
                window.notes_dialogs.shutdown()
                window.retron_runtime.close()
                window.destroy()
                store.close()
                app._window_theme_scope.close()
                app.quit()

    def test_connections_start_hidden_before_mapping_and_can_be_revealed(self):
        for legacy_value in (False, True):
            with self.subTest(legacy_value=legacy_value), self.window(legacy_value) as window:
                self.assertFalse(window.get_mapped())
                self.assertFalse(window.sidebar_visible)
                self.assertFalse(window.sidebar.get_visible())
                self.assertEqual(window.toggle_sidebar_button.get_icon_name(), "sidebar-show-symbolic")
                window.on_toggle_sidebar(None)
                self.assertTrue(window.sidebar_visible)
                self.assertTrue(window.sidebar.get_visible())
                window.on_toggle_sidebar(None)
                window.on_toggle_sidebar(None)
                self.assertEqual(window.body.get_position(), 280)
                self.assertEqual(window.store.data.app.show_sidebar_on_startup, legacy_value)

    def test_mapped_sidebar_bounds_controls_and_preferred_width(self):
        def wait_for(predicate):
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                while GLib.MainContext.default().pending():
                    GLib.MainContext.default().iteration(False)
                if predicate():
                    return
                time.sleep(0.01)
            self.fail("Sidebar layout did not settle")

        for theme in ("system", "light", "dark", "dark_glow"):
            with self.subTest(theme=theme), self.window(theme=theme) as window:
                window.set_default_size(1200, 700)
                window.present()
                window.on_toggle_sidebar(None)
                wait_for(lambda: window.body.get_width() >= 1100
                         and window.body.get_property("max-position") > 0)
                self.assertTrue(window.body.get_shrink_start_child())
                self.assertTrue(window.body.get_shrink_end_child())
                self.assertEqual(window.body.get_property("min-position"), 0)
                preferred = window.body.get_property("max-position") - 20
                self.assertGreater(preferred, window.body.get_width() // 4)
                window.body.set_position(preferred)
                wait_for(lambda preferred=preferred: window.sidebar_width == preferred)
                window.on_toggle_sidebar(None)
                self.assertEqual(window.store.settings_store.app.connection_sidebar_width, preferred)
                window.on_toggle_sidebar(None)
                wait_for(lambda preferred=preferred: window.body.get_position() == preferred)
                window.set_default_size(900, 700)
                wait_for(lambda preferred=preferred: window.body.get_width() < 1000
                         and window.body.get_position() < preferred)
                self.assertEqual(window.sidebar_width, preferred)
                window.set_default_size(1200, 700)
                wait_for(lambda preferred=preferred: window.body.get_position() == preferred)
                for language in ("en", "es", "ca"):
                    window.store.data.app.language = language
                    window.refresh_translated_chrome()
                    window.body.set_position(0)
                    wait_for(lambda: window.body.get_position()
                             == window.body.get_property("min-position"))
                    wait_for(lambda: window.sidebar_width == 0)
                    window.body.set_position(preferred)
                    wait_for(lambda preferred=preferred: window.body.get_position() == preferred)
                    for button in (window.add_group_button, window.add_server_button,
                                   window.add_local_terminal_button, window.save_workspace_button,
                                   window.expand_all_button, window.collapse_all_button):
                        self.assertGreater(button.get_width(), 0)
                        # measure() includes the CSS box and widget margins;
                        # get_width() reports only the content area.
                        style = button.get_style_context()
                        horizontal_insets = sum(
                            box.left + box.right
                            for box in (style.get_padding(), style.get_border(), style.get_margin())
                        )
                        allocated_width = (
                            button.get_width() + horizontal_insets
                            + button.get_margin_start() + button.get_margin_end()
                        )
                        self.assertGreaterEqual(allocated_width, button.measure(0, -1)[0])
                    window.body.set_position(100000)
                    wait_for(lambda: window.body.get_position()
                             == window.body.get_property("max-position"))

    def test_notes_tool_labels_availability_and_window_reuse_across_themes(self):
        for theme in ("system", "light", "dark", "dark_glow"):
            with self.subTest(theme=theme), self.window(theme=theme) as window:
                for language in ("en", "es", "ca"):
                    window.store.data.app.language = language
                    window.refresh_translated_chrome()
                    button = window.tool_launcher.buttons["notes"]
                    self.assertEqual(button.get_tooltip_text(), translate_key("notes_title", language))
                notes = window.notes_dialogs
                window.tool_registry.activate("notes")
                self.assertTrue(notes.notes_list_paned.get_shrink_start_child())
                self.assertTrue(notes.notes_list_paned.get_shrink_end_child())
                original_window = notes.window
                original_tabs = tuple(notes.editor_tabs)
                self.assertFalse(notes.notes_list_visible)
                self.assertIsNone(notes.notes_list_paned.get_start_child())
                notes.toggle_notes_list()
                notes.notes_list_paned.set_position(340)
                window.tool_registry.activate("notes")
                self.assertIs(notes.window, original_window)
                self.assertEqual(tuple(notes.editor_tabs), original_tabs)
                self.assertFalse(notes.notes_list_visible)
                notes.toggle_notes_list()
                self.assertEqual(notes.notes_list_paned.get_position(), 340)
                notes.on_notes_window_active(notes.window)
                self.assertTrue(notes.notes_list_visible)
                window.store.encryption_locked = True
                window.tool_launcher.refresh()
                self.assertNotIn("notes", window.tool_launcher.buttons)
                window.store.encryption_locked = False
                window.shutdown_in_progress = True
                window.tool_launcher.refresh()
                self.assertNotIn("notes", window.tool_launcher.buttons)

    def test_notes_hide_before_present_in_read_only_and_failed_save_paths(self):
        with self.window() as window:
            notes = window.notes_dialogs
            notes.ensure_window()
            window.store.read_only = True
            for allowed in (True, False):
                with self.subTest(scope_change_allowed=allowed):
                    if not notes.notes_list_visible:
                        notes.toggle_notes_list()
                    with (patch.object(notes, "set_notes_scope", return_value=allowed),
                          patch.object(notes.window, "present") as present):
                        present.side_effect = lambda: self.assertFalse(notes.notes_list_visible)
                        notes.show_manager()
                        present.assert_called_once_with()
                    self.assertIsNone(notes.notes_list_paned.get_start_child())
