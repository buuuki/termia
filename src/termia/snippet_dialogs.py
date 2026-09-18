# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent GTK windows for managing and explicitly running command snippets."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gtk, Vte

from .debug import log_event
from .models import CommandSnippet
from .snippet_presenter import SnippetPresenter
from .snippets import SnippetError, render_snippet, snippet_variables
from .stores import ConnectionStore
from .ui_state import TerminalSession


@dataclass
class ManagerState:
    window: Gtk.Window
    stack: Gtk.Stack
    listing: Gtk.ListBox
    actions: tuple[Gtk.Button, Gtk.Button, Gtk.Button]
    name: Gtk.Entry
    category: Gtk.Entry
    scope: Gtk.ComboBoxText
    target: Gtk.ComboBoxText
    command: Gtk.TextView
    delete_detail: Gtk.Label
    visible_ids: list[str] = field(default_factory=list)
    selected_id: str | None = None
    editor_snippet_id: str | None = None
    editor_duplicate: bool = False
    delete_snippet_id: str | None = None
    selection_handler_id: int | None = None


@dataclass
class RunTarget:
    owner: Gtk.Window
    session: TerminalSession
    terminal: Vte.Terminal
    server_id: str | None


@dataclass
class RunContext:
    target: RunTarget
    snippet: CommandSnippet


@dataclass
class PickerState:
    window: Gtk.Window
    stack: Gtk.Stack
    search: Gtk.SearchEntry
    listing: Gtk.ListBox
    preview_button: Gtk.Button
    variable_fields: Gtk.Box
    preview_view: Gtk.TextView
    visible_ids: list[str] = field(default_factory=list)
    selected_id: str | None = None
    selection_handler_id: int | None = None
    target: RunTarget | None = None
    context: RunContext | None = None
    variable_entries: dict[str, Gtk.Entry] = field(default_factory=dict)
    rendered_command: str = ""


