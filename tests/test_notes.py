import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from termia.config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_OBFUSCATED,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
)
from termia.models import Note
from termia.notes import NoteError, normalize_note, note_matches_query
from termia.notes_dialogs import Gdk, Gtk, NoteEditorTab, NotesDialogs, format_note_timestamp
from termia.notes_io import (
    export_notes_file,
    import_notes_file,
    read_notes_file,
    write_notes_file,
)
from termia.notes_presenter import NotesPresenter
from termia.stores import ConnectionStore


class NotesDomainTests(unittest.TestCase):
    def test_note_validation_timestamps_and_search(self):
        note = normalize_note("one", "  Runbook ", " Restart service ", "Ops", now="2026-10-02T12:00:00+00:00")
        self.assertEqual(note.title, "Runbook")
        self.assertEqual(note.content, " Restart service ")
        self.assertEqual(note.created_at, "2026-10-02T12:00:00+00:00")
        self.assertTrue(note_matches_query(note, "restart"))
        self.assertFalse(note_matches_query(note, "database"))
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
        presenter = NotesPresenter(lambda: [first, second], lambda: ["Ops"], lambda: [])

        self.assertEqual([item.note.id for item in presenter.items()], ["new", "old"])
        self.assertEqual([item.note.id for item in presenter.items("backup")], ["new"])


