# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from .connection_utils import (
    find_group,
    find_server,
    group_descendant_ids,
    group_matches_query,
    server_matches_query,
    unique_server_clone_name,
)
from .models import Group, Server
from .ui_state import RowObject


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
        popover.popdown()
        server = find_server(self.store.data.servers, server_id)
        if server is not None:
            self.on_send_files_to_server(popover, server)

    def on_group_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        if not self.ensure_writable():
            return
        group = find_group(self.store.data.groups, group_id)
        if group:
            self.show_group_dialog(group)

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
        for server in self.group_servers(group.id):
            self.open_terminal_tab(server)

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

    def set_all_groups_expanded(self, expanded: bool) -> None:
        for expander in self.group_expanders:
            expander.set_expanded(expanded)
            group_id = getattr(expander, "group_id", None)
            if group_id:
                self.group_expanded_state[group_id] = expanded

    def get_group_expanded(self, group_id: str, query: str) -> bool:
        if query:
            return True
        if group_id == "__favorites__":
            return self.group_expanded_state.get(group_id, True)
        return self.group_expanded_state.get(group_id, not self.collapse_groups_on_startup)

    def on_group_expanded_changed(self, expander: Gtk.Expander, _param: Any) -> None:
        group_id = getattr(expander, "group_id", None)
        if group_id:
            self.group_expanded_state[group_id] = expander.get_expanded()

    def refresh_list(self) -> None:
        query = self.search_entry.get_text().lower().strip() if hasattr(self, "search_entry") else ""
        if not hasattr(self, "server_list"):
            return

        while child := self.server_list.get_first_child():
            self.server_list.remove(child)
        self.group_expanders: list[Gtk.Expander] = []
        self.tree_widgets = {}
        self.selected_tree_widget = None

        children_by_parent: dict[str | None, list[Group]] = {}
        for group in self.store.data.groups:
            children_by_parent.setdefault(group.parent_id, []).append(group)
        servers_by_group: dict[str | None, list[Server]] = {}
        for server in self.store.data.servers:
            if server_matches_query(server, query):
                servers_by_group.setdefault(server.group_id, []).append(server)

        self.visible_tree_rows = self.build_visible_tree_rows(children_by_parent, servers_by_group, query)
        favorite_servers = self.favorite_servers(query)
        if favorite_servers:
            self.server_list.append(self.build_favorites_widget(favorite_servers, query))
        for group in sorted(children_by_parent.get(None, []), key=lambda item: item.name.lower()):
            widget = self.build_group_widget(group, children_by_parent, servers_by_group, query)
            if widget is not None:
                self.server_list.append(widget)

        ungrouped = servers_by_group.get(None, [])
        if ungrouped:
            self.server_list.append(self.build_ungrouped_widget(ungrouped, query))

        root_groups = len([group for group in self.store.data.groups if group.parent_id is None])
        subgroups = len(self.store.data.groups) - root_groups
        self.summary_label.set_label(
            self.t("summary").format(groups=root_groups, subgroups=subgroups, servers=len(self.store.data.servers))
        )

    def favorite_servers(self, query: str) -> list[Server]:
        return sorted(
            [server for server in self.store.data.servers if server.favorite and server_matches_query(server, query)],
            key=lambda item: (item.name.lower(), item.host.lower(), item.user.lower(), item.port),
        )

    def build_visible_tree_rows(
        self,
        children_by_parent: dict[str | None, list[Group]],
        servers_by_group: dict[str | None, list[Server]],
        query: str,
    ) -> list[RowObject]:
        rows: list[RowObject] = []
        if query or self.get_group_expanded("__favorites__", query):
            for server in self.favorite_servers(query):
                rows.append(self.build_server_row_object(server, "favorite"))
        for group in sorted(children_by_parent.get(None, []), key=lambda item: item.name.lower()):
            rows.extend(self.collect_visible_group_rows(group, children_by_parent, servers_by_group, query))
        for server in sorted(servers_by_group.get(None, []), key=lambda item: item.name.lower()):
            rows.append(self.build_server_row_object(server))
        return rows

    def collect_visible_group_rows(
        self,
        group: Group,
        children_by_parent: dict[str | None, list[Group]],
        servers_by_group: dict[str | None, list[Server]],
        query: str,
    ) -> list[RowObject]:
        child_rows: list[RowObject] = []
        if query or self.get_group_expanded(group.id, query):
            for child in sorted(children_by_parent.get(group.id, []), key=lambda item: item.name.lower()):
                child_rows.extend(self.collect_visible_group_rows(child, children_by_parent, servers_by_group, query))
            for server in sorted(servers_by_group.get(group.id, []), key=lambda item: item.name.lower()):
                child_rows.append(self.build_server_row_object(server))

        group_matches = group_matches_query(group, query)
        if query and not group_matches and not child_rows:
            return []

        descendant_servers = sum(1 for row in child_rows if row.kind == "server")
        return [RowObject("group", group.id, group.name, f"{descendant_servers} servidor(es)"), *child_rows]

    def build_server_row_object(self, server: Server, row_kind: str = "server") -> RowObject:
        return RowObject(row_kind, server.id, server.name, self.get_server_connection_text(server))

    def get_server_connection_text(self, server: Server) -> str:
        return f"{server.user}@{server.host}:{server.port}" if server.user else f"{server.host}:{server.port}"

    def build_favorites_widget(self, servers: list[Server], query: str) -> Gtk.Widget:
        expander = Gtk.Expander()
        expander.set_label_widget(self.build_favorites_label(f"{self.t('favorites')} ({len(servers)})"))
        self.group_expanders.append(expander)
        expander.group_id = "__favorites__"
        expander.set_expanded(self.get_group_expanded("__favorites__", query))
        expander.connect("notify::expanded", self.on_group_expanded_changed)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for server in servers:
            content.append(self.build_server_widget(server, row_kind="favorite", icon_name="starred-symbolic"))
        expander.set_child(content)
        return expander

    def build_favorites_label(self, text: str) -> Gtk.Widget:
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label_box.append(Gtk.Image.new_from_icon_name("starred-symbolic"))
        label = Gtk.Label(label=text)
        label.add_css_class("heading")
        label_box.append(label)
        return label_box

    def build_group_widget(
        self,
        group: Group,
        children_by_parent: dict[str | None, list[Group]],
        servers_by_group: dict[str | None, list[Server]],
        query: str,
    ) -> Gtk.Widget | None:
        child_groups = children_by_parent.get(group.id, [])
        servers = servers_by_group.get(group.id, [])
        child_widgets = [
            widget
            for child in sorted(child_groups, key=lambda item: item.name.lower())
            if (widget := self.build_group_widget(child, children_by_parent, servers_by_group, query)) is not None
        ]
        group_matches = group_matches_query(group, query)
        if query and not group_matches and not servers and not child_widgets:
            return None

        descendant_servers = len(servers) + sum(
            int(getattr(widget, "server_count", 0)) for widget in child_widgets
        )
        expander = Gtk.Expander()
        group_label = self.build_group_label(f"{group.name} ({descendant_servers})")
        expander.set_label_widget(group_label)
        self.group_expanders.append(expander)
        expander.group_id = group.id
        expander.server_count = descendant_servers
        expander.set_expanded(self.get_group_expanded(group.id, query))
        expander.connect("notify::expanded", self.on_group_expanded_changed)
        expander.set_margin_top(3)
        expander.set_margin_bottom(3)
        expander.set_margin_start(4)
        expander.set_margin_end(2)

        group_row = RowObject("group", group.id, group.name, f"{descendant_servers} servidor(es)")
        self.register_tree_widget(group_row, group_label)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_group_widget_left_click, group_row, group_label)
        group_label.add_controller(left_click)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_group_widget_right_click, group_row, group_label)
        group_label.add_controller(right_click)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for widget in child_widgets:
            widget.set_margin_start(widget.get_margin_start() + 10)
            content.append(widget)
        for server in sorted(servers, key=lambda item: item.name.lower()):
            content.append(self.build_server_widget(server))
        expander.set_child(content)
        return expander

    def build_group_label(self, text: str) -> Gtk.Widget:
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label_box.append(Gtk.Image.new_from_icon_name("folder-symbolic"))
        label = Gtk.Label(label=text)
        label.add_css_class("heading")
        label_box.append(label)
        return label_box

    def build_ungrouped_widget(self, servers: list[Server], query: str) -> Gtk.Widget:
        expander = Gtk.Expander()
        expander.set_label_widget(self.build_group_label(f"{self.t('no_group')} ({len(servers)})"))
        self.group_expanders.append(expander)
        expander.group_id = "__ungrouped__"
        expander.set_expanded(self.get_group_expanded("__ungrouped__", query))
        expander.connect("notify::expanded", self.on_group_expanded_changed)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for server in sorted(servers, key=lambda item: item.name.lower()):
            content.append(self.build_server_widget(server))
        expander.set_child(content)
        return expander

    def build_server_widget(
        self,
        server: Server,
        row_kind: str = "server",
        icon_name: str = "network-server-symbolic",
    ) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row.set_focusable(False)
        row.set_margin_top(0)
        row.set_margin_bottom(0)
        row.set_margin_start(18)
        row.set_margin_end(6)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.append(Gtk.Image.new_from_icon_name(icon_name))
        title = Gtk.Label(label=server.name)
        title.set_xalign(0)
        title_box.append(title)
        row.append(title_box)

        connection = self.get_server_connection_text(server)
        row.set_tooltip_text(connection)
        row_obj = self.build_server_row_object(server, row_kind)
        self.register_tree_widget(row_obj, row)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_server_widget_left_click, row_obj)
        row.add_controller(left_click)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_server_widget_right_click, row_obj, row)
        row.add_controller(right_click)
        return row

    def register_tree_widget(self, row: RowObject, widget: Gtk.Widget) -> None:
        widget.add_css_class("termia-tree-item")
        if row.kind in {"server", "favorite"}:
            widget.add_css_class("termia-server-item")
        widget.set_focusable(False)
        self.tree_widgets[(row.kind, row.item_id)] = widget
        if self.selected and self.selected.kind == row.kind and self.selected.item_id == row.item_id:
            widget.add_css_class("selected")
            self.selected_tree_widget = widget

    def select_tree_row(self, row: RowObject, widget: Gtk.Widget) -> None:
        self.preserve_sidebar_scroll()
        if self.selected_tree_widget is not None and self.selected_tree_widget is not widget:
            self.selected_tree_widget.remove_css_class("selected")
        self.selected = row
        self.selected_tree_widget = widget
        widget.add_css_class("selected")
        self.render_detail()

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

    def get_group_expander(self, group_id: str) -> Gtk.Expander | None:
        for expander in getattr(self, "group_expanders", []):
            if getattr(expander, "group_id", None) == group_id:
                return expander
        return None

    def get_visible_tree_row_index(self, row: RowObject) -> int | None:
        for index, visible_row in enumerate(getattr(self, "visible_tree_rows", [])):
            if visible_row.kind == row.kind and visible_row.item_id == row.item_id:
                return index
        return None

    def select_visible_tree_row(self, index: int) -> bool:
        rows = getattr(self, "visible_tree_rows", [])
        if not rows:
            return False
        index = max(0, min(index, len(rows) - 1))
        row = rows[index]
        widget = self.tree_widgets.get((row.kind, row.item_id))
        if widget is None:
            return False
        self.select_tree_row(row, widget)
        return True

    def move_visible_tree_selection(self, delta: int) -> bool:
        rows = getattr(self, "visible_tree_rows", [])
        if not rows:
            return False
        current_index = self.get_visible_tree_row_index(self.selected) if self.selected is not None else None
        if current_index is None:
            target_index = 0 if delta >= 0 else len(rows) - 1
        else:
            target_index = max(0, min(current_index + delta, len(rows) - 1))
        return self.select_visible_tree_row(target_index)

    def activate_selected_tree_row(self) -> bool:
        if self.selected is None:
            return False
        if self.selected.kind in {"server", "favorite"}:
            server = find_server(self.store.data.servers, self.selected.item_id)
            if server is None:
                return False
            self.open_terminal_tab(server)
            return True
        if self.selected.kind == "group":
            expander = self.get_group_expander(self.selected.item_id)
            if expander is None:
                return False
            expander.set_expanded(not expander.get_expanded())
            self.refresh_list()
            return True
        return False

    def on_sidebar_search_key_pressed(
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

        enter_keys = {Gdk.KEY_Return, Gdk.KEY_KP_Enter, getattr(Gdk, "KEY_ISO_Enter", Gdk.KEY_Return)}
        if keyval == Gdk.KEY_Up:
            return self.move_visible_tree_selection(-1)
        if keyval == Gdk.KEY_Down:
            return self.move_visible_tree_selection(1)
        if keyval == Gdk.KEY_Home:
            return self.select_visible_tree_row(0)
        if keyval == Gdk.KEY_End:
            return self.select_visible_tree_row(len(getattr(self, "visible_tree_rows", [])) - 1)
        if keyval in enter_keys:
            return self.activate_selected_tree_row()
        return False

    def on_group_widget_left_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
        widget: Gtk.Widget,
    ) -> None:
        self.select_tree_row(row, widget)

    def on_server_widget_left_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
    ) -> None:
        self.select_tree_row(row, self.tree_widgets[(row.kind, row.item_id)])
        if n_press == 2:
            server = find_server(self.store.data.servers, row.item_id)
            if server:
                self.open_terminal_tab(server)

    def on_server_widget_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
        parent: Gtk.Widget,
    ) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        self.close_active_context_menu()
        self.select_tree_row(row, parent)
        self.show_row_context_menu(row, parent, _x, _y)
        self.preserve_sidebar_scroll(*scroll_values)

    def on_group_widget_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
        parent: Gtk.Widget,
    ) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        self.close_active_context_menu()
        self.select_tree_row(row, parent)
        self.show_row_context_menu(row, parent, _x, _y)
        self.preserve_sidebar_scroll(*scroll_values)

    def close_active_context_menu(self) -> None:
        popover = self.active_context_popover
        if popover is None:
            return
        scroll_values = self.get_sidebar_scroll_values()
        self.active_context_popover = None
        popover.popdown()
        if popover.get_parent() is not None:
            popover.unparent()
        self.preserve_sidebar_scroll(*scroll_values)

    def on_context_menu_closed(self, popover: Gtk.Popover) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        if self.active_context_popover is popover:
            self.active_context_popover = None
        if popover.get_parent() is not None:
            popover.unparent()
        self.preserve_sidebar_scroll(*scroll_values)

    def show_row_context_menu(
        self, row: RowObject, parent: Gtk.Widget, x: float, y: float
    ) -> None:
        if row.kind == "group" and row.item_id == "":
            return

        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(parent)
        pointing_rectangle = Gdk.Rectangle()
        pointing_rectangle.x = int(x)
        pointing_rectangle.y = int(y)
        pointing_rectangle.width = 1
        pointing_rectangle.height = 1
        popover.set_pointing_to(pointing_rectangle)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.connect("closed", self.on_context_menu_closed)
        self.active_context_popover = popover
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        if row.kind in {"server", "favorite"}:
            server = find_server(self.store.data.servers, row.item_id)
            if server is not None:
                self.add_context_menu_item(
                    menu,
                    self.t("remove_favorite") if server.favorite else self.t("add_favorite"),
                    lambda: self.on_server_context_toggle_favorite(None, popover, row.item_id),
                    enabled=not self.store.read_only,
                )
            self.add_context_menu_item(
                menu,
                self.t("connect"),
                lambda: self.on_server_context_connect(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("edit_server"),
                lambda: self.on_server_context_edit(None, popover, row.item_id),
                enabled=not self.store.read_only,
            )
            self.add_context_menu_item(
                menu,
                self.t("clone_connection"),
                lambda: self.on_server_context_clone(None, popover, row.item_id),
                enabled=not self.store.read_only,
            )
            self.add_context_menu_item(
                menu,
                self.t("send_files_to_server"),
                lambda: self.on_server_context_send_files(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("delete_server"),
                lambda: self.on_server_context_delete(None, popover, row.item_id),
                destructive=True,
                enabled=not self.store.read_only,
            )
        elif row.kind == "group":
            self.add_context_menu_item(
                menu,
                self.t("start_group"),
                lambda: self.on_group_context_start(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("edit_group"),
                lambda: self.on_group_context_edit(None, popover, row.item_id),
                enabled=not self.store.read_only,
            )
            self.add_context_menu_item(
                menu,
                self.t("delete_group"),
                lambda: self.on_group_context_delete(None, popover, row.item_id),
                destructive=True,
                enabled=not self.store.read_only,
            )

        popover.set_child(menu)
        popover.popup()
        self.preserve_sidebar_scroll()

    def add_context_menu_item(
        self,
        menu: Gtk.ListBox,
        label_text: str,
        callback: Any,
        destructive: bool = False,
        enabled: bool = True,
    ) -> None:
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.set_margin_start(12)
        label.set_margin_end(36)
        if destructive:
            label.add_css_class("error")
        row.set_child(label)
        row.set_sensitive(enabled)

        if enabled:
            click = Gtk.GestureClick.new()
            click.set_button(1)
            click.connect("released", lambda *_args: callback())
            row.add_controller(click)
        menu.append(row)

    def add_context_menu_separator(self, menu: Gtk.ListBox) -> None:
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row.set_selectable(False)
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.add_css_class("termia-menu-separator")
        row.set_child(separator)
        menu.append(row)

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

        if self.selected.kind not in {"server", "favorite"}:
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
