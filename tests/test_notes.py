import json
import shutil
import subprocess
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from gi.repository import Gio, GLib, GObject

from termia.config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_OBFUSCATED,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
    read_connections_payload,
)
from termia.models import Note, NoteCategory
from termia.notes import NoteError, normalize_note, normalized_note_categories, note_category_move_allowed
from termia.notes_dialogs import (
    Gdk, Graphene, Gtk, GtkSource, NOTE_ROW_DND_MIME_TYPE,
    NOTE_CATEGORY_DND_MIME_TYPE, NoteEditorTab, NotesDialogs, NotesTreeNode,
    create_notes_text_view, format_note_timestamp,
)
from termia.notes_io import (
    export_notes_file,
    import_notes_file,
    read_notes_file,
    write_notes_file,
    validate_notes_payload,
    encode_notes_payload,
)
from termia.notes_presenter import NotesPresenter
from termia.stores import ConnectionStore, ReadOnlyStoreError, UnchangedMasterPasswordError


def make_note_tree_dialog(notes=(), categories=(), servers=(), tabs=()):
    """Build the native model state used by refresh tests without a window."""
    dialog = NotesDialogs.__new__(NotesDialogs)
    dialog.store = SimpleNamespace(data=SimpleNamespace(
        notes=list(notes), note_categories=list(categories), servers=list(servers),
    ))
    dialog.presenter = NotesPresenter(
        lambda: dialog.store.data.notes, lambda: dialog.store.data.note_categories,
        lambda: dialog.store.data.servers,
    )
    dialog.notes_list = object()
    dialog.notes_tree_selection = Gtk.SingleSelection.new(None)
    dialog.notes_tree_selection.set_autoselect(False)
    dialog.notes_tree_selection.set_can_unselect(True)
    dialog.search_entry = SimpleNamespace(get_text=lambda: "")
    dialog.editor_tabs = {tab.key: tab for tab in tabs}
    dialog.selected_note_id = dialog.selected_draft_key = None
    dialog.active_editor_tab_key = next(iter(dialog.editor_tabs), "active")
    dialog.scope_mode = "personal"
    dialog.server_filter_id = None
    dialog.loading_note_list = False
    dialog.expanded_note_sections = {"personal", "servers"}
    dialog.expanded_server_groups = set()
    dialog.collapsed_note_categories = set()
    dialog.translate = lambda key: "{count} notes" if key == "notes_category_count" else key
    dialog.close_note_context_menu = MagicMock()
    dialog.close_category_context_menu = MagicMock()
    dialog.show_empty_state = MagicMock()
    dialog.show_idle_workspace = MagicMock()
    return dialog


def bind_note_tree_node(test_case, dialog, node):
    """Exercise a mapped native row with GTK owning its factory lifecycle."""
    root = Gio.ListStore.new(NotesTreeNode)
    root.append(node)
    model = Gtk.TreeListModel.new(root, False, False, dialog.create_note_tree_children)
    selection = Gtk.SingleSelection.new(model)
    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", dialog.setup_note_tree_item)
    factory.connect("bind", dialog.bind_note_tree_item)
    factory.connect("unbind", dialog.unbind_note_tree_item)
    view = Gtk.ListView.new(selection, factory)
    window = Gtk.Window()
    window.set_child(view)
    test_case.addCleanup(window.destroy)
    window.present()
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    pending = [view]
    while pending:
        widget = pending.pop()
        if isinstance(widget, Gtk.TreeExpander):
            return widget.get_child()
        child = widget.get_first_child()
        while child is not None:
            pending.append(child)
            child = child.get_next_sibling()
    test_case.fail("Native category row was not bound")


class PrivateNoteDragTests(unittest.TestCase):
    def setUp(self):
        self.dialog = NotesDialogs.__new__(NotesDialogs)
        self.dialog.store = SimpleNamespace(read_only=False, encryption_locked=False)
        self.dialog.window = MagicMock()
        self.dialog.window.get_visible.return_value = True
        self.dialog.find_note = MagicMock(return_value=SimpleNamespace(id="note-one"))
        self.dialog.move_note_to_category = MagicMock(return_value=True)
        self.dialog.note_row_drag_id = "note-one"
        self.dialog.note_row_drag = object()

    def make_drop(self, mime_type):
        drop = MagicMock()
        drop.get_formats.return_value = Gdk.ContentFormats.new([mime_type])
        drop.get_drag.return_value = self.dialog.note_row_drag
        return drop

    def test_sources_offer_distinct_private_formats_without_text(self):
        provider = self.dialog.on_note_drag_prepare(None, 0, 0, "note-one")
        formats = provider.ref_formats()
        self.assertTrue(formats.contain_mime_type(NOTE_ROW_DND_MIME_TYPE))
        self.assertFalse(formats.contain_gtype(GObject.TYPE_STRING))
        self.assertFalse(formats.match(Gdk.ContentProvider.new_for_value("normal text").ref_formats()))
        self.dialog.find_note.return_value = None
        self.assertIsNone(self.dialog.on_note_drag_prepare(None, 0, 0, "missing"))

    def test_receivers_reject_text_other_kinds_and_foreign_drags(self):
        drop = self.make_drop(NOTE_ROW_DND_MIME_TYPE)
        self.assertTrue(self.dialog.on_note_category_drop_accept(None, drop))
        drop.get_drag.return_value = object()
        self.assertFalse(self.dialog.on_note_category_drop_accept(None, drop))
        drop = self.make_drop(NOTE_ROW_DND_MIME_TYPE)
        for other_type in ("text/plain", "application/x-termia-terminal-tab-id"):
            drop.get_formats.return_value = Gdk.ContentFormats.new([other_type])
            self.assertFalse(self.dialog.on_note_category_drop_accept(None, drop))

    def test_note_rows_respect_locked_and_read_only_storage(self):
        drop = self.make_drop(NOTE_ROW_DND_MIME_TYPE)
        for flag in ("read_only", "encryption_locked"):
            with patch.object(self.dialog.store, flag, True):
                self.assertIsNone(self.dialog.on_note_drag_prepare(None, 0, 0, "note-one"))
                self.assertFalse(self.dialog.on_note_category_drop(None, drop, 0, 0, "Work"))
        drop.read_async.assert_not_called()

    def test_async_drop_only_applies_live_matching_payload(self):
        for condition in ("valid", "wrong-id", "invalid-utf8", "stale", "deleted", "hidden",
                          "replaced-window", "locked", "read-only", "read-error"):
            with self.subTest(condition=condition):
                self.setUp()
                drop = self.make_drop(NOTE_ROW_DND_MIME_TYPE)
                expected = "note-one"
                self.assertTrue(self.dialog.on_note_category_drop(None, drop, 15, 0, "Work"))
                context = drop.read_async.call_args.args[-1]
                self.dialog.note_row_drag_id = None
                self.dialog.note_row_drag = None
                stream = MagicMock()
                payload = b"wrong" if condition == "wrong-id" else b"\xff" if condition == "invalid-utf8" else expected.encode()
                stream.read_bytes_finish.return_value = GLib.Bytes.new(payload)
                if condition == "stale":
                    self.dialog.pending_note_drop = object()
                elif condition == "deleted":
                    self.dialog.find_note.return_value = None
                elif condition == "hidden":
                    self.dialog.window.get_visible.return_value = False
                elif condition == "replaced-window":
                    self.dialog.window = MagicMock()
                elif condition == "locked":
                    self.dialog.store.encryption_locked = True
                elif condition == "read-only":
                    self.dialog.store.read_only = True
                elif condition == "read-error":
                    stream.read_bytes_finish.side_effect = GLib.Error("read failed")
                self.dialog.on_private_note_drop_bytes_read(stream, None, context)
                accepted = condition == "valid"
                drop.finish.assert_called_once_with(Gdk.DragAction.MOVE if accepted else Gdk.DragAction(0))
                self.assertEqual(self.dialog.move_note_to_category.call_count, int(accepted))
                if accepted:
                    self.dialog.move_note_to_category.assert_called_once_with("note-one", "Work")
                stream.close_async.assert_called_once()

    def test_async_reader_validates_mime_and_handles_io_failures(self):
        for condition in ("valid", "wrong-mime", "no-stream", "error"):
            with self.subTest(condition=condition):
                self.setUp()
                drop = self.make_drop(NOTE_ROW_DND_MIME_TYPE)
                self.dialog.on_note_category_drop(None, drop, 0, 0, "Work")
                context = drop.read_async.call_args.args[-1]
                stream = MagicMock()
                drop.read_finish.return_value = (
                    None if condition == "no-stream" else stream,
                    NOTE_ROW_DND_MIME_TYPE if condition == "valid" else "text/plain",
                )
                if condition == "error":
                    drop.read_finish.side_effect = GLib.Error("read failed")
                self.dialog.on_private_note_drop_read(drop, None, context)
                if condition == "valid":
                    self.assertEqual(stream.read_bytes_async.call_args.args[0], 256)
                    drop.finish.assert_not_called()
                else:
                    drop.finish.assert_called_once_with(Gdk.DragAction(0))
                    stream.read_bytes_async.assert_not_called()

class NativeNoteTabsTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.dialog = NotesDialogs.__new__(NotesDialogs)
        self.dialog.editor_tabs = {}
        self.dialog.active_editor_tab_key = None
        self.dialog._syncing_editor_notebook = False
        self.dialog.editor_notebook = Gtk.Notebook()
        self.dialog.editor_notebook.connect("switch-page", self.dialog.on_editor_notebook_switch_page)
        self.dialog.editor_notebook.connect("page-reordered", self.dialog.on_editor_notebook_page_reordered)
        self.dialog.store = SimpleNamespace(data=SimpleNamespace(servers=[]))
        self.dialog.translate = lambda key: key

    def add_tab(self, key):
        tab = NoteEditorTab(key, None, key, "", None, "content for " + key)
        self.dialog.add_editor_tab(tab)
        return tab

    def test_notebook_owns_selection_and_reordering_without_changing_draft(self):
        first, draft, last = (self.add_tab(key) for key in ("one", "draft:one", "two"))
        self.assertEqual(self.dialog.editor_notebook.get_n_pages(), 3)
        self.assertTrue(self.dialog.editor_notebook.get_tab_reorderable(draft.page_widget))
        self.dialog.activate_editor_tab = MagicMock(side_effect=lambda key: setattr(self.dialog, "active_editor_tab_key", key))
        self.dialog.editor_notebook.set_current_page(1)
        self.dialog.activate_editor_tab.assert_called_once_with("draft:one")
        self.dialog.editor_notebook.reorder_child(draft.page_widget, 0)
        self.assertEqual(list(self.dialog.editor_tabs), ["draft:one", "one", "two"])
        self.assertEqual(draft.content, "content for draft:one")
        self.assertIs(self.dialog.editor_notebook.get_nth_page(0), draft.page_widget)

    def test_failed_switch_restores_selected_page(self):
        first, second = self.add_tab("one"), self.add_tab("two")
        self.dialog.active_editor_tab_key = "one"
        self.dialog.activate_editor_tab = MagicMock()
        self.dialog.editor_notebook.set_current_page(1)
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        self.assertEqual(self.dialog.editor_notebook.get_current_page(), 0)
        self.assertIs(self.dialog.editor_notebook.get_nth_page(0), first.page_widget)

    def test_shared_editor_moves_between_pages_and_keeps_each_draft(self):
        first, second = self.add_tab("one"), self.add_tab("two")
        self.dialog.editor_workspace = Gtk.Box()
        self.dialog.text_view = Gtk.TextView()
        self.dialog.status_label = Gtk.Label()
        self.dialog.modified_label = Gtk.Label()
        self.dialog.detail_stack = Gtk.Stack()
        self.dialog.detail_stack.add_named(self.dialog.editor_notebook, "editor")
        self.dialog.scope_mode = "personal"
        self.dialog.server_filter_id = None
        self.dialog.editor_dirty = False
        self.dialog.current_note_id = None
        self.dialog.selected_note_id = None
        self.dialog.cancel_autosave = MagicMock()
        self.dialog.find_note = MagicMock(return_value=None)
        self.dialog.set_editor_enabled = MagicMock()
        self.dialog.refresh_list = MagicMock()
        self.dialog.notes_list = Gtk.ListView()
        self.dialog.editor_content = lambda: self.dialog.text_view.get_buffer().get_text(
            self.dialog.text_view.get_buffer().get_start_iter(),
            self.dialog.text_view.get_buffer().get_end_iter(), True,
        )
        self.dialog.activate_editor_tab("one")
        self.assertIs(self.dialog.editor_workspace.get_parent(), first.page_widget)
        self.dialog.text_view.get_buffer().set_text("edited one")
        self.dialog.editor_notebook.set_current_page(1)
        self.assertIs(self.dialog.editor_workspace.get_parent(), second.page_widget)
        self.assertEqual(first.content, "edited one")
        self.assertEqual(self.dialog.editor_content(), "content for two")
        self.dialog.editor_notebook.set_current_page(0)
        self.assertEqual(self.dialog.editor_content(), "edited one")
        self.dialog.editor_dirty = True
        self.dialog.save_editor = MagicMock(return_value=False)
        self.dialog.editor_notebook.set_current_page(1)
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        self.dialog.save_editor.assert_called_once_with()
        self.assertEqual(self.dialog.active_editor_tab_key, "one")
        self.assertEqual(self.dialog.editor_notebook.get_current_page(), 0)
        self.assertEqual(self.dialog.editor_content(), "edited one")


class NoteHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.categories = [
            NoteCategory("Project"), NoteCategory("Child", parent="Project"),
            NoteCategory("Leaf", parent="Child"), NoteCategory("Other"),
            NoteCategory("Server only", "server"),
        ]

    def test_native_tree_model_preserves_hierarchy_search_and_deep_groups(self):
        note = normalize_note("id", "Needle", "Body", "Leaf")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(data=SimpleNamespace(
            note_categories=self.categories, servers=[],
        ))
        dialog.presenter = NotesPresenter(lambda: [note], lambda: self.categories, lambda: [])
        dialog.search_entry = SimpleNamespace(get_text=lambda: "")
        dialog.notes_list = object()
        dialog.notes_tree_selection = Gtk.SingleSelection.new(None)
        dialog.notes_tree_selection.set_autoselect(False)
        dialog.editor_tabs = {}
        dialog.selected_note_id = "id"
        dialog.selected_draft_key = None
        dialog.active_editor_tab_key = "id"
        dialog.scope_mode = "personal"
        dialog.server_filter_id = None
        dialog.expanded_note_sections = {"personal"}
        dialog.expanded_server_groups = set()
        dialog.collapsed_note_categories = {(None, "Project")}
        dialog.translate = lambda key: "{count} notes" if key == "notes_category_count" else key
        dialog.close_note_context_menu = dialog.close_category_context_menu = lambda: None
        dialog.refresh_list()
        visible = [dialog.notes_tree_model.get_row(i).get_item().title
                   for i in range(dialog.notes_tree_model.get_n_items())]
        self.assertIn("Project", visible)
        self.assertNotIn("Needle", visible)
        dialog.search_entry = SimpleNamespace(get_text=lambda: "Needle")
        dialog.selected_note_id = "id"
        dialog.refresh_list()
        visible = [dialog.notes_tree_model.get_row(i).get_item().title
                   for i in range(dialog.notes_tree_model.get_n_items())]
        self.assertEqual(visible, ["notes_personal_scope", "Project", "Child", "Leaf", "Needle", "notes_server_scope"])
        self.assertEqual(dialog.notes_tree_selection.get_selected_item().get_item().note_id, "id")
        self.categories[:] = [NoteCategory(str(index), parent=str(index - 1) if index else None)
                              for index in range(1100)]
        note.category = "1099"
        dialog.search_entry = SimpleNamespace(get_text=lambda: "")
        dialog.collapsed_note_categories.clear()
        dialog.refresh_list()
        self.assertEqual(dialog.notes_tree_model.get_n_items(), 1103)

    def test_native_tree_rows_bind_and_recycle_controllers(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda key: "{count} notes" if key == "notes_category_count" else key
        dialog.store = SimpleNamespace(read_only=False, encryption_locked=False)
        dialog.on_note_tree_header_clicked = MagicMock()
        root = Gio.ListStore.new(NotesTreeNode)
        category = NotesTreeNode("category", "Folder", "folder-symbolic", 1, category="Folder")
        category.children.append(NotesTreeNode("note", "Needle", note_id="id"))
        root.append(category)
        model = Gtk.TreeListModel.new(root, False, True, dialog.create_note_tree_children)
        selection = Gtk.SingleSelection.new(model)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", dialog.setup_note_tree_item)
        factory.connect("bind", dialog.bind_note_tree_item)
        factory.connect("unbind", dialog.unbind_note_tree_item)
        view = Gtk.ListView.new(selection, factory)
        window = Gtk.Window()
        window.set_child(view)
        window.present()
        for _ in range(10):
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
        self.assertEqual(model.get_n_items(), 2)
        widgets = [view]
        expanders = []
        while widgets:
            widget = widgets.pop()
            if isinstance(widget, Gtk.TreeExpander):
                expanders.append(widget)
            child = widget.get_first_child()
            while child is not None:
                widgets.append(child)
                child = child.get_next_sibling()
        self.assertEqual(len(expanders), 2)
        controllers_by_title = {}
        for expander in expanders:
            content = expander.get_child()
            title = content.get_first_child().get_next_sibling().get_label()
            controllers = content.observe_controllers()
            controllers_by_title[title] = [controllers.get_item(i)
                                           for i in range(controllers.get_n_items())]
        self.assertTrue(any(isinstance(item, Gtk.DragSource)
                            for item in controllers_by_title["Needle"]))
        self.assertTrue(any(isinstance(item, Gtk.DropTargetAsync)
                            for item in controllers_by_title["Folder"]))
        header_click = next(item for item in controllers_by_title["Folder"]
                            if isinstance(item, Gtk.GestureClick) and item.get_button() == 1)
        header_click.emit("pressed", 1, 10.0, 10.0)
        dialog.on_note_tree_header_clicked.assert_not_called()
        header_click.emit("released", 1, 10.0, 10.0)
        dialog.on_note_tree_header_clicked.assert_called_once()
        window.close()

    def test_notes_window_installs_native_tree(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        parent = Gtk.Window()
        store = SimpleNamespace(read_only=True, encryption_locked=False, data=SimpleNamespace(
            app=SimpleNamespace(notes_editor={}), notes=[], note_categories=[], servers=[],
        ))
        presenter = NotesPresenter(lambda: [], lambda: [], lambda: [])
        dialog = NotesDialogs(parent, store, presenter, lambda key: key,
                              lambda: True, lambda _message: None, lambda _message: None)
        dialog.ensure_window()
        self.assertIsInstance(dialog.notes_list, Gtk.ListView)
        self.assertIsInstance(dialog.notes_tree_model, Gtk.TreeListModel)
        dialog.refresh_list()
        dialog.window.present()
        for _ in range(10):
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
        self.assertEqual(dialog.notes_tree_model.get_n_items(), 2)
        dialog.window.close()
        parent.close()

    def test_native_right_click_other_note_defers_selection_and_menu(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        first = Note("one", "First", "Body")
        second = Note("two", "Second", "Body")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(data=SimpleNamespace(notes=[first, second]))
        dialog.translate = lambda key: "{count} notes" if key == "notes_category_count" else key
        dialog.selected_note_id = "one"
        dialog.selected_draft_key = None
        dialog.active_editor_tab_key = "one"
        dialog.scope_mode = "personal"
        dialog.server_filter_id = None
        dialog.loading_note_list = False
        dialog.show_note_context_menu = MagicMock()
        root = Gio.ListStore.new(NotesTreeNode)
        category = NotesTreeNode("category", "Notes", "folder-symbolic", 2)
        for note in (first, second):
            category.children.append(NotesTreeNode("note", note.title, note_id=note.id))
        root.append(category)
        dialog.notes_tree_model = Gtk.TreeListModel.new(root, False, True,
                                                        dialog.create_note_tree_children)
        dialog.notes_tree_selection = Gtk.SingleSelection.new(dialog.notes_tree_model)
        dialog.notes_tree_selection.set_autoselect(False)
        dialog.notes_tree_selection.connect("notify::selected-item", dialog.on_note_tree_selected)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", dialog.setup_note_tree_item)
        factory.connect("bind", dialog.bind_note_tree_item)
        factory.connect("unbind", dialog.unbind_note_tree_item)
        view = Gtk.ListView.new(dialog.notes_tree_selection, factory)
        dialog.window = Gtk.Window()
        dialog.window.set_child(view)
        dialog.window.present()
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        widgets = [view]
        target = None
        while widgets:
            widget = widgets.pop()
            if isinstance(widget, Gtk.TreeExpander):
                content = widget.get_child()
                if getattr(content, "note_id", None) == "two":
                    target = content
            child = widget.get_first_child()
            while child is not None:
                widgets.append(child)
                child = child.get_next_sibling()
        self.assertIsNotNone(target)
        gesture = MagicMock()
        dialog.on_note_tree_context_pressed(gesture, 1, 5, 5, target, "two")
        self.assertEqual(dialog.selected_note_id, "one")
        dialog.show_note_context_menu.assert_not_called()
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        self.assertEqual(dialog.selected_note_id, "two")
        self.assertEqual(dialog.active_editor_tab_key, "one")
        dialog.show_note_context_menu.assert_called_once()
        self.assertEqual(dialog.show_note_context_menu.call_args.kwargs["note_id"], "two")
        dialog.window.close()

    def test_native_category_pointer_drag_starts_without_expanding(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None or not shutil.which("xdotool"):
            self.skipTest("GTK pointer drag test requires a private display and xdotool")
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11

        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda key: "{count} notes" if key == "notes_category_count" else key
        dialog.store = SimpleNamespace(read_only=False, encryption_locked=False,
                                       has_note_category=lambda *_args: True,
                                       data=SimpleNamespace(note_categories=[
                                           NoteCategory("Source"), NoteCategory("Target"),
                                       ]))
        dialog.on_note_tree_header_clicked = MagicMock()
        drag_begin = dialog.on_category_group_drag_begin
        dialog.on_category_group_drag_begin = MagicMock(wraps=drag_begin)
        root = Gio.ListStore.new(NotesTreeNode)
        root.append(NotesTreeNode("category", "Source", "folder-symbolic", category="Source"))
        root.append(NotesTreeNode("category", "Target", "folder-symbolic", category="Target"))
        model = Gtk.TreeListModel.new(root, False, False, dialog.create_note_tree_children)
        selection = Gtk.SingleSelection.new(model)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", dialog.setup_note_tree_item)
        factory.connect("bind", dialog.bind_note_tree_item)
        factory.connect("unbind", dialog.unbind_note_tree_item)
        view = Gtk.ListView.new(selection, factory)
        window = Gtk.Window()
        window.set_default_size(360, 180)
        window.set_child(view)
        dialog.window = window
        source = None
        point = None

        def drain():
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)

        def wait_for(condition, phase):
            deadline = time.monotonic() + 2
            while not condition():
                if time.monotonic() >= deadline:
                    self.fail(
                        f"Timed out waiting for {phase}: "
                        f"window_mapped={window.get_mapped()}, "
                        f"view_size=({view.get_width()}, {view.get_height()}), "
                        f"source_mapped={source.get_mapped() if source is not None else None}, "
                        f"source_size={(source.get_width(), source.get_height()) if source is not None else None}, "
                        f"point={(point.x, point.y) if point is not None else None}, "
                        f"origin={getattr(dialog, 'category_group_drag_origin', None)}, "
                        f"drag_begin_calls={dialog.on_category_group_drag_begin.call_count}, "
                        f"header_click_calls={dialog.on_note_tree_header_clicked.call_count}"
                    )
                GLib.MainContext.default().iteration(False)
                time.sleep(0.005)

        def pointer(*args):
            subprocess.run(["xdotool", *args], check=True, stdout=subprocess.DEVNULL)
            drain()

        def reset_pointer_and_close():
            try:
                pointer("mouseup", "1")
                pointer("mousemove", "0", "0")
            finally:
                window.close()
                drain()

        self.addCleanup(reset_pointer_and_close)
        window.present()
        wait_for(lambda: window.get_mapped() and view.get_width() > 0 and view.get_height() > 0,
                 "mapped and allocated list")
        widgets = [view]
        while widgets:
            widget = widgets.pop()
            if isinstance(widget, Gtk.TreeExpander):
                content = widget.get_child()
                title = content.get_first_child().get_next_sibling().get_label()
                if title == "Source":
                    source = content
            child = widget.get_first_child()
            while child is not None:
                widgets.append(child)
                child = child.get_next_sibling()
        self.assertIsNotNone(source)
        wait_for(lambda: source.get_mapped() and source.get_width() > 0 and source.get_height() > 0,
                 "mapped and allocated source row")
        valid, point = source.compute_point(window, Graphene.Point().init(35, source.get_height() / 2))
        self.assertTrue(valid)
        window.get_display().sync()
        xid = GdkX11.X11Surface.get_xid(window.get_surface())
        pointer("mousemove", "--window", str(xid), str(int(point.x)), str(int(point.y)))
        pointer("mousedown", "1")
        self.assertFalse(dialog.on_note_tree_header_clicked.called)
        for offset in (12, 24, 48, 80):
            pointer("mousemove", "--window", str(xid), str(int(point.x + offset)), str(int(point.y)))
            # Pace the gesture; completion is checked separately with a deadline.
            time.sleep(0.03)
            drain()
        wait_for(lambda: dialog.on_category_group_drag_begin.called, "native drag-begin")
        self.assertTrue(dialog.on_category_group_drag_begin.called)
        pointer("mouseup", "1")
        wait_for(lambda: getattr(dialog, "category_group_drag", None) is None, "native drag-end")
        dialog.on_note_tree_header_clicked.assert_not_called()

    def test_move_validation_rejects_cycles_missing_and_cross_scope_parents(self):
        for name, parent, scope in (
            ("Project", "Project", None), ("Project", "Leaf", None),
            ("Child", "Server only", None), ("Missing", None, None),
            ("Child", "Other", "server"),
        ):
            with self.subTest(name=name, parent=parent, scope=scope):
                self.assertFalse(note_category_move_allowed(self.categories, name, parent, scope))
        self.assertTrue(note_category_move_allowed(self.categories, "Child", "Other"))
        self.assertTrue(note_category_move_allowed(self.categories, "Child", None))

    def test_schema_three_rejects_invalid_hierarchies_and_canonicalizes_parent(self):
        for parent in ("Missing", "Child", 123, " "):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                validate_notes_payload({"schema_version": 3, "categories": [
                    {"name": "Child", "parent": parent},
                ], "notes": []})
        with self.assertRaises(ValueError):
            validate_notes_payload({"schema_version": 3, "categories": [
                {"name": "A", "parent": "B"}, {"name": "B", "parent": "A"},
            ]})
        payload = validate_notes_payload({"schema_version": 3, "categories": [
            {"name": "Project"}, {"name": "Child", "parent": " project "},
        ]})
        self.assertEqual(payload["categories"][1]["parent"], "Project")

    def test_legacy_backup_precedes_first_save_and_keeps_original_protection(self):
        from termia.notes_store import NotesFileStore
        for mode in ("plain", CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_ENCRYPTED):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "notes.json"
                raw = json.dumps(encode_notes_payload({"schema_version": 2,
                    "notes": [], "categories": [{"name": "Legacy"}]}, mode, "test password"))
                path.write_text(raw, encoding="utf-8")
                store = NotesFileStore(path)
                store.load(mode, "test password")
                self.assertEqual(store.categories, [NoteCategory("Legacy")])
                self.assertEqual(path.read_text(encoding="utf-8"), raw)
                store.save(mode, "test password")
                backups = list(Path(directory).glob("notes.json.backup-*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(encoding="utf-8"), raw)
                store.save(mode, "test password")
                self.assertEqual(len(list(Path(directory).glob("notes.json.backup-*"))), 1)

    def test_failed_backup_leaves_legacy_file_unchanged(self):
        from termia.notes_store import NotesFileStore
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.json"
            raw = '{"schema_version": 2, "categories": [{"name": "Legacy"}]}'
            path.write_text(raw, encoding="utf-8")
            store = NotesFileStore(path)
            store.load("plain")
            with patch.object(store, "backup_current_file", side_effect=OSError("test failure")):
                with self.assertRaises(OSError):
                    store.save("plain")
            self.assertEqual(path.read_text(encoding="utf-8"), raw)

    def test_read_only_legacy_and_invalid_hierarchy_preserve_original_files(self):
        from termia.notes_store import NotesFileStore
        for read_only, invalid in ((True, False), (True, True), (False, True)):
            with self.subTest(read_only=read_only, invalid=invalid), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "notes.json"
                raw = json.dumps({"schema_version": 3 if invalid else 2, "categories": [
                    {"name": "Child", **({"parent": "Missing"} if invalid else {})},
                ]})
                path.write_text(raw, encoding="utf-8")
                store = NotesFileStore(path, read_only=read_only)
                store.load("plain")
                if read_only:
                    store.save("plain")
                self.assertEqual(path.read_text(encoding="utf-8"), raw)
                backups = list(Path(directory).glob("notes.json.*"))
                self.assertEqual(len(backups), 1 if invalid and not read_only else 0)
                if backups:
                    self.assertEqual(backups[0].read_text(encoding="utf-8"), raw)

    def test_interrupted_atomic_replace_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.json"
            write_notes_file(path, [], self.categories, "plain")
            original = path.read_bytes()
            with patch("termia.notes_io.os.replace", side_effect=OSError("test interrupted write")):
                with self.assertRaises(OSError):
                    write_notes_file(path, [], [NoteCategory("Different")], "plain")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(read_notes_file(path)[1], self.categories)

    def test_nested_round_trip_and_export_in_all_protection_modes(self):
        note = normalize_note("id", "Title", "Body", "Leaf")
        for mode in ("plain", CONNECTION_STORAGE_OBFUSCATED, CONNECTION_STORAGE_ENCRYPTED):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "notes.json"
                write_notes_file(path, [note], self.categories, mode, "test password")
                self.assertEqual(read_notes_file(path, "test password"), ([note], self.categories))
                export_notes_file(path, [note], self.categories, "export password")
                self.assertEqual(import_notes_file(path, "export password"), ([note], self.categories))

    def test_search_retains_ancestors_and_excludes_unrelated_empty_groups(self):
        note = normalize_note("id", "Needle", "Body", "Leaf")
        presenter = NotesPresenter(lambda: [note], lambda: self.categories, lambda: [])
        tree = presenter.tree("Needle")
        self.assertEqual({item.name: item.parent for item in tree.personal_categories},
                         {"Project": None, "Child": "Project", "Leaf": "Child"})
        self.assertEqual(sum(len(item.items) for item in tree.personal_categories), 1)

    def test_bulk_navigation_preserves_selection_tabs_and_never_saves(self):
        for categories in ([], self.categories):
            dialog = NotesDialogs.__new__(NotesDialogs)
            dialog.store = SimpleNamespace(read_only=True, data=SimpleNamespace(
                servers=[SimpleNamespace(id="server")], note_categories=categories))
            dialog.selected_note_id, dialog.selected_draft_key = "selected", "draft"
            dialog.editor_tabs = {"active": NoteEditorTab("active", None, "Draft", "Child", None, "Unsaved")}
            dialog.active_editor_tab_key = "active"
            def refresh(*_args):
                dialog.selected_note_id = dialog.selected_draft_key = None
            dialog.refresh_list = refresh
            for expanded in (False, True):
                dialog.set_all_note_groups_expanded(expanded)
                self.assertEqual(dialog.expanded_note_sections, {"personal", "servers"} if expanded else set())
                self.assertEqual(dialog.expanded_server_groups, {"server"} if expanded else set())
                self.assertEqual(len(dialog.collapsed_note_categories), 0 if expanded else len(categories))
                self.assertEqual((dialog.selected_note_id, dialog.selected_draft_key), ("selected", "draft"))
                self.assertEqual(dialog.editor_tabs["active"].content, "Unsaved")
                self.assertEqual(dialog.active_editor_tab_key, "active")

    def test_private_category_drag_checks_scope_and_never_offers_text(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(read_only=False, encryption_locked=False,
            data=SimpleNamespace(note_categories=self.categories), has_note_category=lambda *_args: True)
        provider = dialog.on_category_group_drag_prepare(None, 0, 0, "Child", None)
        self.assertTrue(provider.ref_formats().contain_mime_type(NOTE_CATEGORY_DND_MIME_TYPE))
        self.assertFalse(provider.ref_formats().contain_gtype(GObject.TYPE_STRING))
        dialog.category_group_drag = object()
        drop = MagicMock()
        drop.get_drag.return_value = dialog.category_group_drag
        drop.get_formats.return_value = provider.ref_formats()
        self.assertTrue(dialog.on_category_group_drop_accept(None, drop, None, "Other"))
        self.assertTrue(dialog.on_category_group_drop_accept(None, drop, None, None))
        for scope, parent in ((None, "Leaf"), (None, "Child"), ("server", None)):
            self.assertFalse(dialog.on_category_group_drop_accept(None, drop, scope, parent))
        for flag in ("read_only", "encryption_locked"):
            with patch.object(dialog.store, flag, True):
                self.assertFalse(dialog.on_category_group_drop_accept(None, drop, None, "Other"))
        drop.get_drag.return_value = object()
        self.assertFalse(dialog.on_category_group_drop_accept(None, drop, None, "Other"))

    def test_category_async_drop_keeps_accepted_origin_after_drag_end(self):
        for condition in ("valid", "wrong-token", "stale", "hidden", "locked", "read-only"):
            with self.subTest(condition=condition):
                dialog = NotesDialogs.__new__(NotesDialogs)
                dialog.store = SimpleNamespace(read_only=False, encryption_locked=False)
                dialog.window = MagicMock()
                dialog.window.get_visible.return_value = True
                dialog.move_category_group = MagicMock(return_value=True)
                drop = MagicMock()
                dialog.read_private_note_drop(drop, NOTE_CATEGORY_DND_MIME_TYPE, "nonce", (None, "Child", "Other"))
                context = drop.read_async.call_args.args[-1]
                dialog.category_group_drag_origin = dialog.category_group_drag_token = None
                stream = MagicMock()
                stream.read_bytes_finish.return_value = GLib.Bytes.new(
                    b"wrong" if condition == "wrong-token" else b"nonce")
                if condition == "stale":
                    dialog.pending_note_drop = object()
                elif condition == "hidden":
                    dialog.window.get_visible.return_value = False
                elif condition == "locked":
                    dialog.store.encryption_locked = True
                elif condition == "read-only":
                    dialog.store.read_only = True
                dialog.on_private_note_drop_bytes_read(stream, None, context)
                if condition == "valid":
                    dialog.move_category_group.assert_called_once_with(None, "Child", "Other")
                else:
                    dialog.move_category_group.assert_not_called()
                drop.finish.assert_called_once_with(
                    Gdk.DragAction.MOVE if condition == "valid" else Gdk.DragAction(0))

    def test_nested_rows_hide_descendants_and_search_reveals_them(self):
        note = normalize_note("id", "Needle", "Body", "Leaf")
        dialog = make_note_tree_dialog([note], self.categories)
        dialog.collapsed_note_categories = {(None, "Project"), (None, "Child")}
        dialog.refresh_list()
        visible = lambda: [dialog.notes_tree_model.get_row(i)
                          for i in range(dialog.notes_tree_model.get_n_items())]
        self.assertEqual([row.get_item().category for row in visible()
                          if row.get_item().kind == "category"], ["Other", "Project"])
        self.assertFalse(any(row.get_item().kind == "note" for row in visible()))
        dialog.search_entry = SimpleNamespace(get_text=lambda: "Needle")
        dialog.refresh_list()
        self.assertEqual([(row.get_item().category, row.get_depth()) for row in visible()
                          if row.get_item().kind == "category"],
                         [("Project", 1), ("Child", 2), ("Leaf", 3)])
        self.assertEqual([row.get_item().note_id for row in visible()
                          if row.get_item().kind == "note"], ["id"])
        dialog.search_entry = SimpleNamespace(get_text=lambda: "")
        dialog.refresh_list()
        self.assertFalse(any(row.get_item().kind == "note" for row in visible()))
        self.assertEqual(dialog.collapsed_note_categories, {(None, "Project"), (None, "Child")})

    def test_real_category_headers_have_private_drag_targets_and_sources(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        dialog = make_note_tree_dialog()
        node = NotesTreeNode("category", "Child", category="Child", count=1)
        content = bind_note_tree_node(self, dialog, node)
        controllers = content.observe_controllers()
        sources = [controllers.get_item(i) for i in range(controllers.get_n_items())
                   if isinstance(controllers.get_item(i), Gtk.DragSource)]
        targets = [controllers.get_item(i) for i in range(controllers.get_n_items())
                   if isinstance(controllers.get_item(i), Gtk.DropTargetAsync)]
        self.assertEqual(len(sources), 1)
        self.assertEqual(len(targets), 2)
        mime_types = {mime_type for target in targets
                      for mime_type in target.get_property("formats").get_mime_types()}
        self.assertEqual(mime_types, {NOTE_CATEGORY_DND_MIME_TYPE, NOTE_ROW_DND_MIME_TYPE})


class NotesDomainTests(unittest.TestCase):
    def test_focus_active_editor_waits_for_an_editable_active_tab(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.window = SimpleNamespace(
            get_visible=lambda: True, is_active=lambda: True,
        )
        dialog.active_editor_tab_key = "draft"
        dialog.text_view = SimpleNamespace(
            get_editable=lambda: True,
            grab_focus=MagicMock(),
        )

        dialog.window.is_active = lambda: False
        dialog.focus_active_editor()
        dialog.text_view.grab_focus.assert_not_called()

        dialog.window.is_active = lambda: True
        self.assertEqual(dialog.focus_active_editor(), GLib.SOURCE_REMOVE)
        dialog.text_view.grab_focus.assert_called_once_with()

        dialog.active_editor_tab_key = None
        dialog.text_view.grab_focus.reset_mock()
        dialog.focus_active_editor()
        dialog.text_view.grab_focus.assert_not_called()

        dialog.active_editor_tab_key = "draft"
        dialog.tab_context_popover = SimpleNamespace(get_visible=lambda: True)
        dialog.focus_active_editor()
        dialog.text_view.grab_focus.assert_not_called()
        dialog.tab_context_popover = None
        dialog.focus_active_editor()
        dialog.text_view.grab_focus.assert_called_once_with()
        dialog.text_view.grab_focus.reset_mock()
        dialog.notes_context_popover = SimpleNamespace(get_visible=lambda: True)
        dialog.focus_active_editor()
        dialog.text_view.grab_focus.assert_not_called()
        dialog.notes_context_popover = None
        dialog.category_context_popover = SimpleNamespace(get_visible=lambda: True)
        dialog.focus_active_editor()
        dialog.text_view.grab_focus.assert_not_called()

    def test_editor_saves_plain_text_without_rewriting_markdown_punctuation(self):
        content = "**bold **\n# literal café `code`"
        tab = NoteEditorTab("draft", None, "Draft", "", None, "")
        saved = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.cancel_autosave = MagicMock()
        dialog.editor_dirty = True
        dialog.current_note_id = None
        dialog.editor_content = lambda: content
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = tab.key
        dialog.store = SimpleNamespace(
            add_note=lambda title, note_content, category, server_id: (
                saved.append(note_content), SimpleNamespace(
                    id="saved", title=title, modified_at="",
                ),
            )[1],
        )
        dialog.translate = lambda key: key
        dialog.status_label = MagicMock()
        dialog.modified_label = MagicMock()
        dialog.capture_active_editor_tab = MagicMock()
        dialog.refresh_list = MagicMock()
        dialog.set_editor_enabled = MagicMock()

        self.assertTrue(dialog.save_editor())
        self.assertEqual(saved, [content])

    def test_read_only_appearance_changes_do_not_write_settings(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            read_only=True, encryption_locked=False,
            data=SimpleNamespace(app=SimpleNamespace(notes_editor={"size": 12})),
            update_notes_editor=MagicMock(),
        )
        dialog.apply_editor_appearance = MagicMock()
        dialog.update_editor_appearance({"size": 18})
        dialog.store.update_notes_editor.assert_not_called()
        dialog.apply_editor_appearance.assert_called_once_with({"size": 18})

    def test_line_number_toggle_uses_source_view_and_persists_visibility(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.text_view = MagicMock()
        dialog.update_editor_appearance = MagicMock()
        button = SimpleNamespace(get_active=lambda: False)

        dialog.on_line_numbers_toggled(button)

        dialog.text_view.set_show_line_numbers.assert_called_once_with(False)
        dialog.update_editor_appearance.assert_called_once_with({"line_numbers": False})

        dialog.text_view.set_show_line_numbers.reset_mock()
        dialog.update_editor_appearance.reset_mock()
        button.get_active = lambda: True

        dialog.on_line_numbers_toggled(button)

        dialog.text_view.set_show_line_numbers.assert_called_once_with(True)
        dialog.update_editor_appearance.assert_called_once_with({"line_numbers": True})

    def test_notes_editor_uses_plain_text_source_buffer_and_native_numbers(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GtkSourceView integration requires a graphical display")
        view = create_notes_text_view(True)
        self.assertIsInstance(view, GtkSource.View)
        self.assertTrue(view.get_show_line_numbers())
        self.assertEqual(view.get_wrap_mode(), Gtk.WrapMode.WORD_CHAR)
        self.assertFalse(view.get_auto_indent())
        buffer = view.get_buffer()
        self.assertIsInstance(buffer, GtkSource.Buffer)
        self.assertFalse(buffer.get_highlight_syntax())
        self.assertFalse(buffer.get_highlight_matching_brackets())
        scheme = buffer.get_style_scheme()
        self.assertEqual(scheme.get_id(), "termia-notes")
        line_style = scheme.get_style("line-numbers")
        self.assertEqual(line_style.get_property("foreground"), "#0065BF")
        self.assertEqual(line_style.get_property("background"), "#000D1A")
        buffer.set_text("first line\n")
        self.assertEqual(buffer.get_line_count(), 2)
        self.assertEqual(
            buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False),
            "first line\n",
        )
        view.set_show_line_numbers(False)
        self.assertFalse(view.get_show_line_numbers())

    def test_editor_appearance_uses_dark_defaults_when_settings_are_empty(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_css_provider = MagicMock()

        dialog.apply_editor_appearance({"size": 12})

        css = dialog.editor_css_provider.load_from_data.call_args.args[0].decode()
        self.assertIn("color: #ffffff;", css)
        self.assertIn("background-color: #001b33;", css)

    def test_toolbar_visibility_does_not_toggle_the_notes_sidebar(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_toolbar = MagicMock()
        dialog.notes_list_paned = MagicMock()
        dialog.notes_list_visible = True
        dialog.update_editor_appearance = MagicMock()
        button = SimpleNamespace(get_active=lambda: False)
        dialog.on_toolbar_toggled(button)
        dialog.editor_toolbar.set_visible.assert_called_once_with(False)
        dialog.notes_list_paned.set_start_child.assert_not_called()
        self.assertTrue(dialog.notes_list_visible)

    def test_opening_notes_restores_window_before_presenting(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.window = MagicMock()
        dialog.store = SimpleNamespace(encryption_locked=False, read_only=True)
        dialog.ensure_window = MagicMock()
        dialog.set_notes_scope = MagicMock(return_value=True)
        dialog.show_manager()
        self.assertEqual(dialog.window.method_calls, [call.get_visible(), call.unminimize(), call.present()])
        dialog.set_notes_scope.return_value = False
        dialog.window.reset_mock()
        dialog.show_manager()
        self.assertEqual(dialog.window.method_calls, [call.get_visible(), call.unminimize(), call.present()])

    def test_legacy_categories_migrate_to_scopes_that_use_them(self):
        notes = [
            normalize_note("personal", "Personal", "Body", "Ops"),
            normalize_note("server-a", "Server A", "Body", "Ops", "server-a"),
            normalize_note("server-b", "Server B", "Body", "Ops", "server-b"),
        ]

        categories = normalized_note_categories(["Ops", "Unused"], notes)

        self.assertEqual(categories, [
            NoteCategory("Ops"), NoteCategory("Ops", "server-a"),
            NoteCategory("Ops", "server-b"), NoteCategory("Unused"),
        ])

    def test_note_validation_and_timestamps(self):
        note = normalize_note("one", "  Runbook ", " Restart service ", "Ops", now="2026-10-02T12:00:00+00:00")
        self.assertEqual(note.title, "Runbook")
        self.assertEqual(note.content, " Restart service ")
        self.assertEqual(note.created_at, "2026-10-02T12:00:00+00:00")
        with self.assertRaises(NoteError):
            normalize_note("two", " ", "text")
        with self.assertRaises(NoteError):
            normalize_note("two", "Title", " ")

    def test_note_timestamp_display_omits_fractional_seconds(self):
        value = "2026-10-05T12:34:56.123456+00:00"
        expected = datetime.fromisoformat(value).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.assertEqual(format_note_timestamp(value), expected)
        self.assertNotIn("T", format_note_timestamp(value))
        self.assertNotIn(".", format_note_timestamp(value))
        self.assertEqual(format_note_timestamp("unrecognized"), "unrecognized")

    def test_read_only_note_editor_remains_readable_without_enabling_edits(self):
        states = {}
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(read_only=True, encryption_locked=False)
        dialog.text_view = SimpleNamespace(
            set_sensitive=lambda value: states.update(sensitive=value),
            set_editable=lambda value: states.update(editable=value),
            set_cursor_visible=lambda value: states.update(cursor=value),
        )
        dialog.save_button = SimpleNamespace(
            set_sensitive=lambda value: states.update(save=value)
        )
        dialog.delete_button = SimpleNamespace(
            set_sensitive=lambda value: states.update(delete=value)
        )
        dialog.current_note_id = "note-id"

        dialog.set_editor_enabled(True)

        self.assertEqual(
            states,
            {"sensitive": True, "editable": False, "cursor": False,
             "save": False, "delete": False},
        )

    def test_presenter_search_filters_and_sorts_by_modified_time(self):
        first = normalize_note("old", "Runbook", "Restart", now="2026-10-01T10:00:00+00:00")
        second = normalize_note("new", "Database", "Backup", now="2026-10-02T10:00:00+00:00")
        presenter = NotesPresenter(
            lambda: [first, second], lambda: [NoteCategory("Ops")], lambda: [],
        )

        self.assertEqual([item.note.id for item in presenter.items()], ["new", "old"])
        self.assertEqual([item.note.id for item in presenter.items("backup")], ["new"])
        self.assertEqual([item.note.id for item in presenter.items("  RESTART  ")], ["old"])
        self.assertEqual(presenter.items("missing content"), [])

    def test_presenter_tree_nests_personal_categories_and_only_servers_with_notes(self):
        personal = normalize_note("personal", "Checklist", "Inspect", "Ops")
        server_note = normalize_note("server-note", "Runbook", "Restart", "Ops", "server-a")
        presenter = NotesPresenter(
            lambda: [personal, server_note],
            lambda: [NoteCategory("Ops"), NoteCategory("Empty"), NoteCategory("Ops", "server-a")],
            lambda: [
                SimpleNamespace(id="server-a", name="Build host"),
                SimpleNamespace(id="server-empty", name="Empty host"),
            ],
        )

        tree = presenter.tree()

        self.assertEqual(
            [(category.name, len(category.items)) for category in tree.personal_categories],
            [("Empty", 0), ("Ops", 1)],
        )
        self.assertEqual(
            [(server.id, server.name) for server in tree.servers],
            [("server-a", "Build host")],
        )
        self.assertEqual(
            [(category.name, len(category.items)) for category in tree.servers[0].categories],
            [("Ops", 1)],
        )

    def test_presenter_tree_search_hides_empty_categories(self):
        note = normalize_note("note", "Restart", "Restart service", "Ops", "server-a")
        presenter = NotesPresenter(
            lambda: [note], lambda: [NoteCategory("Ops", "server-a"), NoteCategory("Empty")],
            lambda: [SimpleNamespace(id="server-a", name="Build host")],
        )

        tree = presenter.tree("build host")

        self.assertEqual(tree.personal_categories, ())
        self.assertEqual([server.id for server in tree.servers], ["server-a"])
        self.assertEqual([category.name for category in tree.servers[0].categories], ["Ops"])


class NoteTabContextMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        self.bar = Gtk.Box()
        self.parent = Gtk.Box()
        self.parent.set_size_request(220, 40)
        self.parent.append(Gtk.Label(label="Clicked note"))
        self.bar.append(self.parent)
        self.window.set_child(self.bar)
        self.window.present()
        self.addCleanup(self.destroy_window)
        self.tab = NoteEditorTab("clicked", "note-one", "Clicked note", "Ops", "server-one", "Body")
        self.tab.container_widget = self.parent
        self.other = NoteEditorTab("active", None, "Draft", "", None, "Unsaved text", dirty=True)
        self.dialog = NotesDialogs.__new__(NotesDialogs)
        self.dialog.window = self.window
        self.dialog.store = SimpleNamespace(read_only=False, encryption_locked=False)
        self.dialog.translate = lambda key: "Rename"
        self.dialog.tab_context_popover = None
        self.dialog.editor_tabs_bar = self.bar
        self.dialog.editor_tabs = {self.tab.key: self.tab, self.other.key: self.other}
        self.dialog.active_editor_tab_key = self.other.key
        self.dialog.ensure_writable = MagicMock(return_value=True)
        self.dialog.show_note_rename_dialog = MagicMock()

    @staticmethod
    def drain_events(wait_for_rename=False):
        context = GLib.MainContext.default()
        deadline = time.monotonic() + (0.2 if wait_for_rename else 0)
        for _ in range(350):
            if context.pending():
                context.iteration(False)
            elif time.monotonic() < deadline:
                time.sleep(0.001)
            else:
                break

    def destroy_window(self):
        self.dialog.dispose_note_tab_context_menu()
        self.drain_events()
        self.window.destroy()

    def open_menu(self, key=None, x=15.0, y=20.0):
        gesture = MagicMock()
        self.dialog.on_note_tab_context_pressed(gesture, 1, x, y, key or self.tab.key)
        gesture.set_state.assert_called_once_with(Gtk.EventSequenceState.CLAIMED)
        menu = self.dialog.tab_context_popover
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        return menu

    def rename_entry(self, widget):
        if isinstance(widget, Gtk.Label) and widget.get_label() == "Rename":
            return widget.get_parent()
        child = widget.get_first_child()
        while child is not None:
            entry = self.rename_entry(child)
            if entry is not None:
                return entry
            child = child.get_next_sibling()
        return None

    def test_menu_follows_click_and_retains_one_hidden_popup_until_disposal(self):
        for x, y in ((5.75, 8.25), (110, 20), (190.5, 32.75)):
            with self.subTest(x=x, y=y):
                menu = self.open_menu(x=x, y=y)
                valid, rect = menu.get_pointing_to()
                self.assertTrue(valid)
                self.assertEqual((rect.x, rect.y, rect.width, rect.height), (int(x), int(y), 1, 1))
                model = menu.get_menu_model()
                self.assertEqual(model.get_n_items(), 1)
                self.assertEqual(model.get_item_attribute_value(0, "label", None).unpack(), "Rename")
                menu.popdown()
                self.assertIsNone(self.dialog.tab_context_popover)
                self.drain_events()
                self.assertIs(menu.get_parent(), self.bar)
        self.dialog.dispose_note_tab_context_menu()
        self.assertIsNone(menu.get_parent())

    def test_native_entry_defers_rename_for_clicked_saved_note_or_draft(self):
        for tab in (self.tab, self.other):
            with self.subTest(saved=tab.note_id is not None):
                tab.container_widget = self.parent
                menu = self.open_menu(tab.key)
                self.drain_events()
                entry = self.rename_entry(menu)
                self.assertIsNotNone(entry)
                entry.emit("clicked")
                self.dialog.show_note_rename_dialog.assert_not_called()
                self.assertFalse(menu.get_visible())
                self.drain_events(wait_for_rename=True)
                self.dialog.show_note_rename_dialog.assert_called_once_with(
                    tab.title, self.dialog.on_editor_tab_rename_response, tab.key,
                )
                self.dialog.show_note_rename_dialog.reset_mock()
                self.assertIs(menu.get_parent(), self.bar)
                self.assertEqual(self.dialog.active_editor_tab_key, "active")
                self.assertEqual((self.other.content, self.other.dirty), ("Unsaved text", True))
                self.assertEqual((self.tab.category, self.tab.server_id, self.tab.content),
                                 ("Ops", "server-one", "Body"))

    def test_rename_is_disabled_in_read_only_or_locked_storage(self):
        for flag in ("read_only", "encryption_locked"):
            with self.subTest(flag=flag), patch.object(self.dialog.store, flag, True):
                menu = self.open_menu()
                self.drain_events()
                self.assertFalse(self.rename_entry(menu).is_sensitive())
                menu.activate_action("note-tab.rename", None)
                self.drain_events()
                self.dialog.show_note_rename_dialog.assert_not_called()
                self.dialog.close_note_tab_context_menu()
                self.drain_events()

    def test_popup_survives_real_modal_dialog_and_can_be_disposed_after_cancel(self):
        self.dialog.show_note_rename_dialog = NotesDialogs.show_note_rename_dialog.__get__(self.dialog)
        menu = self.open_menu()
        self.drain_events()
        self.rename_entry(menu).emit("clicked")
        self.drain_events(wait_for_rename=True)
        dialogs = [window for window in Gtk.Window.list_toplevels()
                   if window.get_visible() and window.get_transient_for() is self.window]
        self.assertEqual(len(dialogs), 1)
        self.addCleanup(dialogs[0].destroy)
        self.assertFalse(menu.get_visible())
        self.assertIs(menu.get_parent(), self.bar)
        dialogs[0].get_widget_for_response(Gtk.ResponseType.CANCEL).emit("clicked")
        self.drain_events()
        self.assertIs(menu.get_parent(), self.bar)
        self.dialog.dispose_note_tab_context_menu()
        self.assertIsNone(menu.get_parent())
        self.assertEqual(self.tab.title, "Clicked note")

    def test_pending_rename_rejects_stale_tabs_windows_and_permissions(self):
        for condition in ("removed", "replaced", "new-label", "hidden", "new-window",
                          "unparented", "read_only", "encryption_locked"):
            with self.subTest(condition=condition):
                menu = self.open_menu()
                self.drain_events()
                self.rename_entry(menu).emit("clicked")
                if condition == "removed":
                    self.dialog.editor_tabs.pop(self.tab.key)
                elif condition == "replaced":
                    self.dialog.editor_tabs[self.tab.key] = self.other
                elif condition == "new-label":
                    self.tab.container_widget = Gtk.Box()
                elif condition == "hidden":
                    self.window.set_visible(False)
                elif condition == "new-window":
                    self.dialog.window = None
                elif condition == "unparented":
                    self.bar.remove(self.parent)
                else:
                    setattr(self.dialog.store, condition, True)
                self.drain_events(wait_for_rename=True)
                self.dialog.show_note_rename_dialog.assert_not_called()
                self.dialog.editor_tabs[self.tab.key] = self.tab
                self.tab.container_widget = self.parent
                self.dialog.window = self.window
                self.window.present()
                if self.parent.get_parent() is None:
                    self.bar.append(self.parent)
                self.dialog.store.read_only = self.dialog.store.encryption_locked = False

    def test_reopening_reuses_popup_without_clearing_the_new_target(self):
        old = self.open_menu()
        new = self.open_menu(x=180)
        self.drain_events()
        self.assertIs(old, new)
        self.assertIs(old.get_parent(), self.bar)
        self.assertIs(self.dialog.tab_context_popover, new)
        new.activate_action("note-tab.rename", None)
        self.drain_events(wait_for_rename=True)
        self.dialog.show_note_rename_dialog.assert_called_once_with(
            self.tab.title, self.dialog.on_editor_tab_rename_response, self.tab.key,
        )

    def test_missing_or_replaced_tab_cannot_dispatch_old_menu(self):
        self.dialog.show_note_tab_context_menu("missing")
        self.assertIsNone(self.dialog.tab_context_popover)
        menu = self.open_menu()
        self.dialog.editor_tabs[self.tab.key] = self.other
        menu.activate_action("note-tab.rename", None)
        self.drain_events()
        self.dialog.show_note_rename_dialog.assert_not_called()


class CategoryContextMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        self.host = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.button = Gtk.Button(label="Ops")
        self.button.set_size_request(260, 36)
        self.panel.append(self.button)
        self.host.append(self.panel)
        self.window.set_child(self.host)
        self.window.present()
        self.dialog = NotesDialogs.__new__(NotesDialogs)
        self.dialog.window = self.window
        self.dialog.notes_list_panel = self.panel
        self.dialog.category_context_popover = None
        self.categories = {("Ops", None), ("Ops", "server-one")}
        self.dialog.store = SimpleNamespace(
            read_only=False, encryption_locked=False,
            has_note_category=lambda name, server_id=None: (name, server_id) in self.categories,
        )
        self.labels = {"rename": "Rename category", "duplicate": "Duplicate category",
                       "delete": "Delete category"}
        self.dialog.translate = lambda key: self.labels[key.removeprefix("notes_category_")]
        self.dialog.prompt_category_edit = MagicMock()
        self.dialog.confirm_delete_category = MagicMock()
        self.addCleanup(self.destroy_window)
        self.drain_events()

    drain_events = staticmethod(NoteTabContextMenuTests.drain_events)

    def destroy_window(self):
        self.dialog.dispose_category_context_menu()
        self.drain_events()
        self.window.destroy()

    def entry(self, widget, name):
        if isinstance(widget, Gtk.Label) and widget.get_label() == self.labels[name]:
            return widget.get_parent()
        child = widget.get_first_child()
        while child is not None:
            found = self.entry(child, name)
            if found is not None:
                return found
            child = child.get_next_sibling()
        return None

    def open_menu(self, scope=None, position=None):
        self.dialog.show_category_context_menu("Ops", self.button, scope, position)
        menu = self.dialog.category_context_popover
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        return menu

    def test_pointer_anchor_keyboard_anchor_order_reuse_and_disposal(self):
        gesture = MagicMock()
        self.dialog.on_category_context_pressed(gesture, 1, 19, 10, "Ops", self.button)
        gesture.set_state.assert_called_once_with(Gtk.EventSequenceState.CLAIMED)
        menu = self.dialog.category_context_popover
        _, point = self.button.compute_point(self.host, Graphene.Point().init(19, 10))
        _, rect = menu.get_pointing_to()
        self.assertEqual((rect.x, rect.y), (int(point.x), int(point.y)))
        model = menu.get_menu_model()
        self.assertEqual([model.get_item_attribute_value(i, "label", None).unpack()
                          for i in range(model.get_n_items())], list(self.labels.values()))
        menu.popdown()
        self.drain_events()
        self.assertTrue(self.dialog.on_category_context_key_pressed(
            None, Gdk.KEY_F10, 0, Gdk.ModifierType.SHIFT_MASK,
            "Ops", self.button, "server-one",
        ))
        self.assertIs(self.dialog.category_context_popover, menu)
        _, point = self.button.compute_point(self.host, Graphene.Point().init(
            self.button.get_width() / 2, self.button.get_height() / 2,
        ))
        _, rect = menu.get_pointing_to()
        self.assertEqual((rect.x, rect.y), (int(point.x), int(point.y)))
        self.dialog.dispose_category_context_menu()
        self.assertIsNone(menu.get_parent())
        self.assertIs(self.button.get_parent(), self.panel)

    def test_native_entries_dispatch_each_action_in_its_scope_after_closing(self):
        for scope in (None, "server-one"):
            for action in self.labels:
                with self.subTest(scope=scope, action=action):
                    menu = self.open_menu(scope)
                    self.entry(menu, action).emit("clicked")
                    self.assertFalse(menu.get_visible())
                    self.dialog.prompt_category_edit.assert_not_called()
                    self.dialog.confirm_delete_category.assert_not_called()
                    self.drain_events(wait_for_rename=True)
                    if action == "delete":
                        self.dialog.confirm_delete_category.assert_called_once_with("Ops", scope)
                        self.dialog.prompt_category_edit.assert_not_called()
                    else:
                        self.dialog.prompt_category_edit.assert_called_once_with(action, "Ops", scope)
                        self.dialog.confirm_delete_category.assert_not_called()
                    self.dialog.prompt_category_edit.reset_mock()
                    self.dialog.confirm_delete_category.reset_mock()

    def test_permissions_disable_all_native_commands(self):
        for read_only, locked in ((True, False), (False, True), (True, True)):
            self.dialog.store.read_only = read_only
            self.dialog.store.encryption_locked = locked
            menu = self.open_menu()
            for action in self.labels:
                self.assertFalse(self.entry(menu, action).is_sensitive())
                menu.activate_action(f"note-category.{action}", None)
            menu.popdown()
            self.drain_events(wait_for_rename=True)
        self.dialog.prompt_category_edit.assert_not_called()
        self.dialog.confirm_delete_category.assert_not_called()

    def test_pending_action_rejects_stale_scope_window_panel_and_permissions(self):
        for reason in ("missing", "readonly", "locked", "hidden", "window", "panel"):
            with self.subTest(reason=reason):
                menu = self.open_menu("server-one")
                self.entry(menu, "delete").emit("clicked")
                if reason == "missing":
                    self.categories.remove(("Ops", "server-one"))
                elif reason == "readonly":
                    self.dialog.store.read_only = True
                elif reason == "locked":
                    self.dialog.store.encryption_locked = True
                elif reason == "hidden":
                    self.window.set_visible(False)
                elif reason == "window":
                    self.dialog.window = None
                else:
                    self.host.remove(self.panel)
                self.drain_events(wait_for_rename=True)
                self.dialog.confirm_delete_category.assert_not_called()
                self.categories.add(("Ops", "server-one"))
                self.dialog.store.read_only = self.dialog.store.encryption_locked = False
                self.dialog.window = self.window
                self.window.present()
                if self.panel.get_parent() is None:
                    self.host.append(self.panel)
                self.drain_events()

    def test_tree_rebuild_preserves_menu_target_and_new_open_survives_old_close(self):
        menu = self.open_menu("server-one")
        self.panel.remove(self.button)
        self.button = Gtk.Button(label="Ops rebuilt")
        self.panel.append(self.button)
        self.entry(menu, "rename").emit("clicked")
        self.drain_events(wait_for_rename=True)
        self.dialog.prompt_category_edit.assert_called_once_with("rename", "Ops", "server-one")
        self.dialog.prompt_category_edit.reset_mock()
        self.open_menu("server-one")
        menu.popdown()
        self.open_menu(None)
        self.drain_events()
        self.entry(menu, "duplicate").emit("clicked")
        self.drain_events(wait_for_rename=True)
        self.dialog.prompt_category_edit.assert_called_once_with("duplicate", "Ops", None)

    def test_missing_category_does_not_open_menu(self):
        self.dialog.show_category_context_menu("missing", self.button)
        self.dialog.show_category_context_menu("Ops", self.button, "other-server")
        self.assertIsNone(self.dialog.category_context_popover)

    def test_real_category_dialog_cancel_keeps_popup_reusable(self):
        self.dialog.prompt_category_edit = NotesDialogs.prompt_category_edit.__get__(self.dialog)
        self.dialog.ensure_writable = lambda: True
        self.dialog.save_active_editor_if_valid = lambda: True
        self.dialog.translate = lambda key: key
        menu = self.open_menu()
        menu.activate_action("note-category.rename", None)
        self.drain_events(wait_for_rename=True)
        dialogs = [window for window in Gtk.Window.list_toplevels()
                   if isinstance(window, Gtk.Dialog) and window.get_transient_for() is self.window]
        self.assertEqual(len(dialogs), 1)
        dialogs[0].response(Gtk.ResponseType.CANCEL)
        self.drain_events()
        self.assertIs(self.open_menu("server-one"), menu)


class NoteListContextMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        self.window.set_default_size(320, 240)
        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.panel.append(Gtk.Label(label="Notes list"))
        self.host = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.host.append(Gtk.Label(label="Notes workspace"))
        self.host.append(self.panel)
        self.window.set_child(self.host)
        self.addCleanup(self.destroy_window)
        self.notes = [Note("one", "First note", "First body"),
                      Note("two", "Second note", "Second body", "Ops", "server-one")]
        self.original_notes = tuple(self.notes)
        self.dialog = NotesDialogs.__new__(NotesDialogs)
        self.dialog.window = self.window
        self.dialog.notes_list_panel = self.panel
        self.dialog.notes_context_popover = None
        self.dialog.selected_note_id = "one"
        self.dialog.selected_draft_key = None
        self.dialog.active_editor_tab_key = "one"
        self.dialog.scope_mode = "personal"
        self.dialog.server_filter_id = None
        self.dialog.loading_note_list = False
        self.dialog.set_notes_scope = MagicMock()
        self.dialog.store = SimpleNamespace(
            read_only=False, encryption_locked=False, data=SimpleNamespace(notes=self.notes),
        )
        self.labels = {"edit": "Edit", "rename": "Rename", "clone": "Clone",
                       "properties": "Properties", "delete": "Delete"}
        self.dialog.translate = lambda key: self.labels[key.removeprefix("notes_")]
        self.tree_root = Gio.ListStore.new(NotesTreeNode)
        self.dialog.notes_tree_model = Gtk.TreeListModel.new(
            self.tree_root, False, False, self.dialog.create_note_tree_children,
        )
        self.dialog.notes_tree_selection = Gtk.SingleSelection.new(self.dialog.notes_tree_model)
        self.dialog.notes_tree_selection.set_autoselect(False)
        self.dialog.notes_tree_selection.set_can_unselect(True)
        self.dialog.notes_tree_selection.connect("notify::selected-item", self.dialog.on_note_tree_selected)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.dialog.setup_note_tree_item)
        factory.connect("bind", self.dialog.bind_note_tree_item)
        factory.connect("unbind", self.dialog.unbind_note_tree_item)
        self.notes_list = Gtk.ListView.new(self.dialog.notes_tree_selection, factory)
        self.dialog.notes_list = self.notes_list
        self.panel.append(self.notes_list)
        self.window.present()
        self.commands = {name: MagicMock() for name in self.labels}
        for name, method in (("edit", "load_editor"), ("rename", "prompt_note_rename"),
                             ("clone", "clone_note"), ("properties", "show_note_properties"),
                             ("delete", "confirm_delete_note")):
            setattr(self.dialog, method, self.commands[name])
        self.rows = [self.make_row(note) for note in self.notes]
        self.drain_events()

    drain_events = staticmethod(NoteTabContextMenuTests.drain_events)

    def make_row(self, note):
        self.tree_root.append(NotesTreeNode(
            "note", note.title, note_id=note.id, category=note.category, server_id=note.server_id,
        ))
        self.drain_events()
        return self.row_for_note(note.id)

    def row_for_note(self, note_id):
        pending = [self.notes_list]
        while pending:
            widget = pending.pop()
            if isinstance(widget, Gtk.TreeExpander):
                content = widget.get_child()
                if getattr(content, "note_id", None) == note_id:
                    return content
            child = widget.get_first_child()
            while child is not None:
                pending.append(child)
                child = child.get_next_sibling()
        self.fail(f"Native row not bound for {note_id}")

    def destroy_window(self):
        self.dialog.dispose_note_context_menu()
        self.drain_events()
        self.window.destroy()

    def open_menu(self, row=None, x=20, y=12):
        gesture = MagicMock()
        row = row or self.row_for_note("two")
        self.dialog.on_note_tree_context_pressed(gesture, 1, x, y, row, row.note_id)
        gesture.set_state.assert_called_once_with(Gtk.EventSequenceState.CLAIMED)
        self.drain_events()
        menu = self.dialog.notes_context_popover
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        return menu

    def entry(self, widget, name):
        if isinstance(widget, Gtk.Label) and widget.get_label() == self.labels[name]:
            return widget.get_parent()
        child = widget.get_first_child()
        while child is not None:
            found = self.entry(child, name)
            if found is not None:
                return found
            child = child.get_next_sibling()
        return None

    def reset_commands(self):
        for command in self.commands.values():
            command.reset_mock()

    def test_click_anchor_order_reuse_and_disposal(self):
        previous = None
        for x in (8, 180):
            with self.subTest(x=x):
                valid, point = self.row_for_note("two").compute_point(self.host, Graphene.Point().init(x, 12))
                self.assertTrue(valid)
                menu = self.open_menu(x=x)
                if previous is not None:
                    self.assertIs(menu, previous)
                model = menu.get_menu_model()
                self.assertEqual([model.get_item_attribute_value(i, "label", None).unpack()
                                  for i in range(model.get_n_items())], list(self.labels.values()))
                valid, rect = menu.get_pointing_to()
                self.assertTrue(valid)
                self.assertEqual((rect.x, rect.y, rect.width, rect.height),
                                 (int(point.x), int(point.y), 1, 1))
                menu.popdown()
                self.drain_events()
                self.assertIsNone(self.dialog.notes_context_popover)
                self.assertIs(menu.get_parent(), self.host)
                previous = menu
        self.dialog.dispose_note_context_menu()
        self.assertIsNone(menu.get_parent())
        self.assertEqual(self.tree_root.get_n_items(), 2)
        self.assertEqual([self.tree_root.get_item(i).note_id for i in range(2)], ["one", "two"])

    def test_native_entries_defer_each_command_for_the_clicked_note(self):
        for name, command in self.commands.items():
            with self.subTest(action=name):
                menu = self.open_menu()
                self.entry(menu, name).emit("clicked")
                self.assertFalse(menu.get_visible())
                for other in self.commands.values():
                    other.assert_not_called()
                self.drain_events(wait_for_rename=True)
                command.assert_called_once_with(self.notes[1] if name == "edit" else "two")
                for other_name, other in self.commands.items():
                    if other_name != name:
                        other.assert_not_called()
                self.assertEqual(self.dialog.active_editor_tab_key, "one")
                self.assertEqual(self.notes[1].content, "Second body")
                self.reset_commands()

    def test_native_permissions_keep_only_properties_in_read_only_and_none_when_locked(self):
        for read_only, locked in ((False, False), (True, False), (False, True), (True, True)):
            for name, command in self.commands.items():
                with self.subTest(read_only=read_only, locked=locked, action=name):
                    self.dialog.store.read_only = read_only
                    self.dialog.store.encryption_locked = locked
                    menu = self.open_menu()
                    enabled = not locked and (name == "properties" or not read_only)
                    self.assertEqual(self.entry(menu, name).is_sensitive(), enabled)
                    menu.activate_action(f"note-list.{name}", None)
                    self.drain_events(wait_for_rename=enabled)
                    if enabled:
                        command.assert_called_once_with(self.notes[1] if name == "edit" else "two")
                    else:
                        for other in self.commands.values():
                            other.assert_not_called()
                    self.dialog.close_note_context_menu()
                    self.drain_events()
                    self.reset_commands()

    def test_pending_delete_rechecks_target_window_panel_and_permissions(self):
        for condition in ("deleted", "locked", "read-only", "hidden", "new-window", "panel-removed"):
            with self.subTest(condition=condition):
                menu = self.open_menu()
                self.entry(menu, "delete").emit("clicked")
                if condition == "deleted":
                    self.notes.pop()
                elif condition == "locked":
                    self.dialog.store.encryption_locked = True
                elif condition == "read-only":
                    self.dialog.store.read_only = True
                elif condition == "hidden":
                    self.window.set_visible(False)
                elif condition == "new-window":
                    self.dialog.window = None
                else:
                    self.host.remove(self.panel)
                self.drain_events(wait_for_rename=True)
                self.commands["delete"].assert_not_called()
                # Restore the same original identities for the next case.
                self.notes[:] = self.original_notes
                self.dialog.store.encryption_locked = self.dialog.store.read_only = False
                self.dialog.window = self.window
                if self.panel.get_parent() is None:
                    self.host.append(self.panel)
                self.window.present()

    def test_regular_saves_before_and_after_activation_keep_the_persisted_note_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(
                root / "connections.json", root / "settings.json", root / "statistics.json",
                root / "lock", root / "history",
            )
            self.addCleanup(store.close)
            note = store.add_note("Saved sample", "Original body", "", None)
            self.dialog.store = store
            row = self.make_row(note)
            for timing in ("before-activation", "after-activation"):
                with self.subTest(timing=timing):
                    menu = self.open_menu(row)
                    previous = self.dialog.find_note(note.id)
                    if timing == "after-activation":
                        self.entry(menu, "edit").emit("clicked")
                    store.update_note(note.id, "Saved title", timing, "", None)
                    updated = self.dialog.find_note(note.id)
                    self.assertIsNot(updated, previous)
                    if timing == "before-activation":
                        self.entry(menu, "edit").emit("clicked")
                    self.drain_events(wait_for_rename=True)
                    self.commands["edit"].assert_called_once_with(updated)
                    self.assertEqual(updated.content, timing)
                    self.reset_commands()

    def test_selection_can_rebuild_the_clicked_row_without_losing_target_or_anchor(self):
        original = self.row_for_note("two")
        valid, point = original.compute_point(self.host, Graphene.Point().init(90, 12))
        self.assertTrue(valid)
        replacement = []

        def rebuild(selection, _param):
            selected = selection.get_selected_item()
            if not replacement and selected is not None and selected.get_item().note_id == "two":
                node = NotesTreeNode("note", "Rebuilt second", note_id="two", server_id="server-one")
                replacement.append(node)
                self.tree_root.splice(1, 1, [node])
                selection.set_selected(1)

        self.dialog.notes_tree_selection.connect("notify::selected-item", rebuild)
        menu = self.open_menu(original, x=90)
        self.assertIs(self.dialog.notes_tree_selection.get_selected_item().get_item(), replacement[0])
        valid, rect = menu.get_pointing_to()
        self.assertTrue(valid)
        self.assertEqual((rect.x, rect.y), (int(point.x), int(point.y)))
        self.entry(menu, "properties").emit("clicked")
        self.drain_events(wait_for_rename=True)
        self.commands["properties"].assert_called_once_with("two")

    def test_reopening_retains_new_target_and_properties_allow_late_read_only(self):
        old = self.open_menu()
        new = self.open_menu(self.rows[0])
        self.assertIs(old, new)
        self.drain_events()
        self.entry(new, "properties").emit("clicked")
        self.dialog.store.read_only = True
        self.drain_events(wait_for_rename=True)
        self.commands["properties"].assert_called_once_with("one")

    def test_missing_notes_and_draft_rows_do_not_open_a_menu(self):
        for note_id in (None, "deleted"):
            row = Gtk.Box()
            row.note_id = note_id
            self.dialog.show_note_context_menu(row)
            self.assertIsNone(self.dialog.notes_context_popover)


class NotesDialogSignalTests(unittest.TestCase):
    def test_notes_window_title_reflects_server_scope(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        titles = []
        dialog.window = SimpleNamespace(set_title=titles.append)
        dialog.store = SimpleNamespace(
            data=SimpleNamespace(servers=[SimpleNamespace(id="server-id", name="Build host")])
        )
        dialog.translate = lambda key: {
            "notes_title": "Notes",
            "notes_for_server": "Notes for {name}",
            "notes_unknown_server": "Unavailable server",
        }[key]

        dialog.scope_mode = "server"
        dialog.update_window_title("server-id")
        dialog.scope_mode = "personal"
        dialog.update_window_title(None)

        self.assertEqual(titles, ["Notes for Build host", "Notes"])

    def test_notes_window_title_handles_missing_server(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        titles = []
        dialog.window = SimpleNamespace(set_title=titles.append)
        dialog.store = SimpleNamespace(data=SimpleNamespace(servers=[]))
        dialog.scope_mode = "server"
        dialog.translate = lambda key: {
            "notes_title": "Notes",
            "notes_server_scope": "Servers",
            "notes_for_server": "Notes for {name}",
            "notes_unknown_server": "Unavailable server",
        }[key]

        dialog.update_window_title("missing-server")

        self.assertEqual(titles, ["Notes for Unavailable server"])

    def test_notes_header_controls_use_sidebar_alignment_inset(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.window = None
        dialog.parent = MagicMock()
        dialog.store = SimpleNamespace(read_only=False, encryption_locked=False, data=SimpleNamespace(servers=[]))
        dialog.scope_mode = "personal"
        dialog.server_filter_id = None
        dialog.scope_mode = "personal"
        dialog.translate = lambda key: key
        dialog.build_creation_controls = MagicMock()
        dialog.build_editor_toolbar = MagicMock()
        dialog.update_notes_list_toggle = MagicMock()
        dialog.update_note_detail_inset = MagicMock()
        dialog.configure_write_controls = MagicMock()
        dialog.set_editor_enabled = MagicMock()
        boxes = []
        buttons = [MagicMock() for _ in range(5)]

        with patch("termia.notes_dialogs.Gtk") as gtk, patch(
            "termia.notes_dialogs.create_notes_text_view"
        ):
            gtk.Button.side_effect = buttons

            def make_box(**_kwargs):
                box = MagicMock()
                boxes.append(box)
                return box

            gtk.Box.side_effect = make_box
            dialog.ensure_window()

        boxes[0].set_margin_start.assert_called_once_with(8)
        gtk.Window.assert_called_once_with(title="notes_title", application=dialog.parent.get_application())
        gtk.Window.return_value.set_modal.assert_called_once_with(False)
        gtk.HeaderBar.return_value.set_show_title_buttons.assert_called_once_with(True)
        gtk.HeaderBar.return_value.pack_start.assert_called_once_with(boxes[0])
        self.assertEqual(boxes[0].append.call_args_list[1], call(dialog.add_button))
        self.assertEqual(boxes[0].append.call_args_list[2], call(dialog.import_export_menu_button))
        buttons[1].add_css_class.assert_not_called()
        dialog.save_button.add_css_class.assert_not_called()

    def test_category_and_bulk_navigation_controls_above_search(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.server_filter_id = None
        dialog.scope_mode = "personal"
        dialog.add_button = None
        dialog.translate = lambda key: key
        category_button = MagicMock()
        expand_button, collapse_button = MagicMock(), MagicMock()

        with patch("termia.notes_dialogs.Gtk") as gtk:
            gtk.Button.side_effect = [category_button, expand_button, collapse_button]
            controls = dialog.build_creation_controls()

        controls.set_halign.assert_called_once_with(gtk.Align.START)
        self.assertEqual(
            [call.args[0] for call in controls.append.call_args_list],
            [category_button, expand_button, collapse_button],
        )
        category_button.set_tooltip_text.assert_called_once_with("notes_category_add")
        expand_button.set_tooltip_text.assert_called_once_with("notes_expand_all")
        collapse_button.set_tooltip_text.assert_called_once_with("notes_collapse_all")

    def test_only_named_category_rows_get_context_menu_controls(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        dialog = make_note_tree_dialog()
        for category in ("Ops", ""):
            with self.subTest(category=category):
                content = bind_note_tree_node(self, dialog, NotesTreeNode(
                    "category", category or "Uncategorized", category=category,
                ))
                controllers = content.observe_controllers()
                items = [controllers.get_item(i) for i in range(controllers.get_n_items())]
                context_clicks = [item for item in items
                                  if isinstance(item, Gtk.GestureClick) and item.get_button() == 3]
                keys = [item for item in items if isinstance(item, Gtk.EventControllerKey)]
                self.assertEqual(len(context_clicks), int(bool(category)))
                self.assertEqual(len(keys), int(bool(category)))

    def test_category_context_menu_has_keyboard_shortcuts(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.show_category_context_menu = MagicMock()
        button = MagicMock()

        self.assertTrue(dialog.on_category_context_key_pressed(
            None, Gdk.KEY_Menu, 0, Gdk.ModifierType(0), "Ops", button,
        ))
        self.assertTrue(dialog.on_category_context_key_pressed(
            None, Gdk.KEY_F10, 0, Gdk.ModifierType.SHIFT_MASK, "Ops", button,
        ))
        self.assertFalse(dialog.on_category_context_key_pressed(
            None, Gdk.KEY_F10, 0, Gdk.ModifierType(0), "Ops", button,
        ))
        self.assertEqual(dialog.show_category_context_menu.call_count, 2)

    def test_servers_tree_root_selects_server_scope_without_a_picker(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.scope_mode = "personal"
        dialog.expanded_note_sections = {"personal"}
        dialog.expanded_server_groups = set()
        dialog.set_notes_scope = MagicMock()

        dialog.on_note_section_clicked("servers")

        dialog.set_notes_scope.assert_called_once_with("server", None)

    def test_server_tree_node_selects_its_server_scope(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.scope_mode = "personal"
        dialog.server_filter_id = None
        dialog.expanded_server_groups = set()
        dialog.set_notes_scope = MagicMock()

        dialog.on_server_tree_node_clicked("server-id")

        self.assertEqual(dialog.expanded_server_groups, {"server-id"})
        dialog.set_notes_scope.assert_called_once_with("server", "server-id")

    def test_creation_controls_enable_only_after_a_server_is_selected(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.scope_mode = "server"
        dialog.server_filter_id = None
        dialog.store = SimpleNamespace(read_only=False, encryption_locked=False)
        dialog.add_button = MagicMock()
        dialog.category_add_button = MagicMock()
        dialog.translate = lambda key: key

        dialog.update_creation_controls()

        dialog.add_button.set_sensitive.assert_called_with(False)
        dialog.category_add_button.set_sensitive.assert_called_with(False)

        dialog.server_filter_id = "server-id"
        dialog.update_creation_controls()

        dialog.add_button.set_sensitive.assert_called_with(True)
        dialog.category_add_button.set_sensitive.assert_called_with(True)

    def test_category_prompt_preselects_name_for_rename_and_duplicate(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            data=SimpleNamespace(note_categories=[NoteCategory("Ops")]),
            has_note_category=lambda name, server_id=None: name == "Ops" and server_id is None,
        )
        dialog.translate = lambda key: "copy" if key == "snippet_copy_suffix" else key
        dialog.ensure_writable = lambda: True
        dialog.save_active_editor_if_valid = lambda: True
        dialog.window = MagicMock()

        with patch("termia.notes_dialogs.Gtk") as gtk:
            dialog.prompt_category_edit("rename", "Ops")
            gtk.Entry.return_value.set_text.assert_called_with("Ops")
            dialog.prompt_category_edit("duplicate", "Ops")
            gtk.Entry.return_value.set_text.assert_called_with("Ops copy")
            dialog.prompt_category_edit("add")
            gtk.Dialog.assert_called_with(
                title="notes_category_add", transient_for=dialog.window, modal=True,
            )
            gtk.Entry.return_value.set_placeholder_text.assert_called_with("notes_category_name")

    def test_confirmed_category_delete_updates_open_tabs_and_list(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = MagicMock()
        dialog.store.data.note_categories = [NoteCategory("Ops")]
        dialog.store.data.notes = [SimpleNamespace(category="Ops", server_id=None)]
        dialog.store.has_note_category.return_value = True
        dialog.translate = lambda key: "{name}: {count}" if key == "notes_category_delete_confirm" else key
        dialog.ensure_writable = lambda: True
        dialog.save_active_editor_if_valid = lambda: True
        dialog.window = MagicMock()
        dialog.sync_open_note_categories = MagicMock()
        dialog.refresh_current_editor_metadata = MagicMock()
        dialog.refresh_list = MagicMock()

        with patch("termia.notes_dialogs.Gtk") as gtk:
            dialog.confirm_delete_category("Ops")
            gtk.AlertDialog.assert_called_once_with(message="Ops: 1")
            gtk.AlertDialog.return_value.choose.assert_called_once_with(
                dialog.window, None, dialog.on_delete_category_response, "Ops", None,
            )

        result = MagicMock()
        result.choose_finish.return_value = 1
        dialog.on_delete_category_response(result, None, "Ops")

        dialog.store.delete_note_category.assert_called_once_with("Ops", None)
        dialog.sync_open_note_categories.assert_called_once()
        dialog.refresh_list.assert_called_once()

    def test_category_name_response_uses_the_matching_store_operation(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = MagicMock()
        dialog.store.data.note_categories = [NoteCategory("Ops")]
        dialog.store.has_note_category.return_value = True
        dialog.ensure_writable = lambda: True
        dialog.save_active_editor_if_valid = lambda: True
        dialog.sync_open_note_categories = MagicMock()
        dialog.refresh_current_editor_metadata = MagicMock()
        dialog.refresh_list = MagicMock()
        source = MagicMock()

        for mode, original, name, operation in (
            ("add", None, "New", "add_note_category"),
            ("rename", "Ops", "Runbooks", "rename_note_category"),
            ("duplicate", "Ops", "Ops copy", "duplicate_note_category"),
        ):
            with self.subTest(mode=mode):
                entry = SimpleNamespace(get_text=lambda value=name: value)
                dialog.on_category_edit_response(
                    source, Gtk.ResponseType.OK, entry, mode, original,
                )
                args = (name, None) if mode == "add" else (original, name, None)
                getattr(dialog.store, operation).assert_called_once_with(*args)
                dialog.store.reset_mock()

        self.assertEqual(dialog.refresh_list.call_count, 3)
        self.assertEqual(dialog.sync_open_note_categories.call_count, 3)

    def test_category_rename_updates_open_tab_category(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        tab = NoteEditorTab("note-id", "note-id", "Runbook", "Ops", None, "Saved")
        dialog.editor_tabs = {tab.key: tab}
        dialog.find_note = lambda note_id: SimpleNamespace(category="Runbooks")

        dialog.sync_open_note_categories()

        self.assertEqual(tab.category, "Runbooks")

    def test_closing_clean_editor_tab_removes_only_that_tab(self):
        tab = NoteEditorTab("note-id", "note-id", "Runbook", "", None, "Saved")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        removed = []
        dialog.remove_editor_tab = removed.append

        dialog.close_editor_tab(tab.key)

        self.assertEqual(removed, [tab.key])

    def test_footer_close_uses_active_tab_close_flow(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        closed = []
        dialog.close_editor_tab = closed.append
        dialog.active_editor_tab_key = "note-id"

        dialog.close_active_editor_tab()
        dialog.active_editor_tab_key = None
        dialog.close_active_editor_tab()

        self.assertEqual(closed, ["note-id"])

    def test_remove_editor_tab_removes_its_notebook_page(self):
        tab = NoteEditorTab("note-id", "note-id", "Runbook", "", None, "Saved")
        removed = []
        page = object()
        tab.page_widget = page

        class Notebook:
            def page_num(self, widget):
                return 0 if widget is page else -1

            def remove_page(self, index):
                removed.append(index)

        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = "another-tab"
        dialog.editor_notebook = Notebook()

        dialog.remove_editor_tab(tab.key)

        self.assertEqual(removed, [0])
        self.assertEqual(dialog.editor_tabs, {})

    def test_closing_dirty_editor_tab_offers_save_discard_or_keep(self):
        tab = NoteEditorTab("draft-1", None, "Draft", "", None, "Unsaved", dirty=True)
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = None
        dialog.translate = lambda key: key
        dialog.window = object()
        selected = []

        class Alert:
            def __init__(self, message):
                selected.append(("message", message))

            def set_buttons(self, buttons):
                selected.append(("buttons", buttons))

            def set_cancel_button(self, index):
                selected.append(("cancel", index))

            def set_default_button(self, index):
                selected.append(("default", index))

            def choose(self, parent, _cancellable, callback, key):
                selected.append(("choose", parent, callback, key))

        with patch("termia.notes_dialogs.Gtk.AlertDialog", Alert):
            dialog.close_editor_tab(tab.key)

        self.assertEqual(selected[0], ("message", "notes_close_unsaved_message"))
        self.assertEqual(selected[1], (
            "buttons", ["notes_save_and_close", "notes_close_without_saving", "notes_keep_editing"]
        ))
        self.assertEqual(selected[2], ("cancel", 2))
        self.assertEqual(selected[3], ("default", 2))
        self.assertEqual(selected[4][0], "choose")
        self.assertIs(selected[4][2].__func__, NotesDialogs.on_close_editor_tab_response)
        self.assertEqual(selected[4][3], tab.key)

    def test_close_tab_responses_route_to_save_discard_or_keep(self):
        for response, expected in ((0, "save"), (1, "discard"), (2, "keep")):
            with self.subTest(response=response):
                dialog = NotesDialogs.__new__(NotesDialogs)
                calls = []

                class Alert:
                    def choose_finish(self, _result):
                        return response

                dialog.save_editor_tab_and_close = lambda key: calls.append(("save", key))
                dialog.remove_editor_tab = lambda key: calls.append(("discard", key))
                dialog.on_close_editor_tab_response(Alert(), None, "note-id")

                self.assertEqual(calls, [] if expected == "keep" else [(expected, "note-id")])

    def test_save_and_close_persists_inactive_draft_before_removing_tab(self):
        note = Note("saved-id", "Draft", "Content", "Ops", "server-id", "created", "modified")
        tab = NoteEditorTab("draft-1", None, "Draft", "Ops", "server-id", "Content", dirty=True)
        added = []
        removed = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = None
        dialog.current_note_id = None
        dialog.editor_dirty = False
        dialog.selected_note_id = None
        dialog.store = SimpleNamespace(add_note=lambda *args: (added.append(args), note)[1])
        dialog.translate = lambda key: key
        dialog.find_note = lambda note_id: note if note_id == note.id else None
        dialog.update_editor_tab_label = lambda _tab: None
        dialog.refresh_list = lambda note_id: None
        dialog.remove_editor_tab = removed.append

        dialog.save_editor_tab_and_close(tab.key)

        self.assertEqual(added, [("Draft", "Content", "Ops", "server-id")])
        self.assertEqual(tab.note_id, note.id)
        self.assertFalse(tab.dirty)
        self.assertEqual(dialog.selected_note_id, note.id)
        self.assertEqual(removed, [tab.key])

    def test_editor_autosaves_nonempty_content_without_a_title_field(self):
        calls = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.loading_editor = False
        dialog.editor_dirty = False
        dialog.editor_content = lambda: "Some note text"
        dialog.status_label = SimpleNamespace(set_label=lambda _value: None)
        dialog.translate = lambda key: key
        dialog.cancel_autosave = lambda: calls.append("cancel")
        dialog.schedule_autosave = lambda: calls.append("schedule")
        dialog.capture_active_editor_tab = lambda: calls.append("capture")

        dialog.on_editor_changed()

        self.assertEqual(calls, ["schedule", "capture"])
        self.assertTrue(dialog.editor_dirty)

    def test_empty_editor_is_not_saved(self):
        calls = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.loading_editor = False
        dialog.editor_dirty = False
        dialog.editor_content = lambda: "   "
        dialog.status_label = SimpleNamespace(set_label=calls.append)
        dialog.translate = lambda key: key
        dialog.cancel_autosave = lambda: calls.append("cancel")
        dialog.schedule_autosave = lambda: calls.append("schedule")
        dialog.capture_active_editor_tab = lambda: calls.append("capture")

        dialog.on_editor_changed()

        self.assertEqual(calls, ["cancel", "notes_empty_not_saved", "capture"])
        self.assertTrue(dialog.editor_dirty)

    def test_notes_list_toggle_updates_icon_and_tooltip(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        calls = []
        dialog.notes_list_visible = True
        dialog.translate = lambda key: key
        dialog.toggle_notes_list_button = SimpleNamespace(
            set_icon_name=lambda name: calls.append(("icon", name)),
            set_tooltip_text=lambda text: calls.append(("tooltip", text)),
        )

        dialog.update_notes_list_toggle()
        dialog.notes_list_visible = False
        dialog.update_notes_list_toggle()

        self.assertEqual(calls, [
            ("icon", "sidebar-hide-symbolic"), ("tooltip", "notes_hide_list"),
            ("icon", "sidebar-show-symbolic"), ("tooltip", "notes_show_list"),
        ])

    def test_notes_list_toggle_removes_start_pane_completely_and_restores_it(self):
        children = []
        insets = []

        class Paned:
            position = 352

            def get_position(self):
                return self.position

            def set_start_child(self, child):
                children.append(child)

            def set_position(self, position):
                self.position = position

        panel = object()
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.notes_list_visible = True
        dialog.notes_list_width = 330
        dialog.notes_list_paned = Paned()
        dialog.notes_list_panel = panel
        dialog.note_detail_inset_widgets = tuple(
            SimpleNamespace(set_margin_start=lambda value, index=index: insets.append((index, value)))
            for index in range(3)
        )
        dialog.update_notes_list_toggle = lambda: None

        dialog.toggle_notes_list()
        self.assertEqual(children, [None])
        self.assertFalse(dialog.notes_list_visible)
        self.assertEqual(dialog.notes_list_width, 352)
        self.assertEqual(insets, [(0, 0), (1, 0), (2, 0)])

        dialog.toggle_notes_list()
        self.assertEqual(children, [None, panel])
        self.assertTrue(dialog.notes_list_visible)
        self.assertEqual(dialog.notes_list_paned.position, 352)
        self.assertEqual(insets[3:], [(0, 6), (1, 6), (2, 6)])

    def test_import_export_menu_is_hidden_for_server_scoped_notes(self):
        visibility = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(read_only=False, encryption_locked=False)
        dialog.import_action = Gio.SimpleAction.new("import", None)
        dialog.export_action = Gio.SimpleAction.new("export", None)
        dialog.import_export_menu_button = SimpleNamespace(
            set_visible=lambda value: visibility.append(("menu", value))
        )

        dialog.set_import_export_actions_visible(False)
        self.assertFalse(dialog.import_action.get_enabled())
        self.assertFalse(dialog.export_action.get_enabled())
        dialog.set_import_export_actions_visible(True)
        self.assertTrue(dialog.import_action.get_enabled())
        self.assertTrue(dialog.export_action.get_enabled())

        self.assertEqual(visibility, [("menu", False), ("menu", True)])

    def test_import_export_menu_dispatches_to_notes_commands(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda key: {"notes_export": "Export notes", "notes_import": "Import notes"}[key]
        dialog.choose_export_protection = MagicMock()
        dialog.start_import = MagicMock()
        dialog.run_import_export_action = MagicMock()
        dialog.import_export_popover = dialog.build_import_export_menu()
        popover = dialog.import_export_popover
        self.assertIsInstance(popover, Gtk.PopoverMenu)
        self.assertTrue(popover.get_has_arrow())
        model = popover.get_menu_model()
        self.assertEqual([
            model.get_item_attribute_value(i, "label", None).unpack()
            for i in range(model.get_n_items())
        ], ["Export notes", "Import notes"])
        for name, command in (
            ("export", dialog.choose_export_protection), ("import", dialog.start_import),
        ):
            self.assertTrue(popover.activate_action(f"notes-transfer.{name}", None))
            dialog.run_import_export_action.assert_called_once_with(command)
            dialog.run_import_export_action.reset_mock()

    def test_import_export_permissions_preserve_scope_and_storage_guards(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.import_action = Gio.SimpleAction.new("import", None)
        dialog.export_action = Gio.SimpleAction.new("export", None)
        dialog.import_export_menu_button = MagicMock()
        for name in (
            "category_add_button", "add_button", "text_view", "save_button", "delete_button",
        ):
            setattr(dialog, name, MagicMock())
        for scope in ("personal", "server"):
            for read_only, locked in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(scope=scope, read_only=read_only, locked=locked):
                    dialog.scope_mode = scope
                    dialog.store = SimpleNamespace(read_only=read_only, encryption_locked=locked)
                    dialog.configure_write_controls()
                    self.assertEqual(dialog.import_action.get_enabled(),
                                     scope == "personal" and not read_only and not locked)
                    self.assertEqual(dialog.export_action.get_enabled(),
                                     scope == "personal" and not locked)
                    dialog.import_export_menu_button.set_visible.assert_called_with(scope == "personal")

    def test_import_export_action_closes_popover_before_dispatch(self):
        calls = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.import_export_popover = SimpleNamespace(popdown=lambda: calls.append("closed"))
        action = lambda: calls.append("action")

        with patch("termia.notes_dialogs.GLib.idle_add", side_effect=lambda callback: calls.append(callback)):
            dialog.run_import_export_action(action)

        self.assertEqual(calls, ["closed", action])

    def test_capture_active_editor_tab_preserves_generated_metadata(self):
        tab = NoteEditorTab("draft-1", None, "New note 12345678", "", None, "")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.active_editor_tab_key = "draft-1"
        dialog.editor_tabs = {"draft-1": tab}
        dialog.current_note_id = "saved-id"
        dialog.editor_dirty = True
        dialog.editor_content = lambda: "Restart service"
        dialog.status_label = SimpleNamespace(get_label=lambda: "Saving…")
        dialog.update_editor_tab_label = lambda _tab: None

        dialog.capture_active_editor_tab()

        self.assertEqual(
            (tab.note_id, tab.title, tab.category, tab.server_id, tab.content, tab.dirty, tab.status),
            ("saved-id", "New note 12345678", "", None, "Restart service", True, "Saving…"),
        )

    def test_new_note_uses_plain_name_and_inherits_server_scope(self):
        created = []
        activated = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda _key: "New note"
        dialog.store = SimpleNamespace(data=SimpleNamespace(notes=[]))
        dialog.editor_tabs = {}
        dialog.scope_mode = "server"
        dialog.server_filter_id = "server-id"
        dialog.add_editor_tab = created.append
        dialog.activate_editor_tab = activated.append
        dialog.notes_tree_selection = Gtk.SingleSelection.new(None)
        dialog.refresh_list = MagicMock()
        dialog.selected_note_id = None
        dialog.selected_draft_key = None
        dialog.expanded_note_sections = {"personal"}
        dialog.expanded_server_groups = set()

        dialog.create_editor_tab()

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].title, "New note")
        self.assertEqual(created[0].category, "")
        self.assertEqual(created[0].server_id, "server-id")
        self.assertEqual(activated, [created[0].key])
        dialog.refresh_list.assert_called_once_with()

    def test_new_note_titles_increment_independently_per_scope(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda _key: "New note"
        dialog.store = SimpleNamespace(data=SimpleNamespace(notes=[
            normalize_note("personal-1", "New note", "Body"),
            normalize_note("server-1", "New note", "Body", server_id="server-a"),
            normalize_note("personal-3", "New note 3", "Body"),
        ]))
        dialog.editor_tabs = {
            "draft": NoteEditorTab("draft", None, "New note 2", "", None, ""),
        }

        self.assertEqual(dialog.next_note_title(None), "New note 4")
        self.assertEqual(dialog.next_note_title("server-a"), "New note 2")
        self.assertEqual(dialog.next_note_title("server-b"), "New note")

    def test_moving_note_updates_category_and_open_tabs(self):
        note = normalize_note("note-id", "Runbook", "Restart", "Ops", "server-id")
        moved = []
        refreshed = []
        toasts = []
        tabs = [
            NoteEditorTab("tab-one", note.id, note.title, note.category, note.server_id, note.content),
            NoteEditorTab("tab-two", note.id, note.title, note.category, note.server_id, note.content),
        ]
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.ensure_writable = lambda: True
        dialog.save_active_editor_if_valid = lambda: True
        dialog.editor_dirty = False
        dialog.store = SimpleNamespace(
            data=SimpleNamespace(note_categories=[NoteCategory("Ops", "server-id"), NoteCategory("Personal", "server-id")]),
            has_note_category=lambda name, server_id=None: name in ("Ops", "Personal") and server_id == "server-id",
            update_note=lambda *args: (
                moved.append(args), setattr(note, "category", args[3])
            ),
        )
        dialog.find_note = lambda note_id: note if note_id == note.id else None
        dialog.editor_tabs = {tab.key: tab for tab in tabs}
        dialog.current_note_id = None
        dialog.refresh_list = refreshed.append
        dialog.translate = lambda key: key
        dialog.show_toast = toasts.append
        dialog.show_error = lambda message: self.fail(message)

        self.assertTrue(dialog.move_note_to_category(note.id, "Personal"))

        self.assertEqual(moved, [(note.id, "Runbook", "Restart", "Personal", "server-id")])
        self.assertEqual([tab.category for tab in tabs], ["Personal", "Personal"])
        self.assertEqual(refreshed, [note.id])
        self.assertEqual(toasts, ["notes_moved_to_category"])

    def test_persisting_note_rename_updates_open_tabs_and_list(self):
        note = normalize_note("note-id", "Old title", "Body", "Ops", "server-id")
        updates = []
        refreshed = []
        tabs = [
            NoteEditorTab("tab-one", note.id, note.title, note.category, note.server_id, note.content),
            NoteEditorTab("tab-two", note.id, note.title, note.category, note.server_id, note.content),
        ]
        labels = []
        toasts = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            update_note=lambda *args: (
                updates.append(args), setattr(note, "title", args[1])
            ),
        )
        dialog.find_note = lambda note_id: note if note_id == note.id else None
        dialog.editor_tabs = {tab.key: tab for tab in tabs}
        dialog.update_editor_tab_label = lambda tab: labels.append((tab.key, tab.title))
        dialog.refresh_list = refreshed.append
        dialog.detail_stack = SimpleNamespace(get_visible_child_name=lambda: "editor")
        dialog.selected_note_id = note.id
        dialog.translate = lambda key: key
        dialog.show_toast = toasts.append
        dialog.show_error = lambda message: self.fail(message)

        dialog.persist_note_title(note, "New title")

        self.assertEqual(updates, [(note.id, "New title", "Body", "Ops", "server-id")])
        self.assertEqual([tab.title for tab in tabs], ["New title", "New title"])
        self.assertEqual(len(labels), 2)
        self.assertEqual(refreshed, [note.id])
        self.assertEqual(toasts, ["notes_renamed"])

    def test_renaming_a_draft_with_text_schedules_autosave(self):
        tab = NoteEditorTab("draft-one", None, "New note", "", None, "Text")
        calls = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = tab.key
        dialog.ensure_writable = lambda: True
        dialog.schedule_autosave = lambda: calls.append("schedule")
        dialog.update_editor_tab_label = lambda _tab: calls.append("label")
        dialog.show_error = lambda message: self.fail(message)

        class Entry:
            def get_text(self):
                return "Runbook"

        class RenameDialog:
            def destroy(self):
                pass

        dialog.on_editor_tab_rename_response(
            RenameDialog(), Gtk.ResponseType.OK, Entry(), tab.key
        )

        self.assertEqual(tab.title, "Runbook")
        self.assertTrue(tab.dirty)
        self.assertEqual(calls, ["schedule", "label"])

    def test_note_rename_dialog_selects_existing_title(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda key: key
        dialog.window = MagicMock()

        with patch("termia.notes_dialogs.Gtk") as gtk:
            entry = gtk.Entry.return_value
            dialog.show_note_rename_dialog("Existing title", lambda *_args: None)

        entry.grab_focus.assert_called_once_with()
        entry.select_region.assert_called_once_with(0, -1)

    def test_editor_tab_order_tracks_visual_order(self):
        first = NoteEditorTab("one", "one", "First", "", None, "")
        second = NoteEditorTab("two", "two", "Second", "", None, "")

        visual_first, visual_second = object(), object()
        first.page_widget = visual_second
        second.page_widget = visual_first

        class Notebook:
            def get_n_pages(self):
                return 2

            def get_nth_page(self, index):
                return (visual_first, visual_second)[index]

        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {first.key: first, second.key: second}
        dialog.editor_notebook = Notebook()

        dialog.sync_editor_tab_order()

        self.assertEqual(list(dialog.editor_tabs), ["two", "one"])

    def test_empty_existing_note_is_not_written_over(self):
        calls = []
        tab = NoteEditorTab("note-id", "note-id", "Saved title", "Ops", "server", "")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = tab.key
        dialog.current_note_id = tab.note_id
        dialog.editor_dirty = True
        dialog.autosave_id = None
        dialog.editor_content = lambda: "  "
        dialog.status_label = SimpleNamespace(set_label=calls.append)
        dialog.translate = lambda key: key
        dialog.store = SimpleNamespace(update_note=lambda *_args: self.fail("empty note was saved"))

        self.assertTrue(dialog.save_editor())
        self.assertEqual(calls, ["notes_empty_not_saved"])

    def test_opening_a_note_already_in_a_tab_activates_it_without_duplicating(self):
        note = Note("note-id", "Runbook", "Restart service", "Ops", "server-id", "created", "modified")
        tab = NoteEditorTab("note-id", "note-id", "Runbook", "Ops", "server-id", "Restart service")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(encryption_locked=False)
        dialog.store.data = SimpleNamespace(servers=[], notes=[], note_categories=[])
        dialog.store.read_only = False
        dialog.editor_tabs = {}
        dialog.ensure_writable = lambda: True
        dialog.editor_tabs = {"note-id": tab}
        activated = []
        dialog.activate_editor_tab = activated.append

        dialog.load_editor(note)

        self.assertEqual(activated, ["note-id"])
        self.assertEqual(len(dialog.editor_tabs), 1)

    def test_empty_list_refresh_does_not_hide_active_editor_tab(self):
        dialog = make_note_tree_dialog()
        dialog.active_editor_tab_key = "draft-active"
        dialog.refresh_list()
        self.assertEqual(dialog.notes_tree_model.get_n_items(), 2)
        self.assertEqual(dialog.notes_tree_selection.get_selected(), Gtk.INVALID_LIST_POSITION)
        dialog.show_empty_state.assert_not_called()
        self.assertEqual(dialog.active_editor_tab_key, "draft-active")

    def test_server_tree_shows_uncategorized_with_unsaved_draft(self):
        tab = NoteEditorTab("draft-server", None, "New note", "", "server-id", "")
        dialog = make_note_tree_dialog(
            servers=[SimpleNamespace(id="server-id", name="Build host")], tabs=[tab],
        )
        dialog.scope_mode = "server"
        dialog.server_filter_id = "server-id"
        dialog.expanded_server_groups = {"server-id"}
        dialog.selected_draft_key = tab.key
        dialog.refresh_list()
        rows = [dialog.notes_tree_model.get_row(i)
                for i in range(dialog.notes_tree_model.get_n_items())]
        categories = [row for row in rows if row.get_item().kind == "category"]
        self.assertEqual([(row.get_item().category, row.get_item().count, row.get_depth())
                          for row in categories], [("", 1, 2)])
        selected = dialog.notes_tree_selection.get_selected_item()
        self.assertEqual(selected.get_item().draft_key, tab.key)
        self.assertEqual(selected.get_item().server_id, "server-id")
        self.assertEqual(selected.get_depth(), 3)

    def test_presenter_includes_servers_with_empty_categories_and_active_scope(self):
        presenter = NotesPresenter(
            lambda: [],
            lambda: [NoteCategory("Maintenance", "server-category")],
            lambda: [
                SimpleNamespace(id="server-category", name="Category host"),
                SimpleNamespace(id="server-active", name="Active host"),
            ],
        )

        tree = presenter.tree()
        active_tree = presenter.tree("", {"server-active"})

        self.assertEqual(
            [(server.id, [category.name for category in server.categories])
             for server in tree.servers],
            [("server-category", ["Maintenance"])],
        )
        self.assertEqual(
            [server.id for server in active_tree.servers],
            ["server-active", "server-category"],
        )

    def test_refresh_does_not_auto_select_first_note(self):
        note = Note("personal-note", "Personal", "Body", "Ops")
        dialog = make_note_tree_dialog([note], [NoteCategory("Ops")])
        dialog.active_editor_tab_key = None
        dialog.refresh_list()
        nodes = [dialog.notes_tree_model.get_row(i).get_item()
                 for i in range(dialog.notes_tree_model.get_n_items())]
        self.assertTrue(any(node.note_id == note.id for node in nodes))
        self.assertEqual(dialog.notes_tree_selection.get_selected(), Gtk.INVALID_LIST_POSITION)
        self.assertIsNone(dialog.selected_note_id)
        dialog.show_empty_state.assert_called_once_with()

    def test_note_properties_include_server_dates_and_content_counts(self):
        note = Note(
            "note-id", "Restart", "é\nnext", "Ops", "server-id",
            "2026-10-05T12:34:56.123456+00:00",
            "2026-10-06T12:34:56.654321+00:00",
        )
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(data=SimpleNamespace(
            servers=[SimpleNamespace(id="server-id", name="Web")],
        ))
        dialog.translate = lambda key: {"notes_property_bytes": "{count} bytes"}.get(key, key)

        properties = dict(dialog.note_property_rows(note))

        self.assertEqual(properties["name"], "Restart")
        self.assertEqual(properties["notes_category"], "Ops")
        self.assertEqual(properties["notes_association"], "Web")
        self.assertNotIn(".", properties["notes_property_created"])
        self.assertNotIn("T", properties["notes_property_modified"])
        self.assertEqual(properties["notes_property_lines"], "2")
        self.assertEqual(properties["notes_property_characters"], "6")
        self.assertEqual(properties["notes_property_size"], "7 bytes")

    def test_note_properties_window_uses_natural_height_and_insets_close(self):
        note = Note("note-id", "Restart", "Body", "Ops", "server-id")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.find_note = lambda _note_id: note
        dialog.window = MagicMock()
        dialog.translate = lambda key: key
        dialog.note_property_rows = lambda _note: [("Name", "Restart")]

        with patch("termia.notes_dialogs.Gtk") as gtk:
            content, details, actions = MagicMock(), MagicMock(), MagicMock()
            gtk.Box.side_effect = [content, details, actions]
            grid = gtk.Grid.return_value
            close_button = gtk.Button.return_value

            dialog.show_note_properties(note.id)

        gtk.Window.assert_called_once_with(
            title="notes_properties", transient_for=dialog.window, modal=False,
        )
        gtk.Window.return_value.add_css_class.assert_called_once_with(
            "termia-note-properties",
        )
        details.add_css_class.assert_called_once_with(
            "termia-note-properties-content",
        )
        details.set_margin_top.assert_not_called()
        details.set_margin_bottom.assert_not_called()
        content.set_margin_top.assert_called_once_with(6)
        content.set_margin_bottom.assert_called_once_with(6)
        content.set_margin_start.assert_called_once_with(10)
        content.set_margin_end.assert_called_once_with(10)
        gtk.Grid.assert_called_once_with(column_spacing=12, row_spacing=4)
        details.append.assert_called_once_with(grid)
        content.append.assert_has_calls([call(details), call(actions)])
        content.measure.assert_not_called()
        gtk.Window.return_value.set_default_size.assert_not_called()
        gtk.Window.return_value.set_size_request.assert_called_once_with(440, -1)
        gtk.Label.return_value.set_selectable.assert_not_called()
        actions.append.assert_called_once_with(close_button)
        actions.set_halign.assert_called_once_with(gtk.Align.END)
        actions.set_spacing.assert_called_once_with(8)
        actions.set_margin_top.assert_called_once_with(16)
        actions.set_margin_bottom.assert_called_once_with(16)
        actions.set_margin_start.assert_called_once_with(16)
        actions.set_margin_end.assert_called_once_with(16)
        close_button.set_margin_bottom.assert_not_called()
        close_button.set_margin_end.assert_not_called()
        close_button.set_margin_start.assert_not_called()
        close_button.connect.assert_called_once()

    def test_clone_note_copies_content_category_and_server_with_new_identity(self):
        original = Note("source", "Runbook", "Restart service", "Operations", "server-id", "created", "modified")
        cloned = Note("copy-id", "Runbook (copy)", "Restart service", "Operations", "server-id", "created-copy", "modified-copy")
        calls = []
        refreshed = []
        messages = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            add_note=lambda *args: (calls.append(args), cloned)[1],
        )
        dialog.editor_dirty = False
        dialog.ensure_writable = lambda: True
        dialog.find_note = lambda note_id: original if note_id == original.id else None
        dialog.translate = lambda key: {
            "notes_clone_suffix": " (copy)",
            "notes_clone_success": "Note cloned.",
        }[key]
        dialog.refresh_list = lambda note_id: refreshed.append(note_id)
        dialog.show_toast = messages.append
        dialog.show_error = lambda _message: self.fail("clone unexpectedly failed")

        dialog.clone_note(original.id)

        self.assertEqual(
            calls,
            [("Runbook (copy)", "Restart service", "Operations", "server-id")],
        )
        self.assertEqual(dialog.selected_note_id, cloned.id)
        self.assertEqual(refreshed, [cloned.id])
        self.assertEqual(messages, ["Note cloned."])

    def test_export_protection_choice_routes_to_plain_or_password_flow(self):
        for encrypted in (False, True):
            with self.subTest(encrypted=encrypted):
                dialog = NotesDialogs.__new__(NotesDialogs)
                destroyed = []
                dialog.export_protection_window = SimpleNamespace(
                    destroy=lambda: destroyed.append(True),
                )
                dialog.export_password_choice = SimpleNamespace(
                    get_active=lambda: encrypted,
                )
                dialog.translate = lambda key: key
                password_prompts = []
                file_choices = []
                dialog.ask_password = lambda *args: password_prompts.append(args)
                dialog.choose_export_file = lambda password: file_choices.append(password)

                dialog.on_export_protection_continue()

                self.assertEqual(destroyed, [True])
                if encrypted:
                    self.assertEqual(password_prompts, [("notes_export_credential", dialog.on_export_password)])
                    self.assertEqual(file_choices, [])
                else:
                    self.assertEqual(password_prompts, [])
                    self.assertEqual(file_choices, [None])

    def test_initial_selector_signals_do_not_prevent_window_opening(self):
        class EmittingCombo:
            def __init__(self, callback):
                self.callback = callback
                self.active_id = None

            def remove_all(self):
                self.callback(self)

            def append(self, _item_id, _label):
                pass

            def set_active_id(self, item_id):
                self.active_id = item_id
                self.callback(self)

            def get_active_id(self):
                return self.active_id

        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            encryption_locked=False, read_only=True,
            data=SimpleNamespace(note_categories=[], servers=[], notes=[]),
        )
        dialog.editor_tabs = {}
        dialog.scope_mode = "personal"
        dialog.translate = lambda key: key
        dialog.current_note_id = None
        dialog.server_filter_id = None
        dialog.loading_editor = False
        dialog.loading_search = False
        dialog.editor_dirty = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _text: None)
        dialog.import_action = Gio.SimpleAction.new("import", None)
        dialog.export_action = Gio.SimpleAction.new("export", None)
        dialog.import_export_menu_button = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.refresh_list = lambda *_args: None
        dialog.save_editor = lambda: False
        presented = []
        dialog.window = SimpleNamespace(
            get_visible=lambda: True, present=lambda: presented.append(True),
            set_title=lambda _title: None,
            unminimize=lambda: None,
        )
        dialog.ensure_window = lambda: None

        dialog.show_manager()

        self.assertEqual(presented, [True])
        self.assertFalse(dialog.editor_dirty)

    def test_empty_draft_waits_until_text_exists_before_autosaving(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.loading_editor = False
        dialog.editor_dirty = False
        dialog.editor_content = lambda: ""
        dialog.status_label = SimpleNamespace(set_label=lambda _text: None)
        dialog.translate = lambda key: key
        cancelled = []
        scheduled = []
        dialog.cancel_autosave = lambda: cancelled.append(True)
        dialog.schedule_autosave = lambda: scheduled.append(True)

        dialog.on_editor_changed()

        self.assertTrue(dialog.editor_dirty)
        self.assertEqual(cancelled, [True])
        self.assertEqual(scheduled, [])
        dialog.editor_content = lambda: "Restart the service"
        dialog.on_editor_changed()
        self.assertEqual(scheduled, [True])

    def test_failed_save_still_presents_notes_window(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            encryption_locked=False,
            data=SimpleNamespace(servers=[SimpleNamespace(id="server-id", name="Build host")]),
        )
        dialog.ensure_window = lambda: None
        dialog.editor_dirty = True
        dialog.save_editor = lambda: False
        presented = []
        dialog.window = SimpleNamespace(
            get_visible=lambda: True, present=lambda: presented.append(True),
            unminimize=lambda: None,
        )

        dialog.show_manager("server-id")

        self.assertEqual(presented, [True])

    def test_entry_modes_keep_global_actions_out_of_server_view(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            encryption_locked=False, read_only=True,
            data=SimpleNamespace(servers=[SimpleNamespace(id="server-id", name="Build host")], notes=[], note_categories=[]),
        )
        dialog.editor_tabs = {}
        dialog.scope_mode = "personal"
        dialog.translate = lambda key: key
        dialog.ensure_window = lambda: None
        dialog.editor_dirty = False
        dialog.current_note_id = "previous-note"
        dialog.loading_search = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        views = []
        dialog.refresh_list = lambda: views.append(dialog.server_filter_id)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _label: None)
        import_enabled = []
        export_enabled = []
        menu_visibility = []
        dialog.import_action = SimpleNamespace(set_enabled=import_enabled.append)
        dialog.export_action = SimpleNamespace(set_enabled=export_enabled.append)
        dialog.import_export_menu_button = SimpleNamespace(set_visible=menu_visibility.append)
        dialog.window = SimpleNamespace(
            get_visible=lambda: True, present=lambda: None, set_title=lambda _title: None,
            unminimize=lambda: None,
        )

        dialog.show_manager("server-id")
        self.assertEqual(views, ["server-id"])
        self.assertIsNone(dialog.current_note_id)
        self.assertEqual(import_enabled, [False])
        self.assertEqual(export_enabled, [False])
        self.assertEqual(menu_visibility, [False])

        dialog.show_manager()
        self.assertEqual(views, ["server-id", None])
        self.assertEqual(import_enabled, [False, False])
        self.assertEqual(export_enabled, [False, True])
        self.assertEqual(menu_visibility, [False, True])

    def test_opening_hidden_notes_window_starts_a_draft_in_the_current_scope(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            encryption_locked=False, read_only=False,
            data=SimpleNamespace(servers=[SimpleNamespace(id="server-id", name="Build host")]),
        )
        dialog.translate = lambda key: key
        dialog.editor_tabs = {}
        dialog.active_editor_tab_key = None
        dialog.editor_dirty = False
        dialog.loading_search = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _text: None)
        dialog.set_import_export_actions_visible = lambda _visible: None
        dialog.save_active_editor_if_valid = lambda: True
        dialog.capture_active_editor_tab = lambda: None
        dialog.update_window_title = lambda _server_id: None
        dialog.set_import_export_actions_visible = lambda _visible: None
        dialog.editor_tabs = {}
        dialog.server_filter_id = None
        dialog.scope_mode = "personal"
        dialog.selected_note_id = None
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.loading_search = False
        dialog.refresh_list = lambda: None
        dialog.ensure_window = lambda: None
        visible = False
        dialog.window = SimpleNamespace(
            get_visible=lambda: visible, present=lambda: None, set_title=lambda _title: None,
            unminimize=lambda: None,
        )
        created = []
        dialog.create_note = lambda: created.append(dialog.server_filter_id)

        dialog.show_manager()
        self.assertEqual(created, [None])

        visible = True
        dialog.show_manager()
        self.assertEqual(created, [None])

        visible = False
        dialog.show_manager("server-id")
        self.assertEqual(created, [None, "server-id"])

        dialog.store.read_only = True
        dialog.show_manager()
        self.assertEqual(created, [None, "server-id"])

    def test_reopening_notes_reuses_a_draft_for_the_same_scope(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            encryption_locked=False, read_only=False,
            data=SimpleNamespace(servers=[SimpleNamespace(id="server-id", name="Build host")]),
        )
        dialog.translate = lambda key: key
        dialog.editor_tabs = {
            "draft": NoteEditorTab("draft", None, "New note", "", "server-id", ""),
        }
        dialog.active_editor_tab_key = None
        dialog.editor_dirty = False
        dialog.loading_search = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _text: None)
        dialog.set_import_export_actions_visible = lambda _visible: None
        dialog.refresh_list = lambda: None
        dialog.ensure_window = lambda: None
        dialog.window = SimpleNamespace(
            get_visible=lambda: False, present=lambda: None, set_title=lambda _title: None,
            unminimize=lambda: None,
        )
        activated = []
        def activate(key):
            activated.append(key)
            dialog.active_editor_tab_key = key
        dialog.activate_editor_tab = activate
        focused = []
        dialog.text_view = SimpleNamespace(grab_focus=lambda: focused.append(True))
        dialog.create_note = lambda: self.fail("duplicate draft created")

        dialog.show_manager("server-id")

        self.assertEqual(activated, ["draft"])
        self.assertEqual(focused, [True])

    def test_selecting_another_note_does_not_replace_an_open_editor(self):
        note = Note("other-note", "Runbook", "Content", "Ops", "server-id", "", "2026-10-05")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.selected_note_id = "active-note"
        dialog.active_editor_tab_key = "active-tab"
        dialog.scope_mode = "server"
        dialog.server_filter_id = "server-id"
        dialog.loading_note_list = False
        dialog.find_note = lambda note_id: note if note_id == note.id else None

        dialog.on_note_selected(None, SimpleNamespace(note_id=note.id))

        self.assertEqual(dialog.selected_note_id, note.id)
        self.assertEqual(dialog.active_editor_tab_key, "active-tab")

    def test_activating_a_note_row_opens_its_editor_tab(self):
        note = Note("note-id", "Runbook", "Content", "Ops", "server-id", "", "2026-10-05")
        opened = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.find_note = lambda note_id: note if note_id == note.id else None
        dialog.load_editor = opened.append

        dialog.on_note_row_activated(None, SimpleNamespace(note_id=note.id))

        self.assertEqual(opened, [note])

    def test_server_context_waits_for_popover_to_close(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        shown = []
        dialog._show_server_notes = lambda server_id: shown.append(server_id)

        class Popover:
            def connect(self, signal, callback):
                self.signal = signal
                self.callback = callback

            def popdown(self):
                self.callback(self)

        popover = Popover()
        with patch("termia.notes_dialogs.GLib.idle_add") as idle_add, patch(
            "termia.notes_dialogs.GLib.timeout_add"
        ) as timeout_add:
            dialog.show_for_server_after_popover(popover, "server-id")
            timeout_add.call_args.args[1]()

        self.assertEqual(popover.signal, "closed")
        idle_add.assert_not_called()
        self.assertEqual(timeout_add.call_args_list, [
            call(100, dialog._show_server_notes, "server-id"),
            call(150, popover.callback),
        ])

    def test_server_context_opens_when_popover_was_already_closed(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog._show_server_notes = lambda _server_id: None

        class ClosedPopover:
            def connect(self, _signal, _callback):
                pass

            def popdown(self):
                pass

        with patch("termia.notes_dialogs.GLib.idle_add") as idle_add, patch(
            "termia.notes_dialogs.GLib.timeout_add"
        ) as timeout_add:
            dialog.show_for_server_after_popover(ClosedPopover(), "server-id")
            timeout_add.call_args.args[1]()

        idle_add.assert_not_called()
        self.assertEqual(timeout_add.call_args.args, (100, dialog._show_server_notes, "server-id"))

    def test_incomplete_draft_is_kept_when_hiding_reusable_notes_window(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_dirty = True
        dialog.current_note_id = "existing-note"
        dialog.cancel_autosave = lambda: None
        dialog.text_view = object()
        dialog.editor_content = lambda: ""
        dialog.capture_active_editor_tab = lambda: None
        hidden = []
        cleared = []
        dialog.clear_editor = lambda: cleared.append(True)
        dialog.window = SimpleNamespace(set_visible=lambda visible: hidden.append(visible))

        self.assertTrue(dialog.on_close_request(dialog.window))
        self.assertTrue(dialog.editor_dirty)
        self.assertEqual(cleared, [])
        self.assertEqual(hidden, [False])


class NotesIOTests(unittest.TestCase):
    def setUp(self):
        self.notes = [Note(
            "note-1", "Production runbook", "Restart the service.", "Operations",
            "server-1", "2026-10-01T09:00:00+00:00", "2026-10-02T12:00:00+00:00",
        )]
        self.categories = [NoteCategory("Empty"), NoteCategory("Operations", "server-1")]

    def test_plain_and_obfuscated_storage_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ("plain", CONNECTION_STORAGE_OBFUSCATED):
                path = Path(directory) / f"notes-{mode}.json"
                write_notes_file(path, self.notes, self.categories, mode)
                notes, categories = read_notes_file(path)
                self.assertEqual(notes, self.notes)
                self.assertEqual(categories, self.categories)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_encrypted_storage_round_trip_and_password_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.json"
            write_notes_file(path, self.notes, self.categories, CONNECTION_STORAGE_ENCRYPTED, "master")
            with self.assertRaises(MissingMasterPasswordError):
                read_notes_file(path)
            with self.assertRaises(InvalidMasterPasswordError):
                read_notes_file(path, "wrong")
            notes, categories = read_notes_file(path, "master")
        self.assertEqual(notes, self.notes)
        self.assertEqual(categories, self.categories)

    def test_password_protected_export_is_independent_and_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "termia-notes.json"
            export_notes_file(path, self.notes, self.categories, "export password")
            with self.assertRaises(MissingMasterPasswordError):
                import_notes_file(path)
            with self.assertRaises(InvalidMasterPasswordError):
                import_notes_file(path, "wrong password")
            notes, categories = import_notes_file(path, "export password")
        self.assertEqual(notes, self.notes)
        self.assertEqual(categories, self.categories)

    def test_unsupported_or_invalid_import_is_rejected_as_a_whole(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({
                "format": "termia-notes-export-v1",
                "schema_version": 1,
                "categories": ["Ops"],
                "notes": [
                    {"id": "ok", "title": "Good", "content": "Keep"},
                    {"id": "bad", "title": "", "content": "Invalid"},
                ],
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                import_notes_file(path)

    def test_invalid_file_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.json"
            path.write_text(json.dumps({"format": "future-format"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_notes_file(path)

    def test_schema_one_categories_migrate_to_scope_specific_schema_two(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "categories": ["Ops"],
                "notes": [
                    {"id": "personal", "title": "Personal", "content": "Body", "category": "Ops"},
                    {"id": "server", "title": "Server", "content": "Body", "category": "Ops", "server_id": "server-a"},
                ],
            }), encoding="utf-8")

            notes, categories = read_notes_file(path)

        self.assertEqual({note.server_id for note in notes}, {None, "server-a"})
        self.assertEqual(categories, [NoteCategory("Ops"), NoteCategory("Ops", "server-a")])

    def test_schema_two_round_trip_allows_same_category_name_in_scopes(self):
        notes = [
            normalize_note("personal", "Personal", "Body", "Ops"),
            normalize_note("server", "Server", "Body", "Ops", "server-a"),
        ]
        categories = [NoteCategory("Ops"), NoteCategory("Ops", "server-a")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.json"
            write_notes_file(path, notes, categories, "plain")
            restored_notes, restored_categories = read_notes_file(path)

        self.assertEqual(restored_notes, notes)
        self.assertEqual(restored_categories, categories)


class NotesStoreTests(unittest.TestCase):
    def make_store(self, root):
        return ConnectionStore(
            root / "connections.json", root / "settings.json", root / "statistics.json",
            root / "lock", root / "history", root / "notes.json",
        )

    def test_reparenting_preserves_notes_rolls_back_failures_and_reloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                for name in ("Project", "Child", "Leaf", "Other"):
                    store.add_note_category(name)
                note = store.add_note("Title", "Body", "Leaf")
                store.move_note_category("Child", "Project")
                store.move_note_category("Leaf", "Child")
                before = list(store.data.note_categories)
                original_file = (root / "notes.json").read_bytes()
                for name, parent in (("Project", "Leaf"), ("Child", "Child"), ("Child", "missing")):
                    with self.assertRaises(NoteError):
                        store.move_note_category(name, parent)
                with patch.object(store, "save_notes", side_effect=OSError("test failure")):
                    with self.assertRaises(OSError):
                        store.move_note_category("Child", "Other")
                self.assertEqual(store.data.note_categories, before)
                self.assertEqual((root / "notes.json").read_bytes(), original_file)
                with patch.object(store, "_read_only", True), self.assertRaises(ReadOnlyStoreError):
                    store.move_note_category("Child", None)
                with patch.object(store, "encryption_locked", True), self.assertRaises(ReadOnlyStoreError):
                    store.move_note_category("Child", None)
                store.move_note_category("Child", "Other")
                store.move_note_category("Child", None)
                self.assertEqual(store.data.notes, [note])
            finally:
                store.close()
            restored = self.make_store(root)
            try:
                self.assertIn(NoteCategory("Child"), restored.data.note_categories)
                self.assertIn(NoteCategory("Leaf", parent="Child"), restored.data.note_categories)
                self.assertEqual(restored.data.notes, [note])
            finally:
                restored.close()

    def test_rename_duplicate_and_delete_keep_nested_children_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory))
            try:
                for name in ("Project", "Child", "Leaf"):
                    store.add_note_category(name)
                store.move_note_category("Child", "Project")
                store.move_note_category("Leaf", "Child")
                store.rename_note_category("Child", "Renamed")
                self.assertIn(NoteCategory("Leaf", parent="Renamed"), store.data.note_categories)
                store.duplicate_note_category("Renamed", "Copy")
                self.assertIn(NoteCategory("Copy", parent="Project"), store.data.note_categories)
                store.delete_note_category("Renamed")
                self.assertIn(NoteCategory("Leaf", parent="Project"), store.data.note_categories)
            finally:
                store.close()

    def test_server_reparenting_is_isolated_from_other_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory))
            try:
                server = store.add_server("Example", "example.test", "user", 22, None)
                for scope in (None, server.id):
                    for name in ("Project", "Child"):
                        store.add_note_category(name, scope)
                note = store.add_note("Title", "Body", "Child", server.id)
                store.move_note_category("Child", "Project", server.id)
                self.assertIn(NoteCategory("Child"), store.data.note_categories)
                self.assertIn(NoteCategory("Child", server.id, "Project"), store.data.note_categories)
                self.assertEqual(store.data.notes, [note])
            finally:
                store.close()

    def test_notes_default_to_sibling_of_custom_connections_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(
                root / "connections.json", root / "settings.json", root / "statistics.json",
                root / "lock", root / "history",
            )
            try:
                store.add_note("Runbook", "Synthetic content")
                self.assertEqual(store.notes_file_store.path, root / "notes.json")
                self.assertTrue((root / "notes.json").exists())
            finally:
                store.close()

    def test_note_categories_duplicate_rename_delete_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                store.add_note_category("Empty")
                first = store.add_note("Runbook", "Restart the web service", "Ops")
                store.rename_note_category("Ops", "Operations")
                store.duplicate_note_category("Operations", "Operations copy")
                copied = next(note for note in store.data.notes if note.category == "Operations copy")
                self.assertNotEqual(copied.id, first.id)
                self.assertEqual(copied.content, first.content)
                store.delete_note_category("Operations")
                self.assertEqual(next(note for note in store.data.notes if note.id == first.id).category, "")
                self.assertIn(NoteCategory("Empty"), store.data.note_categories)
            finally:
                store.close()
            restored = self.make_store(root)
            try:
                self.assertEqual(restored.data.note_categories, [NoteCategory("Empty"), NoteCategory("Operations copy")])
                self.assertEqual(len(restored.data.notes), 2)
            finally:
                restored.close()

    def test_same_category_name_isolated_between_personal_and_server_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory))
            try:
                server = store.add_server("Web", "web.test", "admin", 22, None)
                store.add_note_category("Ops")
                store.add_note_category("Ops", server.id)
                store.add_note("Personal runbook", "Personal body", "Ops")
                store.add_note("Server runbook", "Server body", "Ops", server.id)

                store.rename_note_category("Ops", "Personal Ops")

                categories = {(item.name, item.server_id) for item in store.data.note_categories}
                notes = {(item.title, item.category) for item in store.data.notes}
                self.assertEqual(categories, {("Personal Ops", None), ("Ops", server.id)})
                self.assertEqual(notes, {("Personal runbook", "Personal Ops"), ("Server runbook", "Ops")})
            finally:
                store.close()

    def test_deleting_server_detaches_notes_and_preserves_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                server = store.add_server("Web", "web.test", "admin", 22, None)
                note = store.add_note("Runbook", "Restart it", server_id=server.id)
                store.delete_server(server.id)
                self.assertEqual(store.data.notes[0].id, note.id)
                self.assertIsNone(store.data.notes[0].server_id)
            finally:
                store.close()

    def test_note_save_respects_encrypted_storage_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                store.master_password = "master"
                store.data.app.connection_storage_mode = CONNECTION_STORAGE_ENCRYPTED
                store.add_note("Secret note", "Private content")
                raw = (root / "notes.json").read_text(encoding="utf-8")
                self.assertNotIn("Private content", raw)
            finally:
                store.close()

    def test_changing_connection_storage_mode_reprotects_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                store.add_note("Runbook", "Private note")
                store.update_connection_storage_mode(CONNECTION_STORAGE_ENCRYPTED, "master")
                raw = (root / "notes.json").read_text(encoding="utf-8")
                self.assertNotIn("Private note", raw)
                notes, _categories = read_notes_file(root / "notes.json", "master")
                self.assertEqual(notes[0].content, "Private note")
            finally:
                store.close()

    def test_change_master_password_reencrypts_connections_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                server = store.add_server(
                    "Web", "web.test", "admin", 22, None, password="saved password",
                )
                store.add_note("Runbook", "Private note", server_id=server.id)
                store.update_connection_storage_mode(CONNECTION_STORAGE_ENCRYPTED, "old master")
                connections_before = read_connections_payload(root / "connections.json", "old master")
                notes_before = read_notes_file(root / "notes.json", "old master")
                paths = (root / "connections.json", root / "notes.json", root / "settings.json")
                raw_before = {path: path.read_bytes() for path in paths}

                with self.assertRaises(UnchangedMasterPasswordError):
                    store.change_master_password("old master", "old master")
                self.assertEqual({path: path.read_bytes() for path in paths}, raw_before)

                store.change_master_password("old master", "new master")

                self.assertEqual(store.master_password, "new master")
                self.assertEqual(
                    read_connections_payload(root / "connections.json", "new master"),
                    connections_before,
                )
                self.assertEqual(
                    read_notes_file(root / "notes.json", "new master"), notes_before,
                )
                with self.assertRaises(InvalidMasterPasswordError):
                    read_connections_payload(root / "connections.json", "old master")
                with self.assertRaises(InvalidMasterPasswordError):
                    read_notes_file(root / "notes.json", "old master")
            finally:
                store.close()

    def test_wrong_current_master_password_leaves_all_files_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                store.add_note("Runbook", "Private note")
                store.update_connection_storage_mode(CONNECTION_STORAGE_ENCRYPTED, "old master")
                paths = (root / "connections.json", root / "notes.json", root / "settings.json")
                before = {path: path.read_bytes() for path in paths}

                with self.assertRaises(InvalidMasterPasswordError):
                    store.change_master_password("wrong password", "new master")

                self.assertEqual({path: path.read_bytes() for path in paths}, before)
                self.assertEqual(store.master_password, "old master")
            finally:
                store.close()

    def test_failed_reencryption_restores_connections_and_notes(self):
        from termia.notes_io import atomic_write

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                store.add_note("Runbook", "Private note")
                store.update_connection_storage_mode(CONNECTION_STORAGE_ENCRYPTED, "old master")
                paths = (root / "connections.json", root / "notes.json", root / "settings.json")
                before = {path: path.read_bytes() for path in paths}
                calls = 0

                def fail_notes_write(path, contents):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise OSError("disk full")
                    return atomic_write(path, contents)

                with patch("termia.notes_io.atomic_write", side_effect=fail_notes_write):
                    with self.assertRaises(OSError):
                        store.change_master_password("old master", "new master")

                self.assertEqual({path: path.read_bytes() for path in paths}, before)
                self.assertEqual(store.master_password, "old master")
                self.assertEqual(
                    read_notes_file(root / "notes.json", "old master")[0][0].content,
                    "Private note",
                )
            finally:
                store.close()

    def test_change_master_password_is_rejected_in_read_only_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                store.update_connection_storage_mode(CONNECTION_STORAGE_ENCRYPTED, "old master")
                paths = (root / "connections.json", root / "notes.json", root / "settings.json")
                before = {path: path.read_bytes() for path in paths}
                store.read_only = True
                with self.assertRaises(ReadOnlyStoreError):
                    store.change_master_password("old master", "new master")
                self.assertEqual({path: path.read_bytes() for path in paths}, before)
            finally:
                store.close()

    def test_failed_new_note_save_keeps_unsaved_content_out_of_store(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(Path(directory))
            try:
                with patch.object(store, "save_notes", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        store.add_note("Runbook", "Keep this in the editor")
                self.assertEqual(store.data.notes, [])
            finally:
                store.close()

    def test_invalid_notes_json_is_backed_up_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.json").write_text("{invalid", encoding="utf-8")
            store = self.make_store(root)
            try:
                self.assertEqual(store.data.notes, [])
                self.assertTrue(list(root.glob("notes.json.invalid-*")))
            finally:
                store.close()

    def test_orphaned_server_associations_are_detached(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = self.make_store(root)
            try:
                server = store.add_server("Web", "web.test", "admin", 22, None)
                store.add_note("Runbook", "Restart it", server_id=server.id)
                store.data.servers.clear()
                self.assertEqual(store.detach_orphaned_notes(), 1)
                self.assertIsNone(store.data.notes[0].server_id)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
