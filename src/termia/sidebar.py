# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GObject, Graphene, Gtk, Pango

from .connection_utils import (
    find_group,
    find_local_terminal_profile,
    find_server,
    find_workspace,
    group_descendant_ids,
    group_matches_query,
    unique_local_terminal_clone_name,
    unique_server_clone_name,
    unique_workspace_clone_name,
)
from .dialog_window import DialogWindow
from .models import Group, LocalTerminalProfile, Server, Workspace
from .sidebar_projection import SidebarRow as RowObject
from .sidebar_projection import build_sidebar_projection
from .workspace_layout import (
    MAX_WORKSPACE_PANES,
    capture_workspace_tabs,
    workspace_pane_count,
    workspace_tab_layouts,
    workspace_total_pane_count,
)

GROUP_START_CONFIRMATION_THRESHOLD = 10
SERVER_GROUP_DND_MIME_TYPE = "application/x-termia-server-id"


def _clear_initial_menu_selection(widget: Gtk.Widget) -> bool:
    """Clear the initial native menu highlight once, preserving later navigation."""
    if widget.get_css_name() == "modelbutton":
        widget.unset_state_flags(Gtk.StateFlags.SELECTED)
        return GLib.SOURCE_REMOVE
    child = widget.get_first_child()
    while child is not None:
        if child.get_css_name() == "modelbutton":
            child.unset_state_flags(Gtk.StateFlags.SELECTED)
            return GLib.SOURCE_REMOVE
        _clear_initial_menu_selection(child)
        child = child.get_next_sibling()
    return GLib.SOURCE_REMOVE


class SidebarTreeNode(GObject.Object):
    """A projected row with stable identity and native GTK tree children."""

    def __init__(self, row: RowObject, icon: str, *, expanded_key: str | None = None):
        super().__init__()
        self.row = row
        self.icon = icon
        self.expanded_key = expanded_key
        self.children = Gio.ListStore.new(SidebarTreeNode)


