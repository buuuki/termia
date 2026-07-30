import importlib.util
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, call, patch


@unittest.skipUnless(importlib.util.find_spec("gi"), "GTK bindings are unavailable")
class StartupTerminalTests(unittest.TestCase):
    def setUp(self) -> None:
        from termia.app import TermiaApp, TermiaWindow

        self.TermiaApp = TermiaApp
        self.TermiaWindow = TermiaWindow

    def test_application_presents_new_window_and_focuses_startup_control(self) -> None:
        app = SimpleNamespace(props=SimpleNamespace(active_window=None))
        window = Mock()

        with patch("termia.app.TermiaWindow", return_value=window):
            self.TermiaApp.do_activate(app)

        self.assertEqual(
            window.method_calls,
            [call.present(), call.focus_startup_control()],
        )

    def test_application_does_not_restart_an_existing_window(self) -> None:
        window = Mock()
        app = SimpleNamespace(props=SimpleNamespace(active_window=window))

        self.TermiaApp.do_activate(app)

        self.assertEqual(window.method_calls, [call.present()])

    def window(
        self,
        *,
        open_on_startup: bool,
        read_only: bool = False,
        unlock_succeeds: bool = False,
    ) -> SimpleNamespace:
        window = SimpleNamespace(
            store=SimpleNamespace(
                read_only=read_only,
                data=SimpleNamespace(
                    app=SimpleNamespace(
                        open_local_terminal_on_startup=open_on_startup,
                    )
                ),
                encryption_error="synthetic encryption error",
                unlock_connections=Mock(return_value=unlock_succeeds),
            ),
            toast_label=SimpleNamespace(set_label=Mock()),
            t=lambda key: key,
            open_startup_local_terminal=Mock(),
            apply_app_theme=Mock(),
            refresh_translated_chrome=Mock(),
            refresh_list=Mock(),
            unlock_panel=Mock(),
            unlock_scrim=Mock(),
            main_root=Mock(),
            toggle_sidebar_button=Mock(),
            new_tab_button=Mock(),
            main_menu_button=Mock(),
            unlock_password_entry=Mock(),
            unlock_error_label=Mock(),
        )
        window.unlock_password_entry.get_text.return_value = "synthetic-password"
        window.schedule_startup_local_terminal = MethodType(
            self.TermiaWindow.schedule_startup_local_terminal,
            window,
        )
        window.hide_unlock_panel = MethodType(
            self.TermiaWindow.hide_unlock_panel,
            window,
        )
        window.set_unlock_header_actions_sensitive = MethodType(
            self.TermiaWindow.set_unlock_header_actions_sensitive,
            window,
        )
        return window

    def test_unlock_panel_is_shown_inside_the_main_window(self) -> None:
        window = self.window(open_on_startup=True)

        result = self.TermiaWindow.request_unlock_connections(window)

        window.unlock_panel.set_visible.assert_called_once_with(True)
        window.unlock_scrim.set_visible.assert_called_once_with(True)
        window.main_root.set_sensitive.assert_called_once_with(False)
        window.toggle_sidebar_button.set_sensitive.assert_called_once_with(False)
        window.new_tab_button.set_sensitive.assert_called_once_with(False)
        window.main_menu_button.set_sensitive.assert_called_once_with(False)
        window.unlock_error_label.set_label.assert_called_once_with("synthetic encryption error")
        window.unlock_password_entry.grab_focus.assert_called_once_with()
        self.assertFalse(result)

    def test_cancel_schedules_startup_terminal_in_read_only_mode(self) -> None:
        window = self.window(open_on_startup=True, read_only=True)

        with patch("termia.app.GLib.idle_add") as idle_add:
            self.TermiaWindow.on_unlock_connections_cancelled(
                window,
            )

        window.unlock_panel.set_visible.assert_called_once_with(False)
        window.unlock_scrim.set_visible.assert_called_once_with(False)
        window.main_root.set_sensitive.assert_called_once_with(True)
        window.toggle_sidebar_button.set_sensitive.assert_called_once_with(True)
        window.new_tab_button.set_sensitive.assert_called_once_with(True)
        window.main_menu_button.set_sensitive.assert_called_once_with(True)
        window.toast_label.set_label.assert_called_once_with("connections_locked")
        idle_add.assert_called_once_with(window.open_startup_local_terminal)

    def test_cancel_does_not_schedule_disabled_startup_terminal(self) -> None:
        window = self.window(open_on_startup=False, read_only=True)

        with patch("termia.app.GLib.idle_add") as idle_add:
            self.TermiaWindow.on_unlock_connections_cancelled(window)

        idle_add.assert_not_called()

    def test_successful_unlock_schedules_one_startup_terminal(self) -> None:
        window = self.window(open_on_startup=True, unlock_succeeds=True)

        with patch("termia.app.GLib.idle_add") as idle_add:
            self.TermiaWindow.on_unlock_connections_requested(
                window,
            )

        window.store.unlock_connections.assert_called_once_with("synthetic-password")
        window.unlock_panel.set_visible.assert_called_once_with(False)
        window.apply_app_theme.assert_called_once_with()
        window.refresh_translated_chrome.assert_called_once_with()
        window.refresh_list.assert_called_once_with()
        idle_add.assert_called_once_with(window.open_startup_local_terminal)
        window.unlock_password_entry.set_text.assert_not_called()

    def test_failed_unlock_keeps_panel_open_and_clears_password(self) -> None:
        window = self.window(open_on_startup=True, unlock_succeeds=False)

        with patch("termia.app.GLib.idle_add") as idle_add:
            self.TermiaWindow.on_unlock_connections_requested(window)

        window.unlock_panel.set_visible.assert_not_called()
        window.unlock_error_label.set_label.assert_called_once_with("unlock_connections_failed")
        window.unlock_password_entry.set_text.assert_called_once_with("")
        window.unlock_password_entry.grab_focus.assert_called_once_with()
        idle_add.assert_not_called()

    def test_startup_callback_does_not_duplicate_an_existing_session(self) -> None:
        opened_sessions: list[object] = []
        window = SimpleNamespace(
            session_registry=opened_sessions,
            on_open_local_terminal=lambda _button: opened_sessions.append(object()),
        )

        first_result = self.TermiaWindow.open_startup_local_terminal(window)
        second_result = self.TermiaWindow.open_startup_local_terminal(window)

        self.assertEqual(len(opened_sessions), 1)
        self.assertFalse(first_result)
        self.assertFalse(second_result)
