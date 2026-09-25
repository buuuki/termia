# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import gc
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from termia.i18n import translate_key
from termia.models import CommandSnippet
from termia.snippet_dialogs import SnippetDialogs
from termia.snippet_presenter import SnippetPresenter
from termia.stores import ConnectionStore


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
            SnippetPresenter(
                lambda: data.snippets, lambda: data.groups, lambda: data.servers,
                lambda: getattr(data, "snippet_categories", []),
            ),
            lambda key: translate_key(key, "en"),
            lambda: True,
            Mock(),
            notice or Mock(),
        )

    @staticmethod
    def make_snippet_store(data):
        store = Mock()

        def add_snippet(name, content, category, scope, target_id):
            snippet = CommandSnippet(str(len(data.snippets) + 1), name, content, category, scope, target_id)
            data.snippets.append(snippet)
            return snippet

        store.add_snippet.side_effect = add_snippet
        return store

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
        self.assertEqual(state.listing.get_row_at_index(0).get_child().get_label(), "No matching snippets.")
        self.assertEqual(state.listing.get_row_at_index(1).get_child().get_label(),
                         "Select a snippet to preview its command.")
        for index in range(20):
            data.snippets.append(CommandSnippet(str(index), f"Snippet {index}", "true"))
            dialogs.refresh_manager(state, str(index))
            gc.collect()

        self.assertEqual(len(state.visible_ids), 20)
        self.assertEqual(state.selected_id, "19")

    def test_manager_categories_and_global_search(self):
        parent = self.make_parent()
        data = SimpleNamespace(
            snippets=[
                CommandSnippet("one", "Deploy", "release", "Release"),
                CommandSnippet("two", "Restart", "restart service", "Operations"),
                CommandSnippet("three", "Status", "status"),
            ],
            groups=[],
            servers=[],
        )
        dialogs = self.make_dialogs(parent, data)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        self.assertIsNotNone(state)
        self.assertEqual(state.window.get_title(), "Manage snippets")
        self.assertFalse(state.stack.get_hhomogeneous())
        self.assertIs(state.search.get_next_sibling(), state.category_scroller.get_parent().get_parent())
        self.assertEqual(state.category_scroller.get_parent().get_first_child().get_label(), "Manage categories")
        self.assertEqual(state.list_scroller.get_parent().get_first_child().get_label(), "Create snippet")
        self.assertEqual(state.preview_title.get_parent().get_first_child().get_label(), "Command preview")
        first_category = state.category_grid.get_child_at_index(0).get_child()
        first_label = first_category.get_child().get_first_child().get_next_sibling()
        self.assertEqual(first_label.get_label(), "All categories")
        self.assertIn("3 snippets", first_category.get_tooltip_text())
        self.assertTrue(state.category_scroller.get_visible())
        self.assertTrue(state.list_scroller.get_visible())
        self.assertEqual(state.visible_ids, ["three", "two", "one"])
        self.assertFalse(state.preview_title.get_visible())
        self.assertEqual(state.selection_hint.get_child().get_label(), "Select a snippet to preview its command.")
        self.assertTrue(state.selection_hint.get_visible())
        self.assertFalse(any(button.get_sensitive() for button in state.actions))
        self.assertFalse(state.preview_view.get_editable())

        state.listing.select_row(state.listing.get_row_at_index(1))
        self.assertEqual(state.selected_id, "two")
        self.assertEqual(state.preview_title.get_label(), "Restart")
        self.assertTrue(state.preview_title.get_visible())
        self.assertFalse(state.selection_hint.get_visible())
        self.assertIn("Operations", state.preview_meta.get_label())
        self.assertEqual(state.preview_view.get_buffer().get_text(
            state.preview_view.get_buffer().get_start_iter(),
            state.preview_view.get_buffer().get_end_iter(), False,
        ), "restart service")
        self.assertTrue(all(button.get_sensitive() for button in state.actions))

        state.category_grid.get_child_at_index(2).get_child().emit("clicked")
        self.assertEqual(state.visible_ids, ["one"])
        self.assertEqual(state.listing.get_row_at_index(0).get_child().get_label(), "Deploy")
        self.assertFalse(state.preview_title.get_visible())
        self.assertTrue(state.selection_hint.get_visible())

        state.search.set_text("service")
        dialogs.on_manager_search(state.search, state)
        self.assertEqual(state.visible_ids, ["two"])
        self.assertIsNone(state.category_filter)
        self.assertTrue(state.list_scroller.get_visible())
        self.assertTrue(state.category_scroller.get_visible())
        self.assertEqual(
            state.listing.get_row_at_index(0).get_child().get_label(),
            "Operations · Restart",
        )

        state.search.set_text("")
        state.category_grid.get_child_at_index(3).get_child().emit("clicked")
        self.assertEqual(state.visible_ids, ["three"])
        self.assertEqual(state.listing.get_row_at_index(0).get_child().get_label(), "Status")
        state.category_grid.get_child_at_index(0).get_child().emit("clicked")
        self.assertEqual(state.visible_ids, ["three", "two", "one"])

    def test_category_rows_keep_the_same_size(self):
        parent = self.make_parent()
        data = SimpleNamespace(snippets=[], groups=[], servers=[])
        dialogs = self.make_dialogs(parent, data)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        sizes = []
        for count in (1, 4, 5, 6):
            data.snippets = [
                CommandSnippet(
                    str(index), f"Snippet {index}", "true",
                    "Very long category name that should not resize its tile"
                    if count == 6 and index == 5 else f"Category {index}",
                )
                for index in range(count)
            ]
            dialogs.refresh_manager(state)
            buttons = [
                state.category_grid.get_child_at_index(index).get_child()
                for index in range(count + 1)
            ]
            sizes.extend(button.get_size_request() for button in buttons)

        self.assertTrue(all(height == 42 for _width, height in sizes), sizes)
        self.assertEqual(len(set(sizes)), 1)
        self.assertIn("Very long category name", buttons[-1].get_tooltip_text())

    def test_manage_categories_create_rename_duplicate_and_delete(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        store = ConnectionStore(
            root / "connections.json", root / "settings.json", root / "statistics.json",
            root / "lock", root / "history",
        )
        self.addCleanup(store.close)
        store.add_snippet_category("Work")
        original = store.add_snippet("Deploy", "true", "Work")
        parent = self.make_parent()
        dialogs = self.make_dialogs(parent, store.data, store=store)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        dialogs.on_category_manage(Mock(), state)
        self.assertEqual(state.stack.get_visible_child_name(), "categories")
        dialogs.on_category_manage_add(Mock(), state)
        state.category_name_entry.set_text("Empty")
        dialogs.on_category_name_save(Mock(), state)
        self.assertIn("Empty", store.data.snippet_categories)
        self.assertIn("Empty", state.category_manage_keys)

        state.category_manage_list.select_row(
            state.category_manage_list.get_row_at_index(state.category_manage_keys.index("Work"))
        )
        dialogs.on_category_manage_rename(Mock(), state)
        state.category_name_entry.set_text("Operations")
        dialogs.on_category_name_save(Mock(), state)
        self.assertEqual(store.data.snippets[0].category, "Operations")

        dialogs.on_category_manage_duplicate(Mock(), state)
        state.category_name_entry.set_text("Operations copy")
        dialogs.on_category_name_save(Mock(), state)
        self.assertEqual(len(store.data.snippets), 2)
        self.assertNotEqual(store.data.snippets[1].id, original.id)

        state.category_manage_list.select_row(
            state.category_manage_list.get_row_at_index(state.category_manage_keys.index("Operations"))
        )
        dialogs.on_category_manage_delete(Mock(), state)
        self.assertEqual(state.stack.get_visible_child_name(), "category_delete")
        self.assertIn("Uncategorized", state.category_delete_detail.get_label())
        dialogs.on_category_delete_cancel(Mock(), state)
        self.assertIn("Operations", store.data.snippet_categories)
        dialogs.on_category_manage_delete(Mock(), state)
        dialogs.on_category_delete_confirm(Mock(), state)
        self.assertEqual(store.data.snippets[0].category, "")
        self.assertNotIn("Operations", state.category_manage_keys)
        dialogs.on_category_manage_back(Mock(), state)
        self.assertEqual(state.stack.get_visible_child_name(), "manager")
        self.assertIn("Empty", [item.key for item in dialogs.presenter.categories()])

    def test_category_management_navigation_has_no_repeated_heading(self):
        parent = self.make_parent()
        data = SimpleNamespace(snippets=[], groups=[], servers=[])
        dialogs = self.make_dialogs(parent, data)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        dialogs.on_category_manage(Mock(), state)
        category_page = state.stack.get_visible_child()
        header = category_page.get_first_child()
        back = header.get_first_child()
        self.assertEqual(back.get_label(), "All categories")
        self.assertIsNone(back.get_next_sibling())

        actions = category_page.get_last_child()
        cancel = actions.get_last_child()
        self.assertEqual(cancel.get_label(), "Cancel")
        self.assertEqual(cancel.get_prev_sibling().get_label(), "Delete category")

        dialogs.on_category_manage_add(Mock(), state)
        state.category_name_entry.set_text("Unsaved")
        cancel.emit("clicked")
        self.assertEqual(state.stack.get_visible_child_name(), "manager")
        self.assertIsNone(state.category_edit_mode)

        dialogs.on_category_manage(Mock(), state)
        back.emit("clicked")
        self.assertEqual(state.stack.get_visible_child_name(), "manager")

    def test_editor_created_category_persists_without_saving_a_snippet(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        store = ConnectionStore(
            root / "connections.json", root / "settings.json", root / "statistics.json",
            root / "lock", root / "history",
        )
        self.addCleanup(store.close)
        parent = self.make_parent()
        dialogs = self.make_dialogs(parent, store.data, store=store)
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        dialogs.show_editor(state, None, False)
        dialogs.on_new_category(Mock(), state)
        state.new_category_entry.set_text("Empty")
        dialogs.on_new_category_confirm(Mock(), state)
        dialogs.on_editor_cancel(Mock(), state)

        self.assertEqual(store.data.snippet_categories, ["Empty"])
        self.assertEqual(state.category_grid.get_child_at_index(1).get_child().get_tooltip_text(), "Empty: 0 snippets")

    def test_editor_creates_first_category_and_persists_the_snippet(self):
        parent = self.make_parent()
        data = SimpleNamespace(snippets=[], groups=[], servers=[])
        dialogs = self.make_dialogs(parent, data, store=self.make_snippet_store(data))
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        dialogs.show_editor(state, None, False)
        dialogs.on_new_category(Mock(), state)
        state.new_category_entry.set_text("First")
        dialogs.on_new_category_confirm(Mock(), state)

        self.assertEqual(dialogs.category_value(state), "First")
        state.name.set_text("Example")
        state.command.get_buffer().set_text("true")
        dialogs.on_editor_save(Mock(), state)
        self.assertEqual(data.snippets[0].category, "First")
        self.assertEqual(state.visible_ids, ["1"])
        dialogs.hide_manager(state)
        reopened = dialogs.show_manager()
        self.assertIs(reopened.window, state.window)
        self.assertEqual(reopened.category_grid.get_child_at_index(1).get_child().get_tooltip_text(), "First: 1 snippets")

    def test_editor_category_defaults_and_reserved_looking_names(self):
        parent = self.make_parent()
        data = SimpleNamespace(
            snippets=[CommandSnippet("one", "Existing", "true", "Operations")],
            groups=[], servers=[],
        )
        dialogs = self.make_dialogs(parent, data, store=self.make_snippet_store(data))
        self.addCleanup(parent.destroy)
        self.addCleanup(dialogs.shutdown)

        state = dialogs.show_manager()
        dialogs.show_editor(state, None, False)
        self.assertEqual(dialogs.category_value(state), "")
        self.assertEqual(state.category.get_active_text(), "Uncategorized")
        dialogs.on_editor_cancel(Mock(), state)

        state.category_grid.get_child_at_index(1).get_child().emit("clicked")
        dialogs.on_manager_add(Mock(), state)
        self.assertEqual(dialogs.category_value(state), "Operations")

        dialogs.on_new_category(Mock(), state)
        state.new_category_entry.set_text("__termia_uncategorized__")
        dialogs.on_new_category_confirm(Mock(), state)
        self.assertEqual(dialogs.category_value(state), "__termia_uncategorized__")
        state.name.set_text("Reserved-looking category")
        state.command.get_buffer().set_text("true")
        dialogs.on_editor_save(Mock(), state)
        self.assertEqual(data.snippets[-1].category, "__termia_uncategorized__")
        self.assertEqual(state.visible_ids, ["2"])

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
