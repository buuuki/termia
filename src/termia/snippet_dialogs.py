# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK views for managing and explicitly running command snippets."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gio, GLib, Gtk, Vte

from .debug import log_event
from .models import CommandSnippet
from .snippet_presenter import SnippetPresenter
from .snippets import SnippetError, render_snippet, snippet_variables
from .stores import ConnectionStore
from .ui_state import TerminalSession


@dataclass
class ManagerState:
    dialog: Gtk.Dialog
    listing: Gtk.ListBox
    actions: tuple[Gtk.Button, Gtk.Button, Gtk.Button]
    visible_ids: list[str]
    selected_id: str | None = None
    selection_handler_id: int | None = None


@dataclass
class EditorState:
    dialog: Gtk.Dialog
    manager: ManagerState
    snippet_id: str | None
    duplicate: bool
    name: Gtk.Entry
    category: Gtk.Entry
    scope: Gtk.ComboBoxText
    target: Gtk.ComboBoxText
    command: Gtk.TextView


@dataclass
class RunContext:
    owner: Gtk.Window
    session: TerminalSession
    terminal: Vte.Terminal
    snippet: CommandSnippet


@dataclass
class PickerState:
    dialog: Gtk.Dialog
    owner: Gtk.Window
    session: TerminalSession
    terminal: Vte.Terminal
    server_id: str | None
    search: Gtk.SearchEntry
    listing: Gtk.ListBox
    preview: Gtk.Button
    visible_ids: list[str]
    selected_id: str | None = None
    selection_handler_id: int | None = None


@dataclass
class DialogLifetime:
    dialog: Gtk.Dialog
    state: object
    handlers: list[tuple[Gtk.Widget, int]]
    closing: bool = False


