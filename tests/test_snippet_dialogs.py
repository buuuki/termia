# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import gc
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from termia.i18n import translate_key
from termia.models import CommandSnippet
from termia.snippet_dialogs import SnippetDialogs
from termia.snippet_presenter import SnippetPresenter


@unittest.skipUnless(
    os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"),
    "GTK display unavailable",
)
class SnippetDialogTests(unittest.TestCase):
    @staticmethod
    def drain_main_context():
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)

    def make_dialogs(self, parent, data, *, store=None, notice=None):
        return SnippetDialogs(
            parent,
            store or SimpleNamespace(data=data),
            SnippetPresenter(lambda: data.snippets, lambda: data.groups, lambda: data.servers),
            lambda key: translate_key(key, "en"),
            lambda: True,
            Mock(),
            notice or Mock(),
        )

    def make_parent(self):
        try:
            return Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))

    def test_manager_rebuilds_repeatedly_without_selection_callbacks(self):
        parent = self.make_parent()
        data = SimpleNamespace(snippets=[], groups=[], servers=[])
        dialogs = self.make_dialogs(parent, data)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        self.assertIsNotNone(state)
        for index in range(20):
            data.snippets.append(CommandSnippet(str(index), f"Snippet {index}", "true"))
            dialogs.refresh_manager(state, str(index))
            gc.collect()

        self.assertEqual(len(state.visible_ids), 20)
        self.assertEqual(state.selected_id, "19")

    def test_manager_reuses_one_window_during_repeated_editor_cancellation(self):
        parent = self.make_parent()
        data = SimpleNamespace(
            snippets=[CommandSnippet("one", "Disk usage", "df -h")],
            groups=[],
            servers=[],
        )
        dialogs = self.make_dialogs(parent, data)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        manager_window = state.window
        for index in range(10):
            dialogs.show_editor(state, None, False)
            self.assertEqual(state.stack.get_visible_child_name(), "editor")
            dialogs.on_editor_cancel(Mock(), state)
            self.assertEqual(state.stack.get_visible_child_name(), "manager")
            dialogs.hide_manager(state)
            reopened = dialogs.show_manager()
            self.assertIs(reopened.window, manager_window)
            parent.set_default_size(640 + index, 480 + index)

        gc.collect()
        self.drain_main_context()

        self.assertIs(dialogs.manager_state.window, manager_window)

    def test_picker_single_selection_survives_filter_rebuild(self):
        parent = self.make_parent()
        data = SimpleNamespace(
            snippets=[
                CommandSnippet("one", "Disk usage", "df -h", "System"),
                CommandSnippet("two", "Processes", "ps aux", "System"),
            ],
            groups=[],
            servers=[],
        )
        dialogs = self.make_dialogs(parent, data)
        terminal = Mock()
        pane = SimpleNamespace(server_id=None, connected=True)
        session = SimpleNamespace(
            detached_window=None,
            active_terminal_ids={id(terminal)},
            pane_for_terminal=lambda candidate: pane if candidate is terminal else None,
        )
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_picker(Gtk.Popover(), session, terminal)
        state.listing.select_row(state.listing.get_row_at_index(0))
        self.assertEqual(state.selected_id, "one")
        self.assertTrue(state.preview_button.get_sensitive())

        state.search.set_text("process")
        dialogs.refresh_picker(state)
        state.listing.select_row(state.listing.get_row_at_index(0))
        gc.collect()

        self.assertEqual(state.selected_id, "two")
        self.assertTrue(state.preview_button.get_sensitive())

    def test_run_flow_reuses_one_window_during_send_and_resize(self):
        parent = self.make_parent()
        data = SimpleNamespace(
            snippets=[CommandSnippet("one", "Disk usage", "df -h")],
            groups=[],
            servers=[],
        )
        terminal = Mock()
        pane = SimpleNamespace(server_id=None, connected=True)
        session = SimpleNamespace(
            detached_window=None,
            active_terminal_ids={id(terminal)},
            pane_for_terminal=lambda candidate: pane if candidate is terminal else None,
        )
        notice = Mock()
        dialogs = self.make_dialogs(parent, data, notice=notice)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        runner_window = None
        for index in range(10):
            state = dialogs.show_picker(Gtk.Popover(), session, terminal)
            if runner_window is None:
                runner_window = state.window
            self.assertIs(state.window, runner_window)
            state.listing.select_row(state.listing.get_row_at_index(0))
            dialogs.on_picker_preview(Mock(), state)
            self.assertEqual(state.stack.get_visible_child_name(), "preview")
            dialogs.on_preview_send(Mock(), state)
            self.assertFalse(state.window.get_visible())
            parent.set_default_size(640 + index, 480 + index)

        gc.collect()
        self.drain_main_context()

        self.assertIs(dialogs.picker_state.window, runner_window)
        self.assertEqual(terminal.feed_child.call_count, 10)
        self.assertEqual(notice.call_count, 10)

    def test_variable_page_can_be_cancelled_without_destroying_runner(self):
        parent = self.make_parent()
        data = SimpleNamespace(
            snippets=[CommandSnippet("one", "Restart", "systemctl restart {{service}}")],
            groups=[],
            servers=[],
        )
        terminal = Mock()
        pane = SimpleNamespace(server_id=None, connected=True)
        session = SimpleNamespace(
            detached_window=None,
            active_terminal_ids={id(terminal)},
            pane_for_terminal=lambda candidate: pane if candidate is terminal else None,
        )
        dialogs = self.make_dialogs(parent, data)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_picker(Gtk.Popover(), session, terminal)
        runner_window = state.window
        state.listing.select_row(state.listing.get_row_at_index(0))
        dialogs.on_picker_preview(Mock(), state)
        self.assertEqual(state.stack.get_visible_child_name(), "variables")

        dialogs.on_picker_cancel(Mock(), state)
        self.assertFalse(runner_window.get_visible())
        reopened = dialogs.show_picker(Gtk.Popover(), session, terminal)
        self.assertIs(reopened.window, runner_window)
        self.assertEqual(reopened.stack.get_visible_child_name(), "picker")
