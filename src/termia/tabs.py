# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

from .debug import log_event
from .ui_state import TerminalSession


class TabsMixin:
    TAB_OVERFLOW_EPSILON = 1.0

    def add_session_to_main_view(self, session: TerminalSession) -> None:
        self.terminal_stack.add_named(session.page, session.id)
        self.session_tab_bar.append(session.tab_label)
        self.update_session_tab_bar_visibility()
        self.set_active_session(session.id)
        self.sync_window_title_with_visible_session()
        log_event("tab.attached", session_id=session.id)

    @staticmethod
    def tab_reveal_scroll_value(
        current: float,
        page_size: float,
        lower: float,
        upper: float,
        tab_start: float,
        tab_end: float,
    ) -> float:
        maximum = max(lower, upper - page_size)
        if tab_start < current:
            return max(lower, tab_start)
        if tab_end > current + page_size:
            return min(maximum, tab_end - page_size)
        return min(maximum, max(lower, current))

    @classmethod
    def tab_strip_has_overflow(
        cls,
        *,
        page_size: float,
        lower: float,
        upper: float,
    ) -> bool:
        """Return whether the tab strip is wider than its viewport."""
        return upper - lower > page_size + cls.TAB_OVERFLOW_EPSILON

    def visible_sessions_in_tab_order(self) -> list[TerminalSession]:
        sessions_by_label = {
            session.tab_label: session
            for session in self.session_registry.sessions()
            if session.detached_window is None
        }
        ordered: list[TerminalSession] = []
        child = self.session_tab_bar.get_first_child()
        while child is not None:
            session = sessions_by_label.get(child)
            if session is not None:
                ordered.append(session)
            child = child.get_next_sibling()
        return ordered

    def set_active_session(self, session_id: str) -> None:
        session = self.session_registry.get(session_id)
        if session is None or session.detached_window is not None:
            return
        self.terminal_stack.set_visible_child(session.page)
        self.update_session_tab_states()
        self.schedule_active_tab_reveal()
        session.terminal.grab_focus()
        log_event("tab.selected", session_id=session.id)

    def update_session_tab_states(self) -> None:
        visible_page = self.terminal_stack.get_visible_child()
        for session in self.session_registry.sessions():
            session.tab_label.remove_css_class("active")
            if visible_page is session.page and session.detached_window is None:
                session.tab_label.add_css_class("active")
        self.rebuild_tab_overflow_popover()

    def schedule_active_tab_reveal(self) -> None:
        pending_id = getattr(self, "active_tab_reveal_id", None)
        if pending_id is not None:
            GLib.source_remove(pending_id)
        self.active_tab_reveal_id = GLib.idle_add(self.reveal_active_tab)

    def reveal_active_tab(self) -> bool:
        self.active_tab_reveal_id = None
        visible_page = self.terminal_stack.get_visible_child()
        active_session = next(
            (
                session
                for session in self.visible_sessions_in_tab_order()
                if session.page is visible_page
            ),
            None,
        )
        if active_session is None:
            return GLib.SOURCE_REMOVE
        ok, bounds = active_session.tab_label.compute_bounds(self.session_tab_bar)
        if not ok:
            return GLib.SOURCE_REMOVE
        adjustment = self.session_tab_scroller.get_hadjustment()
        adjustment.set_value(
            self.tab_reveal_scroll_value(
                adjustment.get_value(),
                adjustment.get_page_size(),
                adjustment.get_lower(),
                adjustment.get_upper(),
                bounds.get_x(),
                bounds.get_x() + bounds.get_width(),
            )
        )
        return GLib.SOURCE_REMOVE

    def on_tab_scroll_adjustment_changed(
        self,
        adjustment: Gtk.Adjustment,
        *_args: object,
    ) -> None:
        self.schedule_active_tab_reveal()
        self.schedule_tab_overflow_visibility()

    def schedule_tab_overflow_visibility(self) -> None:
        pending_id = getattr(self, "tab_overflow_visibility_id", None)
        if pending_id is not None:
            GLib.source_remove(pending_id)
        self.tab_overflow_visibility_id = GLib.idle_add(self.update_tab_overflow_visibility)

    def update_tab_overflow_visibility(self) -> bool:
        self.tab_overflow_visibility_id = None
        if not self.session_tab_controls.get_visible():
            self.tab_overflow_button.set_visible(False)
            return GLib.SOURCE_REMOVE
        adjustment = self.session_tab_scroller.get_hadjustment()
        self.tab_overflow_button.set_visible(
            self.tab_strip_has_overflow(
                page_size=adjustment.get_page_size(),
                lower=adjustment.get_lower(),
                upper=adjustment.get_upper(),
            )
        )
        return GLib.SOURCE_REMOVE

    def rebuild_tab_overflow_popover(self) -> None:
        if not hasattr(self, "tab_overflow_button"):
            return
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        panel.add_css_class("termia-menu-panel")
        panel.set_margin_top(6)
        panel.set_margin_bottom(6)
        panel.set_margin_start(6)
        panel.set_margin_end(6)
        visible_page = self.terminal_stack.get_visible_child()
        for session in self.visible_sessions_in_tab_order():
            display_title = self.session_tab_display_title(session)
            button = Gtk.Button()
            button.add_css_class("flat")
            button.add_css_class("termia-tab-overflow-item")
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            marker = Gtk.Image.new_from_icon_name("object-select-symbolic")
            marker.set_visible(session.page is visible_page)
            label = Gtk.Label(label=display_title)
            label.set_xalign(0)
            label.set_hexpand(True)
            label.set_wrap(True)
            label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_max_width_chars(50)
            label.set_tooltip_text(display_title)
            row.append(marker)
            row.append(label)
            button.set_child(row)
            button.connect("clicked", self.on_tab_overflow_item_clicked, session.id, popover)
            panel.append(button)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_max_content_height(360)
        scroller.set_propagate_natural_height(True)
        scroller.set_child(panel)
        popover.set_child(scroller)
        self.tab_overflow_button.set_popover(popover)

    @staticmethod
    def session_tab_display_title(session: TerminalSession) -> str:
        child = session.tab_label.get_first_child()
        if isinstance(child, Gtk.Label):
            return child.get_label()
        if isinstance(child, Gtk.Box):
            label = child.get_first_child()
            if isinstance(label, Gtk.Label):
                return label.get_label()
        return session.title

    def on_tab_overflow_item_clicked(
        self,
        _button: Gtk.Button,
        session_id: str,
        popover: Gtk.Popover,
    ) -> None:
        popover.popdown()
        self.set_active_session(session_id)

    def remove_session_from_main_view(self, session: TerminalSession) -> None:
        if session.detached_window is None:
            parent = session.tab_label.get_parent()
            if parent is self.session_tab_bar:
                self.session_tab_bar.remove(session.tab_label)
            try:
                self.terminal_stack.remove(session.page)
            except Exception:
                pass
        self.update_session_tab_states()
        self.update_session_tab_bar_visibility()

    def update_session_tab_bar_visibility(self) -> None:
        visible_sessions = [session for session in self.session_registry.sessions() if session.detached_window is None]
        has_multiple_tabs = len(visible_sessions) > 1
        self.session_tab_controls.set_visible(has_multiple_tabs)
        self.tab_overflow_button.set_visible(False)
        if has_multiple_tabs:
            self.schedule_tab_overflow_visibility()
        self.rebuild_tab_overflow_popover()

    def sync_window_title_with_visible_session(self) -> None:
        visible_sessions = [session for session in self.session_registry.sessions() if session.detached_window is None]
        if len(visible_sessions) == 1:
            session = visible_sessions[0]
            if session.server_id is None and session.title_locked:
                self.set_title(session.title)
                return
        self.set_title("Termia")

    def focus_available_session_after_close(
        self,
        closed_session_id: str,
        previous_order: list[TerminalSession],
    ) -> None:
        closed_index = next(
            (index for index, session in enumerate(previous_order) if session.id == closed_session_id),
            -1,
        )
        if closed_index < 0:
            return
        focus_candidates = [
            *reversed(previous_order[:closed_index]),
            *previous_order[closed_index + 1 :],
        ]
        for session in focus_candidates:
            if self.session_registry.contains(session.id) and session.detached_window is None:
                self.set_active_session(session.id)
                return

    def update_session_tab_title(self, session: TerminalSession, title: str) -> None:
        child = session.tab_label.get_first_child()
        if isinstance(child, Gtk.Label):
            child.set_label(title)
        elif isinstance(child, Gtk.Box):
            label = child.get_first_child()
            if isinstance(label, Gtk.Label):
                label.set_label(title)
        self.rebuild_tab_overflow_popover()
        self.schedule_active_tab_reveal()
        self.schedule_tab_overflow_visibility()

    def build_tab_label(self, title: str, session_id: str, page: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.add_css_class("termia-tab-label")
        box.set_hexpand(False)
        box.set_size_request(118, -1)
        box.set_can_target(True)
        box.set_margin_start(0)
        box.set_margin_end(0)
        label = Gtk.Label(label=title)
        label.add_css_class("termia-tab-title")
        label.set_hexpand(True)
        label.set_single_line_mode(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_width_chars(8)
        label.set_max_width_chars(8)
        label.set_tooltip_text(title)
        label.set_can_target(False)
        label.set_margin_start(4)
        label.set_margin_end(4)
        close_button = Gtk.Button(icon_name="window-close-symbolic")
        close_button.add_css_class("termia-tab-close")
        close_button.set_has_frame(False)
        close_button.set_tooltip_text(self.t("close_tab"))
        close_button.connect("clicked", self.on_request_close_tab, session_id, page)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_tab_left_press, session_id)
        box.add_controller(left_click)
        middle_click = Gtk.GestureClick.new()
        middle_click.set_button(2)
        middle_click.connect("pressed", self.on_tab_middle_press, session_id, page)
        box.add_controller(middle_click)
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self.on_tab_drag_prepare, session_id, box)
        drag_source.connect("drag-begin", self.on_tab_drag_begin, session_id, box)
        drag_source.connect("drag-end", self.on_tab_drag_end, session_id)
        box.add_controller(drag_source)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_tab_right_click, session_id, box)
        box.add_controller(right_click)
        box.append(label)
        box.append(close_button)
        return box

    def on_tab_left_press(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        session_id: str,
    ) -> None:
        self.set_active_session(session_id)

    def on_tab_middle_press(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        session_id: str,
        page: Gtk.Widget,
    ) -> None:
        self.request_close_tab(session_id, page)

    def on_tab_drag_prepare(
        self,
        _source: Gtk.DragSource,
        _x: float,
        _y: float,
        session_id: str,
        _tab: Gtk.Widget,
    ) -> Gdk.ContentProvider | None:
        if not self.session_registry.contains(session_id):
            return None
        return Gdk.ContentProvider.new_for_value(session_id)

    def on_tab_drag_begin(
        self,
        source: Gtk.DragSource,
        _drag: Gdk.Drag,
        session_id: str,
        tab: Gtk.Widget,
    ) -> None:
        self.set_active_session(session_id)
        self.tab_drag_session_id = session_id
        tab.add_css_class("dragging")
        source.set_icon(Gtk.WidgetPaintable.new(tab), tab.get_allocated_width() // 2, tab.get_allocated_height() // 2)

    def on_tab_drag_end(
        self,
        _source: Gtk.DragSource,
        _drag: Gdk.Drag,
        _delete_data: bool,
        session_id: str,
    ) -> None:
        session = self.session_registry.get(session_id)
        if session is not None:
            session.tab_label.remove_css_class("dragging")
        self.tab_drag_session_id = None

    def on_tab_bar_drop_motion(self, target: Gtk.DropTarget, x: float, _y: float) -> Gdk.DragAction:
        self.reorder_dragged_tab_at_bar_x(target, x)
        return Gdk.DragAction.MOVE

    def on_tab_bar_drop(self, target: Gtk.DropTarget, dragged_session_id: str, x: float, _y: float) -> bool:
        self.reorder_dragged_tab_at_bar_x(target, x, dragged_session_id)
        dragged = self.session_registry.get(dragged_session_id)
        if dragged is not None:
            self.set_active_session(dragged.id)
        return True

    def reorder_dragged_tab_at_bar_x(
        self,
        target: Gtk.DropTarget,
        pointer_x: float,
        dragged_session_id: str | None = None,
    ) -> None:
        dragged_session_id = dragged_session_id or getattr(self, "tab_drag_session_id", None) or target.get_value()
        if not isinstance(dragged_session_id, str):
            return
        dragged = self.session_registry.get(dragged_session_id)
        if dragged is None or dragged.detached_window is not None:
            return
        sessions = self.visible_sessions_in_tab_order()
        if len(sessions) <= 1:
            return
        try:
            dragged_index = sessions.index(dragged)
        except ValueError:
            return

        previous_sibling = dragged.tab_label.get_prev_sibling()
        for index, session in enumerate(sessions):
            if session.id == dragged_session_id:
                continue
            width = session.tab_label.get_allocated_width()
            ok, start = session.tab_label.compute_point(
                self.session_tab_bar, Graphene.Point().init(0, 0)
            )
            if not ok or pointer_x < start.x or pointer_x > start.x + width:
                continue

            if index < dragged_index:
                threshold = start.x + width * 0.8
                previous_sibling = session.tab_label.get_prev_sibling() if pointer_x < threshold else session.tab_label
            else:
                threshold = start.x + width * 0.2
                previous_sibling = session.tab_label if pointer_x > threshold else session.tab_label.get_prev_sibling()
            break

        if dragged.tab_label.get_prev_sibling() is previous_sibling:
            return
        self.session_tab_bar.reorder_child_after(dragged.tab_label, previous_sibling)
        self.update_session_tab_states()
        self.schedule_active_tab_reveal()

    def on_tab_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        session_id: str,
        parent: Gtk.Widget,
    ) -> None:
        session = self.session_registry.get(session_id)
        if session is None:
            return
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(parent)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("duplicate_tab"), lambda: self.duplicate_tab(popover, session))
        self.add_context_menu_item(menu, self.t("detach_tab"), lambda: self.detach_tab(popover, session))
        self.add_context_menu_item(menu, self.t("rename_tab"), lambda: self.show_rename_tab_dialog(popover, session))
        popover.set_child(menu)
        popover.popup()

    def duplicate_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        self.tab_lifecycle_actions.duplicate_session(session)

    def detach_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        if session.detached_window is not None:
            return
        previous_order = self.visible_sessions_in_tab_order()
        self.remove_session_from_main_view(session)
        self.focus_available_session_after_close(session.id, previous_order)
        window = Gtk.Window(
            title=session.title,
            application=self.get_application(),
        )
        if hasattr(window, "set_handle_menubar_accel"):
            window.set_handle_menubar_accel(False)
        titlebar = Gtk.HeaderBar()
        titlebar.set_title_widget(Gtk.Label(label=session.title))
        window.set_titlebar(titlebar)
        window.set_default_size(860, 520)
        window.set_child(session.page)
        session.detached_window = window
        self.update_session_tab_bar_visibility()
        self.sync_window_title_with_visible_session()
        window.connect("close-request", self.on_detached_window_close, session)
        window.present()
        log_event("tab.detached", session_id=session.id)

    def on_detached_window_close(self, window: Gtk.Window, session: TerminalSession) -> bool:
        window.set_child(None)
        session.detached_window = None
        if self.session_registry.contains(session.id):
            self.add_session_to_main_view(session)
            log_event("tab.reattached", session_id=session.id)
        return False

    def show_rename_tab_dialog(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        dialog = Gtk.Dialog(
            title=self.t("rename_tab"),
            transient_for=self.window_for_session(session),
            modal=True,
        )
        dialog.set_resizable(False)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        entry = Gtk.Entry(text=session.title)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        entry.connect("activate", lambda _entry: dialog.response(Gtk.ResponseType.OK))
        dialog.get_content_area().append(entry)
        dialog.connect("response", self.on_rename_tab_response, entry, session)
        dialog.present()
        entry.grab_focus()

    def window_for_session(self, session: TerminalSession) -> Gtk.Window:
        return session.detached_window or self

    def on_rename_tab_response(
        self, dialog: Gtk.Dialog, response: Gtk.ResponseType, entry: Gtk.Entry, session: TerminalSession
    ) -> None:
        title = entry.get_text().strip()
        if response == Gtk.ResponseType.OK and title:
            session.title = title
            session.title_locked = True
            self.update_session_tab_title(session, title)
            self.update_detached_window_title(session, title)
            self.sync_window_title_with_visible_session()
        dialog.destroy()

    def update_detached_window_title(self, session: TerminalSession, title: str) -> None:
        window = session.detached_window
        if window is None:
            return
        window.set_title(title)
        titlebar = window.get_titlebar()
        if not isinstance(titlebar, Gtk.HeaderBar):
            return
        title_widget = titlebar.get_title_widget()
        if isinstance(title_widget, Gtk.Label):
            title_widget.set_label(title)

    def on_request_close_tab(self, _button: Gtk.Button, session_id: str, page: Gtk.Widget) -> None:
        self.request_close_tab(session_id, page)

    def request_close_tab(self, session_id: str, page: Gtk.Widget) -> None:
        session = self.session_registry.get(session_id)
        if session and session.page == page and session.connected:
            if not self.store.data.app.confirm_disconnect:
                self.close_tab(session_id, page, disconnect=True)
                return
            detail = self.t("close_ssh_session_confirm") if session.server_id is not None else self.t("close_local_session_confirm")
            self.tab_lifecycle_actions.confirm_session_action(
                session,
                self.t("close_session_title"),
                detail,
                self.t("close"),
                lambda: self.close_tab(session_id, page, disconnect=True),
            )
            return
        self.close_tab(session_id, page, disconnect=False)

    def close_tab(self, session_id: str, page: Gtk.Widget, disconnect: bool) -> None:
        session = self.session_registry.get(session_id)
        if disconnect and session and session.page == page and session.connected:
            self.tab_lifecycle_actions.disconnect_session(session)
            session = self.session_registry.get(session_id)
        if session is None:
            return
        previous_order = self.visible_sessions_in_tab_order()
        self.tab_lifecycle_actions.terminate_split_processes(session)
        if session.detached_window is not None:
            window = session.detached_window
            session.detached_window = None
            window.set_child(None)
            window.destroy()
        else:
            self.remove_session_from_main_view(session)
        self.session_registry.remove(session_id)
        self.update_session_tab_bar_visibility()
        self.focus_available_session_after_close(session_id, previous_order)
        self.sync_window_title_with_visible_session()
        log_event("tab.closed", session_id=session_id, remaining_tabs=len(self.session_registry.sessions()))
