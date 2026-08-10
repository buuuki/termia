import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from termia.general_preferences import GENERAL_PREFERENCE_FIELDS, GeneralPreferencesMixin


class GeneralPreferencesNotificationTests(unittest.TestCase):
    def host(self) -> SimpleNamespace:
        translations = {
            "setting_changed": "{setting}: {value}",
            "setting_enabled": "Enabled",
            "setting_disabled": "Disabled",
            "theme_dark": "Dark",
        }
        settings = SimpleNamespace(
            theme="system",
            language="en",
            close_tab_on_disconnect=False,
            close_tab_on_ssh_exit=False,
            open_local_terminal_on_startup=False,
            restore_sessions_on_startup=False,
            show_sidebar_on_startup=False,
            show_session_status_bar=False,
            audible_bell=False,
            statistics_enabled=False,
            confirm_disconnect=False,
            confirm_close_app=False,
            send_password_shortcut=False,
            send_password_enter=False,
            debug_enabled=False,
        )
        return SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(app=settings)),
            toast_label=Mock(),
            t=lambda key: translations.get(key, key),
        )

    def previous_values(self, host: SimpleNamespace) -> dict[str, str | bool]:
        return GeneralPreferencesMixin.general_preference_values(host.store.data.app)

    def test_unchanged_settings_do_not_emit_notifications(self) -> None:
        host = self.host()
        previous_values = self.previous_values(host)

        with patch("termia.general_preferences.configure_debug_logging") as configure:
            GeneralPreferencesMixin.notify_general_preference_changes(host, previous_values)

        configure.assert_not_called()
        host.toast_label.set_label.assert_not_called()

    def test_every_changed_general_preference_emits_a_notification(self) -> None:
        host = self.host()
        previous_values = self.previous_values(host)
        host.store.data.app.theme = "dark"
        host.store.data.app.language = "es"
        for setting_key, attribute in GENERAL_PREFERENCE_FIELDS[2:]:
            self.assertFalse(previous_values[setting_key])
            setattr(host.store.data.app, attribute, True)

        with patch("termia.general_preferences.configure_debug_logging") as configure:
            GeneralPreferencesMixin.notify_general_preference_changes(host, previous_values)

        configure.assert_called_once_with(True)
        messages = [call.args[0] for call in host.toast_label.set_label.call_args_list]
        self.assertEqual(len(messages), len(GENERAL_PREFERENCE_FIELDS))
        self.assertEqual(messages[0], "theme: Dark")
        self.assertEqual(messages[1], "language: Español")
        self.assertEqual(messages[-1], "debug_mode: Enabled")

    def test_non_debug_change_does_not_reconfigure_debug_logging(self) -> None:
        host = self.host()
        previous_values = self.previous_values(host)
        host.store.data.app.confirm_close_app = True

        with patch("termia.general_preferences.configure_debug_logging") as configure:
            GeneralPreferencesMixin.notify_general_preference_changes(host, previous_values)

        configure.assert_not_called()
        host.toast_label.set_label.assert_called_once_with("confirm_close_app: Enabled")


if __name__ == "__main__":
    unittest.main()
