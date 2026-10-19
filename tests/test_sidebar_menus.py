import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import Group, LocalTerminalProfile, Server, Workspace
from termia.sidebar import Gdk, GLib, Graphene, Gtk, SidebarMixin
from termia.sidebar_projection import SidebarRow


class ServerContextMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")

        class Host(SidebarMixin, Gtk.Window):
            pass

        self.host = Host()
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.button = Gtk.Button(label="Synthetic server")
        self.button.set_size_request(300, 40)
        self.rows.append(self.button)
        self.content.append(self.rows)
        self.host.set_child(self.content)
        self.host.present()
        self.host.active_context_popover = None
        self.servers = [Server("one", "First", "one.test", "user"),
                        Server("two", "Second", "two.test", "user")]
        self.host.store = SimpleNamespace(
            read_only=False, encryption_locked=False,
            data=SimpleNamespace(servers=self.servers),
        )
        self.host.sftp_tool = SimpleNamespace(browse=Mock())
        self.host.notes_dialogs = SimpleNamespace(show_for_server_after_popover=Mock())
        self.host.t = lambda key: key
        self.host.get_sidebar_scroll_values = lambda: (11.0, 83.0)
        self.host.preserve_sidebar_scroll = Mock()
        self.commands = {}
        for name, method in (
            ("favorite", "on_server_context_toggle_favorite"),
            ("connect", "on_server_context_connect"),
            ("edit", "on_server_context_edit"),
            ("clone", "on_server_context_clone"),
            ("send-files", "on_server_context_send_files"),
            ("delete", "on_server_context_delete"),
        ):
            self.commands[name] = Mock()
            setattr(self.host, method, self.commands[name])
        self.addCleanup(self.destroy)
        self.drain()

    @staticmethod
    def drain(wait=False):
        deadline = time.monotonic() + (0.2 if wait else 0)
        context = GLib.MainContext.default()
        while True:
            while context.pending():
                context.iteration(False)
            if time.monotonic() >= deadline:
                break
            time.sleep(0.005)

    def destroy(self):
        self.host.dispose_saved_context_menu()
        self.host.dispose_server_context_menu()
        self.drain()
        self.host.destroy()

    def open_menu(self, kind="server", server_id="two", x=20):
        self.host.show_row_context_menu(
            SidebarRow(kind, server_id, "Synthetic"), self.button, x, 10,
        )
        menu = self.host.active_context_popover
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        return menu

    def entry(self, widget, label):
        if isinstance(widget, Gtk.Label) and widget.get_label() == label:
            return widget.get_parent()
        child = widget.get_first_child()
        while child is not None:
            result = self.entry(child, label)
            if result is not None:
                return result
            child = child.get_next_sibling()
        return None

    def test_variants_share_native_menu_anchor_order_and_scroll_preservation(self):
        old = None
        labels = ["add_favorite", "connect", "notes_view_server", "edit_server",
                  "clone_connection", "send_files_to_server", "sftp_browse", "delete_server"]
        for kind, x in (("server", 10), ("favorite", 80), ("recent", 160)):
            menu = self.open_menu(kind, x=x)
            if old is not None:
                self.assertIs(menu, old)
            model = menu.get_menu_model()
            self.assertEqual([model.get_item_attribute_value(i, "label", None).unpack()
                              for i in range(model.get_n_items())], labels)
            _, point = self.button.compute_point(self.content, Graphene.Point().init(x, 10))
            _, rect = menu.get_pointing_to()
            self.assertEqual((rect.x, rect.y, rect.width, rect.height),
                             (int(point.x), int(point.y), 1, 1))
            self.host.close_active_context_menu()
            self.drain()
            self.assertIsNone(self.host.active_context_popover)
            self.assertIs(menu.get_parent(), self.content)
            self.host.preserve_sidebar_scroll.assert_any_call(11.0, 83.0)
            old = menu
        self.servers[1].favorite = True
        menu = self.open_menu()
        self.assertIsNotNone(self.entry(menu, "remove_favorite"))

    def test_native_entries_dispatch_all_commands_to_clicked_server_after_close(self):
        for action, label in (("favorite", "add_favorite"), ("connect", "connect"),
                              ("edit", "edit_server"), ("clone", "clone_connection"),
                              ("send-files", "send_files_to_server"), ("delete", "delete_server"),
                              ("notes", "notes_view_server"), ("sftp", "sftp_browse")):
            with self.subTest(action=action):
                menu = self.open_menu()
                self.entry(menu, label).emit("clicked")
                self.assertFalse(menu.get_visible())
                for command in self.commands.values():
                    command.assert_not_called()
                self.drain(wait=True)
                if action == "notes":
                    self.host.notes_dialogs.show_for_server_after_popover.assert_called_once_with(menu, "two")
                elif action == "sftp":
                    self.host.sftp_tool.browse.assert_called_once_with(menu, None, self.servers[1])
                else:
                    self.commands[action].assert_called_once_with(None, menu, "two")
                for command in self.commands.values():
                    command.reset_mock()
                self.host.notes_dialogs.show_for_server_after_popover.reset_mock()
                self.host.sftp_tool.browse.reset_mock()

    def test_read_only_locked_and_optional_sftp(self):
        self.host.store.read_only = True
        menu = self.open_menu()
        for label in ("add_favorite", "edit_server", "clone_connection", "delete_server"):
            self.assertFalse(self.entry(menu, label).is_sensitive())
        for label in ("connect", "notes_view_server", "send_files_to_server", "sftp_browse"):
            self.assertTrue(self.entry(menu, label).is_sensitive())
        self.host.close_active_context_menu()
        self.host.sftp_tool = None
        menu = self.open_menu()
        self.assertIsNone(self.entry(menu, "sftp_browse"))
        self.host.store.encryption_locked = True
        menu = self.open_menu()
        for action in self.host._server_context_actions.values():
            if action.get_name() != "sftp":
                self.assertFalse(action.get_enabled())
        menu.activate_action("server-menu.connect", None)
        self.drain(wait=True)
        self.commands["connect"].assert_not_called()

    def test_pending_action_revalidates_server_permissions_window_and_shutdown(self):
        for reason in ("deleted", "readonly", "locked", "hidden", "shutdown", "disposed"):
            with self.subTest(reason=reason):
                menu = self.open_menu()
                self.entry(menu, "edit_server").emit("clicked")
                removed = None
                if reason == "deleted":
                    removed = self.servers.pop()
                elif reason == "readonly":
                    self.host.store.read_only = True
                elif reason == "locked":
                    self.host.store.encryption_locked = True
                elif reason == "hidden":
                    self.host.set_visible(False)
                elif reason == "shutdown":
                    self.host.shutdown_in_progress = True
                else:
                    self.host.dispose_server_context_menu()
                self.drain(wait=True)
                self.commands["edit"].assert_not_called()
                if removed is not None:
                    self.servers.append(removed)
                self.host.store.read_only = self.host.store.encryption_locked = False
                self.host.shutdown_in_progress = False
                self.host.present()
                self.drain()

    def test_rebuild_rows_and_reopen_do_not_retain_old_target(self):
        menu = self.open_menu()
        self.rows.remove(self.button)
        self.button = Gtk.Button(label="Rebuilt")
        self.rows.append(self.button)
        self.entry(menu, "edit_server").emit("clicked")
        self.drain(wait=True)
        self.commands["edit"].assert_called_once_with(None, menu, "two")
        self.commands["edit"].reset_mock()
        self.open_menu()
        menu.popdown()
        self.open_menu(server_id="one")
        self.drain()
        self.entry(menu, "edit_server").emit("clicked")
        self.drain(wait=True)
        self.commands["edit"].assert_called_once_with(None, menu, "one")

    def test_disabling_sftp_before_dispatch_prevents_launch(self):
        menu = self.open_menu()
        tool = self.host.sftp_tool
        self.entry(menu, "sftp_browse").emit("clicked")
        self.host.sftp_tool = None
        self.drain(wait=True)
        tool.browse.assert_not_called()

    def test_saved_sidebar_menus_are_native_and_independent_of_server_popup(self):
        self.host.store.data.local_terminals = [LocalTerminalProfile("synthetic", "Profile")]
        self.host.store.data.workspaces = [Workspace("synthetic", "Workspace")]
        native = self.open_menu()
        self.host.close_active_context_menu()
        for kind in ("workspace", "local_terminal"):
            self.host.show_row_context_menu(
                SidebarRow(kind, "synthetic", "Synthetic"), self.button, 12, 10,
            )
            menu = self.host.active_context_popover
            self.assertIsInstance(menu, Gtk.Popover)
            self.assertIsInstance(menu, Gtk.PopoverMenu)
            self.host.close_active_context_menu()
            self.drain()
            self.assertIs(menu.get_parent(), self.content)
        self.assertIs(self.open_menu(), native)

    def test_missing_server_and_detached_parent_do_not_open_and_dispose_releases_popup(self):
        self.host.show_server_context_menu("missing", self.button, 1, 1)
        self.assertIsNone(self.host.active_context_popover)
        detached = Gtk.Button()
        self.host.show_server_context_menu("one", detached, 1, 1)
        self.assertIsNone(self.host.active_context_popover)
        menu = self.open_menu()
        self.host.dispose_server_context_menu()
        self.assertIsNone(menu.get_parent())
        self.assertIsNone(self.host.active_context_popover)


