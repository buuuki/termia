# SPDX-License-Identifier: GPL-3.0-or-later
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from termia.tool_launcher import GLib, Gtk, Tool, ToolLauncher, ToolRegistry


def settle(seconds=0.2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(0.002)


class ToolLauncherTests(unittest.TestCase):
    def test_editor_action_reuses_editor_owned_by_another_main_window(self):
        from termia.app import TermiaWindow

        owner = Mock(spec=TermiaWindow)
        editor = Mock()
        owner.retron_runtime = SimpleNamespace(editor=editor)
        host = SimpleNamespace(
            get_application=lambda: SimpleNamespace(get_windows=lambda: [owner]),
            retron_runtime=Mock(), t=Mock())
        TermiaWindow.on_retron_editor(host)
        editor.present.assert_called_once_with()
        host.retron_runtime.show_editor.assert_not_called()

    def setUp(self):
        self.registry = ToolRegistry()
        self.action = Mock()
        self.enabled = True
        self.registry.register(Tool("one", "One", "preferences-system-symbolic", self.action, lambda: self.enabled))
        self.window = Gtk.Window(default_width=300, default_height=180)
        self.launcher = ToolLauncher(self.registry, lambda key: key)
        self.window.set_child(self.launcher)
        self.window.present()
        self.addCleanup(self.cleanup)
        settle()

    def cleanup(self):
        self.launcher.close()
        self.window.destroy()
        settle(0.02)

    def test_available_tools_refresh_and_registry_rejects_duplicates(self):
        with self.assertRaises(ValueError):
            self.registry.register(Tool("one", "Duplicate", "", self.action))
        self.assertEqual(set(self.launcher.buttons), {"one"})
        self.enabled = False
        self.launcher.refresh()
        self.assertEqual(self.launcher.buttons, {})
        self.assertFalse(self.launcher.get_sensitive())
        self.registry.register(Tool("two", "Two", "utilities-terminal-symbolic", self.action))
        self.launcher.refresh()
        self.assertEqual(set(self.launcher.buttons), {"two"})
        self.registry.unregister("two")
        self.assertEqual(self.registry.available(), ())

    def test_activation_closes_popup_and_dispatches_once_after_release(self):
        self.launcher.popup()
        settle()
        self.launcher.buttons["one"].emit("clicked")
        self.launcher.buttons["one"].emit("clicked")
        self.assertFalse(self.launcher.panel.get_visible())
        self.action.assert_not_called()
        settle()
        self.action.assert_called_once_with()

    def test_pending_action_rechecks_availability_and_is_cancelled_on_close(self):
        self.launcher.buttons["one"].emit("clicked")
        self.enabled = False
        settle()
        self.action.assert_not_called()
        self.enabled = True
        self.launcher.buttons["one"].emit("clicked")
        self.launcher.close()
        settle()
        self.action.assert_not_called()

    def test_native_flowbox_activation_and_focus(self):
        self.launcher.popup()
        settle()
        child = self.launcher.grid.get_child_at_index(0)
        self.assertTrue(child.child_focus(Gtk.DirectionType.TAB_FORWARD))
        self.launcher.grid.emit("child-activated", child)
        settle()
        self.action.assert_called_once_with()
