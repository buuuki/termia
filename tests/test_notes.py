import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from termia.config_io import (
    CONNECTION_STORAGE_ENCRYPTED,
    CONNECTION_STORAGE_OBFUSCATED,
    InvalidMasterPasswordError,
    MissingMasterPasswordError,
)
from termia.models import Note
from termia.notes import NoteError, normalize_note, note_matches_query
from termia.notes_dialogs import NotesDialogs
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

    def test_presenter_search_filters_and_sorts_by_modified_time(self):
        first = normalize_note("old", "Runbook", "Restart", now="2026-10-01T10:00:00+00:00")
        second = normalize_note("new", "Database", "Backup", now="2026-10-02T10:00:00+00:00")
        presenter = NotesPresenter(lambda: [first, second], lambda: ["Ops"], lambda: [])

        self.assertEqual([item.note.id for item in presenter.items()], ["new", "old"])
        self.assertEqual([item.note.id for item in presenter.items("backup")], ["new"])


class NotesDialogSignalTests(unittest.TestCase):
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
            encryption_locked=False,
            data=SimpleNamespace(note_categories=[], servers=[]),
        )
        dialog.translate = lambda key: key
        dialog.current_note_id = None
        dialog.category_filter = None
        dialog.server_filter_id = None
        dialog.loading_editor = False
        dialog.loading_filters = False
        dialog.loading_search = False
        dialog.editor_dirty = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.add_button = SimpleNamespace(set_label=lambda _text: None)
        dialog.import_button = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.export_button = SimpleNamespace(set_visible=lambda _visible: None)
        dialog.category_combo = EmittingCombo(dialog.on_editor_changed)
        dialog.server_combo = EmittingCombo(dialog.on_editor_changed)
        dialog.category_filter_combo = EmittingCombo(dialog.on_category_filter_changed)
        dialog.refresh_list = lambda *_args: None
        dialog.save_editor = lambda: False
        presented = []
        dialog.window = SimpleNamespace(present=lambda: presented.append(True))
        dialog.ensure_window = lambda: (
            dialog.refresh_category_selector(), dialog.refresh_server_selector()
        )

        dialog.show_manager()

        self.assertEqual(presented, [True])
        self.assertFalse(dialog.editor_dirty)

    def test_incomplete_draft_waits_for_both_title_and_text(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.loading_editor = False
        dialog.editor_dirty = False
        dialog.title_entry = SimpleNamespace(get_text=lambda: "Runbook")
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
        dialog.window = SimpleNamespace(present=lambda: presented.append(True))

        dialog.show_manager("server-id")

        self.assertEqual(presented, [True])

    def test_entry_modes_keep_global_actions_out_of_server_view(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(encryption_locked=False)
        dialog.translate = lambda key: key
        dialog.ensure_window = lambda: None
        dialog.editor_dirty = False
        dialog.current_note_id = "previous-note"
        dialog.category_filter = "Previous"
        dialog.loading_search = False
        dialog.search_entry = SimpleNamespace(set_text=lambda _text: None)
        dialog.refresh_category_filter = lambda: None
        dialog.refresh_server_selector = lambda: None
        views = []
        dialog.refresh_list = lambda: views.append(dialog.server_filter_id)
        dialog.add_button = SimpleNamespace(set_label=lambda _label: None)
        import_visibility = []
        export_visibility = []
        dialog.import_button = SimpleNamespace(set_visible=import_visibility.append)
        dialog.export_button = SimpleNamespace(set_visible=export_visibility.append)
        dialog.window = SimpleNamespace(present=lambda: None)

        dialog.show_manager("server-id")
        self.assertEqual(views, ["server-id"])
        self.assertIsNone(dialog.current_note_id)
        self.assertIsNone(dialog.category_filter)
        self.assertEqual(import_visibility, [False])
        self.assertEqual(export_visibility, [False])

        dialog.show_manager()
        self.assertEqual(views, ["server-id", None])
        self.assertEqual(import_visibility, [False, True])
        self.assertEqual(export_visibility, [False, True])

    def test_note_preview_is_read_only_content_for_selected_note(self):
        note = Note("note-id", "Runbook", "Preview content", "Ops", "server-id", "", "2026-10-05")
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.store = SimpleNamespace(data=SimpleNamespace(servers=[SimpleNamespace(id="server-id", name="Web")]))
        dialog.server_filter_id = "server-id"
        dialog.translate = lambda key: key
        dialog.cancel_autosave = lambda: None
        titles = []
        metadata = []
        contents = []
        visible_pages = []
        dialog.preview_title = SimpleNamespace(set_label=titles.append)
        dialog.preview_meta = SimpleNamespace(set_label=metadata.append)
        dialog.preview_text = SimpleNamespace(get_buffer=lambda: SimpleNamespace(set_text=contents.append))
        dialog.detail_stack = SimpleNamespace(set_visible_child_name=visible_pages.append)

        dialog.show_note_preview(note)

        self.assertEqual(dialog.current_note_id, "note-id")
        self.assertEqual(titles, ["Runbook"])
        self.assertEqual(contents, ["Preview content"])
        self.assertNotIn("Web", metadata[0])
        self.assertEqual(visible_pages, ["preview"])

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

    def test_incomplete_draft_can_be_discarded_to_close_window(self):
        dialog = NotesDialogs.__new__(NotesDialogs)
        dialog.editor_dirty = True
        dialog.current_note_id = "existing-note"
        dialog.cancel_autosave = lambda: None
        dialog.title_entry = SimpleNamespace(get_text=lambda: "Runbook")
        dialog.editor_content = lambda: ""
        prompted = []
        hidden = []
        cleared = []
        dialog.confirm_discard_editor = lambda: prompted.append(True)
        dialog.clear_editor = lambda: cleared.append(True)
        dialog.window = SimpleNamespace(set_visible=lambda visible: hidden.append(visible))

        self.assertTrue(dialog.on_close_request(dialog.window))
        self.assertEqual(prompted, [True])
        self.assertEqual(hidden, [])
        dialog.on_discard_editor_response(SimpleNamespace(choose_finish=lambda _result: 1), None)
        self.assertFalse(dialog.editor_dirty)
        self.assertIsNone(dialog.current_note_id)
        self.assertEqual(cleared, [True])
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