class SidebarMixin:
    def on_toggle_sidebar(self, _button: Gtk.Button) -> None:
        self.set_sidebar_visible(not self.sidebar_visible)

    def set_sidebar_visible(self, visible: bool) -> None:
        if visible == self.sidebar_visible:
            return
        if visible:
            self.sidebar.set_visible(True)
            self.body.set_position(self.sidebar_width)
            self.sidebar_visible = True
            self.toggle_sidebar_button.set_icon_name("sidebar-hide-symbolic")
        else:
            self.sidebar_width = max(self.body.get_position(), 180)
            self.sidebar.set_visible(False)
            self.body.set_position(0)
            self.sidebar_visible = False
            self.toggle_sidebar_button.set_icon_name("sidebar-show-symbolic")

    def focus_server_filter(self) -> bool:
        self.set_sidebar_visible(True)
        self.search_entry.grab_focus()
        self.search_entry.select_region(0, -1)
        return True

    def sidebar_navigation_has_focus(self) -> bool:
        focused = self.get_focus()
        if focused is None:
            return False
        return (
            focused is self.search_entry
            or focused.is_ancestor(self.search_entry)
            or focused.is_ancestor(self.server_list)
        )

    def on_server_context_connect(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = find_server(self.store.data.servers, server_id)
        if server:
            self.open_terminal_tab(server)

    def on_server_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        server = find_server(self.store.data.servers, server_id)
        if server:
            self.show_server_dialog(server)

    def on_server_context_delete(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        server = find_server(self.store.data.servers, server_id)
        if server:
            self.store.delete_server(server_id)
            self.selected = None
            self.toast_label.set_label(f"Servidor eliminado: {server.name}")
            self.refresh_list()
            self.render_detail()

    def on_server_context_clone(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        server = find_server(self.store.data.servers, server_id)
        if server is None:
            return
        clone = self.store.add_server(
            unique_server_clone_name(self.store.data.servers, server.name),
            server.host,
            server.user,
            server.port,
            server.group_id,
            server.favorite,
            server.password,
            server.public_key,
            command_on_start=server.command_on_start,
        )
        self.selected = RowObject("server", clone.id, clone.name)
        self.toast_label.set_label(f"Conexión clonada: {clone.name}")
        self.refresh_list()
        self.render_detail()

    def on_server_context_toggle_favorite(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        server = find_server(self.store.data.servers, server_id)
        if server is None:
            return
        new_favorite_state = not server.favorite
        self.store.update_server_favorite(server_id, new_favorite_state)
        self.selected = RowObject("server", server.id, server.name, self.get_server_connection_text(server))
        if new_favorite_state:
            self.toast_label.set_label(f"Favorito añadido: {server.name}")
        else:
            self.toast_label.set_label(f"Favorito eliminado: {server.name}")
        self.refresh_list()
        self.render_detail()

    def on_server_context_send_files(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        server = find_server(self.store.data.servers, server_id)
        if server is not None:
            self.on_send_files_to_server(popover, None, server)

    def on_server_context_sftp(self, popover, server_id):
        server = find_server(self.store.data.servers, server_id)
        if server is not None and self.sftp_tool is not None:
            self.sftp_tool.browse(popover, None, server)

    def on_group_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        group = find_group(self.store.data.groups, group_id)
        if group:
            self.show_group_dialog(group)

    def on_group_context_add_subgroup(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        group = find_group(self.store.data.groups, group_id)
        if group:
            self.show_group_dialog(parent_group_id=group.id)

    def on_group_context_delete(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        self.request_delete_group(group_id)

    def group_servers(self, group_id: str) -> list[Server]:
        group_ids = group_descendant_ids(self.store.data.groups, group_id) | {group_id}
        return sorted(
            [server for server in self.store.data.servers if server.group_id in group_ids],
            key=lambda item: (item.name.lower(), item.host.lower(), item.user.lower(), item.port),
        )

    def on_group_context_start(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        group = find_group(self.store.data.groups, group_id)
        if group is None:
            return
        servers = self.group_servers(group.id)
        if not self.can_open_terminal_tabs(len(servers)):
            return
        if len(servers) > GROUP_START_CONFIRMATION_THRESHOLD:
            self.request_start_group_confirmation(group, servers)
            return
        self.start_group_servers(servers)

    def start_group_servers(self, servers: list[Server]) -> None:
        if not self.can_open_terminal_tabs(len(servers)):
            return
        for server in servers:
            self.open_terminal_tab(server)

    def request_start_group_confirmation(self, group: Group, servers: list[Server]) -> None:
        dialog = Gtk.AlertDialog(
            message=self.t("start_group_confirm"),
            detail=self.t("start_group_confirm_detail").format(
                group=group.name,
                count=len(servers),
                threshold=GROUP_START_CONFIRMATION_THRESHOLD,
            ),
        )
        dialog.set_buttons([self.t("cancel"), self.t("start_group")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_start_group_confirmed, (dialog, servers))

    def on_start_group_confirmed(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, data: tuple[Gtk.AlertDialog, list[Server]]
    ) -> None:
        _dialog, servers = data
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        self.start_group_servers(servers)

    def request_delete_group(self, group_id: str) -> None:
        if not self.ensure_writable():
            return
        group = find_group(self.store.data.groups, group_id)
        if group is None:
            return
        dialog = Gtk.AlertDialog(
            message=self.t("delete_group_confirm"),
            detail=self.t("delete_group_confirm_detail").format(name=group.name),
        )
        dialog.set_buttons([self.t("cancel"), self.t("delete_group")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_delete_group_confirmed, (dialog, group_id, group.name))

    def on_delete_group_confirmed(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, data: tuple[Gtk.AlertDialog, str, str]
    ) -> None:
        _dialog, group_id, group_name = data
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        if not self.ensure_writable():
            return
        self.store.delete_group(group_id)
        self.selected = None
        self.toast_label.set_label(self.t("group_deleted").format(name=group_name))
        self.refresh_list()
        self.render_detail()

    def create_sidebar_tree(self) -> Gtk.ListView:
        self.sidebar_drag = None
        self.sidebar_tree_selection = Gtk.SingleSelection()
        self.sidebar_tree_selection.set_autoselect(False)
        self.sidebar_tree_selection.set_can_unselect(True)
        self.sidebar_tree_selection.connect("notify::selected-item", self.on_sidebar_tree_selected)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_sidebar_tree_item)
        factory.connect("bind", self.bind_sidebar_tree_item)
        factory.connect("unbind", self.unbind_sidebar_tree_item)
        view = Gtk.ListView.new(self.sidebar_tree_selection, factory)
        view.add_css_class("termia-connections-tree")
        view.connect("activate", self.on_sidebar_tree_activated)
        return view

    def set_all_groups_expanded(self, expanded: bool) -> None:
        def remember(nodes):
            for node in nodes:
                if node.expanded_key is not None:
                    self.group_expanded_state[node.expanded_key] = expanded
                remember(node.children)
        remember(self.sidebar_tree_root)
        self.refresh_list()

    def get_group_expanded(self, group_id: str, query: str) -> bool:
        if query:
            return True
        if group_id in {"__recent__", "__favorites__", "__local_terminals__", "__workspaces__"}:
            return self.group_expanded_state.get(group_id, True)
        return self.group_expanded_state.get(group_id, not self.collapse_groups_on_startup)

    def refresh_list(self) -> None:
        if not hasattr(self, "server_list"):
            return
        query = self.search_entry.get_text().lower().strip()
        self.sidebar_query = query
        self.close_active_context_menu()
        self.sidebar_model_token = object()
        self.tree_widgets = {}
        self.selected_tree_widget = None
        projection = build_sidebar_projection(
            self.store.data.groups, self.store.data.servers,
            self.store.data.local_terminals, self.store.data.workspaces,
            self.store.recent_server_ids(), query,
        )
        root = Gio.ListStore.new(SidebarTreeNode)

        def server_node(server, kind="server", icon="network-server-symbolic"):
            return SidebarTreeNode(self.build_server_row_object(server, kind), icon)

        def section(key, title, icon, nodes):
            node = SidebarTreeNode(RowObject("section", key, f"{title} ({len(nodes)})"),
                                   icon, expanded_key=key)
            for child in nodes:
                node.children.append(child)
            root.append(node)

        if projection.workspaces:
            section("__workspaces__", self.t("workspaces"), "view-grid-symbolic", [
                SidebarTreeNode(self.build_workspace_row_object(item), "view-grid-symbolic")
                for item in projection.workspaces])
        if projection.local_terminal_profiles:
            section("__local_terminals__", self.t("local_terminals"), "utilities-terminal-symbolic", [
                SidebarTreeNode(self.build_local_terminal_row_object(item), "utilities-terminal-symbolic")
                for item in projection.local_terminal_profiles])
        if projection.recent_servers:
            section("__recent__", self.t("recent"), "document-open-recent-symbolic", [
                server_node(item, "recent", "document-open-recent-symbolic")
                for item in projection.recent_servers])
        if projection.favorite_servers:
            section("__favorites__", self.t("favorites"), "starred-symbolic", [
                server_node(item, "favorite", "starred-symbolic")
                for item in projection.favorite_servers])

        def group_node(group):
            nodes = [
                node for child in sorted(projection.children_by_parent.get(group.id, []),
                                         key=lambda item: item.name.lower())
                if (node := group_node(child)) is not None
            ]
            servers = sorted(projection.servers_by_group.get(group.id, []),
                             key=lambda item: item.name.lower())
            if query and not group_matches_query(group, query) and not servers and not nodes:
                return None
            count = len(servers) + sum(node.server_count for node in nodes)
            node = SidebarTreeNode(RowObject("group", group.id, group.name, str(count)),
                                   "folder-symbolic", expanded_key=group.id)
            node.server_count = count
            for child in nodes:
                node.children.append(child)
            for server in servers:
                node.children.append(server_node(server))
            return node

        for group in projection.root_groups:
            node = group_node(group)
            if node is not None:
                root.append(node)
        section("__ungrouped__", self.t("no_group"), "folder-symbolic", [
            server_node(item) for item in sorted(projection.ungrouped_servers,
                                                key=lambda item: item.name.lower())])
        self.sidebar_tree_root = root
        model = Gtk.TreeListModel.new(
            root, False, False,
            lambda node: node.children if node.expanded_key is not None else None,
        )
        self.sidebar_tree_model = model
        self._sidebar_tree_wired_rows = set()
        self._sidebar_tree_loading = True
        try:
            position = 0
            while position < model.get_n_items():
                tree_row = model.get_row(position)
                node = tree_row.get_item()
                if node.expanded_key is not None:
                    tree_row.set_expanded(self.get_group_expanded(node.expanded_key, query))
                    self._sidebar_tree_wired_rows.add(tree_row)
                    tree_row.connect("notify::expanded", self.on_sidebar_tree_expanded)
                position += 1
            self.sidebar_tree_selection.set_model(model)
            self.sync_sidebar_tree_rows()
            selected = self.get_visible_tree_row_index(self.selected) if self.selected else None
            self.sidebar_tree_selection.set_selected(
                selected if selected is not None else Gtk.INVALID_LIST_POSITION)
            if selected is None:
                self.selected = None
            else:
                self.selected = model.get_row(selected).get_item().row
        finally:
            self._sidebar_tree_loading = False
        model.connect("items-changed", self.on_sidebar_tree_items_changed)
        root_groups = len([group for group in self.store.data.groups if group.parent_id is None])
        self.summary_label.set_label(self.t("summary").format(
            groups=root_groups, subgroups=len(self.store.data.groups) - root_groups,
            servers=len(self.store.data.servers)))
        self.render_detail()

    def sync_sidebar_tree_rows(self) -> None:
        self.visible_tree_rows = [
            self.sidebar_tree_model.get_row(i).get_item().row
            for i in range(self.sidebar_tree_model.get_n_items())
        ]

    def on_sidebar_tree_items_changed(self, model, _position, _removed, _added) -> None:
        GLib.idle_add(self.wire_sidebar_tree_rows, model)

    def wire_sidebar_tree_rows(self, model) -> bool:
        if model is not self.sidebar_tree_model:
            return GLib.SOURCE_REMOVE
        # Newly expanded children acquire rows only when their parent opens.
        index = 0
        live_rows = set()
        while index < model.get_n_items():
            row = model.get_row(index)
            live_rows.add(row)
            node = row.get_item()
            if node.expanded_key is not None and row not in self._sidebar_tree_wired_rows:
                self._sidebar_tree_wired_rows.add(row)
                row.set_expanded(self.get_group_expanded(
                    node.expanded_key, self.search_entry.get_text().strip()))
                row.connect("notify::expanded", self.on_sidebar_tree_expanded)
            index += 1
        self._sidebar_tree_wired_rows.intersection_update(live_rows)
        self.sync_sidebar_tree_rows()
        return GLib.SOURCE_REMOVE

    def on_sidebar_tree_expanded(self, tree_row, _param) -> None:
        if getattr(self, "_sidebar_tree_loading", False):
            return
        if self.search_entry.get_text().strip():
            if not tree_row.get_expanded():
                def expand():
                    if tree_row in self._sidebar_tree_wired_rows and self.search_entry.get_text().strip():
                        tree_row.set_expanded(True)
                    return GLib.SOURCE_REMOVE
                GLib.idle_add(expand)
            return
        model = self.sidebar_tree_model
        expanded = tree_row.get_expanded()
        def remember():
            if model is self.sidebar_tree_model and any(
                model.get_row(i) == tree_row for i in range(model.get_n_items())
            ):
                self.group_expanded_state[tree_row.get_item().expanded_key] = expanded
            return GLib.SOURCE_REMOVE
        GLib.idle_add(remember)

    def setup_sidebar_tree_item(self, _factory, item) -> None:
        item.set_child(Gtk.TreeExpander())
        item.set_focusable(False)

    def bind_sidebar_tree_item(self, _factory, item) -> None:
        tree_row = item.get_item()
        node = tree_row.get_item()
        row = node.row
        is_header = row.kind in {"group", "section"}
        item.set_selectable(not is_header)
        expander = item.get_child()
        expander.set_list_row(tree_row)
        expander.set_hide_expander(node.expanded_key is None)
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.add_css_class("termia-sidebar-object")
        content.set_halign(Gtk.Align.START)
        content.set_margin_end(6)
        content.append(Gtk.Image.new_from_icon_name(node.icon))
        title = row.title + (f" ({row.subtitle})" if row.kind == "group" else "")
        label = Gtk.Label(label=title, xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_hexpand(True)
        if node.expanded_key is not None:
            label.add_css_class("heading")
        content.append(label)
        content.set_tooltip_text(row.subtitle or row.title)
        content.sidebar_model_token = self.sidebar_model_token
        content.sidebar_row = row
        expander.set_child(content)
        if is_header:
            click = Gtk.GestureClick()
            click.set_button(1)
            click.connect("released", self.on_sidebar_tree_header_clicked, row, self.sidebar_model_token)
            content.add_controller(click)
        self.tree_widgets[(row.kind, row.item_id)] = content
        if row == self.selected:
            self.selected_tree_widget = content
        if row.kind != "section":
            click = Gtk.GestureClick()
            click.set_button(3)
            click.connect("pressed", self.on_sidebar_tree_context_pressed, row, content)
            content.add_controller(click)
        if row.kind == "server":
            source = Gtk.DragSource.new()
            source.set_actions(Gdk.DragAction.MOVE)
            source.connect("prepare", self.on_server_drag_prepare, row.item_id)
            source.connect("drag-begin", self.on_server_drag_begin, row.item_id, content)
            source.connect("drag-end", self.on_server_drag_end, row.item_id, content)
            content.add_controller(source)
            content.add_css_class("termia-server-item")
        if row.kind == "group" or row.item_id == "__ungrouped__":
            content.add_css_class("termia-group-drop-target")
            self.add_server_group_drop_target(content, row.item_id if row.kind == "group" else None)

    def unbind_sidebar_tree_item(self, _factory, item) -> None:
        expander = item.get_child()
        content = expander.get_child()
        if content is not None:
            row = content.sidebar_row
            key = (row.kind, row.item_id)
            if self.tree_widgets.get(key) is content:
                self.tree_widgets.pop(key)
            if self.selected_tree_widget is content:
                self.selected_tree_widget = None
            content.sidebar_model_token = None
        expander.set_list_row(None)
        expander.set_child(None)

    def on_sidebar_tree_selected(self, selection, _param) -> None:
        if getattr(self, "_sidebar_tree_loading", False):
            return
        selected = selection.get_selected_item()
        self.selected = selected.get_item().row if selected else None
        row = self.selected
        self.selected_tree_widget = self.tree_widgets.get((row.kind, row.item_id)) if row else None
        def render():
            if self.selected is row:
                self.render_detail()
            return GLib.SOURCE_REMOVE
        GLib.idle_add(render)

    def on_sidebar_tree_header_clicked(self, _gesture, clicks, _x, _y, row, model_token) -> None:
        if clicks != 1 or model_token is not self.sidebar_model_token:
            return
        tree_row = self.get_group_expander(row.item_id)
        if tree_row is not None:
            self.cancel_sidebar_scroll_restore()
            tree_row.set_expanded(not tree_row.get_expanded())

    def on_sidebar_tree_activated(self, _view, position) -> None:
        row = self.sidebar_tree_model.get_row(position)
        if row is None:
            return
        if row.get_item().expanded_key is not None:
            return
        else:
            self.sidebar_tree_selection.set_selected(position)
            self.activate_selected_tree_row()

    def on_sidebar_tree_context_pressed(self, gesture, _count, x, y, row, content) -> None:
        root = self.get_child()
        valid, point = content.compute_point(root, Graphene.Point().init(x, y))
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        token = self.sidebar_model_token
        if not valid:
            return
        def open_menu():
            if self.sidebar_model_token is not token or not self.get_visible():
                return GLib.SOURCE_REMOVE
            index = self.get_visible_tree_row_index(row)
            if index is not None:
                if row.kind not in {"group", "section"}:
                    self.sidebar_tree_selection.set_selected(index)
                self.show_row_context_menu(row, root, point.x, point.y)
            return GLib.SOURCE_REMOVE
        GLib.idle_add(open_menu)

    def build_local_terminal_row_object(self, profile: LocalTerminalProfile) -> RowObject:
        title = profile.name or self.t("local_terminal")
        return RowObject("local_terminal", profile.id, title)

    def build_workspace_row_object(self, workspace: Workspace) -> RowObject:
        return RowObject("workspace", workspace.id, workspace.name)

    def workspace_description(self, workspace: Workspace) -> str:
        layouts = workspace_tab_layouts(workspace.tabs)
        return self.t("workspace_detail_info").format(
            tabs=len(layouts),
            panes=sum(workspace_pane_count(layout) for layout in layouts),
        )

    def build_server_row_object(self, server: Server, row_kind: str = "server") -> RowObject:
        return RowObject(row_kind, server.id, server.name, self.get_server_connection_text(server))

    def get_server_connection_text(self, server: Server) -> str:
        return f"{server.user}@{server.host}:{server.port}" if server.user else f"{server.host}:{server.port}"

    def on_server_drag_prepare(
        self, _source: Gtk.DragSource, _x: float, _y: float, server_id: str,
    ) -> Gdk.ContentProvider | None:
        if (
            self.store.read_only
            or self.store.encryption_locked
            or getattr(self, "sidebar_pending_group_drop", None) is not None
        ):
            return None
        if find_server(self.store.data.servers, server_id) is None:
            return None
        return Gdk.ContentProvider.new_for_bytes(
            SERVER_GROUP_DND_MIME_TYPE,
            GLib.Bytes.new(server_id.encode("utf-8")),
        )

    def on_server_drag_begin(
        self, source: Gtk.DragSource, _drag: Gdk.Drag, server_id: str, row: Gtk.Widget,
    ) -> None:
        self.sidebar_drag_server_id = server_id
        self.sidebar_drag = _drag
        row.add_css_class("dragging")
        source.set_icon(
            Gtk.WidgetPaintable.new(row),
            row.get_allocated_width() // 2,
            row.get_allocated_height() // 2,
        )

    def on_server_drag_end(
        self, _source: Gtk.DragSource, _drag: Gdk.Drag, _delete_data: bool,
        server_id: str, row: Gtk.Widget,
    ) -> None:
        if self.sidebar_drag_server_id == server_id:
            self.sidebar_drag_server_id = None
            self.sidebar_drag = None
        row.remove_css_class("dragging")

    def add_server_group_drop_target(self, label: Gtk.Widget, group_id: str | None) -> None:
        formats = Gdk.ContentFormats.new([SERVER_GROUP_DND_MIME_TYPE])
        target = Gtk.DropTargetAsync.new(formats, Gdk.DragAction.MOVE)
        target.connect("accept", self.on_server_group_drop_accept)
        target.connect("drag-motion", self.on_server_group_drop_motion, group_id, label)
        target.connect("drag-leave", self.on_server_group_drop_leave, label)
        target.connect("drop", self.on_server_group_drop, group_id, label)
        label.add_controller(target)

    def on_server_group_drop_accept(
        self, _target: Gtk.DropTargetAsync, drop: Gdk.Drop,
    ) -> bool:
        formats = drop.get_formats()
        return (
            self.sidebar_drag_server_id is not None
            and (not hasattr(self, "sidebar_tree_selection") or (
                self.sidebar_drag is not None and drop.get_drag() == self.sidebar_drag))
            and formats is not None
            and formats.contain_mime_type(SERVER_GROUP_DND_MIME_TYPE)
        )

    def on_server_group_drop_motion(
        self, _target: Gtk.DropTargetAsync, _drop: Gdk.Drop, _x: float, _y: float,
        group_id: str | None, label: Gtk.Widget,
    ) -> Gdk.DragAction:
        server_id = self.sidebar_drag_server_id
        if hasattr(self, "sidebar_tree_selection") and label.sidebar_model_token is not self.sidebar_model_token:
            return Gdk.DragAction(0)
        if server_id is not None and self.store.can_move_server_to_group(server_id, group_id):
            label.add_css_class("drop-target")
            return Gdk.DragAction.MOVE
        label.remove_css_class("drop-target")
        return Gdk.DragAction(0)

    def on_server_group_drop_leave(
        self, _target: Gtk.DropTargetAsync, _drop: Gdk.Drop, label: Gtk.Widget,
    ) -> None:
        label.remove_css_class("drop-target")

    def on_server_group_drop(
        self, _target: Gtk.DropTargetAsync, drop: Gdk.Drop, _x: float, _y: float,
        group_id: str | None, label: Gtk.Widget,
    ) -> bool:
        label.remove_css_class("drop-target")
        if hasattr(self, "sidebar_tree_selection") and label.sidebar_model_token is not self.sidebar_model_token:
            return False
        server_id = self.sidebar_drag_server_id
        if server_id is None or not self.on_server_group_drop_accept(_target, drop):
            return False
        if not self.store.can_move_server_to_group(server_id, group_id):
            return False
        drop_token = object()
        self.sidebar_pending_group_drop = drop_token
        drop.read_async(
            [SERVER_GROUP_DND_MIME_TYPE],
            GLib.PRIORITY_DEFAULT,
            None,
            self.on_server_group_drop_read,
            (drop, server_id, group_id, label, drop_token),
        )
        return True

    def on_server_group_drop_read(
        self, _source: Gdk.Drop, result: Gio.AsyncResult, user_data,
    ) -> None:
        drop, server_id, group_id, label, drop_token = user_data
        try:
            stream, mime_type = drop.read_finish(result)
        except GLib.Error:
            self.clear_pending_server_group_drop(drop_token)
            drop.finish(Gdk.DragAction(0))
            return
        if stream is None or mime_type != SERVER_GROUP_DND_MIME_TYPE:
            if stream is not None:
                stream.close_async(GLib.PRIORITY_DEFAULT, None, None)
            self.clear_pending_server_group_drop(drop_token)
            drop.finish(Gdk.DragAction(0))
            return
        stream.read_bytes_async(
            256,
            GLib.PRIORITY_DEFAULT,
            None,
            self.on_server_group_drop_bytes_read,
            (drop, server_id, group_id, label, drop_token),
        )

    def on_server_group_drop_bytes_read(
        self, stream: Gio.InputStream, result: Gio.AsyncResult, user_data,
    ) -> None:
        drop, expected_server_id, group_id, label, drop_token = user_data
        try:
            server_id = stream.read_bytes_finish(result).get_data().decode("utf-8")
        except (GLib.Error, UnicodeDecodeError):
            server_id = ""
        finally:
            stream.close_async(GLib.PRIORITY_DEFAULT, None, None)
        moved = (
            getattr(self, "sidebar_pending_group_drop", None) is drop_token
            and server_id == expected_server_id
            and self.apply_server_group_drop(server_id, group_id, label, require_active_drag=False)
        )
        self.clear_pending_server_group_drop(drop_token)
        drop.finish(Gdk.DragAction.MOVE if moved else Gdk.DragAction(0))

    def clear_pending_server_group_drop(self, drop_token: object) -> None:
        if getattr(self, "sidebar_pending_group_drop", None) is drop_token:
            self.sidebar_pending_group_drop = None

    def apply_server_group_drop(
        self, server_id: str, group_id: str | None, label: Gtk.Widget,
        *, require_active_drag: bool = True,
    ) -> bool:
        if getattr(self, "shutdown_in_progress", False):
            return False
        if hasattr(self, "sidebar_tree_selection") and label.sidebar_model_token is not self.sidebar_model_token:
            return False
        if require_active_drag and server_id != self.sidebar_drag_server_id:
            return False
        if not self.store.can_move_server_to_group(server_id, group_id):
            return False
        scroll_values = self.get_sidebar_scroll_values()
        if not self.store.move_server_to_group(server_id, group_id):
            return False
        self.sidebar_drag_server_id = None
        self.refresh_list()
        self.render_detail()
        self.preserve_sidebar_scroll(*scroll_values)
        return True

    def get_sidebar_scroll_values(self) -> tuple[float, float]:
        return (
            self.server_scroller.get_vadjustment().get_value(),
            self.server_scroller.get_hadjustment().get_value(),
        )

    def preserve_sidebar_scroll(
        self, vertical_value: float | None = None, horizontal_value: float | None = None
    ) -> None:
        vertical = self.server_scroller.get_vadjustment()
        horizontal = self.server_scroller.get_hadjustment()
        if vertical_value is None:
            vertical_value = vertical.get_value()
        if horizontal_value is None:
            horizontal_value = horizontal.get_value()
        if self.scroll_restore_id is not None:
            GLib.source_remove(self.scroll_restore_id)
        self.scroll_restore_id = GLib.idle_add(
            self.restore_sidebar_scroll, vertical, vertical_value, horizontal, horizontal_value
        )

    def cancel_sidebar_scroll_restore(self) -> None:
        if self.scroll_restore_id is not None:
            GLib.source_remove(self.scroll_restore_id)
            self.scroll_restore_id = None

    def restore_sidebar_scroll(
        self, vertical: Gtk.Adjustment, vertical_value: float,
        horizontal: Gtk.Adjustment, horizontal_value: float,
    ) -> bool:
        self.set_sidebar_scroll_value(vertical, vertical_value)
        self.set_sidebar_scroll_value(horizontal, horizontal_value)
        self.scroll_restore_id = GLib.timeout_add(
            50, self.finish_sidebar_scroll_restore, vertical, vertical_value, horizontal, horizontal_value
        )
        return GLib.SOURCE_REMOVE

    def finish_sidebar_scroll_restore(
        self, vertical: Gtk.Adjustment, vertical_value: float,
        horizontal: Gtk.Adjustment, horizontal_value: float,
    ) -> bool:
        self.set_sidebar_scroll_value(vertical, vertical_value)
        self.set_sidebar_scroll_value(horizontal, horizontal_value)
        self.scroll_restore_id = None
        return GLib.SOURCE_REMOVE

    def set_sidebar_scroll_value(self, adjustment: Gtk.Adjustment, value: float) -> None:
        maximum = max(adjustment.get_lower(), adjustment.get_upper() - adjustment.get_page_size())
        adjustment.set_value(min(max(value, adjustment.get_lower()), maximum))

    def focus_selected_tree_row(self) -> bool:
        index = self.sidebar_tree_selection.get_selected()
        if index != Gtk.INVALID_LIST_POSITION:
            self.focus_sidebar_tree_position(index)
        return GLib.SOURCE_REMOVE

    def focus_sidebar_tree_position(self, index: int) -> None:
        self.server_list.grab_focus()
        if hasattr(self.server_list, "scroll_to"):
            self.server_list.scroll_to(index, Gtk.ListScrollFlags.FOCUS, None)
        else:
            self.server_list.activate_action("list.scroll-to-item", GLib.Variant("u", index))
            self.server_list.grab_focus()

    def get_group_expander(self, group_id: str) -> Gtk.TreeListRow | None:
        model = self.sidebar_tree_model
        for index in range(model.get_n_items()):
            tree_row = model.get_row(index)
            if tree_row.get_item().expanded_key == group_id:
                return tree_row
        return None

    def get_visible_tree_row_index(self, row: RowObject) -> int | None:
        if hasattr(self, "sidebar_tree_model"):
            self.sync_sidebar_tree_rows()
        for index, visible_row in enumerate(getattr(self, "visible_tree_rows", [])):
            if visible_row.kind == row.kind and visible_row.item_id == row.item_id:
                return index
        return None

    def select_visible_tree_row(self, index: int) -> bool:
        self.sync_sidebar_tree_rows()
        rows = self.visible_tree_rows
        if not rows:
            return False
        index = max(0, min(index, len(rows) - 1))
        selectable = [i for i, row in enumerate(rows) if row.kind not in {"group", "section"}]
        if not selectable:
            return False
        index = next((i for i in selectable if i >= index), selectable[-1])
        self.cancel_sidebar_scroll_restore()
        self.sidebar_tree_selection.set_selected(index)
        self.focus_sidebar_tree_position(index)
        return True

    def move_visible_tree_selection(self, delta: int) -> bool:
        rows = getattr(self, "visible_tree_rows", [])
        selectable = [i for i, row in enumerate(rows) if row.kind not in {"group", "section"}]
        if not selectable:
            return False
        current_index = self.get_visible_tree_row_index(self.selected) if self.selected is not None else None
        if current_index is None:
            target_index = selectable[0] if delta >= 0 else selectable[-1]
        else:
            candidates = [i for i in selectable if i > current_index] if delta >= 0 else [
                i for i in selectable if i < current_index]
            target_index = (candidates[0] if delta >= 0 else candidates[-1]) if candidates else current_index
        return self.select_visible_tree_row(target_index)

    def activate_selected_tree_row(self) -> bool:
        if self.selected is None or self.get_visible_tree_row_index(self.selected) is None:
            first = next((i for i, row in enumerate(getattr(self, "visible_tree_rows", []))
                          if row.kind not in {"group", "section"}), None)
            if first is None or not self.select_visible_tree_row(first):
                return False
        if self.selected is None or self.get_visible_tree_row_index(self.selected) is None:
            return False
        if self.selected.kind == "local_terminal":
            profile = find_local_terminal_profile(self.store.data.local_terminals, self.selected.item_id)
            if profile is None:
                return False
            self.open_local_terminal_profile(profile)
            return True
        if self.selected.kind == "workspace":
            workspace = find_workspace(self.store.data.workspaces, self.selected.item_id)
            if workspace is None:
                return False
            self.open_workspace(workspace)
            return True
        if self.selected.kind in {"server", "favorite", "recent"}:
            server = find_server(self.store.data.servers, self.selected.item_id)
            if server is None:
                return False
            self.open_terminal_tab(server)
            return True
        if self.selected.kind in {"group", "section"}:
            expander = self.get_group_expander(self.selected.item_id)
            if expander is None:
                return False
            self.cancel_sidebar_scroll_restore()
            expander.set_expanded(not expander.get_expanded())
            GLib.idle_add(self.focus_selected_tree_row)
            return True
        return False

    def on_sidebar_navigation_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        relevant_mask = (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.ALT_MASK
            | Gdk.ModifierType.META_MASK
            | Gdk.ModifierType.SUPER_MASK
        )
        if state & relevant_mask:
            return False

        focused = self.get_focus() if hasattr(self, "sidebar_tree_selection") else None
        if hasattr(self, "sidebar_tree_selection") and not (
            focused is self.search_entry or (focused is not None and focused.is_ancestor(self.search_entry))
        ):
            # GTK owns keyboard navigation while focus is inside the native view.
            return False

        enter_keys = {Gdk.KEY_Return, Gdk.KEY_KP_Enter, getattr(Gdk, "KEY_ISO_Enter", Gdk.KEY_Return)}
        navigation_keys = {Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Home, Gdk.KEY_End, *enter_keys}
        query = self.search_entry.get_text().lower().strip()
        if keyval in navigation_keys and query != self.sidebar_query:
            # SearchEntry debounces search-changed; Enter must use current text.
            self.refresh_list()
        if keyval == Gdk.KEY_Up:
            return self.move_visible_tree_selection(-1)
        if keyval == Gdk.KEY_Down:
            return self.move_visible_tree_selection(1)
        if keyval == Gdk.KEY_Home:
            return self.select_visible_tree_row(0)
        if keyval == Gdk.KEY_End:
            return self.select_visible_tree_row(len(getattr(self, "visible_tree_rows", [])) - 1)
        if keyval in enter_keys:
            if query:
                first = next((i for i, row in enumerate(self.visible_tree_rows)
                              if row.kind in {"server", "favorite", "recent", "workspace", "local_terminal"}), None)
                if first is not None:
                    self.sidebar_tree_selection.set_selected(first)
            return self.activate_selected_tree_row()
        return False

    def close_active_context_menu(self) -> None:
        popover = self.active_context_popover
        if popover is None:
            return
        scroll_values = self.get_sidebar_scroll_values()
        self.active_context_popover = None
        popover.popdown()
        if (
            popover is not getattr(self, "_server_context_menu", None)
            and popover is not getattr(self, "_group_context_menu", None)
            and popover is not getattr(self, "_saved_context_menu", None)
            and popover.get_parent() is not None
        ):
            popover.unparent()
        self.preserve_sidebar_scroll(*scroll_values)

    def on_context_menu_closed(self, popover: Gtk.Popover) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        if self.active_context_popover is popover:
            self.active_context_popover = None
        target_attribute = None
        if popover is getattr(self, "_server_context_menu", None):
            target_attribute = "_server_context_menu_target"
        elif popover is getattr(self, "_group_context_menu", None):
            target_attribute = "_group_context_menu_target"
        elif popover is getattr(self, "_saved_context_menu", None):
            target_attribute = "_saved_context_menu_target"
        if target_attribute is not None:
            target = getattr(self, target_attribute)

            def clear_target() -> bool:
                if getattr(self, target_attribute) is target:
                    setattr(self, target_attribute, None)
                return GLib.SOURCE_REMOVE

            # Native entries close their popup before activating the action.
            GLib.idle_add(clear_target)
        elif popover.get_parent() is not None:
            popover.unparent()
        self.preserve_sidebar_scroll(*scroll_values)

    def show_server_context_menu(
        self, server_id: str, parent: Gtk.Widget, x: float, y: float,
    ) -> None:
        server = find_server(self.store.data.servers, server_id)
        if server is None or parent.get_root() is not self:
            return
        valid, point = parent.compute_point(self.get_child(), Graphene.Point().init(x, y))
        if not valid:
            return
        self.close_active_context_menu()
        popover = getattr(self, "_server_context_menu", None)
        if popover is None:
            popover = self.build_server_context_menu()
            self._server_context_menu = popover
        model = Gio.Menu()
        writable = not self.store.read_only and not self.store.encryption_locked
        for name, label, modifies in (
            ("favorite", "remove_favorite" if server.favorite else "add_favorite", True),
            ("connect", "connect", False),
            ("notes", "notes_view_server", False),
            ("edit", "edit_server", True),
            ("clone", "clone_connection", True),
            ("send-files", "send_files_to_server", False),
            ("sftp", "sftp_browse", False),
            ("delete", "delete_server", True),
        ):
            if name == "sftp" and self.sftp_tool is None:
                continue
            model.append(self.t(label), f"server-menu.{name}")
            self._server_context_actions[name].set_enabled(
                not self.store.encryption_locked and (not modifies or writable),
            )
        popover.set_menu_model(model)
        self._server_context_menu_target = (server_id,)
        rect = Gdk.Rectangle()
        rect.x, rect.y = int(point.x), int(point.y)
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        self.active_context_popover = popover
        popover.popup()
        GLib.idle_add(_clear_initial_menu_selection, popover)
        self.preserve_sidebar_scroll()

    def build_server_context_menu(self) -> Gtk.PopoverMenu:
        actions = Gio.SimpleActionGroup()
        self._server_context_actions = {}
        self._server_context_menu_target = None

        def activate_action(_action, _parameter, name) -> None:
            target = self._server_context_menu_target
            self._server_context_menu_target = None
            if target is not None:
                self.dispatch_server_context_action(name, target[0])

        for name in ("favorite", "connect", "notes", "edit", "clone", "send-files", "sftp", "delete"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", activate_action, name)
            actions.add_action(action)
            self._server_context_actions[name] = action
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(True)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.insert_action_group("server-menu", actions)
        popover.connect("closed", self.on_context_menu_closed)
        # Sidebar rows are rebuilt by favorite, clone and delete actions.
        popover.set_parent(self.get_child())
        self.connect("destroy", lambda *_args: self.dispose_server_context_menu())
        return popover

    def dispose_server_context_menu(self) -> None:
        popover = getattr(self, "_server_context_menu", None)
        self._server_context_menu_target = None
        if popover is not None:
            if self.active_context_popover is popover:
                self.active_context_popover = None
            popover.popdown()
            popover.insert_action_group("server-menu", None)
            if popover.get_parent() is not None:
                popover.unparent()
            self._server_context_menu = None
            self._server_context_actions = {}

    def dispatch_server_context_action(self, name: str, server_id: str) -> None:
        popover = self._server_context_menu
        self.close_active_context_menu()

        def dispatch_if_current() -> bool:
            if (
                not self.get_visible() or getattr(self, "shutdown_in_progress", False)
                or self._server_context_menu is not popover
                or self.store.encryption_locked
                or find_server(self.store.data.servers, server_id) is None
                or (name in {"favorite", "edit", "clone", "delete"} and self.store.read_only)
            ):
                return GLib.SOURCE_REMOVE
            callbacks = {
                "favorite": self.on_server_context_toggle_favorite,
                "connect": self.on_server_context_connect,
                "edit": self.on_server_context_edit,
                "clone": self.on_server_context_clone,
                "send-files": self.on_server_context_send_files,
                "delete": self.on_server_context_delete,
            }
            if name == "notes":
                self.notes_dialogs.show_for_server_after_popover(popover, server_id)
            elif name == "sftp":
                self.on_server_context_sftp(popover, server_id)
            elif name in callbacks:
                callbacks[name](None, popover, server_id)
            return GLib.SOURCE_REMOVE

        # Let GTK release the popup grab before callbacks present a window.
        GLib.timeout_add(100, dispatch_if_current)

    def show_group_context_menu(
        self, group_id: str, parent: Gtk.Widget, x: float, y: float,
    ) -> None:
        if find_group(self.store.data.groups, group_id) is None or parent.get_root() is not self:
            return
        valid, point = parent.compute_point(self.get_child(), Graphene.Point().init(x, y))
        if not valid:
            return
        self.close_active_context_menu()
        popover = getattr(self, "_group_context_menu", None)
        if popover is None:
            popover = self.build_group_context_menu()
            self._group_context_menu = popover
        model = Gio.Menu()
        for name, label in (
            ("start", "start_group"), ("subgroup", "new_subgroup"),
            ("edit", "edit_group"), ("delete", "delete_group"),
        ):
            model.append(self.t(label), f"group-menu.{name}")
            self._group_context_actions[name].set_enabled(
                not self.store.encryption_locked
                and (name == "start" or not self.store.read_only),
            )
        popover.set_menu_model(model)
        self._group_context_menu_target = (group_id,)
        rect = Gdk.Rectangle()
        rect.x, rect.y = int(point.x), int(point.y)
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)
        self.active_context_popover = popover
        popover.popup()
        GLib.idle_add(_clear_initial_menu_selection, popover)
        self.preserve_sidebar_scroll()

    def build_group_context_menu(self) -> Gtk.PopoverMenu:
        actions = Gio.SimpleActionGroup()
        self._group_context_actions = {}
        self._group_context_menu_target = None

        def activate_action(_action, _parameter, name) -> None:
            target = self._group_context_menu_target
            self._group_context_menu_target = None
            if target is not None:
                self.dispatch_group_context_action(name, target[0])

        for name in ("start", "subgroup", "edit", "delete"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", activate_action, name)
            actions.add_action(action)
            self._group_context_actions[name] = action
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(True)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.insert_action_group("group-menu", actions)
        popover.connect("closed", self.on_context_menu_closed)
        popover.set_parent(self.get_child())
        self.connect("destroy", lambda *_args: self.dispose_group_context_menu())
        return popover

    def dispose_group_context_menu(self) -> None:
        popover = getattr(self, "_group_context_menu", None)
        self._group_context_menu_target = None
        if popover is not None:
            if self.active_context_popover is popover:
                self.active_context_popover = None
            popover.popdown()
            popover.insert_action_group("group-menu", None)
            if popover.get_parent() is not None:
                popover.unparent()
            self._group_context_menu = None
            self._group_context_actions = {}

    def dispatch_group_context_action(self, name: str, group_id: str) -> None:
        popover = self._group_context_menu
        self.close_active_context_menu()

        def dispatch_if_current() -> bool:
            if (
                not self.get_visible() or getattr(self, "shutdown_in_progress", False)
                or self._group_context_menu is not popover
                or self.store.encryption_locked
                or find_group(self.store.data.groups, group_id) is None
                or (name != "start" and self.store.read_only)
            ):
                return GLib.SOURCE_REMOVE
            callbacks = {
                "start": self.on_group_context_start,
                "subgroup": self.on_group_context_add_subgroup,
                "edit": self.on_group_context_edit,
                "delete": self.on_group_context_delete,
            }
            callback = callbacks.get(name)
            if callback is not None:
                callback(None, popover, group_id)
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(100, dispatch_if_current)

    def show_row_context_menu(
        self, row: RowObject, parent: Gtk.Widget, x: float, y: float
    ) -> None:
        if row.kind == "group" and row.item_id == "":
            return
        if row.kind in {"server", "favorite", "recent"}:
            self.show_server_context_menu(row.item_id, parent, x, y)
            return
        if row.kind == "group":
            self.show_group_context_menu(row.item_id, parent, x, y)
            return

        if row.kind not in {"local_terminal", "workspace"}:
            return
        find_item = find_local_terminal_profile if row.kind == "local_terminal" else find_workspace
        items = self.store.data.local_terminals if row.kind == "local_terminal" else self.store.data.workspaces
        if find_item(items, row.item_id) is None or parent.get_root() is not self:
            return
        valid, point = parent.compute_point(self.get_child(), Graphene.Point().init(x, y))
        if not valid:
            return
        self.close_active_context_menu()
        popover = getattr(self, "_saved_context_menu", None)
        if popover is None:
            popover = self.build_saved_context_menu()
            self._saved_context_menu = popover
        pointing_rectangle = Gdk.Rectangle()
        pointing_rectangle.x = int(point.x)
        pointing_rectangle.y = int(point.y)
        pointing_rectangle.width = 1
        pointing_rectangle.height = 1
        popover.set_pointing_to(pointing_rectangle)
        popover.set_position(Gtk.PositionType.RIGHT)
        self.active_context_popover = popover
        menu = Gio.Menu()
        if row.kind == "local_terminal":
            entries = (("open", "new_tab"), ("edit", "edit_local_terminal"),
                       ("clone", "clone_connection"), ("delete", "delete_local_terminal"))
        else:
            entries = (("open", "open_workspace"), ("update", "update_workspace"),
                       ("rename", "rename_workspace"), ("duplicate", "duplicate_workspace"),
                       ("delete", "delete_workspace"))
        for name, action in self._saved_context_actions.items():
            action.set_enabled(
                not self.store.encryption_locked and (name == "open" or not self.store.read_only),
            )
        for name, label in entries:
            menu.append(self.t(label), f"saved-menu.{name}")
        popover.set_menu_model(menu)
        self._saved_context_menu_target = (row.kind, row.item_id)
        popover.popup()
        self.preserve_sidebar_scroll()

    def build_saved_context_menu(self) -> Gtk.PopoverMenu:
        actions = Gio.SimpleActionGroup()
        self._saved_context_actions = {}
        self._saved_context_menu_target = None

        def activate_action(_action, _parameter, name) -> None:
            target = self._saved_context_menu_target
            self._saved_context_menu_target = None
            if target is not None:
                self.dispatch_saved_context_action(name, *target)

        for name in ("open", "edit", "clone", "delete", "update", "rename", "duplicate"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", activate_action, name)
            actions.add_action(action)
            self._saved_context_actions[name] = action
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.insert_action_group("saved-menu", actions)
        popover.set_parent(self.get_child())
        popover.connect("closed", self.on_context_menu_closed)
        self.connect("destroy", lambda *_args: self.dispose_saved_context_menu())
        return popover

    def dispose_saved_context_menu(self) -> None:
        popover = getattr(self, "_saved_context_menu", None)
        self._saved_context_menu_target = None
        if popover is not None:
            if self.active_context_popover is popover:
                self.active_context_popover = None
            popover.popdown()
            popover.insert_action_group("saved-menu", None)
            if popover.get_parent() is not None:
                popover.unparent()
            self._saved_context_menu = None
            self._saved_context_actions = {}

    def dispatch_saved_context_action(self, name: str, kind: str, item_id: str) -> None:
        popover = self._saved_context_menu
        self.close_active_context_menu()

        def dispatch_if_current() -> bool:
            local = kind == "local_terminal"
            find_item = find_local_terminal_profile if local else find_workspace
            items = self.store.data.local_terminals if local else self.store.data.workspaces
            if (
                not self.get_visible() or getattr(self, "shutdown_in_progress", False)
                or self._saved_context_menu is not popover
                or self.store.encryption_locked
                or (name != "open" and self.store.read_only)
                or find_item(items, item_id) is None
            ):
                return GLib.SOURCE_REMOVE
            callbacks = {
                "open": self.on_local_terminal_context_open if local else self.on_workspace_context_open,
                "delete": self.on_local_terminal_context_delete if local else self.on_workspace_context_delete,
            }
            if local:
                callbacks.update(edit=self.on_local_terminal_context_edit, clone=self.on_local_terminal_context_clone)
            else:
                callbacks.update(update=self.on_workspace_context_update, rename=self.on_workspace_context_rename,
                                 duplicate=self.on_workspace_context_duplicate)
            callback = callbacks.get(name)
            if callback is not None:
                callback(popover, item_id)
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(100, dispatch_if_current)

    def on_local_terminal_context_open(self, popover: Gtk.Popover, profile_id: str) -> None:
        popover.popdown()
        profile = find_local_terminal_profile(self.store.data.local_terminals, profile_id)
        if profile is not None:
            self.open_local_terminal_profile(profile)

    def on_local_terminal_context_edit(self, popover: Gtk.Popover, profile_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        profile = find_local_terminal_profile(self.store.data.local_terminals, profile_id)
        if profile is not None:
            self.show_local_terminal_dialog(profile)

    def on_local_terminal_context_clone(self, popover: Gtk.Popover, profile_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        profile = find_local_terminal_profile(self.store.data.local_terminals, profile_id)
        if profile is None:
            return
        clone = self.store.add_local_terminal(
            unique_local_terminal_clone_name(self.store.data.local_terminals, profile.name),
            profile.working_directory,
            profile.shell,
            profile.arguments,
            profile.command_on_start,
            profile.tab_title,
            profile.split_layout,
        )
        self.selected = RowObject("local_terminal", clone.id, clone.name)
        self.toast_label.set_label(f"{self.t('local_terminal_cloned')}: {clone.name}")
        self.refresh_list()
        self.render_detail()

    def on_local_terminal_context_delete(self, popover: Gtk.Popover, profile_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        profile = find_local_terminal_profile(self.store.data.local_terminals, profile_id)
        if profile is None:
            return
        self.store.delete_local_terminal(profile_id)
        if self.selected and self.selected.kind == "local_terminal" and self.selected.item_id == profile_id:
            self.selected = None
        self.toast_label.set_label(f"{self.t('delete_local_terminal')}: {profile.name}")
        self.refresh_list()
        self.render_detail()

    def on_save_workspace(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        tabs = capture_workspace_tabs(self.visible_sessions_in_tab_order())
        if not tabs:
            self.toast_label.set_label(self.t("workspace_empty"))
            return
        if not self.workspace_tabs_within_pane_limit(tabs):
            return
        self.show_workspace_name_dialog(self.t("save_workspace_title"), "", tabs)

    def workspace_tabs_within_pane_limit(self, tabs: object) -> bool:
        pane_count = workspace_total_pane_count(tabs)
        if pane_count <= MAX_WORKSPACE_PANES:
            return True
        self.toast_label.set_label(
            self.t("workspace_pane_limit_exceeded").format(
                count=pane_count,
                limit=MAX_WORKSPACE_PANES,
            )
        )
        return False

    def show_workspace_name_dialog(
        self,
        title: str,
        initial_name: str,
        tabs: list[dict[str, object]] | None = None,
        workspace_id: str | None = None,
    ) -> None:
        dialog = DialogWindow(title=title, transient_for=self, modal=True)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        entry = Gtk.Entry(text=initial_name)
        entry.set_hexpand(True)
        entry.set_activates_default(True)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.attach(self.build_form_label(self.t("workspace_name"), True), 0, 0, 1, 1)
        grid.attach(entry, 1, 0, 1, 1)
        grid.attach(self.build_required_hint(), 1, 1, 1, 1)
        content.append(grid)
        dialog.connect("response", self.on_workspace_name_dialog_response, entry, tabs, workspace_id)
        dialog.present()
        entry.grab_focus()

    def on_workspace_name_dialog_response(
        self,
        dialog: DialogWindow,
        response: Gtk.ResponseType,
        entry: Gtk.Entry,
        tabs: list[dict[str, object]] | None,
        workspace_id: str | None,
    ) -> None:
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        name = entry.get_text().strip()
        if not name:
            entry.add_css_class("error")
            return
        if not self.ensure_writable():
            dialog.destroy()
            return
        if tabs is not None and not self.workspace_tabs_within_pane_limit(tabs):
            dialog.destroy()
            return
        if workspace_id is None:
            workspace = self.store.add_workspace(name, tabs or [])
            self.toast_label.set_label(self.t("workspace_saved").format(name=workspace.name))
            self.selected = self.build_workspace_row_object(workspace)
        else:
            self.store.rename_workspace(workspace_id, name)
            workspace = find_workspace(self.store.data.workspaces, workspace_id)
            if workspace is not None:
                self.selected = self.build_workspace_row_object(workspace)
                self.toast_label.set_label(self.t("workspace_renamed").format(name=workspace.name))
        dialog.destroy()
        self.refresh_list()
        self.render_detail()

    def on_workspace_context_open(self, popover: Gtk.Popover, workspace_id: str) -> None:
        popover.popdown()
        workspace = find_workspace(self.store.data.workspaces, workspace_id)
        if workspace is not None:
            self.open_workspace(workspace)

    def on_workspace_context_update(self, popover: Gtk.Popover, workspace_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        workspace = find_workspace(self.store.data.workspaces, workspace_id)
        tabs = capture_workspace_tabs(self.visible_sessions_in_tab_order())
        if workspace is None or not tabs:
            self.toast_label.set_label(self.t("workspace_empty"))
            return
        if not self.workspace_tabs_within_pane_limit(tabs):
            return
        self.store.update_workspace(workspace.id, workspace.name, tabs)
        self.toast_label.set_label(self.t("workspace_updated").format(name=workspace.name))
        self.refresh_list()
        self.render_detail()

    def on_workspace_context_rename(self, popover: Gtk.Popover, workspace_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        workspace = find_workspace(self.store.data.workspaces, workspace_id)
        if workspace is not None:
            self.show_workspace_name_dialog(self.t("rename_workspace"), workspace.name, workspace_id=workspace.id)

    def on_workspace_context_duplicate(self, popover: Gtk.Popover, workspace_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        workspace = find_workspace(self.store.data.workspaces, workspace_id)
        if workspace is None:
            return
        if not self.workspace_tabs_within_pane_limit(workspace.tabs):
            return
        clone = self.store.add_workspace(
            unique_workspace_clone_name(self.store.data.workspaces, workspace.name),
            deepcopy(workspace.tabs),
        )
        self.selected = self.build_workspace_row_object(clone)
        self.toast_label.set_label(self.t("workspace_duplicated").format(name=clone.name))
        self.refresh_list()
        self.render_detail()

    def on_workspace_context_delete(self, popover: Gtk.Popover, workspace_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        workspace = find_workspace(self.store.data.workspaces, workspace_id)
        if workspace is None:
            return
        dialog = Gtk.AlertDialog(
            message=self.t("delete_workspace"),
            detail=self.t("delete_workspace_confirm").format(name=workspace.name),
        )
        dialog.set_buttons([self.t("cancel"), self.t("delete_workspace")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_delete_workspace_confirmed, (dialog, workspace.id, workspace.name))

    def on_delete_workspace_confirmed(
        self,
        dialog: Gtk.AlertDialog,
        result: Gio.AsyncResult,
        data: tuple[Gtk.AlertDialog, str, str],
    ) -> None:
        _dialog, workspace_id, workspace_name = data
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1 or not self.ensure_writable():
            return
        self.store.delete_workspace(workspace_id)
        if self.selected and self.selected.kind == "workspace" and self.selected.item_id == workspace_id:
            self.selected = None
        self.toast_label.set_label(self.t("workspace_deleted").format(name=workspace_name))
        self.refresh_list()
        self.render_detail()

    def render_detail(self) -> None:
        if self.selected is None:
            self.title_label.set_label(self.t("select_server"))
            self.info_label.set_label(self.t("empty_detail_hint"))
            return

        if self.selected.kind == "group":
            group = find_group(self.store.data.groups, self.selected.item_id)
            title = group.name if group else self.t("no_group")
            count = len([server for server in self.store.data.servers if server.group_id == self.selected.item_id])
            self.title_label.set_label(title)
            self.info_label.set_label(
                self.t("group_detail_info").format(count=count)
            )
            return

        if self.selected.kind == "local_terminal":
            profile = find_local_terminal_profile(self.store.data.local_terminals, self.selected.item_id)
            if profile is None:
                return
            self.title_label.set_label(profile.name or self.t("local_terminal"))
            self.info_label.set_label(
                self.t("local_terminal_detail_info").format(
                    working_directory=profile.working_directory or str(Path.home()),
                    shell=profile.shell or self.default_local_terminal_shell(),
                    arguments=profile.arguments or "-",
                    command_on_start=profile.command_on_start or "-",
                    tab_title=profile.tab_title or profile.name or self.t("local_terminal"),
                )
            )
            return

        if self.selected.kind == "workspace":
            workspace = find_workspace(self.store.data.workspaces, self.selected.item_id)
            if workspace is None:
                return
            self.title_label.set_label(workspace.name)
            self.info_label.set_label(self.workspace_description(workspace))
            return

        if self.selected.kind not in {"server", "favorite", "recent"}:
            return
        server = find_server(self.store.data.servers, self.selected.item_id)
        if server is None:
            return
        group = find_group(self.store.data.groups, server.group_id) if server.group_id else None
        self.title_label.set_label(server.name)
        self.info_label.set_label(
            self.t("server_detail_info").format(
                user=server.user,
                host=server.host,
                port=server.port,
                group=group.name if group else self.t("no_group"),
            )
        )

    def on_add_group(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        self.show_group_dialog()

    def on_add_server(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        self.show_server_dialog()

    def on_add_local_terminal(self, _button: Gtk.Button) -> None:
        if not self.ensure_writable():
            return
        self.show_local_terminal_dialog()
