import shutil
import subprocess
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import Group, LocalTerminalProfile, Server, StoreData, Workspace
from termia.sidebar import (
    SERVER_GROUP_DND_MIME_TYPE,
    Gdk,
    GLib,
    Graphene,
    Gtk,
    SidebarMixin,
)
from termia.sidebar_projection import SidebarRow


class FakeWidget:
    def __init__(self) -> None:
        self.focused = False
        self.classes: set[str] = set()

    def add_css_class(self, name: str) -> None:
        self.classes.add(name)

    def remove_css_class(self, name: str) -> None:
        self.classes.discard(name)

    def grab_focus(self) -> None:
        self.focused = True


class SidebarNavigationTests(unittest.TestCase):
    def build_host(self, rows: list[SidebarRow]):
        server = Server(id="current", name="Current", host="current.test", user="user")

        class Host(SidebarMixin):
            def __init__(self) -> None:
                self.visible_tree_rows = rows
                self.tree_widgets = {
                    (row.kind, row.item_id): FakeWidget() for row in rows
                }
                self.selected = None
                self.selected_tree_widget = None
                self.store = SimpleNamespace(data=SimpleNamespace(servers=[server]))
                self.opened = None

            def cancel_sidebar_scroll_restore(self) -> None:
                pass

            def select_visible_tree_row(self, index) -> bool:
                if not self.visible_tree_rows:
                    return False
                self.selected = self.visible_tree_rows[index]
                return True

            def open_terminal_tab(self, selected_server) -> None:
                self.opened = selected_server

        return Host(), server

    def test_enter_replaces_stale_selection_with_first_visible_result(self) -> None:
        current = SidebarRow("server", "current", "Current")
        host, server = self.build_host([current])
        host.selected = SidebarRow("server", "previous", "Previous")

        activated = host.activate_selected_tree_row()

        self.assertTrue(activated)
        self.assertEqual(host.selected, current)
        self.assertIs(host.opened, server)

    def test_enter_with_no_results_does_not_activate_stale_selection(self) -> None:
        host, _server = self.build_host([])
        host.selected = SidebarRow("server", "previous", "Previous")

        activated = host.activate_selected_tree_row()

        self.assertFalse(activated)
        self.assertIsNone(host.opened)

    def test_activation_rejects_selection_removed_during_result_resolution(self) -> None:
        current = SidebarRow("server", "current", "Current")
        host, _server = self.build_host([current])
        host.selected = current
        host.get_visible_tree_row_index = lambda _row: None
        host.select_visible_tree_row = lambda _index: False

        activated = host.activate_selected_tree_row()

        self.assertFalse(activated)
        self.assertIsNone(host.opened)

    def test_server_scp_action_uses_no_session_context(self) -> None:
        host, server = self.build_host([])
        popover = Mock()
        host.on_send_files_to_server = Mock()

        host.on_server_context_send_files(None, popover, server.id)

        host.on_send_files_to_server.assert_called_once_with(popover, None, server)


class NativeConnectionsTreeTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")

        class Host(SidebarMixin, Gtk.Window):
            pass

        self.host = Host()
        host = self.host
        host.store = SimpleNamespace(
            data=StoreData(groups=[Group("parent", "Parent"), Group("child", "Child", "parent")],
                           servers=[Server("one", "First", "one.test", "user", group_id="child", favorite=True),
                                    Server("two", "Second", "two.test", "user")],
                           local_terminals=[LocalTerminalProfile("local", "Local")],
                           workspaces=[Workspace("work", "Workspace")]),
            recent_server_ids=lambda: ["one"], read_only=False, encryption_locked=False,
            can_move_server_to_group=Mock(return_value=True), move_server_to_group=Mock(return_value=True))
        host.selected = None
        host.selected_tree_widget = None
        host.tree_widgets = {}
        host.group_expanded_state = {}
        host.collapse_groups_on_startup = False
        host.sidebar_drag_server_id = None
        host.active_context_popover = None
        host.scroll_restore_id = None
        host.t = lambda key: key
        host.render_detail = Mock()
        host.open_terminal_tab = Mock()
        host.open_local_terminal_profile = Mock()
        host.open_workspace = Mock()
        host.sftp_tool = None
        host.preserve_sidebar_scroll = Mock()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        host.search_entry = Gtk.SearchEntry()
        box.append(host.search_entry)
        host.server_list = host.create_sidebar_tree()
        host.server_scroller = Gtk.ScrolledWindow()
        host.server_scroller.set_vexpand(True)
        host.server_scroller.set_child(host.server_list)
        box.append(host.server_scroller)
        host.summary_label = Gtk.Label()
        box.append(host.summary_label)
        host.set_child(box)
        host.set_default_size(420, 600)
        host.refresh_list()
        host.present()
        self.addCleanup(self.destroy)
        self.drain()

    def destroy(self):
        self.host.dispose_saved_context_menu()
        self.host.dispose_server_context_menu()
        self.host.dispose_group_context_menu()
        self.host.destroy()
        self.drain()

    @staticmethod
    def drain():
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.001)

    def select(self, kind, item_id):
        index = self.host.get_visible_tree_row_index(SidebarRow(kind, item_id, ""))
        self.assertIsNotNone(index)
        self.host.sidebar_tree_selection.set_selected(index)
        return index

    def test_selection_block_fits_object_and_long_names_remain_bounded(self):
        host = self.host
        self.select("server", "two")
        self.drain()
        content = host.tree_widgets[("server", "two")]
        self.assertTrue(content.has_css_class("termia-sidebar-object"))
        self.assertEqual(content.get_halign(), Gtk.Align.START)
        self.assertLess(content.get_width(), host.server_list.get_width() / 2)
        host.store.data.servers[1].name = "Long synthetic server name " * 20
        host.refresh_list()
        self.drain()
        content = host.tree_widgets[("server", "two")]
        self.assertLessEqual(content.get_width(), host.server_list.get_width())
        self.assertEqual(host.selected.item_id, "two")

    def test_headers_toggle_without_replacing_server_selection(self):
        host = self.host
        self.select("server", "two")
        row = SidebarRow("group", "parent", "Parent")
        token = host.sidebar_model_token
        tree_row = host.get_group_expander("parent")
        expanded = tree_row.get_expanded()
        host.on_sidebar_tree_header_clicked(None, 1, 0, 0, row, token)
        self.assertEqual(tree_row.get_expanded(), not expanded)
        self.assertEqual((host.selected.kind, host.selected.item_id), ("server", "two"))
        # A recycled row must not act on the replacement projection.
        host.refresh_list()
        tree_row = host.get_group_expander("parent")
        expanded = tree_row.get_expanded()
        host.on_sidebar_tree_header_clicked(None, 1, 0, 0, row, token)
        self.assertEqual(tree_row.get_expanded(), expanded)
        current_token = host.sidebar_model_token
        host.on_sidebar_tree_header_clicked(None, 2, 0, 0, row, current_token)
        self.assertEqual(tree_row.get_expanded(), expanded)

    def test_keyboard_selection_skips_group_and_section_headers(self):
        host = self.host
        for _ in range(len(host.visible_tree_rows) + 2):
            self.assertTrue(host.move_visible_tree_selection(1))
            self.assertNotIn(host.selected.kind, {"group", "section"})
        for _ in range(len(host.visible_tree_rows) + 2):
            self.assertTrue(host.move_visible_tree_selection(-1))
            self.assertNotIn(host.selected.kind, {"group", "section"})
        host.store.data.servers.clear()
        host.store.data.local_terminals.clear()
        host.store.data.workspaces.clear()
        host.refresh_list()
        self.assertFalse(host.select_visible_tree_row(0))
        self.assertFalse(host.move_visible_tree_selection(1))
        self.assertFalse(host.activate_selected_tree_row())

    def test_hierarchy_expansion_search_and_selection_survive_refresh(self):
        host = self.host
        self.assertIsInstance(host.server_list, Gtk.ListView)
        self.select("server", "one")
        host.refresh_list()
        self.assertEqual((host.selected.kind, host.selected.item_id), ("server", "one"))
        parent = host.get_group_expander("parent")
        parent.set_expanded(False)
        self.drain()
        self.assertFalse(host.group_expanded_state["parent"])
        self.assertIsNone(host.get_visible_tree_row_index(SidebarRow("server", "one", "")))
        host.search_entry.set_text("First")
        host.refresh_list()
        self.assertTrue(host.get_group_expander("parent").get_expanded())
        self.assertTrue(host.get_group_expander("child").get_expanded())
        host.get_group_expander("parent").set_expanded(False)
        self.drain()
        self.assertTrue(host.get_group_expander("parent").get_expanded())
        host.search_entry.set_text("")
        host.refresh_list()
        self.assertFalse(host.get_group_expander("parent").get_expanded())
        host.set_all_groups_expanded(True)
        self.assertTrue(host.get_group_expander("child").get_expanded())
        host.set_all_groups_expanded(False)
        host.set_all_groups_expanded(True)
        self.assertTrue(host.get_group_expander("child").get_expanded())

    def test_activation_uses_each_projected_identity(self):
        host = self.host
        for kind in ("server", "favorite", "recent"):
            index = self.select(kind, "one")
            host.on_sidebar_tree_activated(host.server_list, index)
            host.open_terminal_tab.assert_called_with(host.store.data.servers[0])
        index = self.select("local_terminal", "local")
        host.on_sidebar_tree_activated(host.server_list, index)
        host.open_local_terminal_profile.assert_called_once_with(host.store.data.local_terminals[0])
        index = self.select("workspace", "work")
        host.on_sidebar_tree_activated(host.server_list, index)
        host.open_workspace.assert_called_once_with(host.store.data.workspaces[0])
        host.search_entry.set_text("nonexistent")
        host.refresh_list()
        self.assertIsNone(host.selected)
        self.assertFalse(host.activate_selected_tree_row())

    def test_right_click_keeps_target_and_rejects_rebuilt_rows(self):
        host = self.host
        self.select("server", "one")
        row = SidebarRow("server", "two", "Second")
        content = host.tree_widgets[(row.kind, row.item_id)]
        gesture = Mock()
        host.on_sidebar_tree_context_pressed(gesture, 1, 5, 5, row, content)
        self.assertIsNone(host.active_context_popover)
        self.drain()
        self.assertEqual(host.selected.item_id, "two")
        self.assertEqual(host._server_context_menu_target, ("two",))
        host.close_active_context_menu()
        host.on_sidebar_tree_context_pressed(gesture, 1, 5, 5, row, content)
        host.refresh_list()
        self.drain()
        self.assertIsNone(host.active_context_popover)

    def test_recycled_drop_target_and_foreign_drag_are_rejected(self):
        host = self.host
        target = host.tree_widgets[("group", "child")]
        host.sidebar_drag_server_id = "two"
        host.sidebar_drag = object()
        drop = Mock()
        drop.get_drag.return_value = object()
        drop.get_formats.return_value = Gdk.ContentFormats.new([SERVER_GROUP_DND_MIME_TYPE])
        self.assertFalse(host.on_server_group_drop_accept(None, drop))
        drop.get_drag.return_value = host.sidebar_drag
        self.assertTrue(host.on_server_group_drop_accept(None, drop))
        host.on_server_group_drop(None, drop, 0, 0, "child", target)
        context = drop.read_async.call_args.args[-1]
        host.refresh_list()
        stream = Mock()
        stream.read_bytes_finish.return_value = GLib.Bytes.new(b"two")
        host.on_server_group_drop_bytes_read(stream, None, context)
        host.store.move_server_to_group.assert_not_called()
        drop.finish.assert_called_once_with(Gdk.DragAction(0))

    def test_search_keyboard_enters_view_and_native_view_keeps_navigation(self):
        host = self.host
        host.search_entry.grab_focus()
        self.assertTrue(host.on_sidebar_navigation_key_pressed(None, Gdk.KEY_Down, 0, Gdk.ModifierType(0)))
        self.drain()
        focused = host.get_focus()
        self.assertTrue(focused is host.server_list or focused.is_ancestor(host.server_list))
        self.assertFalse(host.on_sidebar_navigation_key_pressed(None, Gdk.KEY_Down, 0, Gdk.ModifierType(0)))

    def test_immediate_search_enter_uses_current_text_and_skips_group_headers(self):
        host = self.host
        host.search_entry.grab_focus()
        for query, server in (("First", host.store.data.servers[0]), ("Second", host.store.data.servers[1])):
            host.search_entry.set_text(query)
            self.assertTrue(host.on_sidebar_navigation_key_pressed(None, Gdk.KEY_Return, 0, Gdk.ModifierType(0)))
            host.open_terminal_tab.assert_called_with(server)
        host.search_entry.set_text("nonexistent")
        host.open_terminal_tab.reset_mock()
        self.assertFalse(host.on_sidebar_navigation_key_pressed(None, Gdk.KEY_Return, 0, Gdk.ModifierType(0)))
        host.open_terminal_tab.assert_not_called()

    def test_selection_without_realized_row_and_model_row_recycling(self):
        host = self.host
        host.store.data.servers.extend(Server(str(i), f"Server {i:03}", "test.invalid", "user")
                                       for i in range(150))
        host.refresh_list()
        self.drain()
        index = host.get_visible_tree_row_index(SidebarRow("server", "149", ""))
        self.assertTrue(host.select_visible_tree_row(index))
        self.assertEqual(host.selected.item_id, "149")
        self.drain()
        self.assertEqual(host.selected.item_id, "149")
        self.assertGreater(host.server_scroller.get_vadjustment().get_value(), 0)
        host.activate_selected_tree_row()
        host.open_terminal_tab.assert_called_with(host.store.data.servers[-1])

    def test_real_keyboard_navigation_expands_and_activates_native_rows(self):
        if not shutil.which("xdotool"):
            self.skipTest("GTK keyboard test requires xdotool")
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        host = self.host
        xid = GdkX11.X11Surface.get_xid(host.get_surface())
        def key(name):
            subprocess.run(["xdotool", "windowfocus", str(xid), "key", "--clearmodifiers", name],
                           check=True, stdout=subprocess.DEVNULL)
            self.drain()
        parent = host.get_group_expander("parent")
        parent.set_expanded(False)
        index = host.get_visible_tree_row_index(SidebarRow("group", "parent", ""))
        host.select_visible_tree_row(index)
        self.drain()
        self.assertEqual(host.selected.item_id, "two")
        # Headers can receive disclosure focus without becoming selected.
        host.focus_sidebar_tree_position(index)
        key("shift+Right")
        self.assertTrue(parent.get_expanded(), str(host.get_focus()))
        key("Down")
        self.assertEqual(host.selected.item_id, "two")
        key("Down")
        self.assertEqual((host.selected.kind, host.selected.item_id), ("server", "one"))
        key("Return")
        host.open_terminal_tab.assert_called_once_with(host.store.data.servers[0])
        key("End")
        self.assertEqual(host.selected.item_id, "two")
        key("Home")
        self.assertEqual(host.selected.item_id, "two")
        key("Down")
        self.assertEqual(host.selected.item_id, "work")

    def test_pointer_drag_moves_only_the_targeted_server_into_group(self):
        if not shutil.which("xdotool"):
            self.skipTest("GTK pointer drag test requires xdotool")
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        host = self.host
        xid = GdkX11.X11Surface.get_xid(host.get_surface())
        def point(kind, item_id):
            content = host.tree_widgets[(kind, item_id)]
            valid, point = content.compute_point(host, Graphene.Point().init(45, content.get_height() / 2))
            self.assertTrue(valid)
            return int(point.x), int(point.y)
        def pointer(*args):
            subprocess.run(["xdotool", *args], check=True, stdout=subprocess.DEVNULL)
            self.drain()
        def cleanup():
            pointer("mouseup", "1")
            pointer("mousemove", "0", "0")
        self.addCleanup(cleanup)
        x, y = point("server", "two")
        pointer("mousemove", "--window", str(xid), str(x), str(y))
        pointer("mousedown", "1")
        pointer("mousemove", "--window", str(xid), str(x + 30), str(y))
        target_x, target_y = point("group", "child")
        pointer("mousemove", "--window", str(xid), str(target_x), str(target_y))
        pointer("mousemove", "--window", str(xid), str(target_x + 10), str(target_y))
        pointer("mouseup", "1")
        host.store.move_server_to_group.assert_called_once_with("two", "child")
