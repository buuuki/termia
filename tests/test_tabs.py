import unittest
import time
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from gi.repository import Gio, GObject

from termia.session_registry import SessionRegistry
from termia.tab_lifecycle_actions import TabLifecycleActions
from termia.tabs import Gdk, GLib, Graphene, Gtk, TERMINAL_TAB_DND_MIME_TYPE, TabsMixin


class NativeOverflowMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        self.button = Gtk.MenuButton(label="Tabs")
        self.window.set_child(self.button)
        self.window.present()
        self.addCleanup(self.window.destroy)
        self.host = TabsMixin()
        self.host.tab_overflow_button = self.button
        self.sessions = []
        for index in range(40):
            title = f"Session {index}: " + "long title " * 12
            label = Gtk.Box()
            label.append(Gtk.Label(label=title))
            self.sessions.append(SimpleNamespace(id=str(index), title=title,
                tab_label=label, page=Gtk.Box(), detached_window=None))
        self.host.session_registry = SessionRegistry(self.sessions)
        self.host.visible_sessions_in_tab_order = lambda: self.sessions
        self.host.visible_terminal_page = lambda: self.sessions[1].page
        self.host.set_active_session = MagicMock()

    def drain(self):
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

    def test_all_long_titles_order_state_and_selection_are_preserved(self):
        self.host.rebuild_tab_overflow_popover()
        menu = self.button.get_popover()
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        model = menu.get_menu_model()
        self.assertEqual(model.get_n_items(), 40)
        self.assertEqual([model.get_item_attribute_value(i, "label", None).unpack() for i in range(40)],
                         [session.title for session in self.sessions])
        labels = []
        def collect(widget):
            if isinstance(widget, Gtk.Label) and widget.get_label() in {session.title for session in self.sessions}:
                labels.append(widget)
            child = widget.get_first_child()
            while child is not None:
                collect(child)
                child = child.get_next_sibling()
        collect(menu)
        self.assertEqual(len(labels), 40)
        self.assertTrue(all(label.get_wrap() and label.get_max_width_chars() == 50 for label in labels))
        selected = next(label for label in labels if label.get_label() == self.sessions[1].title)
        self.assertTrue(selected.get_parent().get_property("active"))
        menu.activate_action("tab-overflow.select", GLib.Variant("s", "39"))
        self.drain()
        self.host.set_active_session.assert_called_once_with("39")

    def test_removed_or_detached_session_cannot_be_selected_from_stale_menu(self):
        self.host.rebuild_tab_overflow_popover()
        menu = self.button.get_popover()
        menu.activate_action("tab-overflow.select", GLib.Variant("s", "2"))
        self.sessions[2].detached_window = object()
        self.drain()
        self.host.set_active_session.assert_not_called()
        menu.activate_action("tab-overflow.select", GLib.Variant("s", "3"))
        self.host.session_registry.remove("3")
        self.drain()
        self.host.set_active_session.assert_not_called()


