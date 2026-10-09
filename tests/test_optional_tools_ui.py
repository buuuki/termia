import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.main_menu import MainMenuMixin
from termia.optional_tools_dialog import OptionalToolsDialog


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class OptionalToolsUITests(unittest.TestCase):
    def test_main_menu_only_shows_statistics_when_enabled(self) -> None:
        class Host(MainMenuMixin):
            t = staticmethod(lambda key: key)

            def configure_write_action(self, _button) -> None:
                pass

        host = Host()
        actions = SimpleNamespace(**{
            key: Mock()
            for key in (
                "general_preferences", "terminal_settings", "keybinding_settings",
                "security_settings", "optional_tools", "manage_snippets", "manage_notes",
                "statistics", "connection_history", "data_locations", "export_config",
                "import_config", "import_asbru_config", "clear_config", "help", "about",
            )
        })
        popover = Gtk.Popover()

        def labels() -> list[str]:
            content = host.build_main_menu_content(popover, actions)
            result = []
            child = content.get_first_child()
            while child is not None:
                if isinstance(child, Gtk.Button):
                    result.append(child.get_label())
                child = child.get_next_sibling()
            return result

        self.assertIn("optional_tools", labels())
        self.assertIn("statistics", labels())
        actions.statistics = None
        self.assertNotIn("statistics", labels())

    def test_save_records_choices_but_does_not_change_startup_snapshot(self) -> None:
        parent = Gtk.Window()
        store = SimpleNamespace(
            read_only=False,
            encryption_locked=False,
            data=SimpleNamespace(app=SimpleNamespace(statistics_enabled=False, sftp_enabled=True)),
            update_optional_tools=Mock(),
        )
        notifier = Mock()
        OptionalToolsDialog(parent, store, lambda key: key, notifier).show()
        dialog = next(
            window for window in Gtk.Window.list_toplevels()
            if isinstance(window, Gtk.Dialog) and window.get_title() == "optional_tools"
        )
        self.addCleanup(parent.destroy)
        self.addCleanup(dialog.destroy)

        content = dialog.get_content_area()
        statistics_row = content.get_first_child()
        sftp_row = statistics_row.get_next_sibling()
        statistics = statistics_row.get_last_child()
        sftp = sftp_row.get_last_child()
        self.assertIsInstance(statistics, Gtk.Switch)
        self.assertIsInstance(sftp, Gtk.Switch)
        self.assertFalse(statistics.get_active())
        self.assertTrue(sftp.get_active())
        statistics.set_active(True)
        sftp.set_active(False)
        dialog.response(Gtk.ResponseType.OK)

        store.update_optional_tools.assert_called_once_with(
            statistics_enabled=True, sftp_enabled=False
        )
        notifier.assert_called_once_with("optional_tools_restart")

    def test_read_only_instance_cannot_save_tool_changes(self) -> None:
        parent = Gtk.Window()
        store = SimpleNamespace(
            read_only=True,
            encryption_locked=False,
            data=SimpleNamespace(app=SimpleNamespace(statistics_enabled=False, sftp_enabled=True)),
            update_optional_tools=Mock(),
        )
        OptionalToolsDialog(parent, store, lambda key: key, Mock()).show()
        dialog = next(
            window for window in Gtk.Window.list_toplevels()
            if isinstance(window, Gtk.Dialog) and window.get_title() == "optional_tools"
        )
        self.addCleanup(parent.destroy)
        self.addCleanup(dialog.destroy)

        self.assertFalse(dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive())
        store.update_optional_tools.assert_not_called()


if __name__ == "__main__":
    unittest.main()
