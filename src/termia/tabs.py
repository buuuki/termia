# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import weakref

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango

from .debug import log_event
from .dialog_window import DialogWindow
from .ui_state import SignalConnections, TerminalSession

TERMINAL_TAB_DND_MIME_TYPE = "application/x-termia-terminal-tab-id"


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


class TabsMixin:
    TAB_OVERFLOW_EPSILON = 1.0

    def visible_terminal_page(self) -> Gtk.Widget | None:
        return self.terminal_stack.get_visible_child()

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
        if getattr(self, "tab_drag_session_id", None) is None:
            self.invalidate_tab_overflow_menu()

    def schedule_active_tab_reveal(self) -> None:
        pending_id = getattr(self, "active_tab_reveal_id", None)
        if pending_id is not None:
            GLib.source_remove(pending_id)
        self.active_tab_reveal_id = None
        if getattr(self, "tab_drag_session_id", None) is not None:
            return
        self.active_tab_reveal_id = GLib.idle_add(self.reveal_active_tab)

    def reveal_active_tab(self) -> bool:
        self.active_tab_reveal_id = None
        if getattr(self, "tab_drag_session_id", None) is not None:
            return GLib.SOURCE_REMOVE
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

    def initialize_tab_overflow_menu(self) -> None:
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        group = Gio.SimpleActionGroup()
        select = Gio.SimpleAction.new_stateful("select", GLib.VariantType.new("s"),
                                              GLib.Variant("s", ""))
        host_ref = weakref.ref(self)
        popover_ref = popover.weak_ref()

        def activate(_action, parameter):
            session_id = parameter.get_string()
            current = popover_ref()
            if current is None:
                return
            current.popdown()

            def dispatch():
                host = host_ref()
                if host is None or getattr(host, "shutdown_in_progress", False):
                    return GLib.SOURCE_REMOVE
                session = host.session_registry.get(session_id)
                if session is not None and session.detached_window is None:
                    host.set_active_session(session_id)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(dispatch)

        def prepare_menu(_popover):
            host = host_ref()
            if host is not None:
                host.refresh_tab_overflow_menu()

        select.connect("activate", activate)
        group.add_action(select)
        popover.insert_action_group("tab-overflow", group)
        self.tab_overflow_menu = Gio.Menu()
        self.tab_overflow_select_action = select
        self.tab_overflow_entries = None
        popover.set_menu_model(self.tab_overflow_menu)
        popover.connect("show", prepare_menu)
        self.tab_overflow_button.set_popover(popover)

    def invalidate_tab_overflow_menu(self) -> None:
        """Dismiss stale contents; refresh only when GTK next shows the menu."""
        if not hasattr(self, "tab_overflow_button"):
            return
        popover = self.tab_overflow_button.get_popover()
        if popover is not None and popover.get_visible():
            popover.popdown()

    def refresh_tab_overflow_menu(self) -> None:
        sessions = self.visible_sessions_in_tab_order()
        entries = tuple((session.id, self.session_tab_display_title(session))
                        for session in sessions)
        if entries != self.tab_overflow_entries:
            self.tab_overflow_menu.remove_all()
            for session_id, title in entries:
                item = Gio.MenuItem.new(title, None)
                item.set_action_and_target_value(
                    "tab-overflow.select", GLib.Variant("s", session_id)
                )
                self.tab_overflow_menu.append_item(item)
            self.tab_overflow_entries = entries
        visible_page = self.terminal_stack.get_visible_child()
        selected_id = next((session.id for session in sessions
                            if session.page is visible_page), "")
        self.tab_overflow_select_action.set_state(GLib.Variant("s", selected_id))
        self.configure_overflow_labels(
            self.tab_overflow_button.get_popover(), {title for _id, title in entries}
        )

    @staticmethod
    def configure_overflow_labels(widget: Gtk.Widget, titles: set[str]) -> None:
        """Keep native menu labels readable for long session titles."""
        if isinstance(widget, Gtk.Label) and widget.get_label() in titles:
            widget.set_wrap(True)
            widget.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            widget.set_max_width_chars(50)
            widget.set_ellipsize(Pango.EllipsizeMode.NONE)
            widget.set_tooltip_text(widget.get_label())
        child = widget.get_first_child()
        while child is not None:
            TabsMixin.configure_overflow_labels(child, titles)
            child = child.get_next_sibling()

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

    def remove_session_from_main_view(self, session: TerminalSession) -> None:
        if getattr(self, "tab_drag_session_id", None) == session.id:
            self.stop_tab_drag_scroll()
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
        self.invalidate_tab_overflow_menu()

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
        self.invalidate_tab_overflow_menu()
        self.schedule_active_tab_reveal()
        self.schedule_tab_overflow_visibility()

    def build_tab_label(self, title: str, session_id: str, page: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        signals = box._termia_signals = SignalConnections()
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
        signals.connect(close_button, "clicked", self.on_request_close_tab, session_id, page)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        signals.connect(left_click, "pressed", self.on_tab_left_press, session_id)
        box.add_controller(left_click)
        middle_click = Gtk.GestureClick.new()
        middle_click.set_button(2)
        signals.connect(middle_click, "pressed", self.on_tab_middle_press, session_id, page)
        box.add_controller(middle_click)
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        signals.connect(drag_source, "prepare", self.on_tab_drag_prepare, session_id, box)
        signals.connect(drag_source, "drag-begin", self.on_tab_drag_begin, session_id, box)
        signals.connect(drag_source, "drag-end", self.on_tab_drag_end, session_id)
        box.add_controller(drag_source)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        signals.connect(right_click, "pressed", self.on_tab_right_click, session_id, box)
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
        session = self.session_registry.get(session_id)
        if session is None or session.detached_window is not None:
            return None
        return Gdk.ContentProvider.new_for_bytes(
            TERMINAL_TAB_DND_MIME_TYPE, GLib.Bytes.new(session_id.encode("utf-8"))
        )

    def on_tab_drag_begin(
        self,
        source: Gtk.DragSource,
        _drag: Gdk.Drag,
        session_id: str,
        tab: Gtk.Widget,
    ) -> None:
        self.stop_tab_drag_scroll()
        self.set_active_session(session_id)
        self.tab_drag_initial_order = tuple(
            session.id for session in self.visible_sessions_in_tab_order()
        )
        self.tab_drag_session_id = session_id
        self.tab_drag = _drag
        self.pending_tab_drop = None
        tab.add_css_class("dragging")
        source.set_icon(Gtk.WidgetPaintable.new(tab), tab.get_allocated_width() // 2, tab.get_allocated_height() // 2)

    def on_tab_drag_end(
        self,
        _source: Gtk.DragSource,
        _drag: Gdk.Drag,
        _delete_data: bool,
        session_id: str,
    ) -> None:
        self.stop_tab_drag_scroll()
        session = self.session_registry.get(session_id)
        if session is not None:
            session.tab_label.remove_css_class("dragging")
        self.tab_drag_session_id = None
        self.tab_drag = None
        initial_order = getattr(self, "tab_drag_initial_order", None)
        self.tab_drag_initial_order = None
        final_order = tuple(session.id for session in self.visible_sessions_in_tab_order())
        if initial_order is not None and final_order != initial_order:
            self.invalidate_tab_overflow_menu()
        self.schedule_active_tab_reveal()

    def on_tab_bar_drop_accept(self, _target: Gtk.DropTargetAsync, drop: Gdk.Drop) -> bool:
        session = self.session_registry.get(getattr(self, "tab_drag_session_id", None))
        return bool(
            session is not None and session.detached_window is None
            and not getattr(self, "shutdown_in_progress", False)
            and getattr(self, "tab_drag", None) is not None
            and drop.get_drag() == self.tab_drag
            and drop.get_formats().contain_mime_type(TERMINAL_TAB_DND_MIME_TYPE)
        )

    def on_tab_bar_drop_motion(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> Gdk.DragAction:
        if not self.on_tab_bar_drop_accept(target, drop):
            self.stop_tab_drag_scroll()
            return Gdk.DragAction(0)
        valid, point = self.session_tab_scroller.compute_point(
            self.session_tab_bar, Graphene.Point().init(x, y)
        )
        if not valid:
            self.stop_tab_drag_scroll()
            return Gdk.DragAction(0)
        self.reorder_dragged_tab_at_bar_x(point.x)
        adjustment = self.session_tab_scroller.get_hadjustment()
        if self.tab_drag_scroll_delta(x, adjustment.get_page_size()) == 0:
            self.stop_tab_drag_scroll()
        else:
            self.tab_drag_scroll_context = (target, drop, x, y)
            if getattr(self, "tab_drag_scroll_id", None) is None:
                self.tab_drag_scroll_id = GLib.timeout_add(35, self.scroll_tabs_during_drag)
        return Gdk.DragAction.MOVE

    @staticmethod
    def tab_drag_scroll_delta(x: float, width: float) -> float:
        if width <= 0 or x < 0 or x > width:
            return 0
        edge = min(56.0, width / 4)
        if x < edge:
            return -max(6.0, 24.0 * (edge - x) / edge)
        if x > width - edge:
            return max(6.0, 24.0 * (x - width + edge) / edge)
        return 0

    def stop_tab_drag_scroll(self) -> None:
        source_id = getattr(self, "tab_drag_scroll_id", None)
        self.tab_drag_scroll_id = None
        self.tab_drag_scroll_context = None
        if source_id is not None:
            GLib.source_remove(source_id)

    def scroll_tabs_during_drag(self) -> bool:
        context = getattr(self, "tab_drag_scroll_context", None)
        if context is None:
            self.tab_drag_scroll_id = None
            return GLib.SOURCE_REMOVE
        target, drop, x, y = context
        if not self.on_tab_bar_drop_accept(target, drop) or not self.session_tab_scroller.get_mapped():
            self.tab_drag_scroll_id = None
            self.tab_drag_scroll_context = None
            return GLib.SOURCE_REMOVE
        adjustment = self.session_tab_scroller.get_hadjustment()
        previous = adjustment.get_value()
        maximum = max(adjustment.get_lower(), adjustment.get_upper() - adjustment.get_page_size())
        value = min(maximum, max(adjustment.get_lower(), previous +
                    self.tab_drag_scroll_delta(x, adjustment.get_page_size())))
        valid, point = self.session_tab_scroller.compute_point(
            self.session_tab_bar, Graphene.Point().init(x, y)
        )
        if not valid or value == previous:
            self.tab_drag_scroll_id = None
            self.tab_drag_scroll_context = None
            return GLib.SOURCE_REMOVE
        adjustment.set_value(value)
        self.reorder_dragged_tab_at_bar_x(point.x + value - previous)
        return GLib.SOURCE_CONTINUE

    def on_tab_bar_drop_leave(self, *_args) -> None:
        self.stop_tab_drag_scroll()

    def on_tab_bar_drop(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> bool:
        self.stop_tab_drag_scroll()
        if not self.on_tab_bar_drop_accept(target, drop):
            return False
        valid, point = self.session_tab_scroller.compute_point(
            self.session_tab_bar, Graphene.Point().init(x, y)
        )
        if not valid:
            return False
        token = object()
        self.pending_tab_drop = token
        drop.read_async(
            [TERMINAL_TAB_DND_MIME_TYPE], GLib.PRIORITY_DEFAULT, None,
            self.on_tab_bar_drop_read,
            (drop, self.tab_drag_session_id, target, point.x, token),
        )
        return True

    def on_tab_bar_drop_read(self, drop, result, context) -> None:
        try:
            stream, mime_type = drop.read_finish(result)
        except GLib.Error:
            self.finish_tab_drop(context, False)
            return
        if stream is None or mime_type != TERMINAL_TAB_DND_MIME_TYPE:
            if stream is not None:
                stream.close_async(GLib.PRIORITY_DEFAULT, None, None)
            self.finish_tab_drop(context, False)
            return
        stream.read_bytes_async(
            256, GLib.PRIORITY_DEFAULT, None, self.on_tab_bar_drop_bytes_read, context
        )

    def on_tab_bar_drop_bytes_read(self, stream, result, context) -> None:
        _drop, expected_id, _target, x, token = context
        try:
            received_id = stream.read_bytes_finish(result).get_data().decode("utf-8")
        except (GLib.Error, UnicodeError):
            received_id = None
        finally:
            stream.close_async(GLib.PRIORITY_DEFAULT, None, None)
        session = self.session_registry.get(expected_id)
        accepted = (
            getattr(self, "pending_tab_drop", None) is token
            and received_id == expected_id and session is not None
            and session.detached_window is None
            and not getattr(self, "shutdown_in_progress", False)
        )
        if accepted:
            self.reorder_dragged_tab_at_bar_x(x, expected_id)
            self.set_active_session(expected_id)
        self.finish_tab_drop(context, accepted)

    def finish_tab_drop(self, context, accepted: bool) -> None:
        drop, _expected_id, _target, _x, token = context
        if getattr(self, "pending_tab_drop", None) is token:
            self.pending_tab_drop = None
        drop.finish(Gdk.DragAction.MOVE if accepted else Gdk.DragAction(0))

    def reorder_dragged_tab_at_bar_x(
        self,
        pointer_x: float,
        dragged_session_id: str | None = None,
    ) -> None:
        dragged_session_id = dragged_session_id or getattr(self, "tab_drag_session_id", None)
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

        first_ok, first_bounds = sessions[0].tab_label.compute_bounds(self.session_tab_bar)
        last_ok, last_bounds = sessions[-1].tab_label.compute_bounds(self.session_tab_bar)
        if first_ok and last_ok:
            pointer_x = max(first_bounds.get_x(), min(
                last_bounds.get_x() + last_bounds.get_width(), pointer_x))
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
        self.schedule_active_tab_reveal()

    def on_tab_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        session_id: str,
        parent: Gtk.Widget,
    ) -> None:
        session = self.session_registry.get(session_id)
        if (
            session is None
            or session.detached_window is not None
            or session.tab_label is not parent
            or getattr(self, "shutdown_in_progress", False)
        ):
            return
        model = Gio.Menu()
        action_group = Gio.SimpleActionGroup()
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(True)
        popover.set_parent(parent)
        rect = Gdk.Rectangle()
        rect.x, rect.y = int(x), int(y)
        rect.width = rect.height = 1
        popover.set_pointing_to(rect)

        def release_popover() -> bool:
            if popover.get_parent() is not None:
                popover.unparent()
            return GLib.SOURCE_REMOVE

        # Model buttons may close their popover before activating its action.
        # Keep the action group attached until that GTK event has finished.
        popover.connect("closed", lambda *_: GLib.idle_add(release_popover))

        def run_command(callback) -> bool:
            if (
                self.session_registry.get(session_id) is session
                and session.tab_label is parent
                and session.detached_window is None
                and not getattr(self, "shutdown_in_progress", False)
            ):
                callback(popover, session)
            return GLib.SOURCE_REMOVE

        def activate_command(_action, _parameter, callback) -> None:
            popover.popdown()
            GLib.idle_add(run_command, callback)

        for name, callback in (
            ("duplicate_tab", self.duplicate_tab),
            ("detach_tab", self.detach_tab),
            ("rename_tab", self.show_rename_tab_dialog),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", activate_command, callback)
            action_group.add_action(action)
            model.append(self.t(name), f"tab-menu.{name}")
        popover.insert_action_group("tab-menu", action_group)
        popover.set_menu_model(model)
        popover.popup()
        GLib.idle_add(_clear_initial_menu_selection, popover)

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
        if session.detached_window is not window:
            return False
        if not getattr(window, "termia_close_pending", False):
            window.termia_close_pending = True
            GLib.idle_add(self.finish_detached_window_close, window, session)
        return True

    def finish_detached_window_close(
        self,
        window: Gtk.Window,
        session: TerminalSession,
    ) -> bool:
        window.termia_close_pending = False
        if (
            session.detached_window is window
            and self.session_registry.contains(session.id)
        ):
            self.request_close_tab(session.id, session.page)
        return GLib.SOURCE_REMOVE

    def reattach_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        window = session.detached_window
        if window is None or not self.session_registry.contains(session.id):
            return
        window.set_child(None)
        session.detached_window = None
        window.destroy()
        self.add_session_to_main_view(session)
        log_event("tab.reattached", session_id=session.id)

    def show_rename_tab_dialog(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        dialog = DialogWindow(
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
        self, dialog: DialogWindow, response: Gtk.ResponseType, entry: Gtk.Entry, session: TerminalSession
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
        self.cancel_file_transfers(session.id, close_dialog=True)
        if session.detached_window is not None:
            window = session.detached_window
            session.detached_window = None
            window.set_child(None)
            window.destroy()
        else:
            self.remove_session_from_main_view(session)
        self.session_registry.remove(session_id)
        session.retire()
        self.update_session_tab_bar_visibility()
        self.focus_available_session_after_close(session_id, previous_order)
        self.sync_window_title_with_visible_session()
        log_event("tab.closed", session_id=session_id, remaining_tabs=len(self.session_registry.sessions()))
