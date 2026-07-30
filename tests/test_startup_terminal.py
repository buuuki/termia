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

    def startup_window(
        self,
        *,
        encryption_locked: bool,
        mapped: bool,
    ) -> SimpleNamespace:
        window = SimpleNamespace(
            store=SimpleNamespace(encryption_locked=encryption_locked),
            startup_started=False,
            startup_source_id=None,
            get_mapped=Mock(return_value=mapped),
            request_unlock_connections=Mock(),
            schedule_startup_local_terminal=Mock(),
        )
        window.begin_startup_after_present = MethodType(
            self.TermiaWindow.begin_startup_after_present,
            window,
        )
        window.continue_startup_after_map = MethodType(
            self.TermiaWindow.continue_startup_after_map,
            window,
        )
        return window

    def test_application_presents_new_window_before_startup(self) -> None:
        app = SimpleNamespace(props=SimpleNamespace(active_window=None))
        window = Mock()

        with patch("termia.app.TermiaWindow", return_value=window):
            self.TermiaApp.do_activate(app)

        self.assertEqual(
            window.method_calls,
            [call.present(), call.begin_startup_after_present()],
        )

    def test_application_does_not_restart_an_existing_window(self) -> None:
        window = Mock()
        app = SimpleNamespace(props=SimpleNamespace(active_window=window))

        self.TermiaApp.do_activate(app)

        self.assertEqual(window.method_calls, [call.present()])

    def test_locked_startup_waits_for_the_first_window_map(self) -> None:
        window = self.startup_window(encryption_locked=True, mapped=False)

        with patch("termia.app.GLib.idle_add", return_value=73) as idle_add:
            window.begin_startup_after_present()
            waiting_result = window.continue_startup_after_map()
            window.get_mapped.return_value = True
            mapped_result = window.continue_startup_after_map()
            duplicate_result = window.continue_startup_after_map()

        idle_add.assert_called_once_with(window.continue_startup_after_map)
        self.assertTrue(waiting_result)
        self.assertFalse(mapped_result)
        self.assertFalse(duplicate_result)
        window.request_unlock_connections.assert_called_once_with()
        self.assertTrue(window.startup_started)
        self.assertIsNone(window.startup_source_id)

    def test_already_mapped_locked_window_schedules_unlock_immediately(self) -> None:
        window = self.startup_window(encryption_locked=True, mapped=True)

        with patch("termia.app.GLib.idle_add", return_value=73) as idle_add:
            window.begin_startup_after_present()
            window.begin_startup_after_present()
            result = window.continue_startup_after_map()

        idle_add.assert_called_once_with(window.continue_startup_after_map)
        window.request_unlock_connections.assert_called_once_with()
        self.assertFalse(result)

    def test_unlocked_startup_waits_for_map_before_opening_terminal(self) -> None:
        window = self.startup_window(encryption_locked=False, mapped=False)

        with patch("termia.app.GLib.idle_add", return_value=73) as idle_add:
            window.begin_startup_after_present()
            waiting_result = window.continue_startup_after_map()
            window.get_mapped.return_value = True
            mapped_result = window.continue_startup_after_map()

        idle_add.assert_called_once_with(window.continue_startup_after_map)
        self.assertTrue(waiting_result)
        self.assertFalse(mapped_result)
        window.schedule_startup_local_terminal.assert_called_once_with()

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
                unlock_connections=Mock(return_value=unlock_succeeds),
            ),
            toast_label=SimpleNamespace(set_label=Mock()),
            t=lambda key: key,
            open_startup_local_terminal=Mock(),
            apply_app_theme=Mock(),
            refresh_translated_chrome=Mock(),
            refresh_list=Mock(),
        )
        window.schedule_startup_local_terminal = MethodType(
            self.TermiaWindow.schedule_startup_local_terminal,
            window,
        )
        return window

    def unlock_response(
        self,
        window: SimpleNamespace,
        response,
    ) -> tuple[Mock, Mock, Mock]:
        dialog = Mock()
        password_entry = Mock()
        password_entry.get_text.return_value = "synthetic-password"
        error = Mock()
        self.TermiaWindow.on_unlock_connections_response(
            window,
            dialog,
            response,
            password_entry,
            error,
        )
        return dialog, password_entry, error

    def test_cancel_schedules_startup_terminal_in_read_only_mode(self) -> None:
        from gi.repository import Gtk

        window = self.window(open_on_startup=True, read_only=True)

        with patch("termia.app.GLib.idle_add") as idle_add:
            dialog, _password_entry, _error = self.unlock_response(
                window,
                Gtk.ResponseType.CANCEL,
            )

        dialog.destroy.assert_called_once_with()
        window.toast_label.set_label.assert_called_once_with("connections_locked")
        idle_add.assert_called_once_with(window.open_startup_local_terminal)

    def test_cancel_does_not_schedule_disabled_startup_terminal(self) -> None:
        from gi.repository import Gtk

        window = self.window(open_on_startup=False, read_only=True)

        with patch("termia.app.GLib.idle_add") as idle_add:
            self.unlock_response(window, Gtk.ResponseType.CANCEL)

        idle_add.assert_not_called()

    def test_successful_unlock_schedules_one_startup_terminal(self) -> None:
        from gi.repository import Gtk

        window = self.window(open_on_startup=True, unlock_succeeds=True)

        with patch("termia.app.GLib.idle_add") as idle_add:
            dialog, password_entry, _error = self.unlock_response(
                window,
                Gtk.ResponseType.OK,
            )

        window.store.unlock_connections.assert_called_once_with("synthetic-password")
        dialog.destroy.assert_called_once_with()
        window.apply_app_theme.assert_called_once_with()
        window.refresh_translated_chrome.assert_called_once_with()
        window.refresh_list.assert_called_once_with()
        idle_add.assert_called_once_with(window.open_startup_local_terminal)
        password_entry.set_text.assert_not_called()

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