class SnippetDialogs:
    """Own snippet dialog state through explicit callback data."""

    def __init__(
        self,
        parent: Gtk.Window,
        store: ConnectionStore,
        presenter: SnippetPresenter,
        translate: Callable[[str], str],
        ensure_writable: Callable[[], bool],
        show_error: Callable[[str], None],
        show_notice: Callable[[str], None],
    ) -> None:
        self.parent = parent
        self.store = store
        self.presenter = presenter
        self.translate = translate
        self.ensure_writable = ensure_writable
        self.show_error = show_error
        self.show_notice = show_notice
        # PyGObject signal user data is not a safe ownership boundary for a
        # dialog's Python state. Keep it alive until GTK has completely
        # finished destroying the native widget tree.
        self._active_dialog_states: dict[int, DialogLifetime] = {}

    def retain_dialog_state(self, dialog: Gtk.Dialog, state: object) -> None:
        key = id(dialog)
        self._active_dialog_states[key] = DialogLifetime(dialog, state, [])
        self.connect_dialog_signal(dialog, dialog, "close-request", self.on_dialog_close_request, key)

    def connect_dialog_signal(
        self,
        dialog: Gtk.Dialog,
        emitter: Gtk.Widget,
        signal: str,
        callback: Callable[..., object],
        *data: object,
    ) -> int:
        handler_id = emitter.connect(signal, callback, *data)
        self._active_dialog_states[id(dialog)].handlers.append((emitter, handler_id))
        return handler_id

    def on_dialog_close_request(self, dialog: Gtk.Dialog, _key: int) -> bool:
        self.destroy_dialog(dialog)
        return True

    def destroy_dialog(self, dialog: Gtk.Dialog) -> None:
        key = id(dialog)
        lifetime = self._active_dialog_states.get(key)
        if lifetime is None or lifetime.closing:
            return
        lifetime.closing = True
        for emitter, handler_id in reversed(lifetime.handlers):
            if emitter.handler_is_connected(handler_id):
                emitter.disconnect(handler_id)
        lifetime.handlers.clear()
        dialog.set_visible(False)
        GLib.idle_add(self.finalize_dialog, key)

    def finalize_dialog(self, key: int) -> bool:
        lifetime = self._active_dialog_states.get(key)
        if lifetime is not None:
            lifetime.dialog.destroy()
            GLib.idle_add(self.release_dialog_state, key)
        return GLib.SOURCE_REMOVE

    def release_dialog_state(self, key: int) -> bool:
        self._active_dialog_states.pop(key, None)
        return GLib.SOURCE_REMOVE

    def add_actions(self, dialog: Gtk.Dialog, confirm_label: str) -> Gtk.Button:
        cancel = dialog.add_button(self.translate("cancel"), Gtk.ResponseType.CANCEL)
        cancel.set_margin_end(6)
        cancel.set_margin_bottom(12)
        confirm = dialog.add_button(confirm_label, Gtk.ResponseType.OK)
        confirm.set_margin_end(12)
        confirm.set_margin_bottom(12)
        return confirm

    @staticmethod
    def content(dialog: Gtk.Dialog) -> Gtk.Box:
        box = dialog.get_content_area()
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_spacing(10)
        return box

    @staticmethod
    def clear_list(listing: Gtk.ListBox) -> None:
        listing.unselect_all()
        child = listing.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            listing.remove(child)
            child = next_child

    @staticmethod
    def append_row(listing: Gtk.ListBox, text: str, *, enabled: bool = True) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_activatable(enabled)
        row.set_sensitive(enabled)
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.set_margin_start(10)
        label.set_margin_end(10)
        row.set_child(label)
        listing.append(row)
        return row

    def show_manager(self) -> ManagerState | None:
        if not self.ensure_writable():
            return None
        dialog = Gtk.Dialog(
            title=self.translate("manage_snippets"),
            transient_for=self.parent,
            modal=True,
        )
        dialog.set_default_size(680, 460)
        close = dialog.add_button(self.translate("close"), Gtk.ResponseType.CLOSE)
        close.set_margin_end(12)
        close.set_margin_bottom(12)
        listing = Gtk.ListBox()
        listing.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(listing)
        self.content(dialog).append(scroller)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add = Gtk.Button(label=self.translate("snippet_add"))
        edit = Gtk.Button(label=self.translate("snippet_edit"))
        duplicate = Gtk.Button(label=self.translate("snippet_duplicate"))
        delete = Gtk.Button(label=self.translate("snippet_delete"))
        delete.add_css_class("destructive-action")
        for button in (add, edit, duplicate, delete):
            buttons.append(button)
        self.content(dialog).append(buttons)
        state = ManagerState(dialog, listing, (edit, duplicate, delete), [])
        self.retain_dialog_state(dialog, state)
        self.connect_dialog_signal(dialog, dialog, "response", self.on_close_response)
        state.selection_handler_id = self.connect_dialog_signal(
            dialog, listing, "row-selected", self.on_manager_selected, state,
        )
        self.connect_dialog_signal(dialog, add, "clicked", self.on_manager_add, state)
        self.connect_dialog_signal(dialog, edit, "clicked", self.on_manager_edit, state)
        self.connect_dialog_signal(dialog, duplicate, "clicked", self.on_manager_duplicate, state)
        self.connect_dialog_signal(dialog, delete, "clicked", self.on_manager_delete, state)
        self.refresh_manager(state)
        dialog.present()
        return state

    def on_close_response(self, dialog: Gtk.Dialog, _response: Gtk.ResponseType) -> None:
        self.destroy_dialog(dialog)

    def refresh_manager(self, state: ManagerState, selected_id: str | None = None) -> None:
        handler_id = state.selection_handler_id
        if handler_id is not None:
            state.listing.handler_block(handler_id)
        try:
            self.clear_list(state.listing)
            items = self.presenter.manager_items()
            state.visible_ids = [item.id for item in items]
            state.selected_id = None
            for item in items:
                row = self.append_row(state.listing, item.label)
                if item.id == selected_id:
                    state.listing.select_row(row)
                    state.selected_id = item.id
        finally:
            if handler_id is not None:
                state.listing.handler_unblock(handler_id)
        self.update_manager_actions(state)

    def on_manager_selected(
        self, _listing: Gtk.ListBox, row: Gtk.ListBoxRow | None, state: ManagerState,
    ) -> None:
        index = row.get_index() if row is not None else -1
        state.selected_id = state.visible_ids[index] if 0 <= index < len(state.visible_ids) else None
        self.update_manager_actions(state)

    @staticmethod
    def update_manager_actions(state: ManagerState) -> None:
        for button in state.actions:
            button.set_sensitive(state.selected_id is not None)

    def on_manager_add(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.show_editor(state, None, False)

    def on_manager_edit(self, _button: Gtk.Button, state: ManagerState) -> None:
        if state.selected_id:
            self.show_editor(state, state.selected_id, False)

    def on_manager_duplicate(self, _button: Gtk.Button, state: ManagerState) -> None:
        if state.selected_id:
            self.show_editor(state, state.selected_id, True)

    def on_manager_delete(self, _button: Gtk.Button, state: ManagerState) -> None:
        snippet = self.presenter.snippet(state.selected_id)
        if snippet is None:
            return
        alert = Gtk.AlertDialog(
            message=self.translate("snippet_delete"),
            detail=self.translate("snippet_delete_confirm").format(name=snippet.name),
        )
        alert.set_buttons([self.translate("cancel"), self.translate("snippet_delete")])
        alert.set_cancel_button(0)
        alert.set_default_button(0)
        alert.choose(state.dialog, None, self.on_delete_confirmed, (alert, state, snippet.id))

    def on_delete_confirmed(
        self, _source: Gtk.AlertDialog, result: Gio.AsyncResult,
        data: tuple[Gtk.AlertDialog, ManagerState, str],
    ) -> None:
        alert, state, snippet_id = data
        try:
            confirmed = alert.choose_finish(result) == 1
        except Exception:
            return
        if confirmed:
            self.store.delete_snippet(snippet_id)
            self.refresh_manager(state)

    def show_editor(self, manager: ManagerState, snippet_id: str | None, duplicate: bool) -> None:
        snippet = self.presenter.snippet(snippet_id)
        if snippet_id and snippet is None:
            self.refresh_manager(manager)
            return
        dialog = Gtk.Dialog(
            title=self.translate("snippet_add" if snippet is None or duplicate else "snippet_edit"),
            transient_for=manager.dialog,
            modal=True,
        )
        dialog.set_default_size(620, 500)
        self.add_actions(dialog, self.translate("save"))
        box = self.content(dialog)
        name = Gtk.Entry()
        category = Gtk.Entry()
        scope = Gtk.ComboBoxText()
        target = Gtk.ComboBoxText()
        command = Gtk.TextView()
        command.set_monospace(True)
        command.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        command.set_vexpand(True)
        for value, key in (("global", "snippet_scope_global"), ("group", "snippet_scope_group"), ("server", "snippet_scope_server")):
            scope.append(value, self.translate(key))
        if snippet:
            suffix = f" {self.translate('snippet_copy_suffix')}" if duplicate else ""
            name.set_text(f"{snippet.name}{suffix}")
            category.set_text(snippet.category)
            command.get_buffer().set_text(snippet.content)
            scope.set_active_id(snippet.scope)
        else:
            scope.set_active_id("global")
        for label_text, widget in ((self.translate("name"), name), (self.translate("snippet_category"), category), (self.translate("snippet_scope"), scope)):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            box.append(label)
            box.append(widget)
        box.append(target)
        command_label = Gtk.Label(label=self.translate("snippet_content"))
        command_label.set_xalign(0)
        box.append(command_label)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(command)
        box.append(scroller)
        state = EditorState(dialog, manager, snippet_id, duplicate, name, category, scope, target, command)
        self.retain_dialog_state(dialog, state)
        self.connect_dialog_signal(dialog, scope, "changed", self.on_editor_scope_changed, state)
        self.connect_dialog_signal(dialog, dialog, "response", self.on_editor_response, state)
        self.populate_targets(state, snippet.target_id if snippet else "")
        dialog.present()

    def on_editor_scope_changed(self, _scope: Gtk.ComboBoxText, state: EditorState) -> None:
        self.populate_targets(state)

    def populate_targets(self, state: EditorState, preferred_id: str = "") -> None:
        current_id = preferred_id or state.target.get_active_id() or ""
        state.target.remove_all()
        targets = self.presenter.targets(state.scope.get_active_id() or "global")
        for item in targets:
            state.target.append(item.id, item.label)
        state.target.set_visible(bool(targets))
        if targets and not state.target.set_active_id(current_id):
            state.target.set_active(0)

    def on_editor_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType, state: EditorState) -> None:
        if response != Gtk.ResponseType.OK:
            self.destroy_dialog(dialog)
            return
        buffer = state.command.get_buffer()
        command = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        values = (state.name.get_text(), command, state.category.get_text(), state.scope.get_active_id() or "global", state.target.get_active_id() or "")
        try:
            if state.snippet_id is None or state.duplicate:
                selected_id = self.store.add_snippet(*values).id
            else:
                self.store.update_snippet(state.snippet_id, *values)
                selected_id = state.snippet_id
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        self.destroy_dialog(dialog)
        self.refresh_manager(state.manager, selected_id)

    def show_picker(
        self,
        popover: Gtk.Popover,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> PickerState | None:
        popover.popdown()
        pane = session.pane_for_terminal(terminal)
        if pane is None:
            return None
        owner = session.detached_window or self.parent
        dialog = Gtk.Dialog(title=self.translate("run_snippet"), transient_for=owner, modal=True)
        dialog.set_default_size(520, 420)
        preview = self.add_actions(dialog, self.translate("snippet_preview"))
        preview.set_sensitive(False)
        search = Gtk.SearchEntry()
        search.set_placeholder_text(self.translate("search_snippets"))
        listing = Gtk.ListBox()
        listing.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(listing)
        box = self.content(dialog)
        box.append(search)
        box.append(scroller)
        state = PickerState(dialog, owner, session, terminal, pane.server_id, search, listing, preview, [])
        self.retain_dialog_state(dialog, state)
        self.connect_dialog_signal(dialog, search, "search-changed", self.on_picker_search, state)
        state.selection_handler_id = self.connect_dialog_signal(
            dialog, listing, "row-selected", self.on_picker_selected, state,
        )
        self.connect_dialog_signal(dialog, dialog, "response", self.on_picker_response, state)
        self.refresh_picker(state)
        dialog.present()
        log_event("snippet.picker_opened", server_scoped=state.server_id is not None)
        return state

    def on_picker_search(self, _search: Gtk.SearchEntry, state: PickerState) -> None:
        self.refresh_picker(state)

    def refresh_picker(self, state: PickerState) -> None:
        handler_id = state.selection_handler_id
        if handler_id is not None:
            state.listing.handler_block(handler_id)
        try:
            self.clear_list(state.listing)
            items = self.presenter.run_items(state.server_id, state.search.get_text())
            state.visible_ids = [item.id for item in items]
            state.selected_id = None
            state.preview.set_sensitive(False)
            if not items:
                self.append_row(state.listing, self.translate("no_snippets"), enabled=False)
            for item in items:
                self.append_row(state.listing, item.label)
        finally:
            if handler_id is not None:
                state.listing.handler_unblock(handler_id)

    def on_picker_selected(self, _listing: Gtk.ListBox, row: Gtk.ListBoxRow | None, state: PickerState) -> None:
        index = row.get_index() if row is not None else -1
        state.selected_id = state.visible_ids[index] if 0 <= index < len(state.visible_ids) else None
        state.preview.set_sensitive(state.selected_id is not None)

    def on_picker_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType, state: PickerState) -> None:
        snippet = self.presenter.snippet(state.selected_id)
        self.destroy_dialog(dialog)
        if response == Gtk.ResponseType.OK and snippet is not None:
            log_event("snippet.preview_requested", variables=bool(snippet_variables(snippet.content)))
            self.show_variables(RunContext(state.owner, state.session, state.terminal, snippet))

    def show_variables(self, context: RunContext) -> None:
        variables = snippet_variables(context.snippet.content)
        if not variables:
            self.show_preview(context, {})
            return
        dialog = Gtk.Dialog(title=self.translate("snippet_variables"), transient_for=context.owner, modal=True)
        self.add_actions(dialog, self.translate("snippet_preview"))
        entries: dict[str, Gtk.Entry] = {}
        box = self.content(dialog)
        for variable in variables:
            label = Gtk.Label(label=variable)
            label.set_xalign(0)
            entry = Gtk.Entry()
            entries[variable] = entry
            box.append(label)
            box.append(entry)
        state = (context, entries)
        self.retain_dialog_state(dialog, state)
        self.connect_dialog_signal(dialog, dialog, "response", self.on_variables_response, state)
        dialog.present()

    def on_variables_response(
        self, dialog: Gtk.Dialog, response: Gtk.ResponseType,
        data: tuple[RunContext, dict[str, Gtk.Entry]],
    ) -> None:
        context, entries = data
        if response != Gtk.ResponseType.OK:
            self.destroy_dialog(dialog)
            return
        values = {name: entry.get_text() for name, entry in entries.items()}
        try:
            render_snippet(context.snippet.content, values)
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        self.destroy_dialog(dialog)
        self.show_preview(context, values)

    def show_preview(self, context: RunContext, values: dict[str, str]) -> None:
        command = render_snippet(context.snippet.content, values)
        dialog = Gtk.Dialog(title=self.translate("snippet_preview"), transient_for=context.owner, modal=True)
        dialog.set_default_size(620, 340)
        self.add_actions(dialog, self.translate("send_snippet"))
        box = self.content(dialog)
        detail = Gtk.Label(label=self.translate("snippet_preview_detail"))
        detail.set_xalign(0)
        detail.set_wrap(True)
        box.append(detail)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(command)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(view)
        box.append(scroller)
        state = (context, command)
        self.retain_dialog_state(dialog, state)
        self.connect_dialog_signal(dialog, dialog, "response", self.on_preview_response, state)
        dialog.present()
        log_event("snippet.preview_opened")

    def on_preview_response(
        self, dialog: Gtk.Dialog, response: Gtk.ResponseType,
        data: tuple[RunContext, str],
    ) -> None:
        context, command = data
        self.destroy_dialog(dialog)
        if response != Gtk.ResponseType.OK:
            return
        pane = context.session.pane_for_terminal(context.terminal)
        if pane is None or not pane.connected or id(context.terminal) not in context.session.active_terminal_ids:
            self.show_error(self.translate("snippet_terminal_unavailable"))
            return
        log_event("snippet.send_requested")
        context.terminal.feed_child(f"{command}\n".encode())
        log_event("snippet.sent")
        self.show_notice(self.translate("snippet_sent"))