class SnippetDialogs:
    """Own two reusable snippet windows for the application lifetime."""

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
        self.manager_state: ManagerState | None = None
        self.picker_state: PickerState | None = None

    @staticmethod
    def page() -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        return box

    @staticmethod
    def button_row() -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_halign(Gtk.Align.END)
        return row

    @staticmethod
    def button(label: str, *, destructive: bool = False, suggested: bool = False) -> Gtk.Button:
        button = Gtk.Button(label=label)
        if destructive:
            button.add_css_class("destructive-action")
        if suggested:
            button.add_css_class("suggested-action")
        return button

    @staticmethod
    def clear_list(listing: Gtk.ListBox) -> None:
        listing.unselect_all()
        child = listing.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            listing.remove(child)
            child = next_child

    @staticmethod
    def clear_box(box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            box.remove(child)
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
        state = self.manager_state or self.build_manager()
        self.manager_state = state
        state.window.set_title(self.translate("manage_snippets"))
        state.stack.set_visible_child_name("manager")
        self.refresh_manager(state)
        state.window.present()
        log_event("snippet.manager_opened")
        return state

    def build_manager(self) -> ManagerState:
        window = Gtk.Window(
            title=self.translate("manage_snippets"),
            transient_for=self.parent,
            modal=True,
        )
        window.set_default_size(680, 460)
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        window.set_child(stack)

        manager_page = self.page()
        listing = Gtk.ListBox()
        listing.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(listing)
        manager_page.append(scroller)
        manager_buttons = self.button_row()
        add = self.button(self.translate("snippet_add"))
        edit = self.button(self.translate("snippet_edit"))
        duplicate = self.button(self.translate("snippet_duplicate"))
        delete = self.button(self.translate("snippet_delete"), destructive=True)
        close = self.button(self.translate("close"))
        for item in (add, edit, duplicate, delete, close):
            manager_buttons.append(item)
        manager_page.append(manager_buttons)
        stack.add_named(manager_page, "manager")

        editor_page = self.page()
        name = Gtk.Entry()
        category = Gtk.Entry()
        scope = Gtk.ComboBoxText()
        target = Gtk.ComboBoxText()
        command = Gtk.TextView()
        command.set_monospace(True)
        command.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        command.set_vexpand(True)
        for value, key in (
            ("global", "snippet_scope_global"),
            ("group", "snippet_scope_group"),
            ("server", "snippet_scope_server"),
        ):
            scope.append(value, self.translate(key))
        for label_text, widget in (
            (self.translate("name"), name),
            (self.translate("snippet_category"), category),
            (self.translate("snippet_scope"), scope),
        ):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            editor_page.append(label)
            editor_page.append(widget)
        editor_page.append(target)
        command_label = Gtk.Label(label=self.translate("snippet_content"))
        command_label.set_xalign(0)
        editor_page.append(command_label)
        command_scroller = Gtk.ScrolledWindow()
        command_scroller.set_vexpand(True)
        command_scroller.set_child(command)
        editor_page.append(command_scroller)
        editor_buttons = self.button_row()
        editor_cancel = self.button(self.translate("cancel"))
        editor_save = self.button(self.translate("save"), suggested=True)
        editor_buttons.append(editor_cancel)
        editor_buttons.append(editor_save)
        editor_page.append(editor_buttons)
        stack.add_named(editor_page, "editor")

        delete_page = self.page()
        delete_title = Gtk.Label(label=self.translate("snippet_delete"))
        delete_title.set_xalign(0)
        delete_title.add_css_class("title-2")
        delete_detail = Gtk.Label()
        delete_detail.set_xalign(0)
        delete_detail.set_wrap(True)
        delete_page.append(delete_title)
        delete_page.append(delete_detail)
        delete_buttons = self.button_row()
        delete_cancel = self.button(self.translate("cancel"))
        delete_confirm = self.button(self.translate("snippet_delete"), destructive=True)
        delete_buttons.append(delete_cancel)
        delete_buttons.append(delete_confirm)
        delete_page.append(delete_buttons)
        stack.add_named(delete_page, "delete")

        state = ManagerState(
            window, stack, listing, (edit, duplicate, delete), name, category,
            scope, target, command, delete_detail,
        )
        state.selection_handler_id = listing.connect("row-selected", self.on_manager_selected, state)
        add.connect("clicked", self.on_manager_add, state)
        edit.connect("clicked", self.on_manager_edit, state)
        duplicate.connect("clicked", self.on_manager_duplicate, state)
        delete.connect("clicked", self.on_manager_delete, state)
        close.connect("clicked", self.on_manager_close, state)
        scope.connect("changed", self.on_editor_scope_changed, state)
        editor_cancel.connect("clicked", self.on_editor_cancel, state)
        editor_save.connect("clicked", self.on_editor_save, state)
        delete_cancel.connect("clicked", self.on_delete_cancel, state)
        delete_confirm.connect("clicked", self.on_delete_confirmed, state)
        window.connect("close-request", self.on_manager_close_request, state)
        return state

    def hide_manager(self, state: ManagerState) -> None:
        state.stack.set_visible_child_name("manager")
        state.editor_snippet_id = None
        state.delete_snippet_id = None
        state.window.set_visible(False)
        log_event("snippet.manager_hidden")

    def on_manager_close(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.hide_manager(state)

    def on_manager_close_request(self, _window: Gtk.Window, state: ManagerState) -> bool:
        self.hide_manager(state)
        return True

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

    def on_manager_selected(self, _listing: Gtk.ListBox, row: Gtk.ListBoxRow | None, state: ManagerState) -> None:
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

    def show_editor(self, state: ManagerState, snippet_id: str | None, duplicate: bool) -> None:
        snippet = self.presenter.snippet(snippet_id)
        if snippet_id and snippet is None:
            self.refresh_manager(state)
            return
        state.editor_snippet_id = snippet_id
        state.editor_duplicate = duplicate
        suffix = f" {self.translate('snippet_copy_suffix')}" if snippet and duplicate else ""
        state.name.set_text(f"{snippet.name}{suffix}" if snippet else "")
        state.category.set_text(snippet.category if snippet else "")
        state.command.get_buffer().set_text(snippet.content if snippet else "")
        state.scope.set_active_id(snippet.scope if snippet else "global")
        self.populate_targets(state, snippet.target_id if snippet else "")
        state.window.set_title(self.translate("snippet_add" if snippet is None or duplicate else "snippet_edit"))
        state.stack.set_visible_child_name("editor")
        state.name.grab_focus()
        log_event("snippet.editor_opened", duplicate=duplicate, editing=snippet is not None)

    def on_editor_scope_changed(self, _scope: Gtk.ComboBoxText, state: ManagerState) -> None:
        self.populate_targets(state)

    def populate_targets(self, state: ManagerState, preferred_id: str = "") -> None:
        current_id = preferred_id or state.target.get_active_id() or ""
        state.target.remove_all()
        targets = self.presenter.targets(state.scope.get_active_id() or "global")
        for item in targets:
            state.target.append(item.id, item.label)
        state.target.set_visible(bool(targets))
        if targets and not state.target.set_active_id(current_id):
            state.target.set_active(0)

    def on_editor_cancel(self, _button: Gtk.Button, state: ManagerState) -> None:
        state.editor_snippet_id = None
        state.window.set_title(self.translate("manage_snippets"))
        state.stack.set_visible_child_name("manager")
        log_event("snippet.editor_cancelled")

    def on_editor_save(self, _button: Gtk.Button, state: ManagerState) -> None:
        buffer = state.command.get_buffer()
        command = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        values = (
            state.name.get_text(), command, state.category.get_text(),
            state.scope.get_active_id() or "global", state.target.get_active_id() or "",
        )
        try:
            if state.editor_snippet_id is None or state.editor_duplicate:
                selected_id = self.store.add_snippet(*values).id
            else:
                self.store.update_snippet(state.editor_snippet_id, *values)
                selected_id = state.editor_snippet_id
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        state.editor_snippet_id = None
        state.window.set_title(self.translate("manage_snippets"))
        state.stack.set_visible_child_name("manager")
        self.refresh_manager(state, selected_id)
        log_event("snippet.saved")

    def on_manager_delete(self, _button: Gtk.Button, state: ManagerState) -> None:
        snippet = self.presenter.snippet(state.selected_id)
        if snippet is None:
            return
        state.delete_snippet_id = snippet.id
        state.delete_detail.set_label(self.translate("snippet_delete_confirm").format(name=snippet.name))
        state.stack.set_visible_child_name("delete")

    def on_delete_cancel(self, _button: Gtk.Button, state: ManagerState) -> None:
        state.delete_snippet_id = None
        state.stack.set_visible_child_name("manager")

    def on_delete_confirmed(self, _button: Gtk.Button, state: ManagerState) -> None:
        snippet_id = state.delete_snippet_id
        state.delete_snippet_id = None
        if snippet_id is not None:
            self.store.delete_snippet(snippet_id)
        state.stack.set_visible_child_name("manager")
        self.refresh_manager(state)

    def show_picker(self, popover: Gtk.Popover, session: TerminalSession, terminal: Vte.Terminal) -> PickerState | None:
        popover.popdown()
        pane = session.pane_for_terminal(terminal)
        if pane is None:
            return None
        state = self.picker_state or self.build_picker()
        self.picker_state = state
        owner = session.detached_window or self.parent
        state.target = RunTarget(owner, session, terminal, pane.server_id)
        state.context = None
        state.window.set_transient_for(owner)
        state.window.set_title(self.translate("run_snippet"))
        state.search.set_text("")
        state.stack.set_visible_child_name("picker")
        self.refresh_picker(state)
        state.window.present()
        log_event("snippet.picker_opened", server_scoped=pane.server_id is not None)
        return state

    def build_picker(self) -> PickerState:
        window = Gtk.Window(title=self.translate("run_snippet"), transient_for=self.parent, modal=True)
        window.set_default_size(620, 420)
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        window.set_child(stack)

        picker_page = self.page()
        search = Gtk.SearchEntry()
        search.set_placeholder_text(self.translate("search_snippets"))
        listing = Gtk.ListBox()
        listing.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(listing)
        picker_page.append(search)
        picker_page.append(scroller)
        picker_buttons = self.button_row()
        picker_cancel = self.button(self.translate("cancel"))
        preview_button = self.button(self.translate("snippet_preview"), suggested=True)
        preview_button.set_sensitive(False)
        picker_buttons.append(picker_cancel)
        picker_buttons.append(preview_button)
        picker_page.append(picker_buttons)
        stack.add_named(picker_page, "picker")

        variables_page = self.page()
        variable_fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        variable_scroller = Gtk.ScrolledWindow()
        variable_scroller.set_vexpand(True)
        variable_scroller.set_child(variable_fields)
        variables_page.append(variable_scroller)
        variable_buttons = self.button_row()
        variables_cancel = self.button(self.translate("cancel"))
        variables_preview = self.button(self.translate("snippet_preview"), suggested=True)
        variable_buttons.append(variables_cancel)
        variable_buttons.append(variables_preview)
        variables_page.append(variable_buttons)
        stack.add_named(variables_page, "variables")

        preview_page = self.page()
        detail = Gtk.Label(label=self.translate("snippet_preview_detail"))
        detail.set_xalign(0)
        detail.set_wrap(True)
        preview_view = Gtk.TextView()
        preview_view.set_editable(False)
        preview_view.set_monospace(True)
        preview_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        preview_scroller = Gtk.ScrolledWindow()
        preview_scroller.set_vexpand(True)
        preview_scroller.set_child(preview_view)
        preview_page.append(detail)
        preview_page.append(preview_scroller)
        send_buttons = self.button_row()
        preview_cancel = self.button(self.translate("cancel"))
        send = self.button(self.translate("send_snippet"), suggested=True)
        send_buttons.append(preview_cancel)
        send_buttons.append(send)
        preview_page.append(send_buttons)
        stack.add_named(preview_page, "preview")

        state = PickerState(window, stack, search, listing, preview_button, variable_fields, preview_view)
        state.selection_handler_id = listing.connect("row-selected", self.on_picker_selected, state)
        search.connect("search-changed", self.on_picker_search, state)
        picker_cancel.connect("clicked", self.on_picker_cancel, state)
        preview_button.connect("clicked", self.on_picker_preview, state)
        variables_cancel.connect("clicked", self.on_picker_cancel, state)
        variables_preview.connect("clicked", self.on_variables_preview, state)
        preview_cancel.connect("clicked", self.on_picker_cancel, state)
        send.connect("clicked", self.on_preview_send, state)
        window.connect("close-request", self.on_picker_close_request, state)
        return state

    def hide_picker(self, state: PickerState) -> None:
        state.window.set_visible(False)
        state.window.set_transient_for(self.parent)
        state.stack.set_visible_child_name("picker")
        state.target = None
        state.context = None
        state.variable_entries.clear()
        state.rendered_command = ""
        log_event("snippet.picker_hidden")

    def on_picker_cancel(self, _button: Gtk.Button, state: PickerState) -> None:
        self.hide_picker(state)

    def on_picker_close_request(self, _window: Gtk.Window, state: PickerState) -> bool:
        self.hide_picker(state)
        return True

    def on_picker_search(self, _search: Gtk.SearchEntry, state: PickerState) -> None:
        self.refresh_picker(state)

    def refresh_picker(self, state: PickerState) -> None:
        handler_id = state.selection_handler_id
        if handler_id is not None:
            state.listing.handler_block(handler_id)
        try:
            self.clear_list(state.listing)
            server_id = state.target.server_id if state.target is not None else None
            items = self.presenter.run_items(server_id, state.search.get_text())
            state.visible_ids = [item.id for item in items]
            state.selected_id = None
            state.preview_button.set_sensitive(False)
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
        state.preview_button.set_sensitive(state.selected_id is not None)

    def on_picker_preview(self, _button: Gtk.Button, state: PickerState) -> None:
        snippet = self.presenter.snippet(state.selected_id)
        if snippet is None or state.target is None:
            return
        state.context = RunContext(state.target, snippet)
        variables = snippet_variables(snippet.content)
        log_event("snippet.preview_requested", variables=bool(variables))
        if not variables:
            self.show_preview(state, {})
            return
        self.clear_box(state.variable_fields)
        state.variable_entries = {}
        for variable in variables:
            label = Gtk.Label(label=variable)
            label.set_xalign(0)
            entry = Gtk.Entry()
            state.variable_entries[variable] = entry
            state.variable_fields.append(label)
            state.variable_fields.append(entry)
        state.window.set_title(self.translate("snippet_variables"))
        state.stack.set_visible_child_name("variables")
        next(iter(state.variable_entries.values())).grab_focus()

    def on_variables_preview(self, _button: Gtk.Button, state: PickerState) -> None:
        if state.context is None:
            return
        values = {name: entry.get_text() for name, entry in state.variable_entries.items()}
        try:
            render_snippet(state.context.snippet.content, values)
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        self.show_preview(state, values)

    def show_preview(self, state: PickerState, values: dict[str, str]) -> None:
        if state.context is None:
            return
        state.rendered_command = render_snippet(state.context.snippet.content, values)
        state.preview_view.get_buffer().set_text(state.rendered_command)
        state.window.set_title(self.translate("snippet_preview"))
        state.stack.set_visible_child_name("preview")
        log_event("snippet.preview_opened")

    def on_preview_send(self, _button: Gtk.Button, state: PickerState) -> None:
        context = state.context
        command = state.rendered_command
        if context is None or not command:
            return
        pane = context.target.session.pane_for_terminal(context.target.terminal)
        if pane is None or not pane.connected or id(context.target.terminal) not in context.target.session.active_terminal_ids:
            self.show_error(self.translate("snippet_terminal_unavailable"))
            return
        self.hide_picker(state)
        log_event("snippet.send_requested")
        context.target.terminal.feed_child(f"{command}\n".encode())
        log_event("snippet.sent")
        self.show_notice(self.translate("snippet_sent"))

    def shutdown(self) -> None:
        """Destroy persistent surfaces only while the application is shutting down."""
        if self.manager_state is not None:
            self.manager_state.window.destroy()
            self.manager_state = None
        if self.picker_state is not None:
            self.picker_state.window.destroy()
            self.picker_state = None