class PrivateTabDragTests(unittest.TestCase):
    def setUp(self):
        self.host = TabsMixin()
        self.session = SimpleNamespace(id="session-one", detached_window=None)
        self.host.session_registry = SessionRegistry([self.session])
        self.host.tab_drag_session_id = self.session.id
        self.host.tab_drag = object()
        self.host.reorder_dragged_tab_at_bar_x = MagicMock()
        self.host.tab_drop_is_in_header = MagicMock(return_value=True)
        self.host.set_active_session = MagicMock()
        self.drop = MagicMock()
        self.drop.get_drag.return_value = self.host.tab_drag
        self.drop.get_formats.return_value = Gdk.ContentFormats.new([TERMINAL_TAB_DND_MIME_TYPE])

    def test_source_is_private_and_not_convertible_to_text(self):
        provider = self.host.on_tab_drag_prepare(None, 0, 0, self.session.id, None)
        formats = provider.ref_formats()
        self.assertTrue(formats.contain_mime_type(TERMINAL_TAB_DND_MIME_TYPE))
        self.assertFalse(formats.contain_gtype(GObject.TYPE_STRING))
        self.assertFalse(formats.match(Gdk.ContentProvider.new_for_value("ordinary text").ref_formats()))
        self.session.detached_window = object()
        self.assertIsNone(self.host.on_tab_drag_prepare(None, 0, 0, self.session.id, None))

    def test_accept_rejects_foreign_text_missing_and_detached_sessions(self):
        self.assertTrue(self.host.on_tab_bar_drop_accept(None, self.drop))
        for condition in ("foreign", "text", "deleted", "detached", "shutdown"):
            with self.subTest(condition=condition):
                with patch.object(self.host, "tab_drag", object() if condition == "foreign" else self.host.tab_drag), \
                     patch.object(self.drop, "get_formats", return_value=Gdk.ContentFormats.new(
                         ["text/plain"] if condition == "text" else [TERMINAL_TAB_DND_MIME_TYPE])), \
                     patch.object(self.session, "detached_window", object() if condition == "detached" else None), \
                     patch.object(self.host, "shutdown_in_progress", condition == "shutdown", create=True):
                    if condition == "deleted":
                        self.host.session_registry.remove(self.session.id)
                    self.assertFalse(self.host.on_tab_bar_drop(None, self.drop, 20, 0))
                    if condition == "deleted":
                        self.host.session_registry.register(self.session)
        self.drop.read_async.assert_not_called()

    def test_separate_drag_preview_keeps_grab_point_without_coloring_source(self):
        for x in (7, 173):
            with self.subTest(grab_x=x):
                tab = MagicMock()
                self.session.tab_label = tab
                source = MagicMock()
                preview = MagicMock()
                drag = MagicMock()
                icon = MagicMock()
                self.host.on_tab_drag_prepare(source, x, 9, self.session.id, tab)
                with patch.object(self.host, "build_tab_drag_preview", return_value=preview), \
                     patch.object(Gtk.DragIcon, "get_for_drag", return_value=icon):
                    self.host.on_tab_drag_begin(source, drag, self.session.id, tab)
                icon.set_child.assert_called_once_with(preview)
                drag.set_hotspot.assert_called_once_with(x, 9)
                tab.add_css_class.assert_called_once_with("dragging")
                self.host.reorder_dragged_tab_at_bar_x.assert_not_called()
                self.host.on_tab_drag_end(source, self.host.tab_drag, False, self.session.id)
                self.assertIsNone(self.host.tab_drag_hotspot)
                tab.remove_css_class.assert_called_once_with("dragging")

    def test_async_drop_validates_payload_and_lifetime_after_drag_end(self):
        for condition in ("valid", "wrong-id", "invalid-utf8", "stale", "deleted", "detached", "shutdown", "read-error"):
            with self.subTest(condition=condition):
                self.setUp()
                self.assertTrue(self.host.on_tab_bar_drop(None, self.drop, 20, 0))
                context = self.drop.read_async.call_args.args[-1]
                self.host.tab_drag_session_id = None
                self.host.tab_drag = None
                stream = MagicMock()
                payload = b"wrong" if condition == "wrong-id" else b"\xff" if condition == "invalid-utf8" else b"session-one"
                stream.read_bytes_finish.return_value = GLib.Bytes.new(payload)
                if condition == "stale":
                    self.host.pending_tab_drop = object()
                elif condition == "deleted":
                    self.host.session_registry.remove(self.session.id)
                elif condition == "detached":
                    self.session.detached_window = object()
                elif condition == "shutdown":
                    self.host.shutdown_in_progress = True
                elif condition == "read-error":
                    stream.read_bytes_finish.side_effect = GLib.Error("read failed")
                self.host.on_tab_bar_drop_bytes_read(stream, None, context)
                accepted = condition == "valid"
                self.drop.finish.assert_called_once_with(Gdk.DragAction.MOVE if accepted else Gdk.DragAction(0))
                self.assertEqual(self.host.set_active_session.call_count, int(accepted))
                self.assertEqual(self.host.reorder_dragged_tab_at_bar_x.call_count, int(accepted))
                stream.close_async.assert_called_once()

    def test_async_read_rejects_wrong_format_and_io_failure(self):
        for condition in ("wrong-mime", "no-stream", "error"):
            with self.subTest(condition=condition):
                self.setUp()
                self.host.on_tab_bar_drop(None, self.drop, 20, 0)
                context = self.drop.read_async.call_args.args[-1]
                stream = MagicMock()
                self.drop.read_finish.return_value = (None if condition == "no-stream" else stream, "text/plain")
                if condition == "error":
                    self.drop.read_finish.side_effect = GLib.Error("read failed")
                self.host.on_tab_bar_drop_read(self.drop, None, context)
                self.drop.finish.assert_called_once_with(Gdk.DragAction(0))
                stream.read_bytes_async.assert_not_called()

    def test_motion_reorders_only_the_current_local_drag(self):
        self.assertEqual(self.host.on_tab_bar_drop_motion(None, self.drop, 20, 0), Gdk.DragAction.MOVE)
        self.host.reorder_dragged_tab_at_bar_x.assert_not_called()
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        self.host.reorder_dragged_tab_at_bar_x.assert_called_once_with(None, 20, self.session.id)
        self.drop.get_drag.return_value = object()
        self.assertEqual(self.host.on_tab_bar_drop_motion(None, self.drop, 20, 0), Gdk.DragAction(0))
        self.assertEqual(self.host.reorder_dragged_tab_at_bar_x.call_count, 1)

    def test_pending_motion_coalesces_and_revalidates_after_native_event(self):
        for reason in ("latest", "leave", "end", "removed", "replaced", "foreign", "shutdown"):
            with self.subTest(reason=reason):
                self.setUp()
                self.host.on_tab_bar_drop_motion(None, self.drop, 20, 0)
                self.host.on_tab_bar_drop_motion(None, self.drop, 80, 0)
                if reason == "leave":
                    self.host.on_tab_bar_drop_leave()
                elif reason == "end":
                    self.host.tab_drag = None
                elif reason == "removed":
                    self.host.session_registry.remove(self.session.id)
                elif reason == "replaced":
                    self.host.session_registry.remove(self.session.id)
                    self.host.session_registry.register(SimpleNamespace(id=self.session.id, detached_window=None))
                elif reason == "foreign":
                    self.drop.get_drag.return_value = object()
                elif reason == "shutdown":
                    self.host.shutdown_in_progress = True
                self.host.reorder_dragged_tab_at_bar_x.assert_not_called()
                while GLib.MainContext.default().pending():
                    GLib.MainContext.default().iteration(False)
                if reason == "latest":
                    self.host.reorder_dragged_tab_at_bar_x.assert_called_once_with(None, 80, self.session.id)
                else:
                    self.host.reorder_dragged_tab_at_bar_x.assert_not_called()

    def test_drop_over_terminal_content_does_not_reorder_tabs(self):
        self.host.tab_drop_is_in_header.return_value = False
        self.assertEqual(self.host.on_tab_bar_drop_motion(None, self.drop, 20, 200), Gdk.DragAction(0))
        self.assertFalse(self.host.on_tab_bar_drop(None, self.drop, 20, 200))
        self.host.reorder_dragged_tab_at_bar_x.assert_not_called()
        self.drop.read_async.assert_not_called()

    def test_real_async_stream_reorders_widgets_and_preserves_visual_order(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        notebook = Gtk.Notebook()
        window = Gtk.Window()
        window.set_default_size(600, 200)
        window.set_child(notebook)
        self.addCleanup(window.destroy)
        sessions = []
        for session_id in ("first", "second", "third"):
            label = Gtk.Label(label=session_id)
            label.set_size_request(100, 30)
            page = Gtk.Box()
            notebook.append_page(page, label)
            sessions.append(SimpleNamespace(id=session_id, page=page, tab_label=label, detached_window=None))
        window.present()
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.001)
        self.host.terminal_notebook = notebook
        self.host.session_registry = SessionRegistry(sessions)
        self.host.tab_drag_session_id = "third"
        self.host.reorder_dragged_tab_at_bar_x = TabsMixin.reorder_dragged_tab_at_bar_x.__get__(self.host)
        valid, bounds = sessions[0].tab_label.compute_bounds(notebook)
        self.assertTrue(valid)
        self.host.on_tab_bar_drop(None, self.drop, bounds.get_x() + 1, 0)
        context = self.drop.read_async.call_args.args[-1]
        stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(b"third"))
        self.drop.read_finish.return_value = (stream, TERMINAL_TAB_DND_MIME_TYPE)
        self.host.on_tab_bar_drop_read(self.drop, None, context)
        deadline = time.monotonic() + 2
        while not self.drop.finish.called and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.001)
        self.drop.finish.assert_called_once_with(Gdk.DragAction.MOVE)
        self.assertEqual([session.id for session in self.host.visible_sessions_in_tab_order()], ["third", "first", "second"])
        self.host.set_active_session.assert_called_once_with("third")


class TabContextMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        bar = Gtk.Box()
        self.tab = Gtk.Box()
        self.tab.set_size_request(220, 40)
        self.tab.append(Gtk.Label(label="Clicked tab"))
        bar.append(self.tab)
        other_tab = Gtk.Box()
        other_tab.append(Gtk.Label(label="Active tab"))
        bar.append(other_tab)
        self.window.set_child(bar)
        self.window.present()
        self.addCleanup(self.destroy_window)
        self.session = SimpleNamespace(id="clicked", tab_label=self.tab, detached_window=None)
        self.other = SimpleNamespace(id="active", tab_label=other_tab, detached_window=None)
        self.host = TabsMixin()
        self.host.t = lambda key: key
        self.host.session_registry = SessionRegistry([self.session, self.other])
        self.host.duplicate_tab = MagicMock()
        self.host.detach_tab = MagicMock()
        self.host.show_rename_tab_dialog = MagicMock()

    def destroy_window(self) -> None:
        for menu in self.menus():
            menu.popdown()
            if menu.get_parent() is not None:
                menu.unparent()
        self.window.destroy()

    def menus(self):
        result = []
        child = self.tab.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Popover):
                result.append(child)
            child = child.get_next_sibling()
        return result

    @staticmethod
    def drain_events():
        context = GLib.MainContext.default()
        for _ in range(100):
            if not context.pending():
                break
            context.iteration(False)

    def open_menu(self, x=15.0, y=20.0):
        self.host.on_tab_right_click(None, 1, x, y, self.session.id, self.tab)
        menus = self.menus()
        self.assertEqual(len(menus), 1)
        return menus[0]

    def test_menu_anchors_to_different_click_positions_and_preserves_commands(self) -> None:
        for x, y in ((5.75, 8.25), (110.0, 20.0), (190.5, 32.75)):
            with self.subTest(x=x, y=y):
                menu = self.open_menu(x, y)
                self.assertIsInstance(menu, Gtk.PopoverMenu)
                valid, rect = menu.get_pointing_to()
                self.assertTrue(valid)
                self.assertEqual((rect.x, rect.y, rect.width, rect.height),
                                 (int(x), int(y), 1, 1))
                model = menu.get_menu_model()
                self.assertEqual([
                    model.get_item_attribute_value(i, "label", None).unpack()
                    for i in range(model.get_n_items())
                ], ["duplicate_tab", "detach_tab", "rename_tab"])
                menu.popdown()
                self.drain_events()
                self.assertIsNone(menu.get_parent())
                self.assertEqual(self.menus(), [])

    def test_actions_close_menu_then_defer_dispatch_to_the_clicked_tab(self) -> None:
        for name, command in (
            ("duplicate_tab", self.host.duplicate_tab),
            ("detach_tab", self.host.detach_tab),
            ("rename_tab", self.host.show_rename_tab_dialog),
        ):
            with self.subTest(action=name):
                menu = self.open_menu()
                with patch("termia.tabs.GLib.idle_add") as schedule:
                    self.assertTrue(menu.activate_action(f"tab-menu.{name}", None))
                self.assertFalse(menu.get_visible())
                command.assert_not_called()
                release = schedule.call_args_list[0].args[0]
                self.assertEqual(release(), GLib.SOURCE_REMOVE)
                self.assertIsNone(menu.get_parent())
                deferred, callback = schedule.call_args.args
                self.assertEqual(deferred(callback), GLib.SOURCE_REMOVE)
                command.assert_called_once_with(menu, self.session)
                command.reset_mock()

    def test_pending_actions_reject_removed_replaced_detached_and_shutdown_targets(self) -> None:
        for condition in ("removed", "replaced", "detached", "new-label", "shutdown"):
            with self.subTest(condition=condition):
                self.host.session_registry = SessionRegistry([self.session, self.other])
                self.session.detached_window = None
                self.session.tab_label = self.tab
                self.host.shutdown_in_progress = False
                menu = self.open_menu()
                with patch("termia.tabs.GLib.idle_add") as schedule:
                    menu.activate_action("tab-menu.duplicate_tab", None)
                schedule.call_args_list[0].args[0]()
                deferred, callback = schedule.call_args.args
                if condition in ("removed", "replaced"):
                    self.host.session_registry.remove(self.session.id)
                    if condition == "replaced":
                        self.host.session_registry.register(SimpleNamespace(
                            id=self.session.id, tab_label=self.tab, detached_window=None,
                        ))
                elif condition == "detached":
                    self.session.detached_window = object()
                elif condition == "new-label":
                    self.session.tab_label = Gtk.Box()
                else:
                    self.host.shutdown_in_progress = True
                self.assertEqual(deferred(callback), GLib.SOURCE_REMOVE)
                self.host.duplicate_tab.assert_not_called()

    def test_invalid_targets_do_not_open_a_menu(self) -> None:
        for condition in ("missing", "detached", "new-label", "shutdown"):
            with self.subTest(condition=condition):
                self.host.session_registry = SessionRegistry([self.session, self.other])
                self.session.detached_window = None
                self.session.tab_label = self.tab
                self.host.shutdown_in_progress = False
                if condition == "missing":
                    self.host.session_registry.remove(self.session.id)
                elif condition == "detached":
                    self.session.detached_window = object()
                elif condition == "new-label":
                    self.session.tab_label = Gtk.Box()
                else:
                    self.host.shutdown_in_progress = True
                self.host.on_tab_right_click(None, 1, 10, 20, self.session.id, self.tab)
                self.assertEqual(self.menus(), [])

    def test_real_menu_entries_dispatch_after_gtk_closes_the_popover(self) -> None:
        def find_entry(widget, label):
            if isinstance(widget, Gtk.Label) and widget.get_label() == label:
                return widget.get_parent()
            child = widget.get_first_child()
            while child is not None:
                entry = find_entry(child, label)
                if entry is not None:
                    return entry
                child = child.get_next_sibling()
            return None

        for name, command in (
            ("duplicate_tab", self.host.duplicate_tab),
            ("detach_tab", self.host.detach_tab),
            ("rename_tab", self.host.show_rename_tab_dialog),
        ):
            with self.subTest(action=name):
                menu = self.open_menu()
                self.drain_events()
                entry = find_entry(menu, name)
                self.assertIsNotNone(entry)
                entry.emit("clicked")
                command.assert_not_called()
                self.drain_events()
                command.assert_called_once_with(menu, self.session)
                self.assertIsNone(menu.get_parent())
                command.reset_mock()


