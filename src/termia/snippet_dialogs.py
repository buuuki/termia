# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent GTK windows for managing and explicitly running command snippets."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, Gtk, Pango, Vte

from .debug import log_event
from .keybinding_preferences import KeybindingCaptureRow
from .keybindings import (
    SNIPPET_ACTION_PREFIX, KeybindingError, is_snippet_action, keybinding_matches,
    snippet_action, validate_keybindings,
)
from .models import CommandSnippet
from .snippet_presenter import SnippetPresenter
from .snippets import SnippetError, render_snippet, snippet_variables
from .stores import ConnectionStore, ReadOnlyStoreError
from .ui_state import TerminalSession


@dataclass
class ManagerState:
    window: Gtk.Window
    stack: Gtk.Stack
    listing: Gtk.ListBox
    list_scroller: Gtk.ScrolledWindow
    category_grid: Gtk.FlowBox
    category_scroller: Gtk.ScrolledWindow
    search: Gtk.SearchEntry
    preview_title: Gtk.Label
    preview_meta: Gtk.Label
    preview_content_label: Gtk.Label
    preview_view: Gtk.TextView
    actions: tuple[Gtk.Button, Gtk.Button, Gtk.Button]
    name: Gtk.Entry
    category: Gtk.ComboBoxText
    new_category_button: Gtk.Button
    new_category_entry: Gtk.Entry
    new_category_confirm: Gtk.Button
    new_category_cancel: Gtk.Button
    new_category_box: Gtk.Box
    scope: Gtk.ComboBoxText
    target: Gtk.ComboBoxText
    command: Gtk.TextView
    delete_detail: Gtk.Label
    category_manage_grid: Gtk.FlowBox
    category_name_entry: Gtk.Entry
    category_name_box: Gtk.Box
    category_manage_actions: tuple[Gtk.Button, Gtk.Button, Gtk.Button]
    category_delete_detail: Gtk.Label
    shortcut: KeybindingCaptureRow
    editor_error: Gtk.Label
    visible_ids: list[str] = field(default_factory=list)
    selected_id: str | None = None
    editor_snippet_id: str | None = None
    editor_duplicate: bool = False
    delete_snippet_id: str | None = None
    selection_handler_id: int | None = None
    category_filter: str | None = None
    category_options: list[str] = field(default_factory=list)
    category_manage_keys: list[str] = field(default_factory=list)
    selected_category: str | None = None
    category_edit_mode: str | None = None
    category_edit_original: str | None = None
    category_pending_delete: str | None = None
    category_manage_handler_id: int | None = None
    selection_hint: Gtk.ListBoxRow | None = None
    manager_size: tuple[int, int] | None = None
    previous_shortcut: str = ""


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
    def clear_flow_box(grid: Gtk.FlowBox) -> None:
        child = grid.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            grid.remove(child)
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
        self.restore_manager_size(state)
        state.window.set_title(self.translate("manage_snippets"))
        state.stack.set_visible_child_name("manager")
        state.category_filter = None
        state.search.set_text("")
        self.refresh_manager(state)
        state.window.present()
        log_event("snippet.manager_opened")
        return state

    def build_manager(self) -> ManagerState:
        window = Gtk.Window(
            title=self.translate("manage_snippets"),
            application=self.parent.get_application(),
        )
        window.set_default_size(795, 560)
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        stack.set_hhomogeneous(False)
        window.set_child(stack)

        manager_page = self.page()
        search = Gtk.SearchEntry()
        search.set_placeholder_text(self.translate("search_snippets"))
        search.set_hexpand(True)
        manage_categories = self.button(self.translate("snippet_manage_categories"))
        add = self.button(self.translate("snippet_create"), suggested=True)
        manager_page.append(search)

        category_grid = Gtk.FlowBox()
        category_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        category_grid.set_max_children_per_line(1)
        category_grid.set_min_children_per_line(1)
        category_grid.set_row_spacing(4)
        category_grid.set_valign(Gtk.Align.START)
        category_scroller = Gtk.ScrolledWindow()
        category_scroller.set_size_request(190, -1)
        category_scroller.set_hexpand(False)
        category_scroller.set_vexpand(True)
        category_scroller.set_child(category_grid)
        category_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        category_column.append(manage_categories)
        category_column.append(category_scroller)

        listing = Gtk.ListBox()
        listing.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_scroller = Gtk.ScrolledWindow()
        list_scroller.set_hexpand(True)
        list_scroller.set_vexpand(True)
        list_scroller.set_child(listing)
        snippet_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        snippet_column.set_hexpand(True)
        add.set_halign(Gtk.Align.START)
        snippet_column.append(add)
        snippet_column.append(list_scroller)

        preview_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        preview_panel.set_size_request(290, -1)
        preview_heading = Gtk.Label(label=self.translate("snippet_preview_heading"))
        preview_heading.set_xalign(0)
        preview_heading.set_valign(Gtk.Align.CENTER)
        preview_heading.set_size_request(-1, 34)
        preview_title = Gtk.Label()
        preview_title.set_xalign(0)
        preview_title.set_wrap(True)
        preview_title.add_css_class("title-3")
        preview_title.set_visible(False)
        preview_meta = Gtk.Label()
        preview_meta.set_xalign(0)
        preview_meta.set_wrap(True)
        preview_meta.set_visible(False)
        preview_content_label = Gtk.Label(label=self.translate("snippet_content"))
        preview_content_label.set_xalign(0)
        preview_content_label.set_visible(False)
        preview_view = Gtk.TextView()
        preview_view.set_editable(False)
        preview_view.set_cursor_visible(False)
        preview_view.set_monospace(True)
        preview_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        preview_scroller = Gtk.ScrolledWindow()
        preview_scroller.set_vexpand(True)
        preview_scroller.set_child(preview_view)
        preview_panel.append(preview_heading)
        preview_panel.append(preview_title)
        preview_panel.append(preview_meta)
        preview_panel.append(preview_content_label)
        preview_panel.append(preview_scroller)
        preview_actions = self.button_row()
        edit = self.button(self.translate("snippet_action_edit"))
        duplicate = self.button(self.translate("snippet_action_duplicate"))
        delete = self.button(self.translate("snippet_action_delete"), destructive=True)
        for item in (edit, duplicate, delete):
            preview_actions.append(item)
        preview_panel.append(preview_actions)

        manager_columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        manager_columns.set_vexpand(True)
        manager_columns.append(category_column)
        manager_columns.append(snippet_column)
        manager_columns.append(preview_panel)
        manager_page.append(manager_columns)
        manager_buttons = self.button_row()
        close = self.button(self.translate("close"))
        manager_buttons.append(close)
        manager_page.append(manager_buttons)
        stack.add_named(manager_page, "manager")

        editor_page = self.page()
        name = Gtk.Entry()
        category = Gtk.ComboBoxText()
        category_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        category_row.set_halign(Gtk.Align.START)
        category_row.append(category)
        new_category_button = self.button("+")
        new_category_button.set_tooltip_text(self.translate("snippet_new_category"))
        category_row.append(new_category_button)
        new_category_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        new_category_entry = Gtk.Entry()
        new_category_entry.set_placeholder_text(self.translate("snippet_new_category_name"))
        new_category_entry.set_hexpand(True)
        new_category_confirm = self.button(self.translate("save"), suggested=True)
        new_category_cancel = self.button(self.translate("cancel"))
        new_category_box.append(new_category_entry)
        new_category_box.append(new_category_confirm)
        new_category_box.append(new_category_cancel)
        new_category_box.set_visible(False)
        scope = Gtk.ComboBoxText()
        target = Gtk.ComboBoxText()
        for selector in (category, scope, target):
            selector.set_halign(Gtk.Align.START)
            selector.set_size_request(220, -1)
            for cell in selector.get_cells():
                cell.set_property("ellipsize", Pango.EllipsizeMode.END)
                cell.set_property("max-width-chars", 24)
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
        name_label = Gtk.Label(label=self.translate("name"))
        name_label.set_xalign(0)
        editor_page.append(name_label)
        editor_page.append(name)
        category_label = Gtk.Label(label=self.translate("snippet_category"))
        category_label.set_xalign(0)
        editor_page.append(category_label)
        editor_page.append(category_row)
        editor_page.append(new_category_box)
        scope_label = Gtk.Label(label=self.translate("snippet_scope"))
        scope_label.set_xalign(0)
        scope_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scope_box.append(scope_label)
        scope_box.append(scope)
        scope_box.append(target)
        shortcut = KeybindingCaptureRow(
            "", self.translate("keybinding_disabled"), self.translate("keybinding_capture_prompt"),
            self.translate("keybinding_clear"),
        )
        shortcut_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        shortcut_label = Gtk.Label(label=self.translate("snippet_shortcut"), xalign=0)
        shortcut_box.append(shortcut_label)
        shortcut_box.append(shortcut)
        shortcut_help = Gtk.Label(label=self.translate("snippet_shortcut_help"), xalign=0)
        shortcut_help.add_css_class("dim-label")
        shortcut_help.set_wrap(True)
        shortcut_help.set_max_width_chars(32)
        shortcut_box.append(shortcut_help)
        configuration = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        configuration.append(scope_box)
        configuration.append(shortcut_box)
        editor_page.append(configuration)
        editor_error = Gtk.Label(xalign=0)
        editor_error.set_wrap(True)
        editor_error.add_css_class("error")
        editor_error.set_visible(False)
        editor_page.append(editor_error)
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

        category_page = self.page()
        category_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        category_back = self.button(self.translate("snippet_back_to_manager"))
        category_header.append(category_back)
        category_page.append(category_header)
        category_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        category_actions.set_halign(Gtk.Align.START)
        category_add = self.button(self.translate("snippet_category_add"))
        category_rename = self.button(self.translate("snippet_category_rename"))
        category_duplicate = self.button(self.translate("snippet_category_duplicate"))
        category_delete = self.button(self.translate("snippet_category_delete"), destructive=True)
        for item in (category_add, category_rename, category_duplicate, category_delete):
            category_actions.append(item)
        category_page.append(category_actions)
        category_manage_grid = Gtk.FlowBox()
        category_manage_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        category_manage_grid.set_homogeneous(True)
        category_manage_grid.set_min_children_per_line(1)
        category_manage_grid.set_row_spacing(12)
        category_manage_grid.set_column_spacing(12)
        category_manage_grid.set_halign(Gtk.Align.START)
        category_manage_grid.set_valign(Gtk.Align.START)
        category_manage_scroller = Gtk.ScrolledWindow()
        category_manage_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        category_manage_scroller.set_vexpand(True)
        category_manage_scroller.set_child(category_manage_grid)
        category_page.append(category_manage_scroller)
        category_name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        category_name_entry = Gtk.Entry()
        category_name_entry.set_placeholder_text(self.translate("snippet_new_category_name"))
        category_name_entry.set_hexpand(True)
        category_name_save = self.button(self.translate("save"), suggested=True)
        category_name_cancel = self.button(self.translate("cancel"))
        category_name_box.append(category_name_entry)
        category_name_box.append(category_name_save)
        category_name_box.append(category_name_cancel)
        category_name_box.set_visible(False)
        category_page.append(category_name_box)
        category_buttons = self.button_row()
        category_cancel = self.button(self.translate("cancel"))
        category_buttons.append(category_cancel)
        category_page.append(category_buttons)
        stack.add_named(category_page, "categories")

        category_delete_page = self.page()
        category_delete_title = Gtk.Label(label=self.translate("snippet_category_delete"))
        category_delete_title.set_xalign(0)
        category_delete_title.add_css_class("title-2")
        category_delete_detail = Gtk.Label()
        category_delete_detail.set_xalign(0)
        category_delete_detail.set_wrap(True)
        category_delete_page.append(category_delete_title)
        category_delete_page.append(category_delete_detail)
        category_delete_buttons = self.button_row()
        category_delete_cancel = self.button(self.translate("cancel"))
        category_delete_confirm = self.button(self.translate("snippet_category_delete"), destructive=True)
        category_delete_buttons.append(category_delete_cancel)
        category_delete_buttons.append(category_delete_confirm)
        category_delete_page.append(category_delete_buttons)
        stack.add_named(category_delete_page, "category_delete")

        state = ManagerState(
            window, stack, listing, list_scroller, category_grid,
            category_scroller, search, preview_title, preview_meta,
            preview_content_label, preview_view,
            (edit, duplicate, delete), name, category, new_category_button,
            new_category_entry, new_category_confirm, new_category_cancel,
            new_category_box, scope, target, command, delete_detail,
            category_manage_grid, category_name_entry, category_name_box,
            (category_rename, category_duplicate, category_delete),
            category_delete_detail,
            shortcut, editor_error,
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
        manage_categories.connect("clicked", self.on_category_manage, state)
        state.category_manage_handler_id = category_manage_grid.connect(
            "selected-children-changed", self.on_category_manage_selected, state,
        )
        category_add.connect("clicked", self.on_category_manage_add, state)
        category_rename.connect("clicked", self.on_category_manage_rename, state)
        category_duplicate.connect("clicked", self.on_category_manage_duplicate, state)
        category_delete.connect("clicked", self.on_category_manage_delete, state)
        category_back.connect("clicked", self.on_category_manage_back, state)
        category_cancel.connect("clicked", self.on_category_manage_back, state)
        category_name_save.connect("clicked", self.on_category_name_save, state)
        category_name_cancel.connect("clicked", self.on_category_name_cancel, state)
        category_name_entry.connect("activate", self.on_category_name_save, state)
        category_delete_cancel.connect("clicked", self.on_category_delete_cancel, state)
        category_delete_confirm.connect("clicked", self.on_category_delete_confirm, state)
        search.connect("search-changed", self.on_manager_search, state)
        new_category_button.connect("clicked", self.on_new_category, state)
        new_category_confirm.connect("clicked", self.on_new_category_confirm, state)
        new_category_cancel.connect("clicked", self.on_new_category_cancel, state)
        window.connect("close-request", self.on_manager_close_request, state)
        return state

    def hide_manager(self, state: ManagerState) -> None:
        self.restore_manager_size(state)
        state.stack.set_visible_child_name("manager")
        state.editor_snippet_id = None
        state.delete_snippet_id = None
        state.category_filter = None
        state.search.set_text("")
        self.hide_new_category(state)
        self.on_category_name_cancel(state.window, state)
        state.category_pending_delete = None
        state.window.set_visible(False)
        log_event("snippet.manager_hidden")

    def on_manager_close(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.hide_manager(state)

    def on_manager_close_request(self, _window: Gtk.Window, state: ManagerState) -> bool:
        self.hide_manager(state)
        return True

    def on_manager_search(self, _search: Gtk.SearchEntry, state: ManagerState) -> None:
        if state.search.get_text().strip():
            state.category_filter = None
        self.refresh_manager(state)

    def refresh_category_management(self, state: ManagerState, selected: str | None = None) -> None:
        grid = state.category_manage_grid
        handler_id = state.category_manage_handler_id
        if handler_id is not None:
            grid.handler_block(handler_id)
        categories = [item for item in self.presenter.categories() if item.key]
        grid.set_max_children_per_line(max(1, len(categories)))
        try:
            self.clear_flow_box(grid)
            state.category_manage_keys = [item.key for item in categories]
            state.selected_category = None
            for item in categories:
                tile = Gtk.FlowBoxChild()
                tile.add_css_class("termia-snippet-category-tile")
                tile.set_tooltip_text(f"{item.key} ({item.count})")
                frame = Gtk.Frame()
                frame.add_css_class("termia-snippet-category-frame")
                frame.set_size_request(170, 112)
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                content.set_halign(Gtk.Align.CENTER)
                content.set_valign(Gtk.Align.CENTER)
                icon = Gtk.Image.new_from_icon_name(item.icon_name)
                icon.set_pixel_size(32)
                name = Gtk.Label(label=item.key)
                name.set_ellipsize(Pango.EllipsizeMode.END)
                name.set_max_width_chars(18)
                count = Gtk.Label(label=str(item.count))
                count.add_css_class("dim-label")
                for widget in (icon, name, count):
                    content.append(widget)
                frame.set_child(content)
                tile.set_child(frame)
                grid.insert(tile, -1)
                if item.key == selected:
                    grid.select_child(tile)
                    state.selected_category = item.key
        finally:
            if handler_id is not None:
                grid.handler_unblock(handler_id)
        self.update_category_manage_actions(state)

    def update_category_manage_actions(self, state: ManagerState) -> None:
        for button in state.category_manage_actions:
            button.set_sensitive(state.selected_category is not None)

    def on_category_manage(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.on_category_name_cancel(_button, state)
        self.refresh_category_management(state)
        state.stack.set_visible_child_name("categories")

    def on_category_manage_selected(
        self, grid: Gtk.FlowBox, state: ManagerState,
    ) -> None:
        selected = grid.get_selected_children()
        index = selected[0].get_index() if selected else -1
        state.selected_category = (
            state.category_manage_keys[index]
            if 0 <= index < len(state.category_manage_keys) else None
        )
        self.update_category_manage_actions(state)

    def on_category_manage_back(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.on_category_name_cancel(_button, state)
        state.category_filter = None
        state.search.set_text("")
        self.refresh_manager(state)
        state.stack.set_visible_child_name("manager")

    def start_category_name_edit(self, state: ManagerState, mode: str) -> None:
        original = state.selected_category if mode != "add" else None
        if mode != "add" and original is None:
            return
        state.category_edit_mode = mode
        state.category_edit_original = original
        if mode == "rename":
            value = original or ""
        elif mode == "duplicate":
            value = f"{original} {self.translate('snippet_copy_suffix')}"
        else:
            value = ""
        state.category_name_entry.set_text(value)
        state.category_name_box.set_visible(True)
        state.category_name_entry.grab_focus()

    def on_category_manage_add(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.start_category_name_edit(state, "add")

    def on_category_manage_rename(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.start_category_name_edit(state, "rename")

    def on_category_manage_duplicate(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.start_category_name_edit(state, "duplicate")

    def on_category_name_cancel(self, _button: Gtk.Widget, state: ManagerState) -> None:
        state.category_edit_mode = None
        state.category_edit_original = None
        state.category_name_entry.set_text("")
        state.category_name_box.set_visible(False)

    def on_category_name_save(self, _button: Gtk.Widget, state: ManagerState) -> None:
        name = state.category_name_entry.get_text()
        mode = state.category_edit_mode
        original = state.category_edit_original
        try:
            if mode == "add":
                self.store.add_snippet_category(name)
            elif mode == "rename" and original is not None:
                self.store.rename_snippet_category(original, name)
            elif mode == "duplicate" and original is not None:
                self.store.duplicate_snippet_category(original, name)
            else:
                return
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        self.on_category_name_cancel(_button, state)
        self.refresh_category_management(state, name.strip())

    def on_category_manage_delete(self, _button: Gtk.Button, state: ManagerState) -> None:
        name = state.selected_category
        if name is None:
            return
        self.on_category_name_cancel(_button, state)
        count = next(
            (item.count for item in self.presenter.categories() if item.key == name), 0,
        )
        state.category_pending_delete = name
        state.category_delete_detail.set_label(
            self.translate("snippet_category_delete_confirm").format(name=name, count=count)
        )
        state.stack.set_visible_child_name("category_delete")

    def on_category_delete_cancel(self, _button: Gtk.Button, state: ManagerState) -> None:
        state.category_pending_delete = None
        state.stack.set_visible_child_name("categories")

    def on_category_delete_confirm(self, _button: Gtk.Button, state: ManagerState) -> None:
        name = state.category_pending_delete
        if name is None:
            return
        try:
            self.store.delete_snippet_category(name)
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        state.category_pending_delete = None
        self.refresh_category_management(state)
        state.stack.set_visible_child_name("categories")

    def category_label(self, category: str) -> str:
        return category or self.translate("snippet_uncategorized")

    def populate_category_grid(self, state: ManagerState) -> None:
        self.clear_flow_box(state.category_grid)
        categories = self.presenter.categories()
        entries = [
            (None, self.translate("snippet_back_to_categories"),
             sum(item.count for item in categories), "view-grid-symbolic"),
            *(
                (item.key, self.category_label(item.key), item.count, item.icon_name)
                for item in categories
            ),
        ]
        for key, title, count_value, icon_name in entries:
            button = self.button("")
            button.set_size_request(-1, 42)
            button.set_hexpand(True)
            button.set_halign(Gtk.Align.FILL)
            button.set_tooltip_text(
                f"{title}: {self.translate('snippet_category_count').format(count=count_value)}"
            )
            if key == state.category_filter:
                button.add_css_class("suggested-action")
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            image = Gtk.Image.new_from_icon_name(icon_name)
            image.set_pixel_size(20)
            label = Gtk.Label(label=title)
            label.set_hexpand(True)
            label.set_xalign(0)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(14)
            count = Gtk.Label(label=str(count_value))
            count.add_css_class("dim-label")
            content.append(image)
            content.append(label)
            content.append(count)
            button.set_child(content)
            button.connect("clicked", self.on_category_activated, state, key)
            state.category_grid.insert(button, -1)

    def on_category_activated(
        self, _button: Gtk.Button, state: ManagerState, category: str | None,
    ) -> None:
        state.category_filter = category
        state.search.set_text("")
        self.refresh_manager(state)

    def refresh_manager(self, state: ManagerState, selected_id: str | None = None) -> None:
        if selected_id is not None:
            selected = self.presenter.snippet(selected_id)
            if selected is not None:
                state.category_filter = selected.category
                state.search.set_text("")
        query = state.search.get_text().strip()
        self.populate_category_grid(state)
        handler_id = state.selection_handler_id
        if handler_id is not None:
            state.listing.handler_block(handler_id)
        try:
            self.clear_list(state.listing)
            state.selection_hint = None
            items = self.presenter.manager_items(state.category_filter, query)
            state.visible_ids = [item.id for item in items]
            state.selected_id = None
            for item in items:
                row = self.append_row(state.listing, item.label)
                if item.id == selected_id:
                    state.listing.select_row(row)
                    state.selected_id = item.id
            if not items:
                self.append_row(state.listing, self.translate("no_snippets"), enabled=False)
            state.selection_hint = self.append_row(
                state.listing, self.translate("snippet_select_preview"), enabled=False,
            )
        finally:
            if handler_id is not None:
                state.listing.handler_unblock(handler_id)
        self.update_manager_actions(state)
        self.update_manager_preview(state)

    def on_manager_selected(self, _listing: Gtk.ListBox, row: Gtk.ListBoxRow | None, state: ManagerState) -> None:
        index = row.get_index() if row is not None else -1
        state.selected_id = state.visible_ids[index] if 0 <= index < len(state.visible_ids) else None
        self.update_manager_actions(state)
        self.update_manager_preview(state)

    def update_manager_preview(self, state: ManagerState) -> None:
        snippet = self.presenter.snippet(state.selected_id)
        if state.selection_hint is not None:
            state.selection_hint.set_visible(snippet is None)
        for label in (state.preview_title, state.preview_meta, state.preview_content_label):
            label.set_visible(snippet is not None)
        if snippet is None:
            state.preview_title.set_label("")
            state.preview_meta.set_label("")
            state.preview_view.get_buffer().set_text("")
            return
        scope_key = {
            "global": "snippet_scope_global",
            "group": "snippet_scope_group",
            "server": "snippet_scope_server",
        }[snippet.scope]
        state.preview_title.set_label(snippet.name)
        state.preview_meta.set_label(
            f"{self.translate('snippet_category')}: {self.category_label(snippet.category)}\n"
            f"{self.translate('snippet_scope')}: {self.translate(scope_key)}"
        )
        state.preview_view.get_buffer().set_text(snippet.content)

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

    def category_value(self, state: ManagerState) -> str:
        active = state.category.get_active()
        if active < 0 or active >= len(state.category_options):
            raise SnippetError("snippet_category_required")
        return state.category_options[active]

    def populate_editor_categories(self, state: ManagerState, selected: str = "") -> None:
        state.category.remove_all()
        state.category_options = [""] + [
            item.key for item in self.presenter.categories() if item.key
        ]
        for category in state.category_options:
            state.category.append_text(self.category_label(category))
        state.category.set_active(state.category_options.index(selected))

    def hide_new_category(self, state: ManagerState) -> None:
        state.new_category_entry.set_text("")
        state.new_category_box.set_visible(False)
        state.category.set_sensitive(True)
        state.new_category_button.set_sensitive(True)

    def on_new_category(self, _button: Gtk.Button, state: ManagerState) -> None:
        state.new_category_entry.set_text("")
        state.new_category_box.set_visible(True)
        state.category.set_sensitive(False)
        state.new_category_button.set_sensitive(False)
        state.new_category_entry.grab_focus()

    def on_new_category_cancel(self, _button: Gtk.Button, state: ManagerState) -> None:
        self.hide_new_category(state)

    def on_new_category_confirm(self, _button: Gtk.Button, state: ManagerState) -> None:
        category = state.new_category_entry.get_text().strip()
        if not category:
            self.show_error(self.translate("snippet_category_required"))
            return
        existing = next(
            (index for index, name in enumerate(state.category_options)
             if name.casefold() == category.casefold()),
            None,
        )
        if existing is None:
            try:
                self.store.add_snippet_category(category)
            except SnippetError as exc:
                self.show_error(self.translate(str(exc)))
                return
            state.category_options.append(category)
            state.category.append_text(category)
            existing = len(state.category_options) - 1
        state.category.set_active(existing)
        self.hide_new_category(state)

    def show_editor(self, state: ManagerState, snippet_id: str | None, duplicate: bool) -> None:
        snippet = self.presenter.snippet(snippet_id)
        if snippet_id and snippet is None:
            self.refresh_manager(state)
            return
        if state.manager_size is None:
            default_width, default_height = state.window.get_default_size()
            state.manager_size = (
                state.window.get_width() or default_width,
                state.window.get_height() or default_height,
            )
        state.editor_snippet_id = snippet_id
        state.editor_duplicate = duplicate
        state.previous_shortcut = self.store.data.app.keybindings.get(snippet_action(snippet_id or ""), "")
        state.shortcut.set_accelerator("" if duplicate else state.previous_shortcut)
        state.editor_error.set_visible(False)
        suffix = f" {self.translate('snippet_copy_suffix')}" if snippet and duplicate else ""
        state.name.set_text(f"{snippet.name}{suffix}" if snippet else "")
        category = snippet.category if snippet else state.category_filter or ""
        self.populate_editor_categories(state, category)
        self.hide_new_category(state)
        state.command.get_buffer().set_text(snippet.content if snippet else "")
        state.scope.set_active_id(snippet.scope if snippet else "global")
        self.populate_targets(state, snippet.target_id if snippet else "")
        state.window.set_title(self.translate("snippet_add" if snippet is None or duplicate else "snippet_edit"))
        state.stack.set_visible_child_name("editor")
        state.window.set_default_size(600, 560)
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
        self.hide_new_category(state)
        state.window.set_title(self.translate("manage_snippets"))
        state.stack.set_visible_child_name("manager")
        self.restore_manager_size(state)
        self.refresh_manager(state)
        log_event("snippet.editor_cancelled")

    def on_editor_save(self, _button: Gtk.Button, state: ManagerState) -> None:
        if not self.ensure_writable():
            return
        buffer = state.command.get_buffer()
        command = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        try:
            values = (
                state.name.get_text(), command, self.category_value(state),
                state.scope.get_active_id() or "global", state.target.get_active_id() or "",
            )
            if state.editor_snippet_id is None or state.editor_duplicate:
                selected_id = self.store.add_snippet(*values, shortcut=state.shortcut.get_accelerator()).id
            else:
                self.store.update_snippet(
                    state.editor_snippet_id, *values, shortcut=state.shortcut.get_accelerator(),
                    previous_shortcut=state.previous_shortcut,
                )
                selected_id = state.editor_snippet_id
        except SnippetError as exc:
            self.show_error(self.translate(str(exc)))
            return
        except KeybindingError as exc:
            state.editor_error.set_label(self.translate(str(exc)).format(shortcut=exc.shortcut))
            state.editor_error.set_visible(True)
            return
        except ReadOnlyStoreError:
            self.show_error(self.translate("read_only_mode_enabled"))
            return
        state.editor_snippet_id = None
        self.hide_new_category(state)
        state.window.set_title(self.translate("manage_snippets"))
        state.stack.set_visible_child_name("manager")
        self.restore_manager_size(state)
        self.refresh_manager(state, selected_id)
        log_event("snippet.saved")

    @staticmethod
    def restore_manager_size(state: ManagerState) -> None:
        if state.manager_size is not None:
            state.window.set_default_size(*state.manager_size)
            state.manager_size = None

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
        state = self.prepare_picker(session, terminal)
        if state is not None:
            state.window.present()
            log_event("snippet.picker_opened", server_scoped=state.target.server_id is not None)
        return state

    def prepare_picker(self, session: TerminalSession, terminal: Vte.Terminal) -> PickerState | None:
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
        return state

    def on_terminal_shortcut(self, keyval: int, modifiers: object,
                             session: TerminalSession, terminal: Vte.Terminal) -> bool:
        if not modifiers & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK):
            return False
        if not terminal.has_focus() or self.store.encryption_locked:
            return False
        pane = session.pane_for_terminal(terminal)
        if pane is None or not pane.connected or id(terminal) not in session.active_terminal_ids:
            return False
        keybindings = self.store.data.app.keybindings
        try:
            validate_keybindings(keybindings)
        except KeybindingError:
            return False
        for action, shortcut in keybindings.items():
            if is_snippet_action(action) and keybinding_matches(shortcut, keyval, modifiers):
                snippet_id = action[len(SNIPPET_ACTION_PREFIX):]
                if not self.presenter.available(snippet_id, pane.server_id):
                    return False
                state = self.prepare_picker(session, terminal)
                if state is None:
                    return False
                state.selected_id = snippet_id
                self.on_picker_preview(state.preview_button, state)
                state.window.present()
                return True
        return False

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
        if (pane is None or not pane.connected
                or id(context.target.terminal) not in context.target.session.active_terminal_ids
                or pane.server_id != context.target.server_id
                or self.store.encryption_locked
                or not self.presenter.available(context.snippet.id, pane.server_id)):
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
