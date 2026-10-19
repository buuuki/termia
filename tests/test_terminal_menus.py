import time
import unittest
from dataclasses import fields, replace
from types import SimpleNamespace
from unittest.mock import Mock

from termia.models import Server
from termia.terminal_menu_actions import TerminalMenuActions
from termia.terminal_menus import Gdk, Gio, GLib, Gtk, Vte, TerminalMenusMixin


class NativeTerminalMenuTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")
        self.window = Gtk.Window()
        self.terminal = Vte.Terminal()
        self.window.set_child(self.terminal)
        self.window.present()
        self.host = TerminalMenusMixin()
        self.host.t = lambda key: key
        self.callbacks = {field.name: Mock() for field in fields(TerminalMenuActions)}
        self.host.terminal_menu_actions = TerminalMenuActions(**self.callbacks)
        self.server = Server("server", "Synthetic", "synthetic.test", "user")
        self.host.store = SimpleNamespace(data=SimpleNamespace(
            servers=[self.server], app=SimpleNamespace(keybindings={"copy": "<Control><Shift>c"}),
        ))
        self.pane = SimpleNamespace(server_id="server", status_bar=Gtk.Box())
        self.session = SimpleNamespace(id="session", detached_window=None)
        self.session.pane_for_terminal = lambda widget: self.pane if widget is self.terminal else None
        self.sessions = {"session": self.session}
        self.host.session_registry = SimpleNamespace(get=self.sessions.get)
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
        self.host.dispose_terminal_context_menu(self.window)
        self.drain()
        self.window.destroy()

    def open_menu(self):
        self.host.on_terminal_right_click(None, 1, 10, 12, self.session, self.terminal)
        menu = self.host._terminal_context_menus[self.window]
        self.assertIsInstance(menu, Gtk.PopoverMenu)
        return menu

    @staticmethod
    def labels(model):
        return [model.get_item_attribute_value(i, "label", None).unpack()
                for i in range(model.get_n_items())
                if model.get_item_attribute_value(i, "label", None) is not None]

    def entry(self, widget, text):
        if isinstance(widget, Gtk.Label) and widget.get_label() == text:
            return widget.get_parent()
        child = widget.get_first_child()
        while child is not None:
            result = self.entry(child, text)
            if result is not None:
                return result
            child = child.get_next_sibling()
        return None

    def test_model_nested_order_shortcuts_and_optional_actions(self):
        menu = self.open_menu()
        model = menu.get_menu_model()
        self.assertEqual(self.labels(model)[:4], ["disconnect", "hide_session_status_bar", "copy", "paste"])
        self.assertEqual(model.get_item_attribute_value(2, "accel", None).unpack(), "<Control><Shift>c")
        section = model.get_item_link(model.get_n_items() - 1, Gio.MENU_LINK_SECTION)
        self.assertEqual(self.labels(section), ["split", "tab"])
        split = section.get_item_link(0, Gio.MENU_LINK_SUBMENU)
        self.assertEqual(self.labels(split), ["split_up", "split_down", "split_right", "split_left",
                                              "open_connection_in_split"])
        menu.popdown()
        self.drain()
        self.host.terminal_menu_actions = replace(self.host.terminal_menu_actions,
            browse_files=None, run_snippet=None, session_statistics=None)
        model = self.open_menu().get_menu_model()
        self.assertFalse({"sftp_browse", "run_snippet", "session_statistics"} & set(self.labels(model)))

    def test_native_copy_entry_closes_before_deferred_dispatch_and_menu_reuses(self):
        menu = self.open_menu()
        self.entry(menu, "copy").emit("clicked")
        self.assertFalse(menu.get_visible())
        self.callbacks["copy"].assert_not_called()
        self.drain(wait=True)
        self.callbacks["copy"].assert_called_once_with(menu, self.terminal)
        self.assertIs(self.open_menu(), menu)
        self.host.dispose_terminal_context_menu(self.window)
        self.assertIsNone(menu.get_parent())

    def test_scoped_actions_including_each_split_and_tab_command(self):
        for name, callback, tail in (
            ("status", "toggle_status_bar", (self.session, self.terminal)),
            ("disconnect", "disconnect", (self.session, self.terminal)),
            ("paste", "paste", (self.terminal,)),
            ("configure", "configure", (self.session,)),
            ("statistics", "session_statistics", (self.session, self.terminal)),
            ("snippet", "run_snippet", (self.session, self.terminal)),
            ("sftp", "browse_files", (self.session, self.server)),
            ("send", "send_files", (self.session, self.server)),
            ("split-up", "split", (self.session, self.terminal, "up")),
            ("split-down", "split", (self.session, self.terminal, "down")),
            ("split-right", "split", (self.session, self.terminal, "right")),
            ("split-left", "split", (self.session, self.terminal, "left")),
            ("split-connection", "split_connection", (self.session, self.terminal)),
            ("rename", "rename_tab", (self.session,)),
            ("duplicate", "duplicate_tab", (self.session,)),
            ("new", "new_tab", ()), ("close", "close_tab", (self.session,)),
        ):
            with self.subTest(action=name):
                menu = self.open_menu()
                menu.activate_action(f"terminal-menu.{name}", None)
                self.drain(wait=True)
                self.callbacks[callback].assert_called_once_with(menu, *tail)
                self.callbacks[callback].reset_mock()

    def test_stale_session_pane_shutdown_or_window_cannot_dispatch(self):
        for reason in ("session", "pane", "shutdown", "hidden"):
            menu = self.open_menu()
            menu.activate_action("terminal-menu.copy", None)
            if reason == "session":
                self.sessions.clear()
            elif reason == "pane":
                self.session.pane_for_terminal = lambda widget: None
            elif reason == "shutdown":
                self.host.shutdown_in_progress = True
            else:
                self.window.set_visible(False)
            self.drain(wait=True)
            self.callbacks["copy"].assert_not_called()
            self.sessions["session"] = self.session
            self.session.pane_for_terminal = lambda widget: self.pane
            self.host.shutdown_in_progress = False
            self.window.present()
            self.drain()

    def test_detached_menu_includes_reattach_and_server_actions_use_latest_server(self):
        self.session.detached_window = self.window
        menu = self.open_menu()
        model = menu.get_menu_model()
        self.assertEqual(self.labels(model)[:5],
                         ["disconnect", "hide_session_status_bar", "reattach_tab", "copy", "paste"])
        section = model.get_item_link(model.get_n_items() - 1, Gio.MENU_LINK_SECTION)
        tab = section.get_item_link(1, Gio.MENU_LINK_SUBMENU)
        self.assertNotIn("reattach_tab", self.labels(tab))
        menu.activate_action("terminal-menu.reattach", None)
        self.drain(wait=True)
        self.callbacks["reattach_tab"].assert_called_once_with(menu, self.session)
        menu = self.open_menu()
        menu.activate_action("terminal-menu.send", None)
        updated = replace(self.server, name="Updated")
        self.host.store.data.servers[:] = [updated]
        self.drain(wait=True)
        self.callbacks["send_files"].assert_called_once_with(menu, self.session, updated)

    def test_leaving_native_submenu_closes_only_child_and_crossing_to_panel_keeps_it(self):
        menu = self.open_menu()
        panels = []
        def collect(widget):
            if isinstance(widget, Gtk.Popover) and widget is not menu:
                panels.append(widget)
            child = widget.get_first_child()
            while child is not None:
                collect(child)
                child = child.get_next_sibling()
        collect(menu)
        self.assertEqual(len(panels), 2)
        panel = panels[0]
        row = self.entry(menu, "split")
        def motion(widget):
            controllers = widget.observe_controllers()
            return next(controllers.get_item(i) for i in range(controllers.get_n_items())
                        if controllers.get_item(i).get_name() == "termia-submenu-leave")
        row_motion, panel_motion = motion(row), motion(panel)
        panel.popup()
        row_motion.emit("enter", 1.0, 1.0)
        row_motion.emit("leave")
        panel_motion.emit("enter", 1.0, 1.0)
        self.drain(wait=True)
        self.assertTrue(panel.get_visible())
        panel_motion.emit("leave")
        self.drain(wait=True)
        self.assertFalse(panel.get_visible())
        self.assertTrue(menu.get_visible())
        self.assertTrue(menu.get_autohide())
        self.assertIs(menu._termia_target[0], self.session)
        menu.activate_action("terminal-menu.copy", None)
        self.drain(wait=True)
        self.callbacks["copy"].assert_called_once_with(menu, self.terminal)