class FakePopover:
    def __init__(self) -> None:
        self.closed = False

    def popdown(self) -> None:
        self.closed = True


class FakeWindow:
    def __init__(self, **kwargs) -> None:
        self.properties = kwargs
        self.child = None
        self.presented = False
        self.titlebar = None
        self.title = kwargs.get("title", "")
        self.destroyed = False

    def set_handle_menubar_accel(self, _enabled: bool) -> None:
        pass

    def set_default_size(self, _width: int, _height: int) -> None:
        pass

    def set_titlebar(self, titlebar) -> None:
        self.titlebar = titlebar

    def get_titlebar(self):
        return self.titlebar

    def set_title(self, title: str) -> None:
        self.title = title

    def set_child(self, child) -> None:
        self.child = child

    def connect(self, *_args) -> None:
        pass

    def present(self) -> None:
        self.presented = True

    def destroy(self) -> None:
        self.destroyed = True


class FakeHeaderBar:
    def __init__(self) -> None:
        self.title_widget = None

    def set_title_widget(self, widget) -> None:
        self.title_widget = widget

    def get_title_widget(self):
        return self.title_widget


class FakeLabel:
    def __init__(self, *, label: str) -> None:
        self.label = label

    def set_label(self, label: str) -> None:
        self.label = label


class FakeTab:
    def __init__(self) -> None:
        self.next_sibling = None

    def get_next_sibling(self):
        return self.next_sibling


class FakeTabBar:
    def __init__(self, tabs) -> None:
        self.first_child = tabs[0] if tabs else None
        for current, following in zip(tabs, tabs[1:]):
            current.next_sibling = following

    def get_first_child(self):
        return self.first_child