class NotesDialogSignalTests(unittest.TestCase):
    def test_notes_header_controls_use_sidebar_alignment_inset(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.window = None
        dialog.parent = MagicMock()
        dialog.server_filter_id = None
        dialog.translate = lambda key: key
        dialog.build_creation_controls = MagicMock()
        dialog.update_notes_list_toggle = MagicMock()
        dialog.update_note_detail_inset = MagicMock()
        dialog.configure_write_controls = MagicMock()
        dialog.set_editor_enabled = MagicMock()
        boxes = []

        with patch("termia.notes_dialogs.Gtk") as gtk:
            def make_box(**_kwargs):
                box = MagicMock()
                boxes.append(box)
                return box

            gtk.Box.side_effect = make_box
            dialog.ensure_window()

        boxes[0].set_margin_start.assert_called_once_with(8)
        gtk.HeaderBar.return_value.pack_start.assert_called_once_with(boxes[0])

    def test_creation_buttons_share_a_left_aligned_row_in_category_first_order(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.server_filter_id = None
        dialog.translate = lambda key: key
        category_button = MagicMock()
        note_button = MagicMock()

        with patch("termia.notes_dialogs.Gtk") as gtk:
            gtk.Button.side_effect = [category_button, note_button]
            controls = dialog.build_creation_controls()

        controls.set_halign.assert_called_once_with(gtk.Align.START)
        self.assertEqual(
            [call.args[0] for call in controls.append.call_args_list],
            [category_button, note_button],
        )
        category_button.set_tooltip_text.assert_called_once_with("notes_category_add")
        note_button.set_tooltip_text.assert_called_once_with("notes_create")
        note_button.add_css_class.assert_called_once_with("suggested-action")

    def test_only_named_category_rows_get_context_menu_controls(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.notes_list = MagicMock()
        dialog.translate = lambda key: "{count} notes" if key == "notes_category_count" else key

        with patch("termia.notes_dialogs.Gtk") as gtk:
            dialog.append_note_category_header("Ops", 2, False)
            dialog.append_note_category_header("", 0, False)
            dialog.append_note_category_header(None, 1, False)

        self.assertEqual(gtk.GestureClick.call_count, 1)
        self.assertEqual(gtk.EventControllerKey.new.call_count, 1)
        self.assertEqual(dialog.notes_list.append.call_count, 3)

    def test_category_context_menu_has_three_translated_actions(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            read_only=False, encryption_locked=False,
            data=SimpleNamespace(note_categories=["Ops"]),
        )
        dialog.translate = lambda key: key
        dialog.category_context_popover = None
        button = MagicMock()
        actions = [MagicMock() for _ in range(3)]

        with patch("termia.notes_dialogs.Gtk") as gtk:
            gtk.Button.side_effect = actions
            dialog.show_category_context_menu("Ops", button)

        self.assertEqual(
            [call.kwargs["label"] for call in gtk.Button.call_args_list],
            ["notes_category_rename", "notes_category_duplicate", "notes_category_delete"],
        )
        gtk.Popover.return_value.set_parent.assert_called_once_with(button)
        gtk.Popover.return_value.popup.assert_called_once()
        actions[2].add_css_class.assert_any_call("destructive-action")
        for action in actions:
            action.set_sensitive.assert_called_once_with(True)

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

    def test_category_context_action_waits_until_popover_is_closed(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.close_category_context_menu = MagicMock()
        dialog.prompt_category_edit = MagicMock()
        dialog.confirm_delete_category = MagicMock()

        with patch("termia.notes_dialogs.GLib.idle_add") as idle_add:
            dialog.on_category_context_action("rename", "Ops")
            idle_add.assert_called_with(dialog.prompt_category_edit, "rename", "Ops")
            dialog.on_category_context_action("delete", "Ops")
            idle_add.assert_called_with(dialog.confirm_delete_category, "Ops")

        self.assertEqual(dialog.close_category_context_menu.call_count, 2)

    def test_category_prompt_preselects_name_for_rename_and_duplicate(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(data=SimpleNamespace(note_categories=["Ops"]))
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
        dialog.store.data.note_categories = ["Ops"]
        dialog.store.data.notes = [SimpleNamespace(category="Ops")]
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
                dialog.window, None, dialog.on_delete_category_response, "Ops",
            )

        result = MagicMock()
        result.choose_finish.return_value = 1
        dialog.on_delete_category_response(result, None, "Ops")

        dialog.store.delete_note_category.assert_called_once_with("Ops")
        dialog.sync_open_note_categories.assert_called_once()
        dialog.refresh_list.assert_called_once()

    def test_category_name_response_uses_the_matching_store_operation(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = MagicMock()
        dialog.store.data.note_categories = ["Ops"]
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
                args = (name,) if mode == "add" else (original, name)
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

    def test_remove_editor_tab_removes_its_outer_tab_container(self):
        tab = NoteEditorTab("note-id", "note-id", "Runbook", "", None, "Saved")
        removed = []

        class Container:
            parent = None

            def get_parent(self):
                return self.parent

        container = Container()

        class TabBar:
            def remove(self, widget):
                removed.append(widget)
                widget.parent = None

        tab.container_widget = container
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {tab.key: tab}
        dialog.active_editor_tab_key = "another-tab"
        dialog.editor_tabs_bar = TabBar()
        container.parent = dialog.editor_tabs_bar

        dialog.remove_editor_tab(tab.key)

        self.assertEqual(removed, [container])
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
        dialog.import_button = SimpleNamespace(set_visible=lambda value: visibility.append(("import", value)))
        dialog.export_button = SimpleNamespace(set_visible=lambda value: visibility.append(("export", value)))
        dialog.import_export_menu_button = SimpleNamespace(
            set_visible=lambda value: visibility.append(("menu", value))
        )

        dialog.set_import_export_actions_visible(False)
        dialog.set_import_export_actions_visible(True)

        self.assertEqual(visibility, [
            ("import", False), ("export", False), ("menu", False),
            ("import", True), ("export", True), ("menu", True),
        ])

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

    def test_active_note_tab_gets_terminal_style_highlight(self):
        class TabContainer:
            def __init__(self):
                self.classes = set()

            def add_css_class(self, name):
                self.classes.add(name)

            def remove_css_class(self, name):
                self.classes.discard(name)

        class Label:
            def set_label(self, _value):
                pass

        first = NoteEditorTab("one", "one", "First", "", None, "")
        second = NoteEditorTab("two", "two", "Second", "", None, "")
        first.container_widget = TabContainer()
        second.container_widget = TabContainer()
        first.label_widget = Label()
        second.label_widget = Label()
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.active_editor_tab_key = "two"
        dialog.translate = lambda key: key

        dialog.update_editor_tab_label(first)
        dialog.update_editor_tab_label(second)

        self.assertNotIn("active", first.container_widget.classes)
        self.assertIn("active", second.container_widget.classes)

    def test_new_note_uses_plain_name_and_inherits_server_scope(self):
        created = []
        activated = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.translate = lambda _key: "New note"
        dialog.server_filter_id = "server-id"
        dialog.add_editor_tab = created.append
        dialog.activate_editor_tab = activated.append
        dialog.notes_list = SimpleNamespace(unselect_all=lambda: None)

        dialog.create_editor_tab()

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].title, "New note")
        self.assertEqual(created[0].category, "")
        self.assertEqual(created[0].server_id, "server-id")
        self.assertEqual(activated, [created[0].key])

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
            data=SimpleNamespace(note_categories=["Ops", "Personal"]),
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

    def test_editor_tab_order_tracks_visual_order(self):
        first = NoteEditorTab("one", "one", "First", "", None, "")
        second = NoteEditorTab("two", "two", "Second", "", None, "")

        class Child:
            def __init__(self, next_child=None):
                self.next_child = next_child

            def get_next_sibling(self):
                return self.next_child

        visual_first, visual_second = Child(), Child()
        visual_first.next_child = visual_second
        first.container_widget = visual_second
        second.container_widget = visual_first

        class TabBar:
            def get_first_child(self):
                return visual_first

        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_tabs = {first.key: first, second.key: second}
        dialog.editor_tabs_bar = TabBar()

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
        dialog.ensure_writable = lambda: True
        dialog.editor_tabs = {"note-id": tab}
        activated = []
        dialog.activate_editor_tab = activated.append

        dialog.load_editor(note)

        self.assertEqual(activated, ["note-id"])
        self.assertEqual(len(dialog.editor_tabs), 1)

    def test_empty_list_refresh_does_not_hide_active_editor_tab(self):
        empty_state_calls = []
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.notes_list = SimpleNamespace(
            get_first_child=lambda: None,
        )
        dialog.scope_bar = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.server_filter_id = None
        dialog.search_entry = SimpleNamespace(get_text=lambda: "")
        dialog.store = SimpleNamespace(data=SimpleNamespace(note_categories=[], servers=[]))
        dialog.collapsed_note_categories = set()
        dialog.presenter = SimpleNamespace(items=lambda *_args: [])
        dialog.detail_stack = SimpleNamespace(get_visible_child_name=lambda: "editor")
        dialog.active_editor_tab_key = "draft-active"
        dialog.selected_note_id = None
        dialog.close_note_context_menu = lambda: None
        dialog.show_empty_state = lambda: empty_state_calls.append(True)

        dialog.refresh_list()

        self.assertEqual(empty_state_calls, [])

    def test_note_groups_include_empty_categories_and_uncategorized_notes(self):
        notes = [
            normalize_note("one", "Runbook", "Restart", "Operations"),
            normalize_note("two", "Ideas", "Draft", "Personal"),
            normalize_note("three", "Loose note", "Remember this"),
        ]
        items = [SimpleNamespace(note=note) for note in notes]
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            data=SimpleNamespace(note_categories=["Personal", "Empty", "Operations"])
        )

        groups = dialog.group_note_items(items, include_empty_categories=True)

        self.assertEqual([name for name, _items in groups], ["Empty", "Operations", "Personal", ""])
        self.assertEqual([len(group_items) for _name, group_items in groups], [0, 1, 1, 1])

    def test_note_search_grouping_only_keeps_categories_with_matches(self):
        note = normalize_note("one", "Runbook", "Restart", "Operations")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(
            data=SimpleNamespace(note_categories=["Operations", "Empty"])
        )

        groups = dialog.group_note_items(
            [SimpleNamespace(note=note)], include_empty_categories=False
        )

        self.assertEqual([name for name, _items in groups], ["Operations"])

    def test_general_list_places_only_linked_notes_in_virtual_server_group(self):
        personal = normalize_note("personal", "Checklist", "Inspect", "Ops")
        linked = normalize_note("linked", "Restart", "Restart service", "Ops", "server-id")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.server_filter_id = None
        dialog.store = SimpleNamespace(data=SimpleNamespace(note_categories=["Ops"]))
        items = [SimpleNamespace(note=personal), SimpleNamespace(note=linked)]

        groups = dialog.group_note_items(items, include_empty_categories=True)

        self.assertEqual([key for key, _notes in groups], ["Ops", None])
        self.assertEqual([[item.note.id for item in notes] for _key, notes in groups], [
            ["personal"], ["linked"],
        ])

        dialog.server_filter_id = "server-id"
        scoped = dialog.group_note_items([items[1]], include_empty_categories=False)
        self.assertEqual([key for key, _notes in scoped], ["Ops"])

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
                    self.assertEqual(password_prompts, [("notes_export_password", dialog.on_export_password)])
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
            data=SimpleNamespace(note_categories=[], servers=[]),
        )
        dialog.translate = lambda key: key
        dialog.current_note_id = None
        dialog.server_filter_id = None
        dialog.loading_editor = False
        dialog.loading_search = False
        dialog.editor_dirty = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _text: None)
        dialog.import_button = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.export_button = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.import_export_menu_button = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.refresh_list = lambda *_args: None
        dialog.save_editor = lambda: False
        presented = []
        dialog.window = SimpleNamespace(
            get_visible=lambda: True, present=lambda: presented.append(True),
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
        dialog.store = SimpleNamespace(encryption_locked=False)
        dialog.ensure_window = lambda: None
        dialog.editor_dirty = True
        dialog.save_editor = lambda: False
        presented = []
        dialog.window = SimpleNamespace(
            get_visible=lambda: True, present=lambda: presented.append(True),
        )

        dialog.show_manager("server-id")

        self.assertEqual(presented, [True])

    def test_entry_modes_keep_global_actions_out_of_server_view(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(encryption_locked=False)
        dialog.translate = lambda key: key
        dialog.ensure_window = lambda: None
        dialog.editor_dirty = False
        dialog.current_note_id = "previous-note"
        dialog.loading_search = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        views = []
        dialog.refresh_list = lambda: views.append(dialog.server_filter_id)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _label: None)
        import_visibility = []
        export_visibility = []
        menu_visibility = []
        dialog.import_button = SimpleNamespace(set_visible=import_visibility.append)
        dialog.export_button = SimpleNamespace(set_visible=export_visibility.append)
        dialog.import_export_menu_button = SimpleNamespace(set_visible=menu_visibility.append)
        dialog.window = SimpleNamespace(get_visible=lambda: True, present=lambda: None)

        dialog.show_manager("server-id")
        self.assertEqual(views, ["server-id"])
        self.assertIsNone(dialog.current_note_id)
        self.assertEqual(import_visibility, [False])
        self.assertEqual(export_visibility, [False])
        self.assertEqual(menu_visibility, [False])

        dialog.show_manager()
        self.assertEqual(views, ["server-id", None])
        self.assertEqual(import_visibility, [False, True])
        self.assertEqual(export_visibility, [False, True])
        self.assertEqual(menu_visibility, [False, True])

    def test_opening_hidden_notes_window_starts_a_draft_in_the_current_scope(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(encryption_locked=False, read_only=False)
        dialog.translate = lambda key: key
        dialog.editor_tabs = {}
        dialog.active_editor_tab_key = None
        dialog.editor_dirty = False
        dialog.loading_search = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.add_button = SimpleNamespace(set_tooltip_text=lambda _text: None)
        dialog.set_import_export_actions_visible = lambda _visible: None
        dialog.refresh_list = lambda: None
        dialog.ensure_window = lambda: None
        visible = False
        dialog.window = SimpleNamespace(get_visible=lambda: visible, present=lambda: None)
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
        dialog.store = SimpleNamespace(encryption_locked=False, read_only=False)
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
        dialog.window = SimpleNamespace(get_visible=lambda: False, present=lambda: None)
        activated = []
        dialog.activate_editor_tab = activated.append
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
        idle_add.assert_called_once_with(dialog._show_server_notes, "server-id")
        self.assertEqual(timeout_add.call_args.args[0], 150)

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

        idle_add.assert_called_once_with(dialog._show_server_notes, "server-id")

    def test_incomplete_draft_is_kept_when_hiding_reusable_notes_window(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_dirty = True
        dialog.current_note_id = "existing-note"
        dialog.cancel_autosave = lambda: None
        dialog.text_view = object()
        dialog.editor_content = lambda: ""
        dialog.capture_active_editor_tab = lambda: None
        prompted = []
        hidden = []
        cleared = []
        dialog.confirm_discard_editor = lambda: prompted.append(True)
        dialog.clear_editor = lambda: cleared.append(True)
        dialog.window = SimpleNamespace(set_visible=lambda visible: hidden.append(visible))

        self.assertTrue(dialog.on_close_request(dialog.window))
        self.assertEqual(prompted, [])
        self.assertTrue(dialog.editor_dirty)
        self.assertEqual(cleared, [])
        self.assertEqual(hidden, [False])


class NotesIOTests(unittest.TestCase):
    def setUp(self):
        self.notes = [Note(
            "note-1", "Production runbook", "Restart the service.", "Operations",
            "server-1", "2026-10-01T09:00:00+00:00", "2026-10-02T12:00:00+00:00",
        )]
        self.categories = ["Empty", "Operations"]

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


class NotesStoreTests(unittest.TestCase):
    def make_store(self, root):
        return ConnectionStore(
            root / "connections.json", root / "settings.json", root / "statistics.json",
            root / "lock", root / "history", root / "notes.json",
        )

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
                self.assertIn("Empty", store.data.note_categories)
            finally:
                store.close()
            restored = self.make_store(root)
            try:
                self.assertEqual(restored.data.note_categories, ["Empty", "Operations copy"])
                self.assertEqual(len(restored.data.notes), 2)
            finally:
                restored.close()

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
