import unittest

from termia.keybindings import (
    DEFAULT_KEYBINDINGS,
    keybinding_label,
    normalize_keybinding,
    normalize_keybindings,
)


class KeybindingTests(unittest.TestCase):
    def test_normalizes_gtk_style_accelerators(self) -> None:
        self.assertEqual(normalize_keybinding("<Shift><Control>c"), "Ctrl+Shift+C")
        self.assertEqual(normalize_keybinding("control+page_up"), "Ctrl+PageUp")
        self.assertEqual(normalize_keybinding("<Alt><Super>F10"), "Alt+Super+F10")

    def test_normalizes_plus_and_empty_values(self) -> None:
        self.assertEqual(normalize_keybinding("Ctrl++"), "Ctrl++")
        self.assertEqual(normalize_keybinding("  "), "")
        self.assertEqual(keybinding_label("", "Disabled"), "Disabled")

    def test_missing_actions_keep_defaults(self) -> None:
        normalized = normalize_keybindings({"copy": "<Control><Shift>c"})

        self.assertEqual(normalized["copy"], "Ctrl+Shift+C")
        self.assertEqual(normalized["paste"], DEFAULT_KEYBINDINGS["paste"])
        self.assertEqual(set(normalized), set(DEFAULT_KEYBINDINGS))