class DetachTabTests(unittest.TestCase):
    def test_closing_detached_window_defers_session_close_until_after_signal(self) -> None:
        window = FakeWindow()
        session = SimpleNamespace(id="detached", page=object(), detached_window=window)

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.requested = None

            def request_close_tab(self, session_id, page) -> None:
                self.requested = (session_id, page)

        host = Host()
        with patch("termia.tabs.GLib.idle_add") as idle_add:
            handled = host.on_detached_window_close(window, session)

        self.assertTrue(handled)
        self.assertIsNone(host.requested)
        idle_add.assert_called_once_with(host.finish_detached_window_close, window, session)
        self.assertIs(session.detached_window, window)
        self.assertIs(window.child, None)

        result = host.finish_detached_window_close(window, session)

        self.assertEqual(host.requested, (session.id, session.page))
        from gi.repository import GLib

        self.assertEqual(result, GLib.SOURCE_REMOVE)

    def test_deferred_close_ignores_session_reattached_before_callback(self) -> None:
        window = FakeWindow()
        session = SimpleNamespace(id="detached", page=object(), detached_window=window)

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.requested = False

            def request_close_tab(self, _session_id, _page) -> None:
                self.requested = True

        host = Host()
        session.detached_window = None

        host.finish_detached_window_close(window, session)

        self.assertFalse(host.requested)

    def test_explicit_reattach_preserves_session_and_destroys_only_window(self) -> None:
        page = object()
        window = FakeWindow()
        window.set_child(page)
        session = SimpleNamespace(id="detached", page=page, detached_window=window)

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session])
                self.attached = None

            def add_session_to_main_view(self, current_session) -> None:
                self.attached = current_session

        host = Host()
        popover = FakePopover()

        host.reattach_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertIsNone(session.detached_window)
        self.assertIsNone(window.child)
        self.assertTrue(window.destroyed)
        self.assertIs(host.attached, session)
        self.assertTrue(host.session_registry.contains(session.id))

    def test_dialog_owner_uses_detached_window_when_available(self) -> None:
        detached_window = object()
        session = SimpleNamespace(detached_window=detached_window)
        host = TabsMixin()

        self.assertIs(host.window_for_session(session), detached_window)

    def test_dialog_owner_uses_main_window_for_attached_session(self) -> None:
        session = SimpleNamespace(detached_window=None)
        host = TabsMixin()

        self.assertIs(host.window_for_session(session), host)

    def test_detach_tab_keeps_previous_order_for_focus_selection(self) -> None:
        session = SimpleNamespace(
            id="detached",
            title="Detached",
            page=object(),
            detached_window=None,
        )
        previous_session = SimpleNamespace(
            id="previous",
            detached_window=None,
        )

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.application = object()
                self.session_registry = SessionRegistry([session, previous_session])
                self.focused = None
                self.removed = None
                self.visible_sessions = [previous_session, session]

            def visible_sessions_in_tab_order(self):
                return self.visible_sessions

            def get_application(self):
                return self.application

            def remove_session_from_main_view(self, current_session) -> None:
                self.removed = current_session

            def focus_available_session_after_close(self, closed_id, previous_order) -> None:
                self.focused = (closed_id, previous_order)

            def update_session_tab_bar_visibility(self) -> None:
                pass

            def sync_window_title_with_visible_session(self) -> None:
                pass

        host = Host()
        popover = FakePopover()
        with (
            patch("termia.tabs.Gtk.Window", FakeWindow),
            patch("termia.tabs.Gtk.HeaderBar", FakeHeaderBar),
            patch("termia.tabs.Gtk.Label", FakeLabel),
        ):
            host.detach_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertIs(host.removed, session)
        self.assertEqual(host.focused, (session.id, [previous_session, session]))
        self.assertIsInstance(session.detached_window, FakeWindow)
        self.assertIs(session.detached_window.properties["application"], host.application)
        self.assertNotIn("transient_for", session.detached_window.properties)
        self.assertIsInstance(session.detached_window.titlebar, FakeHeaderBar)
        self.assertEqual(session.detached_window.titlebar.title_widget.label, session.title)
        self.assertTrue(session.detached_window.presented)

    def test_renaming_detached_tab_updates_window_and_header_titles(self) -> None:
        window = FakeWindow(title="Old title")
        header = FakeHeaderBar()
        header.set_title_widget(FakeLabel(label="Old title"))
        window.set_titlebar(header)
        session = SimpleNamespace(
            title="Old title",
            title_locked=False,
            detached_window=window,
        )
        dialog = SimpleNamespace(destroy=lambda: setattr(dialog, "destroyed", True))
        entry = SimpleNamespace(get_text=lambda: "New title")

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.updated = None
                self.synced = False

            def update_session_tab_title(self, current_session, title) -> None:
                self.updated = (current_session, title)

            def sync_window_title_with_visible_session(self) -> None:
                self.synced = True

        from gi.repository import Gtk

        host = Host()
        with (
            patch("termia.tabs.Gtk.HeaderBar", FakeHeaderBar),
            patch("termia.tabs.Gtk.Label", FakeLabel),
        ):
            host.on_rename_tab_response(dialog, Gtk.ResponseType.OK, entry, session)

        self.assertEqual(session.title, "New title")
        self.assertTrue(session.title_locked)
        self.assertEqual(host.updated, (session, "New title"))
        self.assertEqual(window.title, "New title")
        self.assertEqual(header.title_widget.label, "New title")
        self.assertTrue(host.synced)
        self.assertTrue(dialog.destroyed)


class DuplicateTabTests(unittest.TestCase):
    def test_duplicate_tab_closes_popover_and_dispatches_lifecycle_action(self) -> None:
        session = SimpleNamespace(id="duplicate")
        duplicated = []

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.tab_lifecycle_actions = TabLifecycleActions(
                    duplicate_session=duplicated.append,
                    disconnect_session=lambda _session: None,
                    terminate_split_processes=lambda _session: None,
                    confirm_session_action=lambda *_args: None,
                )

        host = Host()
        popover = FakePopover()
        host.duplicate_tab(popover, session)

        self.assertTrue(popover.closed)
        self.assertEqual(duplicated, [session])


class CloseTabTests(unittest.TestCase):
    def test_close_tab_removes_only_the_closed_session_from_registry(self) -> None:
        page = object()
        session = SimpleNamespace(
            id="closed",
            page=page,
            connected=True,
            detached_window=None,
        )
        remaining_session = SimpleNamespace(
            id="remaining",
            detached_window=None,
        )

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([session, remaining_session])
                self.removed = None
                self.focused = None
                self.terminated = None
                self.disconnected = None
                self.cancelled_transfers = None
                self.tab_lifecycle_actions = TabLifecycleActions(
                    duplicate_session=lambda _session: None,
                    disconnect_session=self.disconnect_session,
                    terminate_split_processes=self.terminate_split_processes,
                    confirm_session_action=lambda *_args: None,
                )

            def visible_sessions_in_tab_order(self):
                return [session, remaining_session]

            def terminate_split_processes(self, current_session) -> None:
                self.terminated = current_session

            def disconnect_session(self, current_session) -> None:
                self.disconnected = current_session
                current_session.connected = False

            def cancel_file_transfers(self, session_id, *, close_dialog=False) -> None:
                self.cancelled_transfers = (session_id, close_dialog)

            def remove_session_from_main_view(self, current_session) -> None:
                self.removed = current_session

            def update_session_tab_bar_visibility(self) -> None:
                pass

            def focus_available_session_after_close(self, closed_id, previous_order) -> None:
                self.focused = (closed_id, previous_order)

            def sync_window_title_with_visible_session(self) -> None:
                pass

        host = Host()
        host.close_tab(session.id, page, disconnect=True)

        self.assertIs(host.disconnected, session)
        self.assertIs(host.removed, session)
        self.assertIs(host.terminated, session)
        self.assertEqual(host.cancelled_transfers, (session.id, True))
        self.assertIsNone(host.session_registry.get(session.id))
        self.assertIs(host.session_registry.get(remaining_session.id), remaining_session)
        self.assertEqual(host.focused, (session.id, [session, remaining_session]))


