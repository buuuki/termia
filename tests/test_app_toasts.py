import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

from termia.app import TOAST_VISIBLE_SECONDS, TermiaWindow


class AppToastTests(unittest.TestCase):
    def host(self, label_text: str, *, hide_id: int | None = None) -> SimpleNamespace:
        host = SimpleNamespace(
            toast_hide_id=hide_id,
            toast_revealer=Mock(),
            toast_label=Mock(),
        )
        host.toast_label.get_label.return_value = label_text
        host.hide_toast = MethodType(TermiaWindow.hide_toast, host)
        return host

    def test_message_reveals_overlay_and_restarts_hide_timer(self) -> None:
        host = self.host("Global tab limit reached", hide_id=7)

        with (
            patch("termia.app.GLib.source_remove") as source_remove,
            patch("termia.app.GLib.timeout_add_seconds", return_value=11) as timeout_add,
        ):
            TermiaWindow.on_toast_label_changed(host, host.toast_label, None)

        source_remove.assert_called_once_with(7)
        host.toast_revealer.set_reveal_child.assert_called_once_with(True)
        timeout_add.assert_called_once_with(TOAST_VISIBLE_SECONDS, host.hide_toast)
        self.assertEqual(host.toast_hide_id, 11)

    def test_empty_message_hides_overlay_without_scheduling_timer(self) -> None:
        host = self.host("", hide_id=7)

        with (
            patch("termia.app.GLib.source_remove") as source_remove,
            patch("termia.app.GLib.timeout_add_seconds") as timeout_add,
        ):
            TermiaWindow.on_toast_label_changed(host, host.toast_label, None)

        source_remove.assert_called_once_with(7)
        host.toast_revealer.set_reveal_child.assert_called_once_with(False)
        timeout_add.assert_not_called()
        self.assertIsNone(host.toast_hide_id)

    def test_hide_clears_message_for_future_identical_notifications(self) -> None:
        host = self.host("Global tab limit reached", hide_id=11)

        result = TermiaWindow.hide_toast(host)

        host.toast_revealer.set_reveal_child.assert_called_once_with(False)
        host.toast_label.set_label.assert_called_once_with("")
        self.assertIsNone(host.toast_hide_id)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
