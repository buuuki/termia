import importlib.util
import unittest
from types import SimpleNamespace


@unittest.skipUnless(importlib.util.find_spec("gi"), "GTK bindings are unavailable")
class WriteActionTests(unittest.TestCase):
    def setUp(self) -> None:
        from termia.app import TermiaWindow

        self.configure_write_action = TermiaWindow.configure_write_action

    def window(self, *, read_only: bool, encryption_locked: bool):
        return SimpleNamespace(
            store=SimpleNamespace(
                read_only=read_only,
                encryption_locked=encryption_locked,
            ),
            t=lambda key: key,
        )

    def widget(self):
        state = SimpleNamespace(sensitive=None, tooltip="stale")
        state.set_sensitive = lambda value: setattr(state, "sensitive", value)
        state.set_tooltip_text = lambda value: setattr(state, "tooltip", value)
        return state

    def test_write_action_is_reenabled_and_stale_tooltip_is_cleared(self) -> None:
        widget = self.widget()

        result = self.configure_write_action(
            self.window(read_only=False, encryption_locked=False),
            widget,
        )

        self.assertIs(result, widget)
        self.assertTrue(widget.sensitive)
        self.assertIsNone(widget.tooltip)

    def test_encrypted_store_keeps_write_action_disabled(self) -> None:
        widget = self.widget()

        self.configure_write_action(
            self.window(read_only=False, encryption_locked=True),
            widget,
        )

        self.assertFalse(widget.sensitive)
        self.assertEqual(widget.tooltip, "connections_locked_tooltip")

    def test_read_only_store_keeps_write_action_disabled(self) -> None:
        widget = self.widget()

        self.configure_write_action(
            self.window(read_only=True, encryption_locked=False),
            widget,
        )

        self.assertFalse(widget.sensitive)
        self.assertEqual(widget.tooltip, "read_only_mode_tooltip")
