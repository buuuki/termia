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
from termia.snippet_dialogs import PickerState, SnippetDialogs
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

    def test_manager_rebuilds_repeatedly_without_gc_lifecycle_callbacks(self):
        try:
            parent = Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))
        data = SimpleNamespace(snippets=[], groups=[], servers=[])
        store = SimpleNamespace(data=data)
        presenter = SnippetPresenter(lambda: data.snippets, lambda: [], lambda: [])
        dialogs = SnippetDialogs(
            parent,
            store,
            presenter,
            lambda key: translate_key(key, "en"),
            lambda: True,
            Mock(),
            Mock(),
        )
        self.addCleanup(parent.destroy)

        state = dialogs.show_manager()
        self.assertIsNotNone(state)
        self.addCleanup(state.dialog.destroy)
        for index in range(20):
            data.snippets.append(CommandSnippet(str(index), f"Snippet {index}", "true"))
            dialogs.refresh_manager(state, str(index))
            gc.collect()

        self.assertEqual(len(state.visible_ids), 20)
        self.assertEqual(state.selected_id, "19")

    def test_manager_state_survives_native_list_teardown(self):
        try:
            parent = Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))
        data = SimpleNamespace(
            snippets=[CommandSnippet("one", "Disk usage", "df -h")],
            groups=[],
            servers=[],
        )
        dialogs = SnippetDialogs(
            parent,
            SimpleNamespace(data=data),
            SnippetPresenter(lambda: data.snippets, lambda: [], lambda: []),
            lambda key: translate_key(key, "en"),
            lambda: True,
            Mock(),
            Mock(),
        )
        self.addCleanup(parent.destroy)

        for _index in range(20):
            state = dialogs.show_manager()
            self.assertIsNotNone(state)
            dialogs.refresh_manager(state, "one")
            dialogs.destroy_dialog(state.dialog)
            gc.collect()
            self.drain_main_context()

        self.assertEqual(dialogs._active_dialog_states, {})

    def test_picker_single_selection_survives_filter_rebuild(self):
        try:
            parent = Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))
        data = SimpleNamespace(
            snippets=[
                CommandSnippet("one", "Disk usage", "df -h", "System"),
                CommandSnippet("two", "Processes", "ps aux", "System"),
            ],
            groups=[],
            servers=[],
        )
        presenter = SnippetPresenter(lambda: data.snippets, lambda: [], lambda: [])
        dialogs = SnippetDialogs(
            parent,
            SimpleNamespace(data=data),
            presenter,
            lambda key: translate_key(key, "en"),
            lambda: True,
            Mock(),
            Mock(),
        )
        dialog = Gtk.Dialog(transient_for=parent)
        search = Gtk.SearchEntry()
        listing = Gtk.ListBox()
        preview = Gtk.Button()
        state = PickerState(
            dialog,
            parent,
            SimpleNamespace(),
            Mock(),
            None,
            search,
            listing,
            preview,
            [],
        )
        state.selection_handler_id = listing.connect("row-selected", dialogs.on_picker_selected, state)
        self.addCleanup(dialog.destroy)
        self.addCleanup(parent.destroy)

        dialogs.refresh_picker(state)
        listing.select_row(listing.get_row_at_index(0))
        self.assertEqual(state.selected_id, "one")
        self.assertTrue(preview.get_sensitive())

        search.set_text("process")
        dialogs.refresh_picker(state)
        listing.select_row(listing.get_row_at_index(0))
        gc.collect()

        self.assertEqual(state.selected_id, "two")
        self.assertTrue(preview.get_sensitive())

    def test_run_flow_disconnects_dialogs_before_window_resize(self):
        try:
            parent = Gtk.Window()
        except RuntimeError as error:
            self.skipTest(str(error))
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
        dialogs = SnippetDialogs(
            parent,
            SimpleNamespace(data=data),
            SnippetPresenter(lambda: data.snippets, lambda: [], lambda: []),
            lambda key: translate_key(key, "en"),
            lambda: True,
            Mock(),
            notice,
        )
        self.addCleanup(parent.destroy)

        for index in range(20):
            picker = dialogs.show_picker(Gtk.Popover(), session, terminal)
            self.assertIsNotNone(picker)
            picker.listing.select_row(picker.listing.get_row_at_index(0))
            picker.dialog.response(Gtk.ResponseType.OK)
            preview = next(
                lifetime.dialog
                for lifetime in dialogs._active_dialog_states.values()
                if lifetime.dialog.get_title() == translate_key("snippet_preview", "en")
                and not lifetime.closing
            )
            preview.response(Gtk.ResponseType.OK)
            parent.set_default_size(640 + index, 480 + index)
            gc.collect()
            self.drain_main_context()

        self.assertEqual(dialogs._active_dialog_states, {})
        self.assertEqual(terminal.feed_child.call_count, 20)
        self.assertEqual(notice.call_count, 20)
