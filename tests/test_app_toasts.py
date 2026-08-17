import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

from termia.app import TOAST_VISIBLE_SECONDS, TermiaWindow
from termia.notifications import NOTIFICATION_ICONS, GroupedNotificationLabel, NotificationSeverity


class AppToastTests(unittest.TestCase):
    def host(self, *, hide_id: int | None = None) -> SimpleNamespace:
        host = SimpleNamespace(
            toast_hide_id=hide_id,
            toast_revealer=Mock(),
            toast_messages=[],
            toast_severity=NotificationSeverity.INFORMATION,
            toast_icon=Mock(),
            toast_label=Mock(spec=GroupedNotificationLabel),
        )
        host.hide_toast = MethodType(TermiaWindow.hide_toast, host)
        host.show_toast = MethodType(TermiaWindow.show_toast, host)
        return host

    def test_message_reveals_overlay_and_restarts_hide_timer(self) -> None:
        host = self.host(hide_id=7)

        with (
            patch("termia.app.GLib.source_remove") as source_remove,
            patch("termia.app.GLib.timeout_add_seconds", return_value=11) as timeout_add,
        ):
            host.show_toast("Global tab limit reached")

        source_remove.assert_called_once_with(7)
        host.toast_label.set_grouped_text.assert_called_once_with("Global tab limit reached")
        host.toast_revealer.set_reveal_child.assert_called_once_with(True)
        timeout_add.assert_called_once_with(TOAST_VISIBLE_SECONDS, host.hide_toast)
        self.assertEqual(host.toast_hide_id, 11)
        host.toast_icon.set_from_icon_name.assert_called_once_with(
            NOTIFICATION_ICONS[NotificationSeverity.INFORMATION]
        )

    def test_messages_are_grouped_in_arrival_order_and_keep_duplicates(self) -> None:
        host = self.host()

        with (
            patch("termia.app.GLib.source_remove"),
            patch("termia.app.GLib.timeout_add_seconds", side_effect=[7, 8, 9]),
        ):
            host.show_toast("Connected")
            host.show_toast("Upload finished")
            host.show_toast("Connected")

        self.assertEqual(host.toast_messages, ["Connected", "Upload finished", "Connected"])
        host.toast_label.set_grouped_text.assert_called_with(
            "Connected\nUpload finished\nConnected"
        )
        self.assertEqual(host.toast_hide_id, 9)

    def test_group_keeps_the_highest_severity_icon_until_hidden(self) -> None:
        host = self.host()

        with patch("termia.app.GLib.timeout_add_seconds", side_effect=[7, 8, 9]):
            host.show_toast("Connected", NotificationSeverity.SUCCESS)
            host.show_toast("Connection failed", NotificationSeverity.ERROR)
            host.show_toast("Closing connection", NotificationSeverity.INFORMATION)

        self.assertEqual(host.toast_severity, NotificationSeverity.ERROR)
        host.toast_icon.set_from_icon_name.assert_called_with(
            NOTIFICATION_ICONS[NotificationSeverity.ERROR]
        )

    def test_hide_clears_message_for_future_identical_notifications(self) -> None:
        host = self.host(hide_id=11)
        host.toast_messages.extend(["Global tab limit reached", "Connected"])

        result = TermiaWindow.hide_toast(host)

        host.toast_revealer.set_reveal_child.assert_called_once_with(False)
        host.toast_label.set_grouped_text.assert_called_once_with("")
        self.assertEqual(host.toast_messages, [])
        self.assertEqual(host.toast_severity, NotificationSeverity.INFORMATION)
        host.toast_icon.set_from_icon_name.assert_called_once_with(
            NOTIFICATION_ICONS[NotificationSeverity.INFORMATION]
        )
        self.assertIsNone(host.toast_hide_id)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
