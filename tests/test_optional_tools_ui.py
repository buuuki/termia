import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from termia.dialog_window import DialogWindow
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
        def labels() -> list[str]:
            popover = host.build_main_menu(actions, write_allowed=True)
            model = popover.get_menu_model()
            result = []
            for index in range(model.get_n_items()):
                section = model.get_item_link(index, Gio.MENU_LINK_SECTION)
                result.extend(
                    section.get_item_attribute_value(item, "label", None).unpack()
                    for item in range(section.get_n_items())
                )
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
            if isinstance(window, DialogWindow) and window.get_title() == "optional_tools"
        )
        self.addCleanup(parent.destroy)
        self.addCleanup(dialog.destroy)

        content = dialog.get_content_area()
        sftp = content.get_first_child().get_last_child()
        self.assertIsInstance(sftp, Gtk.Switch)
        self.assertTrue(sftp.get_active())
        sftp.set_active(False)
        dialog.response(Gtk.ResponseType.OK)

        store.update_optional_tools.assert_called_once_with(
            statistics_enabled=False, sftp_enabled=False
        )
        notifier.assert_called_once_with("addon_pending_restart")

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
            if isinstance(window, DialogWindow) and window.get_title() == "optional_tools"
        )
        self.addCleanup(parent.destroy)
        self.addCleanup(dialog.destroy)

        self.assertFalse(dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive())
        store.update_optional_tools.assert_not_called()


