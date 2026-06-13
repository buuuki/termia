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

    def setup_row(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        title = Gtk.Label()
        title.set_xalign(0)
        title.add_css_class("heading")
        box.append(title)

        subtitle = Gtk.Label()
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        box.append(subtitle)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_row_right_click, item, box)
        box.add_controller(right_click)

        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_row_left_click, item)
        box.add_controller(left_click)

        item.set_child(box)

    def bind_row(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        obj = item.get_item()
        box = item.get_child()
        title = box.get_first_child()
        subtitle = title.get_next_sibling()
        title.set_label(obj.title)
        subtitle.set_label(obj.subtitle)

    def on_row_left_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        item: Gtk.ListItem,
    ) -> None:
        if n_press != 2:
            return
        row = item.get_item()
        if row is None or row.kind != "server":
            return
        server = find_server(self.store.data.servers, row.item_id)
        if server:
            self.open_terminal_tab(server)

    def on_row_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        item: Gtk.ListItem,
        parent: Gtk.Widget,
    ) -> None:
        row = item.get_item()
        if row is None:
            return

        self.selected = row
        position = item.get_position()
        if position != Gtk.INVALID_LIST_POSITION:
            self.selection.set_selected(position)

        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(parent)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        if row.kind == "server":
            connect_button = Gtk.Button(label="Conectar")
            connect_button.add_css_class("suggested-action")
            connect_button.connect("clicked", self.on_server_context_connect, popover, row.item_id)
            edit_button = Gtk.Button(label="Editar servidor")
            edit_button.connect("clicked", self.on_server_context_edit, popover, row.item_id)
            delete_button = Gtk.Button(label="Eliminar servidor")
            delete_button.add_css_class("destructive-action")
            delete_button.connect("clicked", self.on_server_context_delete, popover, row.item_id)
            for button in (connect_button, edit_button, delete_button):
                menu.append(button)
        elif row.kind == "group" and row.item_id:
            edit_button = Gtk.Button(label="Editar grupo")
            edit_button.connect("clicked", self.on_group_context_edit, popover, row.item_id)
            delete_button = Gtk.Button(label="Eliminar grupo")
            delete_button.add_css_class("destructive-action")
            delete_button.connect("clicked", self.on_group_context_delete, popover, row.item_id)
            menu.append(edit_button)
            menu.append(delete_button)
        else:
            return

        popover.set_child(menu)
        popover.popup()

    def on_server_context_connect(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = find_server(self.store.data.servers, server_id)
        if server:
            self.open_terminal_tab(server)

    def on_server_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = find_server(self.store.data.servers, server_id)
        if server:
            self.show_server_dialog(server)

    def on_server_context_delete(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = find_server(self.store.data.servers, server_id)
        if server:
            self.store.delete_server(server_id)
            self.selected = None
            self.toast_label.set_label(f"Servidor eliminado: {server.name}")
            self.refresh_list()
            self.render_detail()

    def on_server_context_clone(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = find_server(self.store.data.servers, server_id)
        if server is None:
            return
        clone = self.store.add_server(
            unique_server_clone_name(self.store.data.servers, server.name),
            server.host,
            server.user,
            server.port,
            server.group_id,
            server.password,
            server.public_key,
        )
        self.selected = RowObject("server", clone.id, clone.name)
        self.toast_label.set_label(f"Conexión clonada: {clone.name}")
        self.refresh_list()
        self.render_detail()

    def on_group_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        group = find_group(self.store.data.groups, group_id)
        if group:
            self.show_group_dialog(group)

    def on_group_context_delete(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        self.request_delete_group(group_id)

    def request_delete_group(self, group_id: str) -> None:
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

    def build_server_widget(self, server: Server) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row.set_focusable(False)
        row.set_margin_top(0)
        row.set_margin_bottom(0)
        row.set_margin_start(18)
        row.set_margin_end(6)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.append(Gtk.Image.new_from_icon_name("network-server-symbolic"))
        title = Gtk.Label(label=server.name)
        title.set_xalign(0)
        title_box.append(title)
        row.append(title_box)

        connection = f"{server.user}@{server.host}:{server.port}" if server.user else f"{server.host}:{server.port}"
        row.set_tooltip_text(connection)
        row_obj = RowObject("server", server.id, server.name, connection)
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
        if row.kind == "server":
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
        self.update_actions()

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

        if row.kind == "server":
            self.add_context_menu_item(
                menu,
                self.t("connect"),
                lambda: self.on_server_context_connect(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("edit_server"),
                lambda: self.on_server_context_edit(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("clone_connection"),
                lambda: self.on_server_context_clone(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("delete_server"),
                lambda: self.on_server_context_delete(None, popover, row.item_id),
                destructive=True,
            )
        elif row.kind == "group":
            self.add_context_menu_item(
                menu,
                self.t("edit_group"),
                lambda: self.on_group_context_edit(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("delete_group"),
                lambda: self.on_group_context_delete(None, popover, row.item_id),
                destructive=True,
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

    def server_row(self, server: Server, groups_by_id: dict[str, Group]) -> RowObject:
        group_name = groups_by_id.get(server.group_id).name if server.group_id in groups_by_id else "Sin grupo"
        return RowObject("server", server.id, server.name, f"{server.user}@{server.host}:{server.port} · {group_name}")

    def on_selection_changed(self, selection: Gtk.SingleSelection, _position: int, _n_items: int) -> None:
        self.selected = selection.get_selected_item()
        self.render_detail()
        self.update_actions()

    def render_detail(self) -> None:
        if self.selected is None:
            self.title_label.set_label("Selecciona un servidor")
            self.info_label.set_label("Crea grupos y servidores desde la barra superior.")
            return

        if self.selected.kind == "group":
            group = find_group(self.store.data.groups, self.selected.item_id)
            title = group.name if group else "Sin grupo"
            count = len([server for server in self.store.data.servers if server.group_id == self.selected.item_id])
            self.title_label.set_label(title)
            self.info_label.set_label(
                f"{count} servidor(es) en este grupo. "
                "Usa Editar grupo o Eliminar grupo para gestionarlo."
            )
            return

        server = find_server(self.store.data.servers, self.selected.item_id)
        if server is None:
            return
        group = find_group(self.store.data.groups, server.group_id) if server.group_id else None
        self.title_label.set_label(server.name)
        self.info_label.set_label(
            f"SSH: {server.user}@{server.host}\n"
            f"Puerto: {server.port}\n"
            f"Grupo: {group.name if group else 'Sin grupo'}"
        )

    def update_actions(self) -> None:
        return

    def on_add_group(self, _button: Gtk.Button) -> None:
        self.show_group_dialog()

    def on_add_server(self, _button: Gtk.Button) -> None:
        self.show_server_dialog()

    def on_edit(self, _button: Gtk.Button) -> None:
        if self.selected is None:
            return
        if self.selected.kind == "group":
            group = find_group(self.store.data.groups, self.selected.item_id)
            if group:
                self.show_group_dialog(group)
        elif self.selected.kind == "server":
            server = find_server(self.store.data.servers, self.selected.item_id)
            if server:
                self.show_server_dialog(server)

    def on_delete(self, _button: Gtk.Button) -> None:
        if self.selected is None:
            return
        if self.selected.kind == "group" and self.selected.item_id:
            self.request_delete_group(self.selected.item_id)
            return
        elif self.selected.kind == "server":
            server = find_server(self.store.data.servers, self.selected.item_id)
            self.store.delete_server(self.selected.item_id)
            self.toast_label.set_label(
                f"Servidor eliminado: {server.name}" if server else "Servidor eliminado"
            )
            self.selected = None
        self.refresh_list()
        self.render_detail()

    def on_connect(self, _button: Gtk.Button) -> None:
        if self.selected is None or self.selected.kind != "server":
            return
        server = find_server(self.store.data.servers, self.selected.item_id)
        if server is None:
            return

        self.open_terminal_tab(server)