class SavedContextMenuTests(unittest.TestCase):
    drain = staticmethod(ServerContextMenuTests.drain)
    entry = ServerContextMenuTests.entry

    def setUp(self):
        ServerContextMenuTests.setUp(self)
        self.host.store.data.local_terminals = [LocalTerminalProfile("profile", "Profile")]
        self.host.store.data.workspaces = [Workspace("workspace", "Workspace")]
        self.saved_callbacks = {}
        for prefix, names in (("local_terminal", ("open", "edit", "clone", "delete")),
                              ("workspace", ("open", "update", "rename", "duplicate", "delete"))):
            for name in names:
                callback = Mock()
                self.saved_callbacks[prefix, name] = callback
                setattr(self.host, f"on_{prefix}_context_{name}", callback)

    destroy = ServerContextMenuTests.destroy

    def open_menu(self, kind="local_terminal"):
        self.host.show_row_context_menu(SidebarRow(kind, "profile" if kind == "local_terminal" else "workspace", "Saved"),
                                        self.button, 12, 10)
        return self.host.active_context_popover

    def test_native_entries_dispatch_each_profile_and_workspace_command(self):
        entries = {
            "local_terminal": (("open", "new_tab"), ("edit", "edit_local_terminal"),
                               ("clone", "clone_connection"), ("delete", "delete_local_terminal")),
            "workspace": (("open", "open_workspace"), ("update", "update_workspace"),
                          ("rename", "rename_workspace"), ("duplicate", "duplicate_workspace"),
                          ("delete", "delete_workspace")),
        }
        previous = None
        for kind, items in entries.items():
            for name, label in items:
                menu = self.open_menu(kind)
                self.assertIsInstance(menu, Gtk.PopoverMenu)
                if previous is not None:
                    self.assertIs(menu, previous)
                self.entry(menu, label).emit("clicked")
                self.assertFalse(menu.get_visible())
                self.saved_callbacks[kind, name].assert_not_called()
                self.drain(wait=True)
                self.saved_callbacks[kind, name].assert_called_once_with(
                    menu, "profile" if kind == "local_terminal" else "workspace")
                self.saved_callbacks[kind, name].reset_mock()
                previous = menu

    def test_saved_permissions_and_stale_targets_are_rechecked(self):
        for kind in ("local_terminal", "workspace"):
            self.host.store.read_only = True
            menu = self.open_menu(kind)
            self.assertTrue(self.entry(menu, "new_tab" if kind == "local_terminal" else "open_workspace").is_sensitive())
            label = "edit_local_terminal" if kind == "local_terminal" else "rename_workspace"
            self.assertFalse(self.entry(menu, label).is_sensitive())
            self.host.store.read_only = False
            menu = self.open_menu(kind)
            self.entry(menu, label).emit("clicked")
            self.host.store.encryption_locked = True
            self.drain(wait=True)
            for callback in self.saved_callbacks.values():
                callback.assert_not_called()
            self.host.store.encryption_locked = False
        menu = self.open_menu()
        self.entry(menu, "new_tab").emit("clicked")
        self.host.store.data.local_terminals.clear()
        self.drain(wait=True)
        self.saved_callbacks["local_terminal", "open"].assert_not_called()

    def test_switching_kind_before_old_close_idle_preserves_new_target(self):
        old = self.open_menu()
        old.popdown()
        menu = self.open_menu("workspace")
        self.drain()
        self.entry(menu, "rename_workspace").emit("clicked")
        self.drain(wait=True)
        self.saved_callbacks["workspace", "rename"].assert_called_once_with(menu, "workspace")


class GroupContextMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")

        class Host(SidebarMixin, Gtk.Window):
            pass

        self.host = Host()
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.rows = Gtk.Box()
        self.button = Gtk.Button(label="Group")
        self.button.set_size_request(300, 40)
        self.rows.append(self.button)
        self.content.append(self.rows)
        self.host.set_child(self.content)
        self.host.present()
        self.host.active_context_popover = None
        self.groups = [Group("parent", "Parent"), Group("child", "Child", "parent"),
                       Group("other", "Other")]
        self.servers = [Server("one", "Zulu", "one.test", "user", group_id="parent"),
                        Server("two", "Alpha", "two.test", "user", group_id="child"),
                        Server("three", "Outside", "outside.test", "user", group_id="other")]
        self.host.store = SimpleNamespace(
            read_only=False, encryption_locked=False,
            data=SimpleNamespace(groups=self.groups, servers=self.servers),
        )
        self.host.t = lambda key: key
        self.host.get_sidebar_scroll_values = lambda: (120.0, 0.0)
        self.host.preserve_sidebar_scroll = Mock()
        self.host.ensure_writable = lambda: not (self.host.store.read_only or self.host.store.encryption_locked)
        self.host.show_group_dialog = Mock()
        self.host.can_open_terminal_tabs = Mock(return_value=True)
        self.host.open_terminal_tab = Mock()
        self.host.request_delete_group = Mock()
        self.addCleanup(self.destroy)
        self.drain()

    drain = staticmethod(ServerContextMenuTests.drain)
    entry = ServerContextMenuTests.entry

    def destroy(self):
        for window in Gtk.Window.list_toplevels():
            if window.get_transient_for() is self.host:
                window.destroy()
        self.host.dispose_group_context_menu()
        self.host.dispose_server_context_menu()
        self.drain()
        self.host.destroy()

    def open_menu(self, group_id="parent", x=15):
        self.host.show_row_context_menu(
            SidebarRow("group", group_id, "Group"), self.button, x, 10,
        )
        menu = self.host.active_context_popover
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        return menu

    def test_order_anchor_reuse_and_cleanup_for_parent_and_subgroup(self):
        previous = None
        for group_id, x in (("parent", 10), ("child", 160)):
            menu = self.open_menu(group_id, x)
            if previous is not None:
                self.assertIs(menu, previous)
            model = menu.get_menu_model()
            self.assertEqual([model.get_item_attribute_value(i, "label", None).unpack()
                              for i in range(model.get_n_items())],
                             ["start_group", "new_subgroup", "edit_group", "delete_group"])
            _, point = self.button.compute_point(self.content, Graphene.Point().init(x, 10))
            _, rect = menu.get_pointing_to()
            self.assertEqual((rect.x, rect.y), (int(point.x), int(point.y)))
            self.host.close_active_context_menu()
            self.drain()
            self.assertIs(menu.get_parent(), self.content)
            self.host.preserve_sidebar_scroll.assert_any_call(120.0, 0.0)
            previous = menu
        self.host.dispose_group_context_menu()
        self.assertIsNone(menu.get_parent())

    def test_native_entries_call_existing_handlers_on_clicked_group_after_close(self):
        for group_id in ("parent", "child"):
            for action in ("start", "subgroup", "edit", "delete"):
                with self.subTest(group=group_id, action=action):
                    menu = self.open_menu(group_id)
                    self.entry(menu, {"start": "start_group", "subgroup": "new_subgroup",
                                      "edit": "edit_group", "delete": "delete_group"}[action]).emit("clicked")
                    self.assertFalse(menu.get_visible())
                    self.host.show_group_dialog.assert_not_called()
                    self.host.open_terminal_tab.assert_not_called()
                    self.host.request_delete_group.assert_not_called()
                    self.drain(wait=True)
                    group = next(item for item in self.groups if item.id == group_id)
                    if action == "start":
                        expected = self.servers[:2][::-1] if group_id == "parent" else [self.servers[1]]
                        self.assertEqual([call.args[0] for call in self.host.open_terminal_tab.call_args_list], expected)
                    elif action == "subgroup":
                        self.host.show_group_dialog.assert_called_once_with(parent_group_id=group_id)
                    elif action == "edit":
                        self.host.show_group_dialog.assert_called_once_with(group)
                    else:
                        self.host.request_delete_group.assert_called_once_with(group_id)
                    self.host.show_group_dialog.reset_mock()
                    self.host.open_terminal_tab.reset_mock()
                    self.host.request_delete_group.reset_mock()

    def test_permissions_keep_start_in_read_only_and_disable_all_when_locked(self):
        self.host.store.read_only = True
        menu = self.open_menu()
        self.assertTrue(self.entry(menu, "start_group").is_sensitive())
        for label in ("new_subgroup", "edit_group", "delete_group"):
            self.assertFalse(self.entry(menu, label).is_sensitive())
        self.entry(menu, "start_group").emit("clicked")
        self.drain(wait=True)
        self.assertEqual(self.host.open_terminal_tab.call_count, 2)
        self.host.open_terminal_tab.reset_mock()
        self.host.store.encryption_locked = True
        menu = self.open_menu()
        for name, action in self.host._group_context_actions.items():
            self.assertFalse(action.get_enabled())
            menu.activate_action(f"group-menu.{name}", None)
        self.drain(wait=True)
        self.host.open_terminal_tab.assert_not_called()
        self.host.show_group_dialog.assert_not_called()

    def test_deferred_commands_reject_deleted_group_permissions_close_and_disposal(self):
        for reason in ("deleted", "readonly", "locked", "hidden", "shutdown", "disposed"):
            with self.subTest(reason=reason):
                menu = self.open_menu("child")
                self.entry(menu, "edit_group").emit("clicked")
                removed = None
                if reason == "deleted":
                    removed = self.groups.pop(1)
                elif reason == "readonly":
                    self.host.store.read_only = True
                elif reason == "locked":
                    self.host.store.encryption_locked = True
                elif reason == "hidden":
                    self.host.set_visible(False)
                elif reason == "shutdown":
                    self.host.shutdown_in_progress = True
                else:
                    self.host.dispose_group_context_menu()
                self.drain(wait=True)
                self.host.show_group_dialog.assert_not_called()
                if removed is not None:
                    self.groups.insert(1, removed)
                self.host.store.read_only = self.host.store.encryption_locked = False
                self.host.shutdown_in_progress = False
                self.host.present()
                self.drain()

    def test_row_rebuild_and_reopen_preserve_group_identity(self):
        menu = self.open_menu()
        self.rows.remove(self.button)
        self.button = Gtk.Button(label="Rebuilt")
        self.rows.append(self.button)
        self.entry(menu, "edit_group").emit("clicked")
        self.drain(wait=True)
        self.host.show_group_dialog.assert_called_once_with(self.groups[0])
        self.host.show_group_dialog.reset_mock()
        self.open_menu()
        menu.popdown()
        self.open_menu("child")
        self.drain()
        self.entry(menu, "edit_group").emit("clicked")
        self.drain(wait=True)
        self.host.show_group_dialog.assert_called_once_with(self.groups[1])

    def test_missing_group_and_synthetic_root_do_not_open_menu(self):
        for group_id in ("", "missing"):
            self.host.show_row_context_menu(
                SidebarRow("group", group_id, "Group"), self.button, 1, 1,
            )
            self.assertIsNone(self.host.active_context_popover)

    def test_switching_server_and_group_menus_preserves_each_cached_popup(self):
        self.host.sftp_tool = None
        group_menu = self.open_menu()
        self.host.show_row_context_menu(
            SidebarRow("server", "one", "Server"), self.button, 20, 10,
        )
        server_menu = self.host.active_context_popover
        self.assertIsInstance(server_menu, Gtk.PopoverMenu)
        self.assertIsNot(server_menu, group_menu)
        self.assertIs(self.open_menu("child"), group_menu)
        self.drain()
        self.entry(group_menu, "edit_group").emit("clicked")
        self.drain(wait=True)
        self.host.show_group_dialog.assert_called_once_with(self.groups[1])
        self.assertIs(server_menu.get_parent(), self.content)

    def test_group_start_limit_and_large_group_confirmation_cancel_and_accept(self):
        self.host.can_open_terminal_tabs.return_value = False
        menu = self.open_menu()
        self.entry(menu, "start_group").emit("clicked")
        self.drain(wait=True)
        self.host.open_terminal_tab.assert_not_called()
        self.host.can_open_terminal_tabs.return_value = True
        self.servers[:] = [Server(str(i), f"Server {i:02}", "synthetic.test", "user",
                                  group_id="child") for i in range(11)]
        for label in ("cancel", "start_group"):
            menu = self.open_menu()
            self.entry(menu, "start_group").emit("clicked")
            self.drain(wait=True)
            alerts = [window for window in Gtk.Window.list_toplevels()
                      if window.get_visible() and window.get_transient_for() is self.host]
            self.assertEqual(len(alerts), 1)
            self.host.open_terminal_tab.assert_not_called()
            self.entry(alerts[0], label).emit("clicked")
            self.drain(wait=True)
        self.assertEqual([call.args[0] for call in self.host.open_terminal_tab.call_args_list], self.servers)

    def test_real_delete_confirmation_cancel_and_accept(self):
        self.host.request_delete_group = SidebarMixin.request_delete_group.__get__(self.host)
        self.host.store.delete_group = Mock()
        self.host.toast_label = Gtk.Label()
        self.host.refresh_list = Mock()
        self.host.render_detail = Mock()
        for label in ("cancel", "delete_group"):
            menu = self.open_menu("child")
            self.entry(menu, "delete_group").emit("clicked")
            self.drain(wait=True)
            alerts = [window for window in Gtk.Window.list_toplevels()
                      if window.get_visible() and window.get_transient_for() is self.host]
            self.assertEqual(len(alerts), 1)
            self.host.store.delete_group.assert_not_called()
            self.entry(alerts[0], label).emit("clicked")
            self.drain(wait=True)
        self.host.store.delete_group.assert_called_once_with("child")


if __name__ == "__main__":
    unittest.main()