@unittest.skipUnless(
    (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check(),
    "GTK display unavailable",
)
class ExternalToolsDialogTests(unittest.TestCase):
    def open_dialog(self, *, enabled=False, read_only=False, locked=False):
        parent = Gtk.Window()
        self.addCleanup(parent.destroy)
        store = SimpleNamespace(
            read_only=read_only,
            encryption_locked=locked,
            data=SimpleNamespace(app=SimpleNamespace(statistics_enabled=False, sftp_enabled=True)),
            update_optional_tools=Mock(),
        )
        state = {"alpha": enabled, "beta": False}
        titles = {"alpha": "Alpha", "beta": "Beta"}

        def options():
            return [(key, titles[key], "", active, True) for key, active in state.items()]

        def apply(identifier, active):
            state[identifier] = active

        callback = Mock(side_effect=apply)
        notifier = Mock()
        messages = {
            "addon_external_title": "External: {name}",
            "addon_external_pending": "Pending: {addons}",
            "addon_external_applied": "Applied: {addons}",
            "addon_external_failed": "Failed: {name}",
        }
        previous = set(Gtk.Window.list_toplevels())
        OptionalToolsDialog(
            parent, store, lambda key: messages.get(key, key), notifier,
            external_options=options, external_apply=callback,
        ).show()
        dialog = next(window for window in Gtk.Window.list_toplevels()
                      if window not in previous and isinstance(window, DialogWindow))
        self.addCleanup(dialog.destroy)
        switches = {}
        child = dialog.get_content_area().get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Box):
                switch = child.get_last_child()
                if isinstance(switch, Gtk.Switch):
                    switches[switch.get_tooltip_text()] = switch
            child = child.get_next_sibling()
        return SimpleNamespace(
            dialog=dialog, store=store, state=state, apply=callback, notify=notifier,
            alpha=switches["External: Alpha"], beta=switches["External: Beta"],
        )

    def test_external_changes_apply_only_on_save(self):
        for initial in (False, True):
            with self.subTest(initial=initial):
                ui = self.open_dialog(enabled=initial)
                ui.alpha.set_active(not initial)
                self.assertEqual(ui.state["alpha"], initial)
                ui.apply.assert_not_called()
                ui.dialog.response(Gtk.ResponseType.OK)
                ui.apply.assert_called_once_with("alpha", not initial)
                self.assertEqual(ui.state["alpha"], not initial)
                ui.store.update_optional_tools.assert_not_called()
                ui.notify.assert_called_once_with("Applied: Alpha")
                self.assertNotIn(ui.dialog, Gtk.Window.list_toplevels())

    def test_cancel_and_close_discard_external_changes(self):
        for response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
            with self.subTest(response=response):
                ui = self.open_dialog()
                ui.alpha.set_active(True)
                ui.dialog.response(response)
                ui.apply.assert_not_called()
                ui.store.update_optional_tools.assert_not_called()
                ui.notify.assert_not_called()
                self.assertFalse(ui.state["alpha"])
                self.assertNotIn(ui.dialog, Gtk.Window.list_toplevels())

    def test_save_without_changes_does_not_apply_plugins(self):
        ui = self.open_dialog()
        ui.dialog.response(Gtk.ResponseType.OK)
        ui.apply.assert_not_called()
        ui.store.update_optional_tools.assert_not_called()
        ui.notify.assert_not_called()
        self.assertNotIn(ui.dialog, Gtk.Window.list_toplevels())

    def test_locked_profiles_disable_external_controls(self):
        for field in ("read_only", "encryption_locked"):
            with self.subTest(field=field):
                ui = self.open_dialog(read_only=field == "read_only",
                                      locked=field == "encryption_locked")
                self.assertFalse(ui.alpha.get_sensitive())
                self.assertFalse(ui.beta.get_sensitive())
                self.assertFalse(ui.dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive())
                ui.alpha.set_active(True)
                ui.dialog.response(Gtk.ResponseType.OK)
                ui.apply.assert_not_called()
                ui.store.update_optional_tools.assert_not_called()
                self.assertFalse(ui.state["alpha"])

    def test_profile_lock_after_selection_prevents_save(self):
        for field in ("read_only", "encryption_locked"):
            with self.subTest(field=field):
                ui = self.open_dialog()
                ui.alpha.set_active(True)
                setattr(ui.store, field, True)
                ui.dialog.response(Gtk.ResponseType.OK)
                ui.apply.assert_not_called()
                ui.store.update_optional_tools.assert_not_called()
                self.assertFalse(ui.state["alpha"])
                ui.notify.assert_called_once_with("read_only_mode_enabled")
                self.assertIn(ui.dialog, Gtk.Window.list_toplevels())
                ui.dialog.destroy()

    def test_partial_failure_keeps_success_and_retry_does_not_repeat_it(self):
        ui = self.open_dialog()

        def fail_second(identifier, active):
            if identifier == "beta":
                raise OSError("synthetic preference write failure")
            ui.state[identifier] = active

        ui.apply.side_effect = fail_second
        ui.alpha.set_active(True)
        ui.beta.set_active(True)
        with self.assertLogs("termia.optional_tools_dialog", level="ERROR"):
            ui.dialog.response(Gtk.ResponseType.OK)
        self.assertEqual(ui.apply.call_args_list, [call("alpha", True), call("beta", True)])
        self.assertEqual(ui.state, {"alpha": True, "beta": False})
        self.assertTrue(ui.alpha.get_active())
        self.assertFalse(ui.beta.get_active())
        self.assertIn(ui.dialog, Gtk.Window.list_toplevels())
        ui.notify.assert_called_once_with("Applied: Alpha\nFailed: Beta")
        labels = []
        child = ui.dialog.get_content_area().get_first_child()
        while child is not None:
            if isinstance(child, Gtk.Label) and child.get_visible():
                labels.append(child.get_text())
            child = child.get_next_sibling()
        self.assertIn("Failed: Beta", labels)
        ui.apply.reset_mock()
        ui.notify.reset_mock()
        ui.apply.side_effect = lambda identifier, active: ui.state.__setitem__(identifier, active)
        ui.beta.set_active(True)
        ui.dialog.response(Gtk.ResponseType.OK)
        ui.apply.assert_called_once_with("beta", True)
        self.assertEqual(ui.state, {"alpha": True, "beta": True})
        ui.notify.assert_called_once_with("Applied: Beta")
        ui.store.update_optional_tools.assert_not_called()
        self.assertNotIn(ui.dialog, Gtk.Window.list_toplevels())


if __name__ == "__main__":
    unittest.main()
