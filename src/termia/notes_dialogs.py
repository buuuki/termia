# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk

from .config_io import InvalidMasterPasswordError, MissingMasterPasswordError
from .models import Note, NoteCategory
from .notes import NoteError, normalized_note_categories
from .notes_io import export_notes_file, import_notes_file
from .notes_presenter import NoteTreeCategory, NotesPresenter


def format_note_timestamp(value: str) -> str:
    """Render stored ISO timestamps without fractional seconds."""
    if not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return value
    return timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class NoteEditorTab:
    key: str
    note_id: str | None
    title: str
    category: str
    server_id: str | None
    content: str
    dirty: bool = False
    status: str = ""
    label_widget: Gtk.Label | None = None
    scope_icon_widget: Gtk.Image | None = None
    container_widget: Gtk.Widget | None = None


class NotesDialogs:
    """Reusable modeless notes workspace and its dialogs."""

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
        self.export_protection_window: Gtk.Window | None = None
        self.notes_context_popover: Gtk.Popover | None = None
        self.category_context_popover: Gtk.Popover | None = None
        self.tab_context_popover: Gtk.Popover | None = None
        self.current_note_id: str | None = None
        self.selected_note_id: str | None = None
        self.selected_draft_key: str | None = None
        self.server_filter_id: str | None = None
        self.scope_mode = "personal"
        self.expanded_note_sections = {"personal"}
        self.expanded_server_groups: set[str] = set()
        self.last_search_query = ""
        self.autosave_id: int | None = None
        self.loading_editor = False
        self.loading_search = False
        self.editor_dirty = False
        self.editor_tabs: dict[str, NoteEditorTab] = {}
        self.active_editor_tab_key: str | None = None
        self.loading_note_list = False
        self.notes_list_visible = True
        self.collapsed_note_categories: set[tuple[str | None, str]] = set()

    def show_manager(self, server_id: str | None = None) -> None:
        if self.store.encryption_locked:
            self.ensure_writable()
            return
        opening_window = self.window is None or not self.window.get_visible()
        self.ensure_window()
        if not self.set_notes_scope(
            "server" if server_id else "personal", server_id,
        ):
            self.window.present()
            return
        self.window.present()
        if opening_window and not self.store.read_only:
            draft = next(
                (tab for tab in self.editor_tabs.values()
                 if tab.note_id is None and tab.server_id == server_id),
                None,
            )
            if draft is not None:
                if self.active_editor_tab_key != draft.key:
                    self.activate_editor_tab(draft.key)
                self.text_view.grab_focus()
            else:
                self.create_note()

    def ensure_window(self) -> None:
        if self.window is not None:
            return
        window = Gtk.Window(
            title=self.translate("notes_title"),
            application=self.parent.get_application(),
        )
        window.set_modal(False)
        window.set_default_size(1240, 660)
        window.add_css_class("termia-notes-window")
        window.connect("close-request", self.on_close_request)
        self.window = window

        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        window.set_titlebar(header)
        header_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        # Match the sidebar's first button inside the window's content inset.
        header_actions.set_margin_start(8)
        header.pack_start(header_actions)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(root, f"set_margin_{side}")(14)
        window.set_child(root)

        self.toggle_notes_list_button = Gtk.Button()
        self.toggle_notes_list_button.connect("clicked", lambda *_: self.toggle_notes_list())
        header_actions.append(self.toggle_notes_list_button)

        self.add_button = Gtk.Button(icon_name="tab-new-symbolic")
        self.add_button.connect("clicked", lambda *_: self.create_note())
        header_actions.append(self.add_button)

        self.import_export_popover = Gtk.Popover()
        import_export_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.style_notes_menu(self.import_export_popover, import_export_actions)
        self.export_button = Gtk.Button(label=self.translate("notes_export"))
        self.export_button.set_halign(Gtk.Align.FILL)
        self.export_button.connect(
            "clicked",
            lambda *_: self.run_import_export_action(self.choose_export_protection),
        )
        import_export_actions.append(self.export_button)
        self.import_button = Gtk.Button(label=self.translate("notes_import"))
        self.import_button.set_halign(Gtk.Align.FILL)
        self.import_button.connect(
            "clicked",
            lambda *_: self.run_import_export_action(self.start_import),
        )
        import_export_actions.append(self.import_button)
        self.import_export_popover.set_child(import_export_actions)
        self.import_export_menu_button = Gtk.MenuButton(icon_name="view-more-symbolic")
        self.import_export_menu_button.set_tooltip_text(
            self.translate("notes_import_export_options")
        )
        self.import_export_menu_button.set_popover(self.import_export_popover)
        header_actions.append(self.import_export_menu_button)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(330)
        paned.set_vexpand(True)
        root.append(paned)

        list_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        list_panel.set_vexpand(True)
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_box.connect("row-selected", self.on_note_selected)
        list_box.connect("row-activated", self.on_note_row_activated)
        self.notes_list = list_box
        creation_controls = self.build_creation_controls()
        list_panel.append(creation_controls)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_size_request(300, -1)
        self.search_entry.set_margin_end(6)
        self.search_entry.set_placeholder_text(self.translate("notes_search"))
        self.search_entry.connect("search-changed", self.on_search_changed)
        list_panel.append(self.search_entry)

        list_scroller = Gtk.ScrolledWindow()
        list_scroller.set_vexpand(True)
        list_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroller.set_child(list_box)
        self.notes_list_scroller = list_scroller
        list_panel.append(list_scroller)
        paned.set_start_child(list_panel)
        self.notes_list_panel = list_panel
        self.notes_list_paned = paned
        self.notes_list_width = 330
        self.update_notes_list_toggle()

        detail_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.editor_tabs_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.editor_tabs_bar.set_halign(Gtk.Align.START)
        self.editor_tabs_bar.add_css_class("termia-notes-tab-bar")
        tabs_scroller = Gtk.ScrolledWindow()
        tabs_scroller.add_css_class("termia-notes-tab-scroller")
        tabs_scroller.set_hexpand(True)
        tabs_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        tabs_scroller.set_child(self.editor_tabs_bar)
        detail_area.append(tabs_scroller)
        self.notes_top_row_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.VERTICAL)
        self.notes_top_row_size_group.add_widget(creation_controls)
        self.notes_top_row_size_group.add_widget(tabs_scroller)
        tab_drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        tab_drop_target.set_preload(True)
        tab_drop_target.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        tab_drop_target.connect("motion", self.on_editor_tab_drop_motion)
        tab_drop_target.connect("drop", self.on_editor_tab_drop)
        self.editor_tabs_bar.add_controller(tab_drop_target)

        self.detail_stack = Gtk.Stack()
        self.detail_stack.set_hexpand(True)
        self.detail_stack.set_vexpand(True)
        detail_area.append(self.detail_stack)
        paned.set_end_child(detail_area)

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty.set_valign(Gtk.Align.CENTER)
        self.empty_label = Gtk.Label()
        self.empty_label.add_css_class("dim-label")
        empty.append(self.empty_label)
        self.detail_stack.add_named(empty, "empty")

        editor_workspace = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_monospace(False)
        text_view.set_left_margin(12)
        text_view.set_right_margin(12)
        text_view.set_top_margin(12)
        text_view.set_bottom_margin(12)
        text_view.get_buffer().connect("changed", self.on_editor_changed)
        self.text_view = text_view
        text_scroller = Gtk.ScrolledWindow()
        text_scroller.add_css_class("termia-notes-editor")
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
        self.save_button.connect("clicked", lambda *_: self.save_editor())
        footer.append(self.save_button)
        self.delete_button = Gtk.Button(label=self.translate("notes_delete"))
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", lambda *_: self.confirm_delete_note())
        footer.append(self.delete_button)
        self.close_editor_button = Gtk.Button(label=self.translate("close_tab"))
        self.close_editor_button.connect("clicked", lambda *_: self.close_active_editor_tab())
        footer.append(self.close_editor_button)
        editor.append(footer)
        editor_workspace.append(editor)
        self.detail_stack.add_named(editor_workspace, "editor")
        self.note_detail_inset_widgets = (tabs_scroller, empty, editor)
        self.update_note_detail_inset()

        self.configure_write_controls()
        self.set_editor_enabled(False)
        self.detail_stack.set_visible_child_name("empty")

    def set_notes_scope(self, mode: str, server_id: str | None = None) -> bool:
        if mode not in ("personal", "server"):
            return False
        self.expanded_note_sections = getattr(
            self, "expanded_note_sections", {"personal"}
        )
        self.expanded_server_groups = getattr(self, "expanded_server_groups", set())
        if mode == "personal":
            server_id = None
        elif server_id and not any(
            server.id == server_id for server in self.store.data.servers
        ):
            server_id = None
        if not self.save_active_editor_if_valid():
            return False
        self.capture_active_editor_tab()
        self.scope_mode = mode
        self.server_filter_id = server_id
        self.selected_note_id = None
        self.selected_draft_key = None
        if mode == "personal":
            self.expanded_note_sections.add("personal")
        else:
            self.expanded_note_sections.add("servers")
            if server_id:
                self.expanded_server_groups = {server_id}
            else:
                self.expanded_server_groups.clear()
        self.loading_search = True
        try:
            self.search_entry.set_text("")
        finally:
            self.loading_search = False
        self.last_search_query = ""
        self.update_creation_controls()
        self.update_window_title(server_id if mode == "server" else None)
        self.set_import_export_actions_visible(mode == "personal")
        self.refresh_list()

        if mode == "server" and server_id is None:
            matching_tab = None
        else:
            target_server_id = server_id if mode == "server" else None
            matching_tab = next(
                (
                    tab for tab in self.editor_tabs.values()
                    if tab.server_id == target_server_id
                ),
                None,
            )
        if matching_tab is not None:
            self.activate_editor_tab(matching_tab.key)
        else:
            had_active_tab = getattr(self, "active_editor_tab_key", None) is not None
            self.active_editor_tab_key = None
            self.current_note_id = None
            self.editor_dirty = False
            if had_active_tab:
                self.loading_editor = True
                try:
                    self.text_view.get_buffer().set_text("")
                    self.modified_label.set_label("")
                    self.status_label.set_label(self.translate("notes_select_or_create"))
                    self.set_editor_enabled(False)
                    self.show_empty_state()
                finally:
                    self.loading_editor = False
            for tab in self.editor_tabs.values():
                self.update_editor_tab_label(tab)
        return True

    def build_creation_controls(self) -> Gtk.Box:
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        controls.set_halign(Gtk.Align.START)
        self.category_add_button = Gtk.Button(icon_name="list-add-symbolic")
        self.category_add_button.set_tooltip_text(self.translate("notes_category_add"))
        self.category_add_button.connect(
            "clicked",
            lambda *_: self.prompt_category_edit(
                "add", server_id=self.server_filter_id if self.scope_mode == "server" else None,
            ),
        )
        controls.append(self.category_add_button)
        self.update_creation_controls()
        return controls

    @staticmethod
    def style_notes_menu(popover: Gtk.Popover, panel: Gtk.Widget) -> None:
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        panel.add_css_class("termia-menu-panel")
        for side in ("top", "bottom", "start", "end"):
            getattr(panel, f"set_margin_{side}")(6)

    def update_creation_controls(self) -> None:
        add_button = getattr(self, "add_button", None)
        category_button = getattr(self, "category_add_button", None)
        if add_button is None:
            return
        server_scope = getattr(self, "scope_mode", "personal") == "server"
        server_id = getattr(self, "server_filter_id", None)
        store = getattr(self, "store", None)
        writable = not getattr(store, "read_only", False) and not getattr(
            store, "encryption_locked", False
        )
        enabled = writable and (not server_scope or server_id is not None)
        add_button.set_tooltip_text(
            self.translate("notes_create_for_server")
            if server_scope and server_id else self.translate("notes_create")
        )
        if hasattr(add_button, "set_sensitive"):
            add_button.set_sensitive(enabled)
        if category_button is not None and hasattr(category_button, "set_sensitive"):
            category_button.set_sensitive(enabled)

    def configure_write_controls(self) -> None:
        writable = not self.store.read_only and not self.store.encryption_locked
        for widget in (
            self.category_add_button,
            self.add_button,
            self.import_button,
            self.text_view,
            self.save_button,
            self.delete_button,
        ):
            widget.set_sensitive(writable)
        self.export_button.set_sensitive(not self.store.encryption_locked)

    def set_import_export_actions_visible(self, visible: bool) -> None:
        self.import_button.set_visible(visible)
        self.export_button.set_visible(visible)
        self.import_export_menu_button.set_visible(visible)

    def run_import_export_action(self, callback) -> None:
        self.import_export_popover.popdown()
        GLib.idle_add(callback)

    def update_notes_list_toggle(self) -> None:
        if not hasattr(self, "toggle_notes_list_button"):
            return
        self.toggle_notes_list_button.set_icon_name(
            "sidebar-hide-symbolic" if self.notes_list_visible else "sidebar-show-symbolic"
        )
        self.toggle_notes_list_button.set_tooltip_text(self.translate(
            "notes_hide_list" if self.notes_list_visible else "notes_show_list"
        ))

    def save_active_editor_if_valid(self) -> bool:
        if not self.editor_dirty:
            return True
        if not hasattr(self, "text_view"):
            return self.save_editor()
        if self.editor_content().strip():
            return self.save_editor()
        self.cancel_autosave()
        self.capture_active_editor_tab()
        return True

    def toggle_notes_list(self) -> None:
        if self.notes_list_visible:
            position = self.notes_list_paned.get_position()
            if position > 64:
                self.notes_list_width = position
            self.notes_list_visible = False
            self.notes_list_paned.set_start_child(None)
        else:
            self.notes_list_visible = True
            self.notes_list_paned.set_start_child(self.notes_list_panel)
            self.notes_list_paned.set_position(self.notes_list_width)
        self.update_note_detail_inset()
        self.update_notes_list_toggle()

    def update_note_detail_inset(self) -> None:
        inset = 6 if self.notes_list_visible else 0
        for widget in self.note_detail_inset_widgets:
            widget.set_margin_start(inset)

    def on_search_changed(self, *_args) -> None:
        if self.loading_search:
            return
        query = self.search_entry.get_text()
        if not self.save_active_editor_if_valid():
            self.loading_search = True
            try:
                self.search_entry.set_text(self.last_search_query)
            finally:
                self.loading_search = False
            return
        self.last_search_query = query
        self.refresh_list()

    def update_window_title(self, server_id: str | None) -> None:
        if getattr(self, "scope_mode", "personal") == "personal":
            title = self.translate("notes_title")
        elif server_id is None:
            title = self.translate("notes_server_scope")
        else:
            servers = getattr(getattr(self.store, "data", None), "servers", ())
            server = next(
                (item for item in servers if item.id == server_id),
                None,
            )
            server_name = server.name if server else self.translate("notes_unknown_server")
            title = self.translate("notes_for_server").format(name=server_name)
        self.window.set_title(title)

    def refresh_list(self, selected_id: str | None = None) -> None:
        if not hasattr(self, "notes_list"):
            return
        was_loading = getattr(self, "loading_note_list", False)
        self.loading_note_list = True
        try:
            self._refresh_list_rows(selected_id)
        finally:
            self.loading_note_list = was_loading

    def _refresh_list_rows(self, selected_id: str | None = None) -> None:
        self.close_note_context_menu()
        self.close_category_context_menu()
        selected_id = selected_id if selected_id is not None else self.selected_note_id
        query = self.search_entry.get_text().strip()
        while child := self.notes_list.get_first_child():
            self.notes_list.remove(child)
        tabs = tuple(getattr(self, "editor_tabs", {}).values())
        drafts_by_scope: dict[str | None, list[NoteEditorTab]] = {}
        for tab in tabs:
            if tab.note_id is None:
                drafts_by_scope.setdefault(tab.server_id, []).append(tab)
        server_ids_with_drafts = {
            server_id for server_id in drafts_by_scope if server_id is not None
        }
        if (
            getattr(self, "scope_mode", "personal") == "server"
            and self.server_filter_id is not None
        ):
            server_ids_with_drafts.add(self.server_filter_id)
        tree = self.presenter.tree(query, server_ids_with_drafts)
        selected_row = None
        selected_draft_key = getattr(self, "selected_draft_key", None)
        server_names = {
            server.id: server.name
            for server in getattr(getattr(self.store, "data", None), "servers", ())
        }

        def matching_drafts(server_id: str | None) -> list[NoteEditorTab]:
            drafts = drafts_by_scope.get(server_id, [])
            if not query:
                return drafts
            searchable = query.casefold()
            server_name = server_names.get(server_id or "", "").casefold()
            return [
                tab for tab in drafts
                if searchable in " ".join((
                    tab.title, tab.content, tab.category, server_name,
                )).casefold()
            ]

        def append_categories(
            categories, server_id: str | None, level: int,
            drafts: list[NoteEditorTab],
        ) -> None:
            nonlocal selected_row
            category_names = {category.name for category in categories}
            extra_names = {
                tab.category or "" for tab in drafts
                if (tab.category or "") not in category_names
            }
            categories = tuple(categories) + tuple(
                NoteTreeCategory(name, ()) for name in sorted(
                    extra_names, key=lambda value: (value != "", value.casefold())
                )
            )
            categories = tuple(sorted(
                categories,
                key=lambda category: (category.name != "", category.name.casefold()),
            ))
            for category in categories:
                key = (server_id, category.name)
                collapsed = key in self.collapsed_note_categories and not query
                category_drafts = [
                    tab for tab in drafts if (tab.category or "") == category.name
                ]
                self.append_note_category_header(
                    category.name, len(category.items) + len(category_drafts), collapsed,
                    server_id=server_id, level=level,
                )
                if collapsed:
                    continue
                for item in category.items:
                    row = self.append_note_row(item, level + 1)
                    if item.note.id == selected_id:
                        selected_row = row
                for tab in category_drafts:
                    row = self.append_note_draft_row(tab, level + 1)
                    if tab.key == selected_draft_key:
                        selected_row = row

        personal_drafts = matching_drafts(None)
        personal_count = sum(
            len(category.items) for category in tree.personal_categories
        ) + len(personal_drafts)
        personal_expanded = "personal" in self.expanded_note_sections or bool(query)
        self.append_note_tree_header(
            self.translate("notes_personal_scope"), "avatar-default-symbolic",
            personal_expanded, personal_count,
            lambda: self.on_note_section_clicked("personal"), level=0,
        )
        if personal_expanded:
            append_categories(tree.personal_categories, None, 1, personal_drafts)

        server_count = sum(
            len(item.items) for server in tree.servers for item in server.categories
        ) + sum(len(matching_drafts(server.id)) for server in tree.servers)
        servers_expanded = "servers" in self.expanded_note_sections or bool(query)
        self.append_note_tree_header(
            self.translate("notes_server_scope"), "network-server-symbolic",
            servers_expanded, server_count,
            lambda: self.on_note_section_clicked("servers"), level=0,
        )
        if servers_expanded:
            for server in tree.servers:
                expanded = server.id in self.expanded_server_groups or bool(query)
                self.append_note_tree_header(
                    server.name or self.translate("notes_unknown_server"),
                    "network-server-symbolic", expanded,
                    sum(len(category.items) for category in server.categories)
                    + len(matching_drafts(server.id)),
                    lambda server_id=server.id: self.on_server_tree_node_clicked(server_id),
                    level=1,
                )
                if expanded:
                    append_categories(
                        server.categories, server.id, 2,
                        matching_drafts(server.id),
                    )
        if selected_row is not None:
            if getattr(selected_row, "draft_key", None):
                self.selected_note_id = None
                self.selected_draft_key = selected_row.draft_key
            else:
                self.selected_note_id = selected_row.note_id
                self.selected_draft_key = None
            self.notes_list.select_row(selected_row)
        else:
            self.selected_note_id = None
            self.selected_draft_key = None
            self.notes_list.unselect_all()
        if selected_row is not None:
            if getattr(self, "active_editor_tab_key", None) is None:
                self.show_idle_workspace()
        elif getattr(self, "active_editor_tab_key", None) is None:
            self.show_empty_state()

    def append_note_draft_row(self, tab: NoteEditorTab, level: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.note_id = None
        row.draft_key = tab.key
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label=tab.title)
        title.set_xalign(0)
        title.set_ellipsize(3)
        title.set_hexpand(True)
        title.add_css_class("dim-label")
        content.append(title)
        content.set_margin_top(4)
        content.set_margin_bottom(4)
        content.set_margin_start(24 + level * 16)
        content.set_margin_end(8)
        row.set_child(content)
        self.notes_list.append(row)
        return row

    def append_note_row(self, item, level: int) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.note_id = item.note.id
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label=item.note.title)
        title.set_xalign(0)
        title.set_ellipsize(3)
        title.set_hexpand(True)
        title.add_css_class("heading")
        content.append(title)
        content.set_margin_top(4)
        content.set_margin_bottom(4)
        content.set_margin_start(24 + level * 16)
        content.set_margin_end(8)
        row.set_child(content)
        context_click = Gtk.GestureClick()
        context_click.set_button(3)
        context_click.connect("pressed", self.on_note_context_pressed, row)
        row.add_controller(context_click)
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self.on_note_drag_prepare, item.note.id)
        drag_source.connect("drag-begin", self.on_note_drag_begin, row)
        drag_source.connect("drag-end", self.on_note_drag_end, row)
        row.add_controller(drag_source)
        self.notes_list.append(row)
        return row

    def append_note_tree_header(
        self, label: str, icon_name: str, expanded: bool, count: int,
        callback, *, level: int,
    ) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        button = Gtk.Button()
        button.add_css_class("flat")
        button.add_css_class("termia-note-category")
        button.add_css_class("termia-note-tree-root" if level == 0 else "termia-note-server")
        button.set_hexpand(True)
        button.set_halign(Gtk.Align.FILL)
        button.connect("clicked", lambda *_args: callback())
        contents = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        contents.append(Gtk.Image.new_from_icon_name(
            "pan-down-symbolic" if expanded else "pan-end-symbolic"
        ))
        contents.append(Gtk.Image.new_from_icon_name(icon_name))
        name = Gtk.Label(label=label)
        name.set_xalign(0)
        name.set_ellipsize(3)
        name.set_hexpand(True)
        name.set_tooltip_text(label)
        name.add_css_class("heading")
        contents.append(name)
        count_label = Gtk.Label(
            label=self.translate("notes_category_count").format(count=count)
        )
        count_label.add_css_class("dim-label")
        contents.append(count_label)
        contents.set_margin_start(4 + level * 16)
        contents.set_margin_end(4)
        contents.set_margin_top(4)
        contents.set_margin_bottom(4)
        button.set_child(contents)
        row.set_child(button)
        self.notes_list.append(row)
        return row

    def on_note_section_clicked(self, section: str) -> None:
        if section == "personal":
            if self.scope_mode != "personal":
                self.set_notes_scope("personal")
                return
        elif self.scope_mode != "server" or self.server_filter_id is not None:
            self.set_notes_scope("server", None)
            return
        self.toggle_note_section(section)

    def toggle_note_section(self, section: str) -> None:
        if section in self.expanded_note_sections:
            self.expanded_note_sections.remove(section)
        else:
            self.expanded_note_sections.add(section)
        self.refresh_list(self.selected_note_id)

    def on_server_tree_node_clicked(self, server_id: str) -> None:
        expanded = server_id in self.expanded_server_groups
        if self.scope_mode != "server" or self.server_filter_id != server_id:
            if expanded:
                self.expanded_server_groups.discard(server_id)
            else:
                self.expanded_server_groups = {server_id}
            self.set_notes_scope("server", server_id)
            return
        if expanded:
            self.expanded_server_groups.discard(server_id)
        else:
            self.expanded_server_groups = {server_id}
        self.refresh_list(self.selected_note_id)

    def append_note_category_header(
        self, category: str, count: int, collapsed: bool,
        *, server_id: str | None, level: int,
    ) -> None:
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        button = Gtk.Button()
        button.add_css_class("flat")
        button.set_hexpand(True)
        button.set_halign(Gtk.Align.FILL)
        button.connect(
            "clicked",
            lambda _button, name=category, scope=server_id:
                self.toggle_note_category(name, scope),
        )
        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        drop_target.set_preload(True)
        drop_target.connect("motion", self.on_note_category_drop_motion, button)
        drop_target.connect("leave", self.on_note_category_drop_leave, button)
        drop_target.connect("drop", self.on_note_category_drop, category)
        button.add_controller(drop_target)
        contents = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        disclosure = Gtk.Image.new_from_icon_name(
            "pan-end-symbolic" if collapsed else "pan-down-symbolic"
        )
        contents.append(disclosure)
        contents.append(Gtk.Image.new_from_icon_name(
            "view-list-symbolic" if category == "" else "folder-symbolic"
        ))
        name = category or self.translate("notes_uncategorized")
        label = Gtk.Label(label=name)
        label.set_xalign(0)
        label.set_ellipsize(3)
        label.set_hexpand(True)
        label.set_tooltip_text(name)
        label.add_css_class("heading")
        contents.append(label)
        count_label = Gtk.Label(
            label=self.translate("notes_category_count").format(count=count)
        )
        count_label.add_css_class("dim-label")
        contents.append(count_label)
        contents.set_margin_start(4 + level * 16)
        contents.set_margin_end(4)
        contents.set_margin_top(4)
        contents.set_margin_bottom(4)
        button.set_child(contents)
        row.set_child(button)
        button.add_css_class("termia-note-category")
        if category:
            context_click = Gtk.GestureClick()
            context_click.set_button(3)
            context_click.connect(
                "pressed", self.on_category_context_pressed,
                category, button, server_id,
            )
            button.add_controller(context_click)
            context_key = Gtk.EventControllerKey.new()
            context_key.connect(
                "key-pressed", self.on_category_context_key_pressed,
                category, button, server_id,
            )
            button.add_controller(context_key)
        self.notes_list.append(row)

    def on_note_drag_prepare(
        self, _source: Gtk.DragSource, _x: float, _y: float, note_id: str
    ) -> Gdk.ContentProvider | None:
        if self.find_note(note_id) is None:
            return None
        return Gdk.ContentProvider.new_for_value(note_id)

    def on_note_drag_begin(
        self, source: Gtk.DragSource, _drag: Gdk.Drag, row: Gtk.ListBoxRow
    ) -> None:
        row.add_css_class("dragging")
        source.set_icon(
            Gtk.WidgetPaintable.new(row),
            row.get_allocated_width() // 2,
            row.get_allocated_height() // 2,
        )

    def on_note_drag_end(
        self, _source: Gtk.DragSource, _drag: Gdk.Drag,
        _delete_data: bool, row: Gtk.ListBoxRow,
    ) -> None:
        row.remove_css_class("dragging")

    def on_note_category_drop_motion(
        self, _target: Gtk.DropTarget, _x: float, _y: float, button: Gtk.Button
    ) -> Gdk.DragAction:
        button.add_css_class("drop-target")
        return Gdk.DragAction.MOVE

    def on_note_category_drop_leave(
        self, _target: Gtk.DropTarget, button: Gtk.Button
    ) -> None:
        button.remove_css_class("drop-target")

    def on_note_category_drop(
        self, _target: Gtk.DropTarget, note_id: str, _x: float, _y: float,
        category: str,
    ) -> bool:
        return self.move_note_to_category(note_id, category)

    def move_note_to_category(self, note_id: str, category: str) -> bool:
        if not self.ensure_writable():
            return False
        if self.editor_dirty:
            if self.editor_content().strip():
                if not self.save_editor(refresh=False):
                    return False
            else:
                self.cancel_autosave()
                self.capture_active_editor_tab()
        note = self.find_note(note_id)
        if note is None:
            return False
        if category and not self.store.has_note_category(category, note.server_id):
            return False
        if note.category == category:
            return True
        try:
            self.store.update_note(
                note.id, note.title, note.content, category, note.server_id
            )
        except (NoteError, OSError, RuntimeError, ValueError):
            self.show_error(self.translate("notes_save_failed_detail"))
            return False
        updated_note = self.find_note(note.id)
        for tab in self.editor_tabs.values():
            if tab.note_id == note.id:
                tab.category = category
        if updated_note is not None and self.current_note_id == note.id:
            self.modified_label.set_label(
                self.translate("notes_modified").format(
                    date=format_note_timestamp(updated_note.modified_at)
                )
            )
        self.refresh_list(note.id)
        display_category = category or self.translate("notes_uncategorized")
        self.show_toast(
            self.translate("notes_moved_to_category").format(category=display_category)
        )
        return True

    def toggle_note_category(
        self, category: str, scope_id: str | None = None,
    ) -> None:
        target_mode = "server" if scope_id else "personal"
        if (
            getattr(self, "scope_mode", "personal") != target_mode
            or self.server_filter_id != (scope_id if scope_id else None)
        ):
            self.set_notes_scope(target_mode, scope_id)
            return
        key = (scope_id, category or "")
        if key in self.collapsed_note_categories:
            self.collapsed_note_categories.remove(key)
        else:
            self.collapsed_note_categories.add(key)
        self.refresh_list(self.selected_note_id)

    def on_category_context_pressed(
        self, gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float,
        category: str, button: Gtk.Button, server_id: str | None = None,
    ) -> None:
        self.show_category_context_menu(category, button, server_id)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def on_category_context_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int,
        state: Gdk.ModifierType, category: str, button: Gtk.Button,
        server_id: str | None = None,
    ) -> bool:
        if keyval == Gdk.KEY_Menu or (
            keyval == Gdk.KEY_F10 and state & Gdk.ModifierType.SHIFT_MASK
        ):
            self.show_category_context_menu(category, button, server_id)
            return True
        return False

    def show_category_context_menu(
        self, category: str, button: Gtk.Button, server_id: str | None = None,
    ) -> None:
        if not self.store.has_note_category(category, server_id):
            return
        self.close_category_context_menu()
        popover = Gtk.Popover()
        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.style_notes_menu(popover, actions)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.connect("closed", self.on_category_context_menu_closed)
        for action, label_key in (
            ("rename", "notes_category_rename"),
            ("duplicate", "notes_category_duplicate"),
            ("delete", "notes_category_delete"),
        ):
            item = Gtk.Button(label=self.translate(label_key))
            item.set_halign(Gtk.Align.FILL)
            if action == "delete":
                item.add_css_class("destructive-action")
            item.set_sensitive(not self.store.read_only and not self.store.encryption_locked)
            item.connect(
                "clicked",
                lambda _button, selected_action=action, name=category, scope=server_id:
                    self.on_category_context_action(selected_action, name, scope),
            )
            actions.append(item)
        popover.set_child(actions)
        popover.set_parent(button)
        self.category_context_popover = popover
        popover.popup()

    def on_category_context_menu_closed(self, popover: Gtk.Popover) -> None:
        if self.category_context_popover is popover:
            self.category_context_popover = None
        if popover.get_parent() is not None:
            popover.unparent()

    def close_category_context_menu(self) -> None:
        popover = getattr(self, "category_context_popover", None)
        if popover is None:
            return
        self.category_context_popover = None
        popover.popdown()
        if popover.get_parent() is not None:
            popover.unparent()

    def on_category_context_action(
        self, action: str, category: str, server_id: str | None = None,
    ) -> None:
        self.close_category_context_menu()
        if action in ("rename", "duplicate"):
            GLib.idle_add(self.prompt_category_edit, action, category, server_id)
        elif action == "delete":
            GLib.idle_add(self.confirm_delete_category, category, server_id)

    def on_note_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        if self.loading_note_list:
            return
        draft_key = getattr(row, "draft_key", None)
        if draft_key:
            if draft_key == getattr(self, "selected_draft_key", None):
                return
            self.selected_note_id = None
            self.selected_draft_key = draft_key
            self.activate_editor_tab(draft_key)
            return
        note_id = getattr(row, "note_id", None)
        if not note_id or note_id == self.selected_note_id:
            return
        note = self.find_note(note_id)
        if note is None:
            return
        target_mode = "server" if note.server_id else "personal"
        if (
            getattr(self, "scope_mode", "personal") != target_mode
            or self.server_filter_id != (note.server_id if note.server_id else None)
        ):
            self.set_notes_scope(target_mode, note.server_id)
        self.selected_note_id = note.id
        self.selected_draft_key = None
        if getattr(self, "active_editor_tab_key", None) is None:
            self.show_idle_workspace()

    def on_note_row_activated(
        self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow,
    ) -> None:
        draft_key = getattr(row, "draft_key", None)
        if draft_key:
            self.activate_editor_tab(draft_key)
            return
        note_id = getattr(row, "note_id", None)
        note = self.find_note(note_id) if note_id else None
        if note is not None:
            self.load_editor(note)

    def iter_note_rows(self):
        row = self.notes_list.get_first_child()
        while row:
            yield row
            row = row.get_next_sibling()

    def on_note_context_pressed(
        self, gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float,
        row: Gtk.ListBoxRow,
    ) -> None:
        note_id = getattr(row, "note_id", None)
        self.notes_list.select_row(row)
        if self.notes_list.get_selected_row() is not row:
            if not note_id or self.selected_note_id != note_id:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
                return
            row = next(
                (item for item in self.iter_note_rows() if getattr(item, "note_id", None) == note_id),
                None,
            )
            if row is None:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
                return
            self.notes_list.select_row(row)
        if self.notes_list.get_selected_row() is not row:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        self.show_note_context_menu(row)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def show_note_context_menu(self, row: Gtk.ListBoxRow) -> None:
        self.close_note_context_menu()
        popover = Gtk.Popover()
        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.style_notes_menu(popover, actions)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.connect("closed", self.on_note_context_menu_closed)
        for action, label_key in (
            ("edit", "notes_edit"),
            ("rename", "notes_rename"),
            ("clone", "notes_clone"),
            ("properties", "notes_properties"),
            ("delete", "notes_delete"),
        ):
            button = Gtk.Button(label=self.translate(label_key))
            button.set_halign(Gtk.Align.FILL)
            if action == "delete":
                button.add_css_class("destructive-action")
            button.connect(
                "clicked",
                lambda _button, selected_action=action, note_id=row.note_id:
                    self.on_note_context_action(selected_action, note_id),
            )
            button.set_sensitive(
                not self.store.encryption_locked
                and (action == "properties" or not self.store.read_only),
            )
            actions.append(button)
        popover.set_child(actions)
        popover.set_parent(row)
        self.notes_context_popover = popover
        popover.popup()

    def on_note_context_menu_closed(self, popover: Gtk.Popover) -> None:
        if self.notes_context_popover is popover:
            self.notes_context_popover = None
        if popover.get_parent() is not None:
            popover.unparent()

    def close_note_context_menu(self) -> None:
        popover = getattr(self, "notes_context_popover", None)
        if popover is None:
            return
        self.notes_context_popover = None
        popover.popdown()
        if popover.get_parent() is not None:
            popover.unparent()

    def on_note_context_action(self, action: str, note_id: str) -> None:
        self.close_note_context_menu()
        if action == "edit":
            note = self.find_note(note_id)
            if note is not None:
                self.load_editor(note)
        elif action == "clone":
            self.clone_note(note_id)
        elif action == "rename":
            GLib.idle_add(self.prompt_note_rename, note_id)
        elif action == "properties":
            GLib.idle_add(self.show_note_properties, note_id)
        elif action == "delete":
            self.confirm_delete_note(note_id)

    def note_property_rows(self, note: Note) -> list[tuple[str, str]]:
        server_name = self.translate("notes_standalone")
        if note.server_id:
            server_name = next(
                (server.name for server in self.store.data.servers if server.id == note.server_id),
                self.translate("notes_unknown_server"),
            )
        line_count = len(note.content.splitlines())
        if note.content.endswith(("\n", "\r")):
            line_count += 1
        created = format_note_timestamp(note.created_at) or "—"
        modified = format_note_timestamp(note.modified_at) or "—"
        return [
            (self.translate("name"), note.title),
            (
                self.translate("notes_category"),
                note.category or self.translate("notes_uncategorized"),
            ),
            (self.translate("notes_association"), server_name),
            (self.translate("notes_property_created"), created),
            (self.translate("notes_property_modified"), modified),
            (self.translate("notes_property_lines"), str(line_count)),
            (self.translate("notes_property_characters"), str(len(note.content))),
            (
                self.translate("notes_property_size"),
                self.translate("notes_property_bytes").format(
                    count=len(note.content.encode("utf-8"))
                ),
            ),
        ]

    def show_note_properties(self, note_id: str) -> None:
        note = self.find_note(note_id)
        if note is None:
            return
        dialog = Gtk.Window(
            title=self.translate("notes_properties"),
            transient_for=self.window,
            modal=False,
        )
        dialog.set_resizable(False)
        dialog.add_css_class("termia-note-properties")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_margin_top(6)
        content.set_margin_bottom(6)
        content.set_margin_start(10)
        content.set_margin_end(10)
        content.set_vexpand(False)
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        details.add_css_class("termia-note-properties-content")
        grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        for index, (name, value) in enumerate(self.note_property_rows(note)):
            name_label = Gtk.Label(label=name)
            name_label.set_xalign(0)
            name_label.set_valign(Gtk.Align.START)
            name_label.set_wrap(True)
            name_label.set_max_width_chars(20)
            name_label.add_css_class("dim-label")
            value_label = Gtk.Label(label=value)
            value_label.set_xalign(0)
            value_label.set_wrap(True)
            value_label.set_max_width_chars(40)
            grid.attach(name_label, 0, index, 1, 1)
            grid.attach(value_label, 1, index, 1, 1)
        details.append(grid)
        content.append(details)
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        actions.set_hexpand(True)
        close_button = Gtk.Button(label=self.translate("close"))
        close_button.set_hexpand(True)
        close_button.set_halign(Gtk.Align.END)
        close_button.set_margin_end(2)
        close_button.connect("clicked", lambda *_: dialog.destroy())
        actions.append(close_button)
        content.append(actions)
        dialog.set_child(content)
        dialog.set_size_request(440, -1)
        dialog.present()

    def on_note_tab_context_pressed(
        self, gesture: Gtk.GestureClick, _presses: int, _x: float, _y: float,
        key: str,
    ) -> None:
        self.show_note_tab_context_menu(key)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def show_note_tab_context_menu(self, key: str) -> None:
        tab = self.editor_tabs.get(key)
        if tab is None or tab.container_widget is None:
            return
        self.close_note_tab_context_menu()
        popover = Gtk.Popover()
        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.style_notes_menu(popover, actions)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.connect("closed", self.on_note_tab_context_menu_closed)
        rename = Gtk.Button(label=self.translate("notes_rename"))
        rename.set_halign(Gtk.Align.FILL)
        rename.set_sensitive(not self.store.read_only and not self.store.encryption_locked)
        rename.connect(
            "clicked",
            lambda *_args, selected_key=key: self.on_note_tab_rename_action(selected_key),
        )
        actions.append(rename)
        popover.set_child(actions)
        popover.set_parent(tab.container_widget)
        self.tab_context_popover = popover
        popover.popup()

    def on_note_tab_rename_action(self, key: str) -> None:
        self.close_note_tab_context_menu()
        GLib.idle_add(self.prompt_editor_tab_rename, key)

    def on_note_tab_context_menu_closed(self, popover: Gtk.Popover) -> None:
        if self.tab_context_popover is popover:
            self.tab_context_popover = None
        if popover.get_parent() is not None:
            popover.unparent()

    def close_note_tab_context_menu(self) -> None:
        popover = getattr(self, "tab_context_popover", None)
        if popover is None:
            return
        self.tab_context_popover = None
        popover.popdown()
        if popover.get_parent() is not None:
            popover.unparent()

    def show_note_rename_dialog(self, title: str, response_callback, *callback_args) -> None:
        dialog = Gtk.Dialog(
            title=self.translate("notes_rename"), transient_for=self.window, modal=True
        )
        dialog.add_button(self.translate("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.translate("save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        entry = Gtk.Entry()
        entry.set_text(title)
        entry.set_activates_default(True)
        content.append(entry)
        dialog.connect("response", response_callback, entry, *callback_args)
        dialog.present()
        entry.grab_focus()
        entry.select_region(0, -1)

    def prompt_note_rename(self, note_id: str) -> None:
        if not self.ensure_writable() or not self.save_active_editor_if_valid():
            return
        note = self.find_note(note_id)
        if note is not None:
            self.show_note_rename_dialog(
                note.title, self.on_note_rename_response, note.id
            )

    def on_note_rename_response(
        self, dialog: Gtk.Dialog, response: int, entry: Gtk.Entry, note_id: str
    ) -> None:
        title = entry.get_text().strip()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not title:
            self.show_error(self.translate("notes_title_required"))
            return
        if not self.save_active_editor_if_valid():
            return
        note = self.find_note(note_id)
        if note is None:
            return
        self.persist_note_title(note, title)

    def prompt_editor_tab_rename(self, key: str) -> None:
        if not self.ensure_writable():
            return
        tab = self.editor_tabs.get(key)
        if tab is not None:
            self.show_note_rename_dialog(
                tab.title, self.on_editor_tab_rename_response, tab.key
            )

    def on_editor_tab_rename_response(
        self, dialog: Gtk.Dialog, response: int, entry: Gtk.Entry, key: str
    ) -> None:
        title = entry.get_text().strip()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not title:
            self.show_error(self.translate("notes_title_required"))
            return
        tab = self.editor_tabs.get(key)
        if tab is None:
            return
        if tab.note_id is not None:
            if not self.save_active_editor_if_valid():
                return
            note = self.find_note(tab.note_id)
            if note is not None:
                self.persist_note_title(note, title)
            return
        tab.title = title
        if tab.content.strip():
            tab.dirty = True
            if key == self.active_editor_tab_key:
                self.editor_dirty = True
                self.schedule_autosave()
        self.update_editor_tab_label(tab)

    def persist_note_title(self, note: Note, title: str) -> None:
        try:
            self.store.update_note(
                note.id, title, note.content, note.category, note.server_id
            )
        except (NoteError, OSError, RuntimeError, ValueError):
            self.show_error(self.translate("notes_save_failed_detail"))
            return
        updated = self.find_note(note.id)
        if updated is None:
            return
        for tab in self.editor_tabs.values():
            if tab.note_id == updated.id:
                tab.title = updated.title
                self.update_editor_tab_label(tab)
        self.refresh_list(updated.id)
        self.show_toast(self.translate("notes_renamed"))

    def clone_note(self, note_id: str) -> None:
        if not self.ensure_writable():
            return
        if not self.save_active_editor_if_valid():
            return
        note = self.find_note(note_id)
        if note is None:
            return
        title = note.title + self.translate("notes_clone_suffix")
        try:
            cloned = self.store.add_note(
                title, note.content, note.category, note.server_id,
            )
        except (NoteError, OSError, RuntimeError, ValueError):
            self.show_error(self.translate("notes_save_failed_detail"))
            return
        self.selected_note_id = cloned.id
        self.refresh_list(cloned.id)
        self.show_toast(self.translate("notes_clone_success"))

    def find_note(self, note_id: str) -> Note | None:
        return next((note for note in self.store.data.notes if note.id == note_id), None)

    def show_idle_workspace(self) -> None:
        self.empty_label.set_label(self.translate("notes_double_click_to_open"))
        self.detail_stack.set_visible_child_name("empty")

    def show_empty_state(self) -> None:
        if self.search_entry.get_text():
            message = self.translate("notes_empty")
        elif getattr(self, "scope_mode", "personal") == "server" and self.server_filter_id is None:
            message = self.translate("notes_choose_server_empty")
        elif getattr(self, "scope_mode", "personal") == "server":
            message = self.translate("notes_empty_server")
        else:
            message = self.translate("notes_empty_personal")
        self.empty_label.set_label(message)
        self.detail_stack.set_visible_child_name("empty")

    def load_editor(self, note: Note) -> None:
        if self.store.encryption_locked:
            self.ensure_writable()
            return
        existing = next((tab for tab in self.editor_tabs.values() if tab.note_id == note.id), None)
        if existing is not None:
            self.activate_editor_tab(existing.key)
            return
        tab = NoteEditorTab(
            key=note.id,
            note_id=note.id,
            title=note.title,
            category=note.category,
            server_id=note.server_id,
            content=note.content,
            status=self.translate("notes_saved"),
        )
        self.add_editor_tab(tab)
        self.activate_editor_tab(tab.key)

    def create_editor_tab(self) -> None:
        key = f"draft-{uuid4().hex}"
        scope_mode = getattr(self, "scope_mode", "personal")
        server_id = self.server_filter_id if scope_mode == "server" else None
        tab = NoteEditorTab(
            key=key,
            note_id=None,
            title=self.next_note_title(server_id),
            category="",
            server_id=server_id,
            content="",
            status=self.translate("notes_start_typing"),
        )
        self.add_editor_tab(tab)
        self.activate_editor_tab(tab.key)
        self.selected_note_id = None
        self.selected_draft_key = tab.key
        if server_id is None:
            self.expanded_note_sections.add("personal")
        else:
            self.expanded_note_sections.add("servers")
            self.expanded_server_groups = {server_id}
        self.loading_note_list = True
        try:
            self.notes_list.unselect_all()
        finally:
            self.loading_note_list = False
        self.refresh_list()

    def next_note_title(self, server_id: str | None) -> str:
        base = self.translate("notes_new_tab")
        existing = {
            note.title.casefold()
            for note in self.store.data.notes
            if note.server_id == (server_id or None)
        }
        existing.update(
            tab.title.casefold()
            for tab in self.editor_tabs.values()
            if tab.server_id == (server_id or None)
        )
        if base.casefold() not in existing:
            return base
        suffix = 2
        while f"{base} {suffix}".casefold() in existing:
            suffix += 1
        return f"{base} {suffix}"

    def add_editor_tab(self, tab: NoteEditorTab) -> None:
        self.editor_tabs[tab.key] = tab
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_box.add_css_class("termia-tab-label")
        tab_box.add_css_class("termia-note-tab")
        tab_box.set_hexpand(False)
        tab_box.set_size_request(150, -1)
        tab_box.set_focusable(True)
        scope_icon = Gtk.Image.new_from_icon_name(
            "network-server-symbolic" if tab.server_id else "avatar-default-symbolic"
        )
        scope_icon.add_css_class("dim-label")
        scope_icon.set_can_target(False)
        label = Gtk.Label()
        label.add_css_class("termia-tab-title")
        label.set_hexpand(True)
        label.set_ellipsize(3)
        label.set_width_chars(10)
        label.set_max_width_chars(14)
        label.set_can_target(False)
        close_button = Gtk.Button(icon_name="window-close-symbolic")
        close_button.add_css_class("termia-tab-close")
        close_button.set_has_frame(False)
        close_button.set_tooltip_text(self.translate("notes_close_tab"))
        close_button.connect("clicked", lambda _button, key=tab.key: self.close_editor_tab(key))
        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("pressed", lambda _gesture, _presses, _x, _y, key=tab.key: self.activate_editor_tab(key))
        tab_box.add_controller(click)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_note_tab_context_pressed, tab.key)
        tab_box.add_controller(right_click)
        tab_box.append(scope_icon)
        tab_box.append(label)
        tab_box.append(close_button)
        tab.label_widget = label
        tab.scope_icon_widget = scope_icon
        tab.container_widget = tab_box
        self.update_editor_tab_label(tab)
        self.editor_tabs_bar.append(tab_box)

        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self.on_editor_tab_drag_prepare, tab.key)
        drag_source.connect("drag-begin", self.on_editor_tab_drag_begin, tab.key, tab_box)
        drag_source.connect("drag-end", self.on_editor_tab_drag_end, tab.key, tab_box)
        tab_box.add_controller(drag_source)

    def update_editor_tab_label(self, tab: NoteEditorTab) -> None:
        if tab.label_widget is None:
            return
        title = tab.title.strip() or self.translate("notes_new_tab")
        tab.label_widget.set_label(f"{title}{' •' if tab.dirty else ''}")
        if tab.container_widget is not None:
            is_server_note = tab.server_id is not None
            if hasattr(tab.container_widget, "set_tooltip_text"):
                tab.container_widget.set_tooltip_text(
                    self.note_tab_tooltip(tab, is_server_note)
                )
            if tab.key == self.active_editor_tab_key:
                tab.container_widget.add_css_class("active")
            else:
                tab.container_widget.remove_css_class("active")
        if tab.scope_icon_widget is not None:
            tab.scope_icon_widget.set_from_icon_name(
                "network-server-symbolic" if tab.server_id else "avatar-default-symbolic"
            )

    def note_tab_tooltip(self, tab: NoteEditorTab, is_server_note: bool) -> str:
        title = tab.title.strip() or self.translate("notes_new_tab")
        if not is_server_note:
            return self.translate("notes_tab_personal_tooltip").format(title=title)
        server = next(
            (
                item for item in getattr(self.store.data, "servers", ())
                if item.id == tab.server_id
            ),
            None,
        )
        server_name = server.name if server else self.translate("notes_unknown_server")
        return self.translate("notes_tab_server_tooltip").format(
            server=server_name, title=title,
        )

    def on_editor_tab_drag_prepare(
        self, _source: Gtk.DragSource, _x: float, _y: float, key: str
    ) -> Gdk.ContentProvider | None:
        if key not in self.editor_tabs:
            return None
        return Gdk.ContentProvider.new_for_value(key)

    def on_editor_tab_drag_begin(
        self, source: Gtk.DragSource, _drag: Gdk.Drag, key: str, tab_box: Gtk.Widget
    ) -> None:
        self.activate_editor_tab(key)
        self.editor_tab_drag_key = key
        tab_box.add_css_class("dragging")
        source.set_icon(
            Gtk.WidgetPaintable.new(tab_box),
            tab_box.get_allocated_width() // 2,
            tab_box.get_allocated_height() // 2,
        )

    def on_editor_tab_drag_end(
        self, _source: Gtk.DragSource, _drag: Gdk.Drag, _delete_data: bool,
        _key: str, tab_box: Gtk.Widget,
    ) -> None:
        tab_box.remove_css_class("dragging")
        self.editor_tab_drag_key = None

    def on_editor_tab_drop_motion(
        self, target: Gtk.DropTarget, x: float, _y: float
    ) -> Gdk.DragAction:
        self.reorder_editor_tab_at_bar_x(target, x)
        return Gdk.DragAction.MOVE

    def on_editor_tab_drop(
        self, target: Gtk.DropTarget, key: str, x: float, _y: float
    ) -> bool:
        self.reorder_editor_tab_at_bar_x(target, x, key)
        if key in self.editor_tabs:
            self.activate_editor_tab(key)
        return True

    def reorder_editor_tab_at_bar_x(
        self, target: Gtk.DropTarget, pointer_x: float, dragged_key: str | None = None
    ) -> None:
        dragged_key = dragged_key or getattr(self, "editor_tab_drag_key", None) or target.get_value()
        if not isinstance(dragged_key, str):
            return
        dragged = self.editor_tabs.get(dragged_key)
        if dragged is None or dragged.container_widget is None:
            return
        ordered = [
            tab for tab in self.editor_tabs.values()
            if tab.container_widget is not None
        ]
        if len(ordered) <= 1:
            return
        try:
            dragged_index = ordered.index(dragged)
        except ValueError:
            return

        previous_sibling = dragged.container_widget.get_prev_sibling()
        for index, tab in enumerate(ordered):
            if tab.key == dragged_key:
                continue
            widget = tab.container_widget
            width = widget.get_allocated_width()
            ok, start = widget.compute_point(
                self.editor_tabs_bar, Graphene.Point().init(0, 0)
            )
            if not ok or pointer_x < start.x or pointer_x > start.x + width:
                continue
            if index < dragged_index:
                previous_sibling = (
                    widget.get_prev_sibling()
                    if pointer_x < start.x + width * 0.8 else widget
                )
            else:
                previous_sibling = (
                    widget if pointer_x > start.x + width * 0.2
                    else widget.get_prev_sibling()
                )
            break

        if dragged.container_widget.get_prev_sibling() is previous_sibling:
            return
        self.editor_tabs_bar.reorder_child_after(
            dragged.container_widget, previous_sibling
        )
        self.sync_editor_tab_order()

    def sync_editor_tab_order(self) -> None:
        ordered: dict[str, NoteEditorTab] = {}
        child = self.editor_tabs_bar.get_first_child()
        while child is not None:
            tab = next(
                (item for item in self.editor_tabs.values() if item.container_widget is child),
                None,
            )
            if tab is not None:
                ordered[tab.key] = tab
            child = child.get_next_sibling()
        ordered.update(
            (key, tab) for key, tab in self.editor_tabs.items() if key not in ordered
        )
        self.editor_tabs = ordered

    def capture_active_editor_tab(self) -> None:
        key = getattr(self, "active_editor_tab_key", None)
        if key is None or key not in self.editor_tabs:
            return
        tab = self.editor_tabs[key]
        tab.note_id = self.current_note_id
        tab.content = self.editor_content()
        tab.dirty = self.editor_dirty
        tab.status = self.status_label.get_label()
        self.update_editor_tab_label(tab)

    def activate_editor_tab(self, key: str, save_previous: bool = True) -> None:
        tab = self.editor_tabs.get(key)
        if tab is None:
            return
        target_mode = "server" if tab.server_id else "personal"
        if (
            self.scope_mode != target_mode
            or self.server_filter_id != (tab.server_id if target_mode == "server" else None)
        ):
            if not self.set_notes_scope(target_mode, tab.server_id):
                return
            if self.active_editor_tab_key == key:
                return
        if key == getattr(self, "active_editor_tab_key", None):
            for current_tab in self.editor_tabs.values():
                self.update_editor_tab_label(current_tab)
            self.detail_stack.set_visible_child_name("editor")
            return
        if self.active_editor_tab_key is not None:
            if (
                save_previous
                and self.editor_dirty
                and self.editor_content().strip()
            ):
                if not self.save_editor():
                    for current_tab in self.editor_tabs.values():
                        self.update_editor_tab_label(current_tab)
                    return
            self.cancel_autosave()
            self.capture_active_editor_tab()
        self.active_editor_tab_key = key
        for current_tab in self.editor_tabs.values():
            self.update_editor_tab_label(current_tab)
        note = self.find_note(tab.note_id) if tab.note_id else None
        if note is not None and not tab.dirty:
            tab.title = note.title
            tab.category = note.category
            tab.server_id = note.server_id
            tab.content = note.content
            tab.status = self.translate("notes_saved")
        self.loading_editor = True
        try:
            self.current_note_id = tab.note_id
            self.selected_note_id = tab.note_id
            self.editor_dirty = tab.dirty
            self.text_view.get_buffer().set_text(tab.content)
            self.modified_label.set_label(
                self.translate("notes_modified").format(
                    date=format_note_timestamp(note.modified_at)
                ) if note else ""
            )
            self.status_label.set_label(tab.status)
            self.set_editor_enabled(True)
            self.detail_stack.set_visible_child_name("editor")
        finally:
            self.loading_editor = False
        self.capture_active_editor_tab()
        self.refresh_list(tab.note_id)
        if tab.note_id is None:
            self.loading_note_list = True
            try:
                self.notes_list.unselect_all()
            finally:
                self.loading_note_list = False
        if self.editor_dirty and self.editor_content().strip():
            self.schedule_autosave()

    def close_editor_tab(self, key: str) -> None:
        tab = self.editor_tabs.get(key)
        if tab is None:
            return
        if key == getattr(self, "active_editor_tab_key", None):
            self.cancel_autosave()
            self.capture_active_editor_tab()
        if tab.dirty:
            dialog = Gtk.AlertDialog(message=self.translate("notes_close_unsaved_message"))
            dialog.set_buttons([
                self.translate("notes_save_and_close"),
                self.translate("notes_close_without_saving"),
                self.translate("notes_keep_editing"),
            ])
            dialog.set_cancel_button(2)
            dialog.set_default_button(2)
            dialog.choose(self.window, None, self.on_close_editor_tab_response, key)
            return
        self.remove_editor_tab(key)

    def close_active_editor_tab(self) -> None:
        if self.active_editor_tab_key is not None:
            self.close_editor_tab(self.active_editor_tab_key)

    def on_close_editor_tab_response(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, key: str) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 0:
            self.save_editor_tab_and_close(key)
        elif response == 1:
            self.remove_editor_tab(key)

    def save_editor_tab_and_close(self, key: str) -> None:
        tab = self.editor_tabs.get(key)
        if tab is None:
            return
        if key == self.active_editor_tab_key:
            self.capture_active_editor_tab()
        if not tab.content.strip():
            # Empty drafts are intentionally not persisted. Emptying an existing
            # note must not erase its previous saved content.
            self.remove_editor_tab(key)
            return
        try:
            if tab.note_id is None:
                note = self.store.add_note(
                    tab.title, tab.content, tab.category, tab.server_id
                )
                tab.note_id = note.id
            else:
                self.store.update_note(
                    tab.note_id, tab.title, tab.content, tab.category, tab.server_id
                )
                note = self.find_note(tab.note_id)
            if note is None:
                raise NoteError("The note no longer exists.")
        except (OSError, NoteError, RuntimeError, ValueError):
            self.show_error(self.translate("notes_save_failed_detail"))
            return
        tab.dirty = False
        tab.status = self.translate("notes_saved")
        self.selected_note_id = note.id
        self.update_editor_tab_label(tab)
        self.refresh_list(note.id)
        if key == self.active_editor_tab_key:
            self.current_note_id = note.id
            self.editor_dirty = False
        self.remove_editor_tab(key)

    def remove_editor_tab(self, key: str) -> None:
        tab = self.editor_tabs.pop(key, None)
        if tab is None:
            return
        if getattr(self, "selected_draft_key", None) == key:
            self.selected_draft_key = None
        self.close_note_tab_context_menu()
        was_active = key == self.active_editor_tab_key
        if was_active:
            self.cancel_autosave()
            self.active_editor_tab_key = None
            self.current_note_id = None
            self.editor_dirty = False
        if (
            tab.container_widget is not None
            and tab.container_widget.get_parent() is self.editor_tabs_bar
        ):
            self.editor_tabs_bar.remove(tab.container_widget)
        if not was_active:
            self.refresh_list()
            return
        next_tab = next(reversed(self.editor_tabs.values()), None)
        if next_tab is not None:
            self.activate_editor_tab(next_tab.key, save_previous=False)
        else:
            self.clear_editor()
            if not self.selected_note_id:
                self.show_empty_state()
            else:
                self.show_idle_workspace()
        self.refresh_list()

    def clear_editor(self) -> None:
        if not hasattr(self, "text_view"):
            return
        self.cancel_autosave()
        self.loading_editor = True
        try:
            self.editor_dirty = False
            self.text_view.get_buffer().set_text("")
            self.modified_label.set_label("")
            self.status_label.set_label(self.translate("notes_select_or_create"))
            self.set_editor_enabled(False)
            self.show_idle_workspace()
        finally:
            self.loading_editor = False

    def set_editor_enabled(self, enabled: bool) -> None:
        writable = enabled and not self.store.read_only and not self.store.encryption_locked
        self.text_view.set_sensitive(enabled)
        self.text_view.set_editable(writable)
        self.text_view.set_cursor_visible(writable)
        self.save_button.set_sensitive(writable)
        self.delete_button.set_sensitive(writable and self.current_note_id is not None)

    def create_note(self) -> None:
        if not self.ensure_writable():
            return
        if getattr(self, "scope_mode", "personal") == "server" and self.server_filter_id is None:
            self.show_error(self.translate("notes_choose_server_empty"))
            return
        self.create_editor_tab()
        self.text_view.grab_focus()

    def on_editor_changed(self, *_args) -> None:
        if self.loading_editor:
            return
        self.editor_dirty = True
        if not self.editor_content().strip():
            self.cancel_autosave()
            self.status_label.set_label(self.translate("notes_empty_not_saved"))
            self.capture_active_editor_tab()
            return
        self.schedule_autosave()
        self.capture_active_editor_tab()

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

    def save_editor(self, *, refresh: bool = True) -> bool:
        self.cancel_autosave()
        if not self.editor_dirty and self.current_note_id is not None:
            self.status_label.set_label(self.translate("notes_saved"))
            return True
        content = self.editor_content()
        tab = self.editor_tabs.get(self.active_editor_tab_key)
        if tab is None:
            return False
        if not content.strip():
            self.status_label.set_label(self.translate("notes_empty_not_saved"))
            return True
        try:
            if self.current_note_id is None:
                note = self.store.add_note(
                    tab.title, content, tab.category, tab.server_id
                )
                self.current_note_id = note.id
            else:
                self.store.update_note(
                    self.current_note_id, tab.title, content,
                    tab.category, tab.server_id,
                )
                note = self.find_note(self.current_note_id)
            self.status_label.set_label(self.translate("notes_saved"))
            self.editor_dirty = False
            self.selected_note_id = self.current_note_id
            if note is not None:
                tab.title = note.title
            self.capture_active_editor_tab()
            if note is not None:
                self.modified_label.set_label(
                    self.translate("notes_modified").format(
                        date=format_note_timestamp(note.modified_at)
                    )
                )
            if refresh:
                self.refresh_list(self.current_note_id)
            self.set_editor_enabled(True)
            return True
        except (OSError, NoteError, RuntimeError, ValueError):
            self.status_label.set_label(self.translate("notes_save_failed"))
            self.show_error(self.translate("notes_save_failed_detail"))
            return False

    def on_close_request(self, _window: Gtk.Window) -> bool:
        self.close_note_context_menu()
        self.close_category_context_menu()
        self.close_note_tab_context_menu()
        if not self.save_active_editor_if_valid():
            self.window.present()
            return True
        self.cancel_autosave()
        self.capture_active_editor_tab()
        self.window.set_visible(False)
        return True

    def confirm_delete_note(self, note_id: str | None = None) -> None:
        if not self.save_active_editor_if_valid():
            return
        note_id = note_id or self.current_note_id or self.selected_note_id
        if not note_id or not self.ensure_writable():
            return
        note = self.find_note(note_id)
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
        for tab in tuple(self.editor_tabs.values()):
            if tab.note_id == note_id:
                self.remove_editor_tab(tab.key)
        self.selected_note_id = None
        self.refresh_list()

    def prompt_category_edit(
        self, mode: str, original: str | None = None,
        server_id: str | None = None,
    ) -> None:
        if mode not in ("add", "rename", "duplicate"):
            return
        if mode != "add" and not self.store.has_note_category(original, server_id):
            return
        if not self.ensure_writable() or not self.save_active_editor_if_valid():
            return
        title_key = {
            "add": "notes_category_add",
            "rename": "notes_category_rename",
            "duplicate": "notes_category_duplicate",
        }[mode]
        dialog = Gtk.Dialog(
            title=self.translate(title_key), transient_for=self.window, modal=True
        )
        dialog.set_default_size(360, -1)
        dialog.add_button(self.translate("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.translate("save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        for side in ("top", "bottom", "start", "end"):
            getattr(content, f"set_margin_{side}")(12)
        entry = Gtk.Entry()
        entry.set_placeholder_text(self.translate("notes_category_name"))
        if mode == "rename":
            entry.set_text(original)
        elif mode == "duplicate":
            entry.set_text(f"{original} {self.translate('snippet_copy_suffix')}")
        entry.set_activates_default(True)
        content.append(entry)
        dialog.connect(
            "response", self.on_category_edit_response,
            entry, mode, original, server_id,
        )
        dialog.present()
        entry.grab_focus()
        entry.set_position(-1)

    def on_category_edit_response(
        self, dialog: Gtk.Dialog, response: int, entry: Gtk.Entry,
        mode: str, original: str | None, server_id: str | None = None,
    ) -> None:
        name = entry.get_text()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not self.ensure_writable() or not self.save_active_editor_if_valid():
            return
        if mode != "add" and not self.store.has_note_category(original, server_id):
            return
        try:
            if mode == "add":
                self.store.add_note_category(name, server_id)
            elif mode == "rename":
                self.store.rename_note_category(original, name, server_id)
            elif mode == "duplicate":
                self.store.duplicate_note_category(original, name, server_id)
            else:
                return
        except (NoteError, OSError, RuntimeError) as exc:
            self.show_error(
                self.translate(str(exc)) if isinstance(exc, NoteError)
                else self.translate("notes_save_failed_detail")
            )
            return
        self.sync_open_note_categories()
        self.refresh_current_editor_metadata()
        self.refresh_list()

    def sync_open_note_categories(self) -> None:
        for tab in self.editor_tabs.values():
            if tab.note_id:
                note = self.find_note(tab.note_id)
                if note is not None:
                    tab.category = note.category

    def refresh_current_editor_metadata(self) -> None:
        note = self.find_note(self.current_note_id) if self.current_note_id else None
        if note:
            self.modified_label.set_label(
                self.translate("notes_modified").format(
                    date=format_note_timestamp(note.modified_at)
                )
            )

    def confirm_delete_category(
        self, name: str, server_id: str | None = None,
    ) -> None:
        if not self.store.has_note_category(name, server_id):
            return
        if not self.ensure_writable() or not self.save_active_editor_if_valid():
            return
        count = sum(
            note.category == name and note.server_id == (server_id or None)
            for note in self.store.data.notes
        )
        dialog = Gtk.AlertDialog(
            message=self.translate("notes_category_delete_confirm").format(name=name, count=count),
        )
        dialog.set_buttons([self.translate("cancel"), self.translate("notes_category_delete")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(
            self.window, None, self.on_delete_category_response, name, server_id,
        )

    def on_delete_category_response(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult,
        name: str, server_id: str | None = None,
    ) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        if not self.ensure_writable():
            return
        try:
            self.store.delete_note_category(name, server_id)
        except (NoteError, OSError, RuntimeError) as exc:
            self.show_error(
                self.translate(str(exc)) if isinstance(exc, NoteError)
                else self.translate("notes_save_failed_detail")
            )
            return
        self.sync_open_note_categories()
        self.refresh_current_editor_metadata()
        self.refresh_list()

    def choose_export_protection(self) -> None:
        if not self.save_active_editor_if_valid():
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
        if not self.save_active_editor_if_valid():
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
        categories = normalized_note_categories(
            [
                NoteCategory(category.name, None)
                if category.server_id and category.server_id not in server_ids
                else category
                for category in categories
            ],
            notes,
        )
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
        self.scope_mode = "personal"
        self.server_filter_id = None
        self.selected_note_id = None
        for tab in tuple(self.editor_tabs.values()):
            if tab.note_id is not None:
                self.remove_editor_tab(tab.key)
        self.set_notes_scope("personal")
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
        self.close_note_context_menu()
        self.close_category_context_menu()
        self.close_note_tab_context_menu()
        if self.window is not None:
            self.window.destroy()

    def prepare_shutdown(self) -> bool:
        if self.window is None:
            return True
        if self.editor_dirty:
            self.cancel_autosave()
            if self.editor_content().strip():
                if not self.save_editor():
                    self.window.present()
                    return False
        for tab in tuple(self.editor_tabs.values()):
            if tab.dirty and tab.key != self.active_editor_tab_key:
                if tab.content.strip():
                    self.save_editor_tab_and_close(tab.key)
                    if tab.key in self.editor_tabs:
                        self.window.present()
                        return False
                else:
                    self.remove_editor_tab(tab.key)
            elif tab.dirty and not tab.content.strip():
                self.remove_editor_tab(tab.key)
        return True
