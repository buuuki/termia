# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .config_io import InvalidMasterPasswordError, MissingMasterPasswordError
from .models import Note
from .notes import NoteError
from .notes_io import export_notes_file, import_notes_file
from .notes_presenter import NotesPresenter


class NotesDialogs:
    """Reusable modeless notes manager and category-management window."""

    AUTOSAVE_DELAY_MS = 700

    def __init__(
        self,
        parent: Gtk.Window,
        store: Any,
        presenter: NotesPresenter,
        translate,
        ensure_writable,
        show_error,
        show_toast,
    ) -> None:
        self.parent = parent
        self.store = store
        self.presenter = presenter
        self.translate = translate
        self.ensure_writable = ensure_writable
        self.show_error = show_error
        self.show_toast = show_toast
        self.window: Gtk.Window | None = None
        self.category_window: Gtk.Window | None = None
        self.export_protection_window: Gtk.Window | None = None
        self.current_note_id: str | None = None
        self.server_filter_id: str | None = None
        self.category_filter: str | None = None
        self.last_search_query = ""
        self.autosave_id: int | None = None
        self.loading_editor = False
        self.loading_filters = False
        self.loading_search = False
        self.editor_dirty = False
        self.category_selected: str | None = None
        self.category_edit_mode: str | None = None

    def show_manager(self, server_id: str | None = None) -> None:
        if self.store.encryption_locked:
            self.ensure_writable()
            return
        self.ensure_window()
        if self.editor_dirty and not self.save_editor():
            self.window.present()
            return
        self.server_filter_id = server_id
        self.current_note_id = None
        self.category_filter = None
        self.loading_search = True
        try:
            self.search_entry.set_text("")
        finally:
            self.loading_search = False
        self.last_search_query = ""
        self.refresh_category_filter()
        self.refresh_server_selector()
        self.add_button.set_label(self.translate("notes_create_for_server") if server_id else self.translate("notes_create"))
        self.import_button.set_visible(server_id is None)
        self.export_button.set_visible(server_id is None)
        self.refresh_list()
        self.window.present()

    def ensure_window(self) -> None:
        if self.window is not None:
            return
        window = Gtk.Window(title=self.translate("notes_title"), transient_for=self.parent)
        window.set_modal(False)
        window.set_default_size(1240, 660)
        window.add_css_class("termia-notes-window")
        window.connect("close-request", self.on_close_request)
        self.window = window

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, f"set_margin_{side}")(14)
        window.set_child(root)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_size_request(360, -1)
        self.search_entry.set_placeholder_text(self.translate("notes_search"))
        self.search_entry.connect("search-changed", self.on_search_changed)
        toolbar.append(self.search_entry)

        self.category_filter_combo = Gtk.ComboBoxText()
        self.category_filter_combo.connect("changed", self.on_category_filter_changed)
        toolbar.append(self.category_filter_combo)

        self.category_manage_button = Gtk.Button(label=self.translate("notes_manage_categories"))
        self.category_manage_button.connect("clicked", lambda *_: self.show_categories())
        toolbar.append(self.category_manage_button)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        toolbar.append(spacer)

        self.add_button = Gtk.Button(label=self.translate("notes_create"))
        self.add_button.add_css_class("suggested-action")
        self.add_button.connect("clicked", lambda *_: self.create_note())
        toolbar.append(self.add_button)

        self.export_button = Gtk.Button(label=self.translate("notes_export"))
        self.export_button.connect("clicked", lambda *_: self.choose_export_protection())
        toolbar.append(self.export_button)

        self.import_button = Gtk.Button(label=self.translate("notes_import"))
        self.import_button.connect("clicked", lambda *_: self.start_import())
        toolbar.append(self.import_button)
        root.append(toolbar)

        self.scope_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.scope_label = Gtk.Label()
        self.scope_label.set_xalign(0)
        self.scope_label.set_hexpand(True)
        self.scope_bar.append(self.scope_label)
        root.append(self.scope_bar)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(330)
        paned.set_vexpand(True)
        root.append(paned)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_box.connect("row-selected", self.on_note_selected)
        self.notes_list = list_box
        list_scroller = Gtk.ScrolledWindow()
        list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroller.set_child(list_box)
        paned.set_start_child(list_scroller)

        self.detail_stack = Gtk.Stack()
        self.detail_stack.set_hexpand(True)
        self.detail_stack.set_vexpand(True)
        paned.set_end_child(self.detail_stack)

        preview = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        preview.set_margin_start(14)
        preview_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.preview_title = Gtk.Label()
        self.preview_title.set_xalign(0)
        self.preview_title.set_wrap(True)
        self.preview_title.set_hexpand(True)
        self.preview_title.add_css_class("title-2")
        preview_header.append(self.preview_title)
        self.preview_edit_button = Gtk.Button(label=self.translate("notes_edit"))
        self.preview_edit_button.connect("clicked", lambda *_: self.edit_selected_note())
        preview_header.append(self.preview_edit_button)
        preview.append(preview_header)
        self.preview_meta = Gtk.Label()
        self.preview_meta.set_xalign(0)
        self.preview_meta.set_wrap(True)
        self.preview_meta.add_css_class("dim-label")
        preview.append(self.preview_meta)
        self.preview_text = Gtk.TextView()
        self.preview_text.set_editable(False)
        self.preview_text.set_cursor_visible(False)
        self.preview_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        preview_scroller = Gtk.ScrolledWindow()
        preview_scroller.set_vexpand(True)
        preview_scroller.set_child(self.preview_text)
        preview.append(preview_scroller)
        self.detail_stack.add_named(preview, "preview")

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty.set_margin_start(14)
        empty.set_valign(Gtk.Align.CENTER)
        self.empty_label = Gtk.Label()
        self.empty_label.add_css_class("title-3")
        empty.append(self.empty_label)
        empty_create = Gtk.Button(label=self.translate("notes_create"))
        empty_create.set_halign(Gtk.Align.CENTER)
        empty_create.connect("clicked", lambda *_: self.create_note())
        self.empty_create_button = empty_create
        empty.append(empty_create)
        self.detail_stack.add_named(empty, "empty")

        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        editor.set_margin_start(14)
        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text(self.translate("notes_title_placeholder"))
        self.title_entry.add_css_class("title-3")
        self.title_entry.connect("changed", self.on_editor_changed)
        editor.append(self.title_entry)

        selectors = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        category_label = Gtk.Label(label=self.translate("notes_category"))
        selectors.append(category_label)
        self.category_combo = Gtk.ComboBoxText()
        self.category_combo.connect("changed", self.on_editor_changed)
        selectors.append(self.category_combo)
        server_label = Gtk.Label(label=self.translate("notes_association"))
        selectors.append(server_label)
        self.server_combo = Gtk.ComboBoxText()
        self.server_combo.set_hexpand(True)
        self.server_combo.connect("changed", self.on_editor_changed)
        selectors.append(self.server_combo)
        editor.append(selectors)

        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_monospace(False)
        text_view.get_buffer().connect("changed", self.on_editor_changed)
        self.text_view = text_view
        text_scroller = Gtk.ScrolledWindow()
        text_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        text_scroller.set_vexpand(True)
        text_scroller.set_child(text_view)
        editor.append(text_scroller)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_label = Gtk.Label()
        self.status_label.set_xalign(0)
        self.status_label.set_hexpand(True)
        footer.append(self.status_label)
        self.modified_label = Gtk.Label()
        self.modified_label.add_css_class("dim-label")
        footer.append(self.modified_label)
        self.save_button = Gtk.Button(label=self.translate("save"))
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", lambda *_: self.save_editor())
        footer.append(self.save_button)
        self.delete_button = Gtk.Button(label=self.translate("notes_delete"))
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", lambda *_: self.confirm_delete_note())
        footer.append(self.delete_button)
        self.done_button = Gtk.Button(label=self.translate("notes_done"))
        self.done_button.connect("clicked", lambda *_: self.finish_editing())
        footer.append(self.done_button)
        self.cancel_editor_button = Gtk.Button(label=self.translate("cancel"))
        self.cancel_editor_button.connect("clicked", lambda *_: self.cancel_editing())
        footer.append(self.cancel_editor_button)
        editor.append(footer)
        self.detail_stack.add_named(editor, "editor")

        self.refresh_category_selector()
        self.refresh_server_selector()
        self.configure_write_controls()
        self.set_editor_enabled(False)
        self.detail_stack.set_visible_child_name("empty")

    def configure_write_controls(self) -> None:
        writable = not self.store.read_only and not self.store.encryption_locked
        for widget in (
            self.category_manage_button,
            self.add_button,
            self.empty_create_button,
            self.import_button,
            self.title_entry,
            self.category_combo,
            self.server_combo,
            self.text_view,
            self.save_button,
            self.delete_button,
            self.done_button,
        ):
            widget.set_sensitive(writable)
        self.export_button.set_sensitive(not self.store.encryption_locked)
        self.preview_edit_button.set_sensitive(writable)

    def refresh_category_filter(self, selected: str | None = None) -> None:
        combo = self.category_filter_combo
        current = self.category_filter if selected is None else selected
        self.loading_filters = True
        try:
            combo.remove_all()
            combo.append("__all__", self.translate("notes_all_categories"))
            combo.append("", self.translate("notes_uncategorized"))
            for category in self.store.data.note_categories:
                combo.append(category, category)
            if current is None or current not in {"", *self.store.data.note_categories}:
                current = "__all__"
            combo.set_active_id(current)
        finally:
            self.loading_filters = False
        self.category_filter = None if current == "__all__" else current

    def refresh_category_selector(self, selected: str | None = None) -> None:
        if not hasattr(self, "category_combo"):
            return
        was_loading = self.loading_editor
        self.loading_editor = True
        try:
            self.category_combo.remove_all()
            self.category_combo.append("", self.translate("notes_uncategorized"))
            for category in self.store.data.note_categories:
                self.category_combo.append(category, category)
            self.category_combo.set_active_id(selected or "")
        finally:
            self.loading_editor = was_loading

    def refresh_server_selector(self, selected: str | None = None) -> None:
        if not hasattr(self, "server_combo"):
            return
        current = selected
        if current is None and self.current_note_id:
            note = self.find_note(self.current_note_id)
            current = note.server_id if note else None
        was_loading = self.loading_editor
        self.loading_editor = True
        try:
            self.server_combo.remove_all()
            self.server_combo.append("", self.translate("notes_standalone"))
            for server in sorted(self.store.data.servers, key=lambda item: item.name.casefold()):
                self.server_combo.append(server.id, server.name)
            self.server_combo.set_active_id(current or "")
        finally:
            self.loading_editor = was_loading

    def on_category_filter_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self.loading_filters:
            return
        active = combo.get_active_id()
        previous = self.category_filter
        next_filter = None if active in (None, "__all__") else active
        if self.editor_dirty and not self.save_editor():
            self.refresh_category_filter(previous)
            return
        self.category_filter = next_filter
        self.refresh_list()

    def on_search_changed(self, *_args) -> None:
        if self.loading_search:
            return
        query = self.search_entry.get_text()
        if self.editor_dirty and not self.save_editor():
            self.loading_search = True
            try:
                self.search_entry.set_text(self.last_search_query)
            finally:
                self.loading_search = False
            return
        self.last_search_query = query
        self.refresh_list()

    def refresh_list(self, selected_id: str | None = None) -> None:
        if not hasattr(self, "notes_list"):
            return
        selected_id = selected_id if selected_id is not None else self.current_note_id
        while child := self.notes_list.get_first_child():
            self.notes_list.remove(child)
        self.scope_bar.set_visible(self.server_filter_id is not None)
        if self.server_filter_id:
            server = next((item for item in self.store.data.servers if item.id == self.server_filter_id), None)
            self.scope_label.set_label(
                self.translate("notes_for_server").format(name=server.name if server else self.translate("notes_standalone"))
            )
        items = self.presenter.items(
            self.search_entry.get_text(), self.category_filter, self.server_filter_id,
        )
        selected_row = None
        first_row = None
        for item in items:
            row = Gtk.ListBoxRow()
            row.note_id = item.note.id
            if first_row is None:
                first_row = row
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            title = Gtk.Label(label=item.note.title)
            title.set_xalign(0)
            title.set_ellipsize(3)
            title.add_css_class("heading")
            detail = " · ".join(part for part in (
                item.note.category or self.translate("notes_uncategorized"),
                item.server_name or self.translate("notes_standalone"),
                item.note.modified_at,
            ) if part)
            subtitle = Gtk.Label(label=detail)
            subtitle.set_xalign(0)
            subtitle.set_ellipsize(3)
            subtitle.add_css_class("dim-label")
            content.append(title)
            content.append(subtitle)
            content.set_margin_top(8)
            content.set_margin_bottom(8)
            content.set_margin_start(8)
            content.set_margin_end(8)
            row.set_child(content)
            self.notes_list.append(row)
            if item.note.id == selected_id:
                selected_row = row
        selected_row = selected_row or first_row
        if selected_row is not None:
            self.notes_list.select_row(selected_row)
            selected_note = self.find_note(selected_row.note_id)
            if (
                selected_note is not None
                and self.current_note_id == selected_note.id
                and self.detail_stack.get_visible_child_name() != "editor"
            ):
                self.show_note_preview(selected_note)
        else:
            self.current_note_id = None
            self.clear_editor()
            self.show_empty_state()

    def on_note_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        note_id = getattr(row, "note_id", None)
        if not note_id or note_id == self.current_note_id:
            return
        if self.editor_dirty and not self.save_editor():
            previous = next(
                (item for item in self.iter_note_rows() if getattr(item, "note_id", None) == self.current_note_id),
                None,
            )
            if previous is not None:
                self.notes_list.select_row(previous)
            else:
                self.notes_list.unselect_all()
            return
        note = self.find_note(note_id)
        if note is None:
            return
        self.show_note_preview(note)

    def iter_note_rows(self):
        row = self.notes_list.get_first_child()
        while row:
            yield row
            row = row.get_next_sibling()

    def find_note(self, note_id: str) -> Note | None:
        return next((note for note in self.store.data.notes if note.id == note_id), None)

    def show_note_preview(self, note: Note) -> None:
        self.cancel_autosave()
        self.current_note_id = note.id
        self.editor_dirty = False
        self.preview_title.set_label(note.title)
        parts = [note.category or self.translate("notes_uncategorized")]
        if self.server_filter_id is None:
            server = next((item for item in self.store.data.servers if item.id == note.server_id), None)
            parts.append(server.name if server else self.translate("notes_standalone"))
        parts.append(self.translate("notes_modified").format(date=note.modified_at))
        self.preview_meta.set_label(" · ".join(parts))
        self.preview_text.get_buffer().set_text(note.content)
        self.detail_stack.set_visible_child_name("preview")

    def show_empty_state(self) -> None:
        if self.search_entry.get_text() or self.category_filter is not None:
            message = self.translate("notes_empty")
        elif self.server_filter_id is not None:
            message = self.translate("notes_empty_server")
        else:
            message = self.translate("notes_empty_all")
        self.empty_label.set_label(message)
        self.empty_create_button.set_label(
            self.translate("notes_create_for_server") if self.server_filter_id else self.translate("notes_create")
        )
        self.detail_stack.set_visible_child_name("empty")

    def edit_selected_note(self) -> None:
        if not self.ensure_writable() or not self.current_note_id:
            return
        note = self.find_note(self.current_note_id)
        if note is not None:
            self.load_editor(note)

    def load_editor(self, note: Note) -> None:
        self.cancel_autosave()
        self.loading_editor = True
        try:
            self.current_note_id = note.id
            self.editor_dirty = False
            self.title_entry.set_text(note.title)
            self.refresh_category_selector(note.category)
            self.refresh_server_selector(note.server_id)
            self.text_view.get_buffer().set_text(note.content)
            self.modified_label.set_label(
                self.translate("notes_modified").format(date=note.modified_at)
            )
            self.status_label.set_label(self.translate("notes_saved"))
            self.set_editor_enabled(True)
            self.detail_stack.set_visible_child_name("editor")
        finally:
            self.loading_editor = False

    def clear_editor(self) -> None:
        if not hasattr(self, "title_entry"):
            return
        self.cancel_autosave()
        self.loading_editor = True
        try:
            self.editor_dirty = False
            self.title_entry.set_text("")
            self.refresh_category_selector()
            self.refresh_server_selector(self.server_filter_id)
            self.text_view.get_buffer().set_text("")
            self.modified_label.set_label("")
            self.status_label.set_label(self.translate("notes_select_or_create"))
            self.set_editor_enabled(False)
        finally:
            self.loading_editor = False

    def set_editor_enabled(self, enabled: bool) -> None:
        writable = enabled and not self.store.read_only and not self.store.encryption_locked
        for widget in (self.title_entry, self.category_combo, self.server_combo, self.text_view, self.save_button, self.delete_button, self.done_button):
            widget.set_sensitive(writable)
        self.delete_button.set_sensitive(writable and self.current_note_id is not None)

    def create_note(self) -> None:
        if not self.ensure_writable():
            return
        if self.editor_dirty and not self.save_editor():
            return
        self.current_note_id = None
        self.loading_editor = True
        try:
            self.editor_dirty = False
            self.title_entry.set_text("")
            self.refresh_category_selector()
            self.refresh_server_selector(self.server_filter_id)
            self.text_view.get_buffer().set_text("")
            self.modified_label.set_label("")
            self.status_label.set_label(self.translate("notes_enter_to_save"))
            self.set_editor_enabled(True)
        finally:
            self.loading_editor = False
        self.notes_list.unselect_all()
        self.detail_stack.set_visible_child_name("editor")
        self.title_entry.grab_focus()

    def finish_editing(self) -> None:
        if self.editor_dirty and not self.save_editor():
            return
        note = self.find_note(self.current_note_id) if self.current_note_id else None
        if note is not None:
            self.show_note_preview(note)
        else:
            self.refresh_list()

    def cancel_editing(self) -> None:
        if self.editor_dirty:
            self.confirm_discard_editor(close_window=False)
            return
        selected_id = self.current_note_id
        self.current_note_id = None
        self.refresh_list(selected_id)

    def on_editor_changed(self, *_args) -> None:
        if self.loading_editor:
            return
        self.editor_dirty = True
        if not self.title_entry.get_text().strip() or not self.editor_content().strip():
            self.cancel_autosave()
            self.status_label.set_label(self.translate("notes_enter_to_save"))
            return
        self.schedule_autosave()

    def schedule_autosave(self) -> None:
        if self.store.read_only or self.store.encryption_locked:
            return
        self.cancel_autosave()
        self.status_label.set_label(self.translate("notes_saving"))
        self.autosave_id = GLib.timeout_add(self.AUTOSAVE_DELAY_MS, self.on_autosave_timeout)

    def cancel_autosave(self) -> None:
        if self.autosave_id is not None:
            GLib.source_remove(self.autosave_id)
            self.autosave_id = None

    def on_autosave_timeout(self) -> bool:
        self.autosave_id = None
        self.save_editor()
        return GLib.SOURCE_REMOVE

    def editor_content(self) -> str:
        buffer = self.text_view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def save_editor(self) -> bool:
        if not self.editor_dirty and self.current_note_id is not None:
            self.status_label.set_label(self.translate("notes_saved"))
            return True
        title, content = self.title_entry.get_text(), self.editor_content()
        if not title.strip() or not content.strip():
            self.status_label.set_label(self.translate("notes_content_required"))
            return False
        category = self.category_combo.get_active_id() or ""
        server_id = self.server_combo.get_active_id() or None
        try:
            if self.current_note_id is None:
                note = self.store.add_note(title, content, category, server_id)
                self.current_note_id = note.id
            else:
                self.store.update_note(self.current_note_id, title, content, category, server_id)
                note = self.find_note(self.current_note_id)
            self.status_label.set_label(self.translate("notes_saved"))
            self.editor_dirty = False
            if note is not None:
                self.modified_label.set_label(self.translate("notes_modified").format(date=note.modified_at))
            self.refresh_category_filter()
            self.refresh_list(self.current_note_id)
            self.set_editor_enabled(True)
            return True
        except (OSError, NoteError, RuntimeError, ValueError):
            self.status_label.set_label(self.translate("notes_save_failed"))
            self.show_error(self.translate("notes_save_failed_detail"))
            return False

    def on_close_request(self, _window: Gtk.Window) -> bool:
        if self.editor_dirty:
            self.cancel_autosave()
            if not self.title_entry.get_text().strip() or not self.editor_content().strip():
                self.confirm_discard_editor()
                return True
            if not self.save_editor():
                self.confirm_discard_editor()
                return True
        self.window.set_visible(False)
        return True

    def confirm_discard_editor(self, close_window: bool = True) -> None:
        dialog = Gtk.AlertDialog(message=self.translate("notes_discard_unsaved"))
        dialog.set_buttons([self.translate("notes_keep_editing"), self.translate("notes_discard")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self.window, None, self.on_discard_editor_response, close_window)

    def on_discard_editor_response(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, close_window: bool = True) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            selected_id = self.current_note_id
            self.editor_dirty = False
            self.current_note_id = None
            self.clear_editor()
            if close_window:
                self.window.set_visible(False)
            else:
                self.refresh_list(selected_id)

    def confirm_delete_note(self) -> None:
        if self.editor_dirty and not self.save_editor():
            return
        if not self.current_note_id or not self.ensure_writable():
            return
        note = self.find_note(self.current_note_id)
        if note is None:
            return
        dialog = Gtk.AlertDialog(
            message=self.translate("notes_delete_confirm").format(name=note.title),
        )
        dialog.set_buttons([self.translate("cancel"), self.translate("notes_delete")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self.window, None, self.on_delete_note_response, note.id)

    def on_delete_note_response(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, note_id: str) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        try:
            self.store.delete_note(note_id)
        except (OSError, RuntimeError):
            self.show_error(self.translate("notes_save_failed_detail"))
            return
        self.current_note_id = None
        self.refresh_list()

    def show_categories(self) -> None:
        if self.editor_dirty and not self.save_editor():
            return
        if not self.ensure_writable():
            return
        if self.category_window is None:
            self.build_category_window()
        self.refresh_category_grid()
        self.category_window.present()

    def build_category_window(self) -> None:
        window = Gtk.Window(title=self.translate("notes_manage_categories"), transient_for=self.window)
        window.set_modal(False)
        window.set_default_size(640, 480)
        window.connect("close-request", lambda source: (source.set_visible(False), True)[1])
        self.category_window = window
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, f"set_margin_{side}")(12)
        window.set_child(root)
        self.category_grid = Gtk.FlowBox()
        self.category_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.category_grid.set_max_children_per_line(3)
        self.category_grid.set_row_spacing(8)
        self.category_grid.set_column_spacing(8)
        self.category_grid.connect("selected-children-changed", self.on_category_selected)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self.category_grid)
        root.append(scroll)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.category_add = Gtk.Button(label=self.translate("notes_category_add"))
        self.category_rename = Gtk.Button(label=self.translate("notes_category_rename"))
        self.category_duplicate = Gtk.Button(label=self.translate("notes_category_duplicate"))
        self.category_delete = Gtk.Button(label=self.translate("notes_category_delete"))
        self.category_delete.add_css_class("destructive-action")
        for button in (self.category_add, self.category_rename, self.category_duplicate, self.category_delete):
            actions.append(button)
        root.append(actions)
        self.category_name_entry = Gtk.Entry()
        self.category_name_entry.set_placeholder_text(self.translate("notes_category_name"))
        self.category_name_entry.set_visible(False)
        root.append(self.category_name_entry)
        edit_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.category_name_save = Gtk.Button(label=self.translate("save"))
        self.category_name_cancel = Gtk.Button(label=self.translate("cancel"))
        self.category_name_save.set_visible(False)
        self.category_name_cancel.set_visible(False)
        edit_actions.append(self.category_name_save)
        edit_actions.append(self.category_name_cancel)
        root.append(edit_actions)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer.set_halign(Gtk.Align.END)
        close = Gtk.Button(label=self.translate("close"))
        close.connect("clicked", lambda *_: window.set_visible(False))
        footer.append(close)
        root.append(footer)
        self.category_add.connect("clicked", lambda *_: self.begin_category_edit("add"))
        self.category_rename.connect("clicked", lambda *_: self.begin_category_edit("rename"))
        self.category_duplicate.connect("clicked", lambda *_: self.begin_category_edit("duplicate"))
        self.category_delete.connect("clicked", lambda *_: self.confirm_delete_category())
        self.category_name_save.connect("clicked", lambda *_: self.save_category_edit())
        self.category_name_entry.connect("activate", lambda *_: self.save_category_edit())
        self.category_name_cancel.connect("clicked", lambda *_: self.cancel_category_edit())

    def refresh_category_grid(self, selected: str | None = None) -> None:
        self.category_grid.unselect_all()
        while child := self.category_grid.get_first_child():
            self.category_grid.remove(child)
        self.category_keys = []
        counts = dict(self.presenter.categories())
        for category in self.store.data.note_categories:
            tile = Gtk.FlowBoxChild()
            tile.add_css_class("termia-note-category-tile")
            frame = Gtk.Frame()
            frame.add_css_class("termia-note-category-frame")
            frame.set_size_request(170, 112)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            icon = Gtk.Image.new_from_icon_name("folder-symbolic")
            icon.set_pixel_size(30)
            name = Gtk.Label(label=category)
            name.set_ellipsize(3)
            count = Gtk.Label(label=self.translate("notes_category_count").format(count=counts.get(category, 0)))
            count.add_css_class("dim-label")
            for child in (icon, name, count):
                box.append(child)
            frame.set_child(box)
            tile.set_child(frame)
            self.category_grid.insert(tile, -1)
            self.category_keys.append(category)
            if category == selected:
                self.category_grid.select_child(tile)
        self.category_selected = selected if selected in self.category_keys else None
        self.update_category_buttons()

    def on_category_selected(self, grid: Gtk.FlowBox) -> None:
        selected = grid.get_selected_children()
        index = selected[0].get_index() if selected else -1
        self.category_selected = self.category_keys[index] if 0 <= index < len(self.category_keys) else None
        self.update_category_buttons()

    def update_category_buttons(self) -> None:
        selected = self.category_selected is not None
        self.category_rename.set_sensitive(selected)
        self.category_duplicate.set_sensitive(selected)
        self.category_delete.set_sensitive(selected)

    def begin_category_edit(self, mode: str) -> None:
        if mode != "add" and self.category_selected is None:
            return
        self.category_edit_mode = mode
        if mode == "rename":
            value = self.category_selected or ""
        elif mode == "duplicate":
            value = f"{self.category_selected} {self.translate('snippet_copy_suffix')}"
        else:
            value = ""
        self.category_name_entry.set_text(value)
        self.category_name_entry.set_visible(True)
        self.category_name_save.set_visible(True)
        self.category_name_cancel.set_visible(True)
        self.category_name_entry.grab_focus()

    def save_category_edit(self) -> None:
        name, mode, original = self.category_name_entry.get_text(), self.category_edit_mode, self.category_selected
        try:
            if mode == "add":
                self.store.add_note_category(name)
            elif mode == "rename" and original:
                self.store.rename_note_category(original, name)
            elif mode == "duplicate" and original:
                self.store.duplicate_note_category(original, name)
            else:
                return
        except (NoteError, OSError, RuntimeError) as exc:
            self.show_error(
                self.translate(str(exc)) if isinstance(exc, NoteError)
                else self.translate("notes_save_failed_detail")
            )
            return
        self.cancel_category_edit()
        self.refresh_category_filter()
        self.refresh_current_editor_metadata()
        self.refresh_list()
        self.refresh_category_grid(name.strip())

    def refresh_current_editor_metadata(self) -> None:
        note = self.find_note(self.current_note_id) if self.current_note_id else None
        self.refresh_category_selector(note.category if note else None)
        self.refresh_server_selector(note.server_id if note else self.server_filter_id)
        if note:
            self.modified_label.set_label(
                self.translate("notes_modified").format(date=note.modified_at)
            )

    def cancel_category_edit(self) -> None:
        self.category_edit_mode = None
        self.category_name_entry.set_text("")
        self.category_name_entry.set_visible(False)
        self.category_name_save.set_visible(False)
        self.category_name_cancel.set_visible(False)

    def confirm_delete_category(self) -> None:
        if not self.category_selected:
            return
        name = self.category_selected
        count = sum(note.category == name for note in self.store.data.notes)
        dialog = Gtk.AlertDialog(
            message=self.translate("notes_category_delete_confirm").format(name=name, count=count),
        )
        dialog.set_buttons([self.translate("cancel"), self.translate("notes_category_delete")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self.category_window, None, self.on_delete_category_response, name)

    def on_delete_category_response(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, name: str) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        try:
            self.store.delete_note_category(name)
        except (NoteError, OSError, RuntimeError) as exc:
            self.show_error(
                self.translate(str(exc)) if isinstance(exc, NoteError)
                else self.translate("notes_save_failed_detail")
            )
            return
        self.category_filter = None
        self.refresh_category_filter()
        self.refresh_current_editor_metadata()
        self.refresh_list()
        self.refresh_category_grid()

    def choose_export_protection(self) -> None:
        if self.editor_dirty and not self.save_editor():
            return
        if self.export_protection_window is not None:
            self.export_protection_window.present()
            return

        window = Gtk.Window(
            title=self.translate("notes_export"), transient_for=self.window,
        )
        window.set_modal(True)
        window.set_resizable(False)
        window.set_default_size(500, -1)
        window.connect("close-request", self.on_export_protection_close)
        self.export_protection_window = window

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, f"set_margin_{side}")(18)
        window.set_child(root)

        explanation = Gtk.Label(label=self.translate("notes_export_protection"))
        explanation.set_xalign(0)
        explanation.set_wrap(True)
        explanation.add_css_class("title-3")
        root.append(explanation)

        options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.append(options)
        self.export_plain_choice = self.export_protection_option(
            "notes_export_plain", "notes_export_plain_detail",
        )
        self.export_password_choice = self.export_protection_option(
            "notes_export_password", "notes_export_password_detail",
        )
        self.export_password_choice.set_group(self.export_plain_choice)
        options.append(self.export_plain_choice)
        options.append(self.export_password_choice)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        root.append(actions)
        cancel = Gtk.Button(label=self.translate("cancel"))
        cancel.connect("clicked", lambda *_: window.close())
        actions.append(cancel)
        self.export_continue_button = Gtk.Button(
            label=self.translate("notes_export_continue"),
        )
        self.export_continue_button.add_css_class("suggested-action")
        self.export_continue_button.set_sensitive(False)
        self.export_continue_button.connect(
            "clicked", self.on_export_protection_continue,
        )
        actions.append(self.export_continue_button)
        self.export_plain_choice.connect(
            "toggled", self.on_export_protection_choice_changed,
        )
        self.export_password_choice.connect(
            "toggled", self.on_export_protection_choice_changed,
        )
        window.present()

    def export_protection_option(self, title_key: str, detail_key: str) -> Gtk.CheckButton:
        choice = Gtk.CheckButton()
        choice.set_hexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label=self.translate(title_key))
        title.set_xalign(0)
        title.set_wrap(True)
        title.add_css_class("heading")
        content.append(title)
        detail = Gtk.Label(label=self.translate(detail_key))
        detail.set_xalign(0)
        detail.set_wrap(True)
        detail.add_css_class("dim-label")
        content.append(detail)
        choice.set_child(content)
        return choice

    def on_export_protection_choice_changed(self, *_args) -> None:
        selected = (
            self.export_plain_choice.get_active()
            or self.export_password_choice.get_active()
        )
        self.export_continue_button.set_sensitive(selected)

    def on_export_protection_close(self, window: Gtk.Window) -> bool:
        if self.export_protection_window is window:
            self.export_protection_window = None
        return False

    def on_export_protection_continue(self, *_args) -> None:
        encrypted = self.export_password_choice.get_active()
        window = self.export_protection_window
        self.export_protection_window = None
        if window is not None:
            window.destroy()
        if encrypted:
            self.ask_password(self.translate("notes_export_password"), self.on_export_password)
        else:
            self.choose_export_file(None)

    def on_export_password(self, password: str | None) -> None:
        if password:
            self.choose_export_file(password)

    def choose_export_file(self, password: str | None) -> None:
        dialog = Gtk.FileDialog(title=self.translate("notes_export"))
        dialog.set_initial_name("termia-notes.json")
        dialog.save(self.window, None, self.on_export_file_selected, password)

    def on_export_file_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, password: str | None) -> None:
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if not file or not file.get_path():
            return
        try:
            export_notes_file(Path(file.get_path()), self.store.data.notes, self.store.data.note_categories, password)
            self.show_toast(self.translate("notes_export_success"))
        except (OSError, ValueError) as exc:
            self.show_error(self.translate("notes_export_failed").format(error=exc))

    def start_import(self) -> None:
        if not self.ensure_writable():
            return
        if self.editor_dirty and not self.save_editor():
            return
        dialog = Gtk.FileDialog(title=self.translate("notes_import"))
        dialog.open(self.window, None, self.on_import_file_selected)

    def on_import_file_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file and file.get_path():
            self.import_path = Path(file.get_path())
            self.read_import(None)

    def read_import(self, password: str | None) -> None:
        try:
            notes, categories = import_notes_file(self.import_path, password)
        except MissingMasterPasswordError:
            self.ask_password(self.translate("notes_import_password"), self.on_import_password)
            return
        except (InvalidMasterPasswordError, OSError, ValueError, TypeError) as exc:
            self.show_error(self.translate("notes_import_failed").format(error=exc))
            return
        server_ids = {server.id for server in self.store.data.servers}
        detached = 0
        for note in notes:
            if note.server_id and note.server_id not in server_ids:
                note.server_id = None
                detached += 1
        self.pending_import = (notes, categories, detached)
        if self.store.data.notes or self.store.data.note_categories:
            dialog = Gtk.AlertDialog(
                message=self.translate("notes_import_existing").format(
                    notes=len(self.store.data.notes), categories=len(self.store.data.note_categories),
                ),
                detail=self.translate("notes_import_backup_detail"),
            )
            dialog.set_buttons([
                self.translate("notes_keep_existing"),
                self.translate("notes_backup_replace"),
            ])
            dialog.set_cancel_button(0)
            dialog.set_default_button(0)
            dialog.choose(self.window, None, self.on_import_replace_response)
        else:
            self.replace_notes_with_import()

    def on_import_password(self, password: str | None) -> None:
        if password:
            self.read_import(password)

    def on_import_replace_response(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, _data=None) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            self.replace_notes_with_import()

    def replace_notes_with_import(self) -> None:
        notes, categories, detached = self.pending_import
        old_notes = list(self.store.data.notes)
        old_categories = list(self.store.data.note_categories)
        try:
            if old_notes or old_categories:
                self.store.notes_file_store.backup_current_file()
            self.store.data.notes = notes
            self.store.data.note_categories = categories
            self.store.save_notes()
        except (OSError, ValueError, RuntimeError) as exc:
            self.store.data.notes = old_notes
            self.store.data.note_categories = old_categories
            self.show_error(self.translate("notes_import_failed").format(error=exc))
            return
        self.server_filter_id = None
        self.category_filter = None
        self.current_note_id = None
        self.editor_dirty = False
        self.refresh_category_filter()
        self.refresh_category_selector()
        self.refresh_server_selector()
        self.refresh_list()
        message = self.translate("notes_import_success").format(count=len(notes))
        if detached:
            message = f"{message} {self.translate('notes_import_detached').format(count=detached)}"
        self.show_toast(message)

    def ask_password(self, title: str, callback) -> None:
        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.set_default_size(420, 120)
        content = dialog.get_content_area()
        content.set_margin_top(14)
        content.set_margin_bottom(8)
        content.set_margin_start(14)
        content.set_margin_end(14)
        password_label = Gtk.Label(label=self.translate("notes_password"))
        password_label.set_xalign(0)
        content.append(password_label)
        entry = Gtk.PasswordEntry()
        entry.set_show_peek_icon(True)
        content.append(entry)
        dialog.add_button(self.translate("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.translate("continue"), Gtk.ResponseType.ACCEPT)

        def response(source: Gtk.Dialog, result: int) -> None:
            password = entry.get_text() if result == Gtk.ResponseType.ACCEPT else None
            source.destroy()
            callback(password or None)

        dialog.connect("response", response)
        dialog.present()
        entry.grab_focus()

    def show_for_server_after_popover(self, popover: Gtk.Popover, server_id: str) -> None:
        presented = False

        def present_once(*_args) -> bool:
            nonlocal presented
            if not presented:
                presented = True
                GLib.idle_add(self._show_server_notes, server_id)
            return GLib.SOURCE_REMOVE

        popover.connect("closed", present_once)
        popover.popdown()
        GLib.timeout_add(150, present_once)

    def _show_server_notes(self, server_id: str) -> bool:
        self.show_manager(server_id)
        return GLib.SOURCE_REMOVE

    def shutdown(self) -> None:
        self.cancel_autosave()
        for window in (self.category_window, self.window):
            if window is not None:
                window.destroy()

    def prepare_shutdown(self) -> bool:
        if not self.editor_dirty or self.window is None:
            return True
        self.cancel_autosave()
        if not self.save_editor():
            self.window.present()
            return False
        return True