class MiddleClickTabTests(unittest.TestCase):
    def test_middle_click_requests_tab_close(self) -> None:
        page = object()

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.closed = None

            def request_close_tab(self, session_id, clicked_page) -> None:
                self.closed = (session_id, clicked_page)

        host = Host()
        host.on_tab_middle_press(None, 1, 0.0, 0.0, "session", page)

        self.assertEqual(host.closed, ("session", page))


class TabOverflowTests(unittest.TestCase):
    def test_overflow_order_matches_visual_tab_order_and_skips_detached_tabs(self) -> None:
        first_tab = FakeTab()
        second_tab = FakeTab()
        detached_tab = FakeTab()
        first = SimpleNamespace(id="first", page=object(), tab_label=first_tab, detached_window=None)
        second = SimpleNamespace(id="second", page=object(), tab_label=second_tab, detached_window=None)
        detached = SimpleNamespace(id="detached", page=object(), tab_label=detached_tab, detached_window=object())

        class Host(TabsMixin):
            def __init__(self) -> None:
                self.session_registry = SessionRegistry([first, detached, second])
                pages = [second.page, detached.page, first.page]
                self.terminal_notebook = SimpleNamespace(get_n_pages=lambda: len(pages), get_nth_page=pages.__getitem__)

        self.assertEqual(Host().visible_sessions_in_tab_order(), [second, first])

class NativeTerminalNotebookTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        self.window.set_default_size(400, 220)
        self.host = TabsMixin()
        self.host.terminal_notebook = Gtk.Notebook(scrollable=True)
        self.host.install_terminal_tab_drop_target()
        self.host.t = lambda key: key
        self.host.tab_overflow_button = Gtk.MenuButton()
        self.host.terminal_notebook.set_action_widget(self.host.tab_overflow_button, Gtk.PackType.END)
        self.window.set_child(self.host.terminal_notebook)
        self.host.session_registry = SessionRegistry()
        self.host.sync_window_title_with_visible_session = lambda: None
        self.host.terminal_notebook.connect("switch-page", self.host.on_terminal_page_switched)
        self.window.present()
        self.addCleanup(self.window.destroy)

    def add_session(self, name):
        page = Gtk.Box()
        terminal = Gtk.Entry()
        page.append(terminal)
        label = self.host.build_tab_label(name, name, page)
        session = SimpleNamespace(id=name, title=name, page=page, terminal=terminal,
                                  tab_label=label, detached_window=None)
        self.host.session_registry.register(session)
        self.host.add_session_to_main_view(session)
        return session

    def drain(self):
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.001)

    def test_drag_preview_preserves_exterior_size_and_grab_point(self):
        from termia.styles import build_application_css
        provider = Gtk.CssProvider()
        provider.load_from_data(build_application_css("#001b33", "#008712", 1))
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.addCleanup(Gtk.StyleContext.remove_provider_for_display, display, provider)
        self.host.terminal_notebook.add_css_class("termia-terminal-notebook")
        session = self.add_session("First")
        self.add_session("Second")
        self.drain()
        tab = session.tab_label
        valid, bounds = tab.get_parent().compute_bounds(tab)
        self.assertTrue(valid)
        self.assertGreater(bounds.get_width(), tab.get_width())
        preview_window = Gtk.Window()
        self.addCleanup(preview_window.destroy)
        drag = MagicMock()
        icon = MagicMock()
        icon.set_child.side_effect = preview_window.set_child
        self.host.on_tab_drag_prepare(None, 7, 9, session.id, tab)
        with patch.object(Gtk.DragIcon, "get_for_drag", return_value=icon):
            self.host.on_tab_drag_begin(MagicMock(), drag, session.id, tab)
        preview_window.present()
        self.drain()
        preview = preview_window.get_child()
        self.assertEqual(preview.get_width(), round(bounds.get_width()))
        self.assertEqual(preview.get_height(), round(bounds.get_height()))
        drag.set_hotspot.assert_called_once_with(int(7 - bounds.get_x()), int(9 - bounds.get_y()))
        self.host.on_tab_drag_end(None, drag, False, session.id)

    def test_native_selection_order_and_removed_page_focus(self):
        first = self.add_session("first")
        second = self.add_session("second")
        self.assertTrue(self.host.terminal_notebook.get_show_tabs())
        self.host.terminal_notebook.set_current_page(0)
        self.drain()
        self.assertIs(self.host.visible_terminal_page(), first.page)
        self.assertTrue(self.window.get_focus().is_ancestor(first.terminal))
        self.host.terminal_notebook.reorder_child(first.page, 1)
        self.assertEqual(self.host.visible_sessions_in_tab_order(), [second, first])
        self.host.set_active_session("second")
        self.host.remove_session_from_main_view(second)
        self.drain()
        self.assertIs(self.host.visible_terminal_page(), first.page)
        self.assertFalse(self.host.terminal_notebook.get_show_tabs())
        self.assertTrue(self.window.get_focus().is_ancestor(first.terminal))

    def test_forty_tabs_native_overflow_selection_and_empty_state(self):
        sessions = [self.add_session(str(i)) for i in range(40)]
        self.drain()
        self.assertTrue(self.host.tab_overflow_button.get_visible())
        self.assertTrue(self.host.terminal_notebook.get_scrollable())
        self.host.set_active_session("0")
        self.assertIs(self.host.visible_terminal_page(), sessions[0].page)
        self.host.set_active_session("39")
        self.assertIs(self.host.visible_terminal_page(), sessions[-1].page)
        for session in sessions:
            self.host.remove_session_from_main_view(session)
        self.drain()
        self.assertIsNone(self.host.visible_terminal_page())
        self.assertEqual(self.host.terminal_notebook.get_n_pages(), 0)

    def test_overflow_selector_tracks_native_tab_visibility_after_resize(self):
        self.window.set_default_size(800, 220)
        self.add_session("first")
        self.add_session("second")
        self.drain()
        self.assertFalse(self.host.tab_overflow_button.get_visible())
        for i in range(6):
            self.add_session(str(i))
        self.drain()
        self.assertTrue(self.host.tab_overflow_button.get_visible())
        self.window.set_default_size(1600, 220)
        self.drain()
        self.assertFalse(self.host.tab_overflow_button.get_visible())

    def test_tabs_share_full_header_width_and_shrink_when_a_tab_is_added(self):
        self.window.set_default_size(800, 220)
        first, second = [self.add_session(name) for name in ("first", "second")]
        self.drain()
        def tab_bounds(session):
            valid, bounds = session.tab_label.get_parent().compute_bounds(self.host.terminal_notebook)
            self.assertTrue(valid)
            return bounds
        original_width = tab_bounds(first).get_width()
        self.assertAlmostEqual(original_width, tab_bounds(second).get_width(), delta=1)
        self.assertLessEqual(tab_bounds(first).get_x(), 16)
        self.assertGreaterEqual(tab_bounds(second).get_x() + tab_bounds(second).get_width(),
                                self.host.terminal_notebook.get_width() - 16)
        third = self.add_session("third")
        self.drain()
        widths = [tab_bounds(item).get_width() for item in (first, second, third)]
        self.assertLess(widths[0], original_width)
        self.assertLessEqual(max(widths) - min(widths), 1)
        self.assertLessEqual(tab_bounds(first).get_x(), 16)
        self.assertGreaterEqual(tab_bounds(third).get_x() + tab_bounds(third).get_width(),
                                self.host.terminal_notebook.get_width() - 16)

    def test_pointer_drag_reorders_private_notebook_tabs(self):
        if not shutil.which("xdotool"):
            self.skipTest("GTK pointer drag test requires xdotool")
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        self.window.set_default_size(800, 220)
        self.host.reorder_dragged_tab_at_bar_x = MagicMock(wraps=self.host.reorder_dragged_tab_at_bar_x)
        self.host.on_tab_bar_drop_accept = MagicMock(wraps=self.host.on_tab_bar_drop_accept)
        sessions = [self.add_session(name) for name in ("first", "second", "third")]
        self.drain()
        xid = GdkX11.X11Surface.get_xid(self.window.get_surface())
        def point(session):
            valid, bounds = session.tab_label.compute_bounds(self.window)
            self.assertTrue(valid)
            return int(bounds.get_x() + 20), int(bounds.get_y() + bounds.get_height() / 2)
        def pointer(*args):
            subprocess.run(["xdotool", *args], check=True, stdout=subprocess.DEVNULL)
            self.drain()
        def cleanup():
            pointer("mouseup", "1")
            pointer("mousemove", "0", "0")
        self.addCleanup(cleanup)
        x, y = point(sessions[-1])
        pointer("mousemove", "--window", str(xid), str(x), str(y))
        pointer("mousedown", "1")
        pointer("mousemove", "--window", str(xid), str(x - 30), str(y))
        target_x, target_y = point(sessions[0])
        pointer("mousemove", "--window", str(xid), str(target_x), str(target_y))
        pointer("mouseup", "1")
        self.assertEqual([item.id for item in self.host.visible_sessions_in_tab_order()],
                         ["third", "first", "second"])
        self.assertIs(self.host.visible_terminal_page(), sessions[-1].page)


    def test_repeated_overflow_drag_does_not_abort_gtk(self):
        if not shutil.which("xdotool") or not Gdk.Display.get_default().get_name().startswith("127.0.0.1:"):
            self.skipTest("GTK drag stress test requires the private display runner and xdotool")
        try:
            result = subprocess.run(
                [sys.executable, "-X", "faulthandler", "-c",
                 "from tests.test_tabs import exercise_overflow_drag; exercise_overflow_drag()"],
                capture_output=True, text=True, timeout=35,
            )
        finally:
            subprocess.run(["xdotool", "mouseup", "1", "mouseup", "3", "mousemove", "0", "0"],
                           check=True, stdout=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TerminalNotebookApplicationTests(unittest.TestCase):
    def test_local_split_detach_reattach_and_close_keep_process_ownership(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK application integration requires a graphical display")
        if not Gdk.Display.get_default().get_name().startswith("127.0.0.1:"):
            self.skipTest("Local VTE integration requires the project's private display runner")
        from termia.app import TermiaApp, TermiaWindow
        from termia.stores import ConnectionStore
        from termia.terminal_processes import terminal_process_is_active

        app = TermiaApp()
        app.register(None)
        for enabled in (False, True):
            with self.subTest(optional_tools=enabled), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = ConnectionStore(root / "connections.json", root / "settings.json",
                                        root / "statistics.json", root / "lock", root / "history")
                store.data.app.open_local_terminal_on_startup = False
                store.data.app.confirm_disconnect = False
                store.data.app.sftp_enabled = enabled
                store.data.app.statistics_enabled = enabled
                with patch("termia.app.ConnectionStore", return_value=store):
                    window = TermiaWindow(app)
                window.present()
                try:
                    first = window.open_process_terminal_tab("First", ["/bin/sh"], None)
                    second = window.open_process_terminal_tab("Second", ["/bin/sh"], None)
                    NativeTerminalNotebookTests.drain(self)
                    processes = [first.child_process, second.child_process]
                    self.assertTrue(all(terminal_process_is_active(item) for item in processes))
                    pane = window.split_terminal_pane(first, first.terminal, "horizontal")
                    self.assertIsNotNone(pane)
                    self.assertEqual(len(first.panes), 2)
                    window.set_active_session(first.id)
                    window.move_terminal_tab_focus(first, 1)
                    self.assertIs(window.visible_terminal_page(), second.page)
                    window.detach_tab(FakePopover(), first)
                    self.assertEqual(window.terminal_notebook.get_n_pages(), 1)
                    self.assertIs(first.page.get_root(), first.detached_window)
                    self.assertEqual(len(first.panes), 2)
                    NativeTerminalNotebookTests.drain(self)
                    if shutil.which("xdotool"):
                        import gi
                        gi.require_version("GdkX11", "4.0")
                        from gi.repository import GdkX11
                        detached = first.detached_window
                        valid, point = first.terminal.compute_point(detached, Graphene.Point().init(20, 20))
                        self.assertTrue(valid)
                        xid = GdkX11.X11Surface.get_xid(detached.get_surface())
                        subprocess.run(["xdotool", "mousemove", "--window", str(xid),
                                        str(int(point.x)), str(int(point.y)), "click", "3"], check=True)
                        NativeTerminalNotebookTests.drain(self)
                    else:
                        window.on_terminal_right_click(None, 1, 20, 20, first, first.terminal)
                    menu = window._terminal_context_menus[first.detached_window]
                    def entry(widget, text):
                        if isinstance(widget, Gtk.Label) and widget.get_label() == text:
                            return widget.get_parent()
                        child = widget.get_first_child()
                        while child is not None:
                            found = entry(child, text)
                            if found is not None:
                                return found
                            child = child.get_next_sibling()
                        return None
                    reattach = entry(menu, window.t("reattach_tab"))
                    self.assertIsNotNone(reattach)
                    reattach.emit("clicked")
                    NativeTerminalNotebookTests.drain(self)
                    NativeTerminalNotebookTests.drain(self)
                    self.assertIsNone(first.detached_window)
                    self.assertEqual(window.terminal_notebook.get_n_pages(), 2)
                    self.assertIs(first.page.get_root(), window)
                    self.assertTrue(all(terminal_process_is_active(item) for item in processes))
                    self.assertTrue(window.cycle_main_focus(1))
                    window.close_tab(first.id, first.page, disconnect=True)
                    window.close_tab(second.id, second.page, disconnect=True)
                    deadline = time.monotonic() + 2
                    while any(terminal_process_is_active(item) for item in processes) and time.monotonic() < deadline:
                        NativeTerminalNotebookTests.drain(self)
                    self.assertFalse(any(terminal_process_is_active(item) for item in processes))
                    self.assertEqual(window.terminal_notebook.get_n_pages(), 0)
                finally:
                    if shutil.which("xdotool"):
                        subprocess.run(["xdotool", "mouseup", "1", "mouseup", "3", "mousemove", "0", "0"],
                                       check=True, stdout=subprocess.DEVNULL)
                    window.shutdown_in_progress = True
                    window.prepare_terminal_sessions_for_shutdown()
                    window.terminate_open_terminal_processes(force=True)
                    window.snippet_dialogs.shutdown()
                    window.notes_dialogs.shutdown()
                    for owner in tuple(getattr(window, "_terminal_context_menus", {})):
                        window.dispose_terminal_context_menu(owner)
                    for session in window.session_registry.sessions():
                        if session.detached_window is not None:
                            session.detached_window.destroy()
                            session.detached_window = None
                    window.destroy()
                    store.close()
                    NativeTerminalNotebookTests.drain(self)


def exercise_overflow_drag():
    """Run the GTK assertion reproducer in a child process on the private display."""
    import resource
    import gi
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11

    case = NativeTerminalNotebookTests("test_native_selection_order_and_removed_page_focus")
    case.setUp()
    try:
        case.window.set_default_size(800, 220)
        sessions = [case.add_session(str(i)) for i in range(12)]
        case.drain()
        xid = GdkX11.X11Surface.get_xid(case.window.get_surface())
        def drain():
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
        def pointer(x, y):
            subprocess.run(["xdotool", "mousemove", "--window", str(xid), str(x), str(y)], check=True)
            drain()
        valid, bounds = sessions[-1].tab_label.compute_bounds(case.window)
        case.assertTrue(valid)
        x, y = int(bounds.get_x() + 20), int(bounds.get_y() + bounds.get_height() / 2)
        pointer(x, y)
        subprocess.run(["xdotool", "mousedown", "1"], check=True)
        try:
            pointer(x - 30, y)
            for _cycle in range(10):
                for pos in [*range(770, 20, -25), *range(20, 770, 25)]:
                    pointer(pos, y)
                    time.sleep(0.008)
                pointer(20, y)
                time.sleep(0.6)
                drain()
                pointer(500, 140)
                pointer(500, y)
            pointer(20, y)
        finally:
            subprocess.run(["xdotool", "mouseup", "1", "mousemove", "0", "0"], check=True)
            case.drain()
        case.assertEqual(sorted(item.id for item in case.host.visible_sessions_in_tab_order()),
                         sorted(str(i) for i in range(12)))
    finally:
        case.doCleanups()
