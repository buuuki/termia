# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango

from .debug import log_event
from .ui_state import TerminalSession

TERMINAL_TAB_DND_MIME_TYPE = "application/x-termia-terminal-tab-id"


class TabsMixin:
    def install_terminal_tab_drop_target(self) -> None:
        target = Gtk.DropTargetAsync.new(
            Gdk.ContentFormats.new([TERMINAL_TAB_DND_MIME_TYPE]), Gdk.DragAction.MOVE)
        target.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        target.connect("accept", self.on_tab_bar_drop_accept)
        target.connect("drag-motion", self.on_tab_bar_drop_motion)
        target.connect("drag-leave", self.on_tab_bar_drop_leave)
        target.connect("drop", self.on_tab_bar_drop)
        self.terminal_notebook.add_controller(target)

    def add_session_to_main_view(self, session: TerminalSession) -> None:
        self.terminal_notebook.append_page(session.page, session.tab_label)
        notebook_page = self.terminal_notebook.get_page(session.page)
        notebook_page.set_property("tab-expand", True)
        notebook_page.set_property("tab-fill", True)
        if not getattr(session.tab_label, "_termia_visibility_wired", False):
            session.tab_label.connect("map", self.on_terminal_tab_visibility_changed)
            session.tab_label.connect("unmap", self.on_terminal_tab_visibility_changed)
            session.tab_label._termia_visibility_wired = True
        # Keep Termia's private drag format; GTK owns selection and overflow.
        self.terminal_notebook.set_tab_reorderable(session.page, False)
        self.update_session_tab_bar_visibility()
        self.set_active_session(session.id)
        self.sync_window_title_with_visible_session()
        log_event("tab.attached", session_id=session.id)

    def visible_terminal_page(self) -> Gtk.Widget | None:
        return self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page())

    def on_terminal_page_switched(self, _notebook, page, _position) -> None:
        # switch-page runs before GTK updates current-page. Defer focus until
        # the change finishes and reject a page removed in the meantime.
        def focus_page() -> bool:
            if getattr(self, "shutdown_in_progress", False) or self.visible_terminal_page() is not page:
                return GLib.SOURCE_REMOVE
            for session in self.session_registry.sessions():
                if session.page is page and session.detached_window is None:
                    session.terminal.grab_focus()
                    break
            self.rebuild_tab_overflow_popover()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(focus_page)

    def on_terminal_page_reordered(self, *_args) -> None:
        self.rebuild_tab_overflow_popover()

    def on_terminal_tab_visibility_changed(self, *_args) -> None:
        if getattr(self, "tab_overflow_visibility_id", None) is None:
            self.tab_overflow_visibility_id = GLib.idle_add(self.update_tab_overflow_visibility)

    def update_tab_overflow_visibility(self) -> bool:
        self.tab_overflow_visibility_id = None
        if self.terminal_notebook.get_mapped():
            sessions = self.visible_sessions_in_tab_order()
            self.tab_overflow_button.set_visible(
                len(sessions) > 1 and any(not item.tab_label.get_mapped() for item in sessions))
        return GLib.SOURCE_REMOVE

    def visible_sessions_in_tab_order(self) -> list[TerminalSession]:
        sessions_by_page = {
            session.page: session
            for session in self.session_registry.sessions()
            if session.detached_window is None
        }
        ordered: list[TerminalSession] = []
        for position in range(self.terminal_notebook.get_n_pages()):
            session = sessions_by_page.get(self.terminal_notebook.get_nth_page(position))
            if session is not None:
                ordered.append(session)
        return ordered

    def set_active_session(self, session_id: str) -> None:
        session = self.session_registry.get(session_id)
        if session is None or session.detached_window is not None:
            return
        position = self.terminal_notebook.page_num(session.page)
        if position < 0:
            return
        self.terminal_notebook.set_current_page(position)
        self.rebuild_tab_overflow_popover()
        session.terminal.grab_focus()
        log_event("tab.selected", session_id=session.id)

    def rebuild_tab_overflow_popover(self) -> None:
        if not hasattr(self, "tab_overflow_button"):
            return
        popover = Gtk.PopoverMenu.new_from_model(None)
        popover.add_css_class("termia-menu-popover")
        menu = Gio.Menu()
        group = Gio.SimpleActionGroup()
        visible_page = self.visible_terminal_page()
        selected_id = ""
        for session in self.visible_sessions_in_tab_order():
            display_title = self.session_tab_display_title(session)
            if session.page is visible_page:
                selected_id = session.id
            item = Gio.MenuItem.new(display_title, None)
            item.set_action_and_target_value("tab-overflow.select", GLib.Variant("s", session.id))
            menu.append_item(item)
        select = Gio.SimpleAction.new_stateful("select", GLib.VariantType.new("s"),
                                              GLib.Variant("s", selected_id))

        def activate(_action, parameter):
            session_id = parameter.get_string()
            popover.popdown()

            def dispatch():
                session = self.session_registry.get(session_id)
                if session is not None and session.detached_window is None:
                    self.set_active_session(session_id)
                return GLib.SOURCE_REMOVE

            GLib.idle_add(dispatch)

        select.connect("activate", activate)
        group.add_action(select)
        popover.insert_action_group("tab-overflow", group)
        popover.set_menu_model(menu)
        self.configure_overflow_labels(popover, {self.session_tab_display_title(session)
                                               for session in self.visible_sessions_in_tab_order()})
        self.tab_overflow_button.set_popover(popover)

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
        if session.detached_window is None:
            position = self.terminal_notebook.page_num(session.page)
            if position >= 0:
                self.terminal_notebook.remove_page(position)
        self.update_session_tab_bar_visibility()

    def update_session_tab_bar_visibility(self) -> None:
        has_multiple_tabs = self.terminal_notebook.get_n_pages() > 1
        self.terminal_notebook.set_show_tabs(has_multiple_tabs)
        if not has_multiple_tabs:
            self.tab_overflow_button.set_visible(False)
        self.on_terminal_tab_visibility_changed()
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

    def build_tab_label(self, title: str, session_id: str, page: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.add_css_class("termia-tab-label")
        box.set_hexpand(True)
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
        close_button.set_valign(Gtk.Align.CENTER)
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
        session = self.session_registry.get(session_id)
        if session is None or session.detached_window is not None:
            return None
        if isinstance(_tab, Gtk.Widget):
            outer = _tab.get_parent()
            if outer is not None and outer.get_css_name() == "tab":
                valid, bounds = outer.compute_bounds(_tab)
                if valid:
                    _x -= bounds.get_x()
                    _y -= bounds.get_y()
        self.tab_drag_hotspot = (session_id, int(_x), int(_y))
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
        self.set_active_session(session_id)
        self.tab_drag_session_id = session_id
        self.tab_drag = _drag
        self.pending_tab_reorder = None
        self.pending_tab_drop = None
        # Keep the floating tab's selection tint separate from its source.
        preview = self.build_tab_drag_preview(tab)
        hotspot = getattr(self, "tab_drag_hotspot", None)
        if hotspot is not None and hotspot[0] == session_id:
            x, y = hotspot[1:]
        else:
            x, y = tab.get_width() // 2, tab.get_height() // 2
        Gtk.DragIcon.get_for_drag(_drag).set_child(preview)
        _drag.set_hotspot(x, y)
        tab.add_css_class("dragging")

    def build_tab_drag_preview(self, tab: Gtk.Widget) -> Gtk.Widget:
        preview = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        preview.add_css_class("termia-tab-drag-preview")
        outer = tab.get_parent()
        if outer is None or outer.get_css_name() != "tab":
            outer = tab
        valid, bounds = outer.compute_bounds(tab)
        if valid:
            preview.set_size_request(round(bounds.get_width()), round(bounds.get_height()))
        else:
            preview.set_size_request(tab.get_width(), tab.get_height())
        title = Gtk.Label(label=tab.get_first_child().get_label())
        title.add_css_class("termia-tab-title")
        title.set_hexpand(True)
        title.set_single_line_mode(True)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_margin_start(20)
        title.set_margin_end(4)
        close_icon = Gtk.Image.new_from_icon_name("window-close-symbolic")
        close_icon.set_margin_start(4)
        close_icon.set_margin_end(20)
        preview.append(title)
        preview.append(close_icon)
        return preview

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
        self.tab_drag = None
        self.tab_drag_hotspot = None
        self.pending_tab_reorder = None

    def on_tab_bar_drop_accept(self, _target: Gtk.DropTargetAsync, drop: Gdk.Drop) -> bool:
        session = self.session_registry.get(getattr(self, "tab_drag_session_id", None))
        return bool(
            session is not None and session.detached_window is None
            and not getattr(self, "shutdown_in_progress", False)
            and getattr(self, "tab_drag", None) is not None
            and drop.get_drag() == self.tab_drag
            and drop.get_formats().contain_mime_type(TERMINAL_TAB_DND_MIME_TYPE)
        )

    def tab_drop_is_in_header(self, x: float, y: float) -> bool:
        for session in self.visible_sessions_in_tab_order():
            label = session.tab_label
            if not label.get_mapped():
                continue
            valid, bounds = label.compute_bounds(self.terminal_notebook)
            if valid and bounds.get_y() <= y < bounds.get_y() + bounds.get_height():
                return 0 <= x < self.terminal_notebook.get_width()
        return False

    def on_tab_bar_drop_motion(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> Gdk.DragAction:
        if not self.on_tab_bar_drop_accept(target, drop) or not self.tab_drop_is_in_header(x, y):
            self.pending_tab_reorder = None
            return Gdk.DragAction(0)
        # Reordering here changes GTK's own tab enter/leave path while its
        # hover-switch timer is being dispatched. Coalesce movement after the
        # native event and revalidate the originating drag before touching pages.
        self.pending_tab_reorder = (target, drop, x, self.session_registry.get(self.tab_drag_session_id))
        if getattr(self, "pending_tab_reorder_id", None) is None:
            self.pending_tab_reorder_id = GLib.idle_add(self.apply_pending_tab_reorder)
        return Gdk.DragAction.MOVE

    def apply_pending_tab_reorder(self) -> bool:
        self.pending_tab_reorder_id = None
        pending = getattr(self, "pending_tab_reorder", None)
        self.pending_tab_reorder = None
        if pending is not None:
            target, drop, x, session = pending
            if (
                session is not None and self.tab_drag_session_id == session.id
                and self.session_registry.get(session.id) is session
                and self.on_tab_bar_drop_accept(target, drop)
            ):
                self.reorder_dragged_tab_at_bar_x(target, x, session.id)
        return GLib.SOURCE_REMOVE

    def on_tab_bar_drop_leave(self, *_args) -> None:
        self.pending_tab_reorder = None

    def on_tab_bar_drop(self, target: Gtk.DropTargetAsync, drop: Gdk.Drop, x: float, y: float) -> bool:
        self.pending_tab_reorder = None
        if not self.on_tab_bar_drop_accept(target, drop) or not self.tab_drop_is_in_header(x, y):
            return False
        token = object()
        self.pending_tab_drop = token
        drop.read_async(
            [TERMINAL_TAB_DND_MIME_TYPE], GLib.PRIORITY_DEFAULT, None,
            self.on_tab_bar_drop_read,
            (drop, self.tab_drag_session_id, target, x, token),
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
        _drop, expected_id, target, x, token = context
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
            self.reorder_dragged_tab_at_bar_x(target, x, expected_id)
            self.set_active_session(expected_id)
        self.finish_tab_drop(context, accepted)

    def finish_tab_drop(self, context, accepted: bool) -> None:
        drop, _expected_id, _target, _x, token = context
        if getattr(self, "pending_tab_drop", None) is token:
            self.pending_tab_drop = None
        drop.finish(Gdk.DragAction.MOVE if accepted else Gdk.DragAction(0))

    def reorder_dragged_tab_at_bar_x(
        self,
        target: Gtk.DropTargetAsync,
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

        destination = dragged_index
        for index, session in enumerate(sessions):
            if session.id == dragged_session_id or not session.tab_label.get_mapped():
                continue
            width = session.tab_label.get_allocated_width()
            ok, start = session.tab_label.compute_point(
                self.terminal_notebook, Graphene.Point().init(0, 0)
            )
            if not ok or pointer_x < start.x or pointer_x > start.x + width:
                continue

            if index < dragged_index:
                threshold = start.x + width * 0.8
                destination = index if pointer_x < threshold else index + 1
            else:
                threshold = start.x + width * 0.2
                destination = index if pointer_x > threshold else index - 1
            break

        if dragged_index == destination:
            return
        self.terminal_notebook.reorder_child(dragged.page, destination)
        self.rebuild_tab_overflow_popover()

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
        popover.set_has_arrow(False)
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
        self.cancel_file_transfers(session.id, close_dialog=True)
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
