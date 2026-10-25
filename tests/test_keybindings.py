import unittest

from termia.keybindings import (
    DEFAULT_KEYBINDINGS,
    keybinding_label,
    keybinding_accelerator,
    normalize_keybinding,
    normalize_keybindings,
    KeybindingError,
    merge_keybindings,
    snippet_action,
    validate_keybindings,
)


class KeybindingTests(unittest.TestCase):
    def test_menu_accelerators_parse_to_the_configured_keys_and_modifiers(self):
        from gi.repository import Gdk, Gtk

        for stored, key, modifiers in (
            ("Ctrl+Shift+V", Gdk.KEY_v, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK),
            ("<Control><Shift>c", Gdk.KEY_c, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK),
            ("Ctrl++", Gdk.KEY_plus, Gdk.ModifierType.CONTROL_MASK),
            ("Ctrl+-", Gdk.KEY_minus, Gdk.ModifierType.CONTROL_MASK),
            ("Ctrl+PageUp", Gdk.KEY_Page_Up, Gdk.ModifierType.CONTROL_MASK),
            ("Alt+PageDown", Gdk.KEY_Page_Down, Gdk.ModifierType.ALT_MASK),
            ("Super+Left", Gdk.KEY_Left, Gdk.ModifierType.SUPER_MASK),
            ("F10", Gdk.KEY_F10, Gdk.ModifierType(0)),
            ("Ctrl+semicolon", Gdk.KEY_semicolon, Gdk.ModifierType.CONTROL_MASK),
        ):
            with self.subTest(shortcut=stored):
                valid, actual_key, actual_modifiers = Gtk.accelerator_parse(keybinding_accelerator(stored))
                self.assertTrue(valid)
                self.assertEqual(actual_key, key)
                self.assertEqual(actual_modifiers, modifiers)

    def test_disabled_and_unknown_menu_accelerators_are_omitted(self):
        for shortcut in ("", "  ", "Ctrl+NotARealKeyName"):
            with self.subTest(shortcut=shortcut):
                self.assertEqual(keybinding_accelerator(shortcut), "")

    def test_snippet_keys_survive_normalization_and_unknown_actions_do_not(self):
        bindings = normalize_keybindings({"snippet:one": "<Control><Alt>d", "unknown": "Ctrl+K"})
        self.assertEqual(bindings["snippet:one"], "Ctrl+Alt+D")
        self.assertNotIn("unknown", bindings)

    def test_snippet_shortcuts_require_modifiers_and_cannot_conflict(self):
        for shortcut in ("D", "F8", "Shift+D", "Ctrl+Shift+C", "Ctrl+Shift++", "Ctrl+Shift+-",
                         "Ctrl+KP_Page_Up", "Ctrl+KP_Left"):
            with self.subTest(shortcut=shortcut), self.assertRaises(KeybindingError):
                merge_keybindings(DEFAULT_KEYBINDINGS, {snippet_action("one"): shortcut})
        with self.assertRaises(KeybindingError):
            validate_keybindings({"snippet:one": "Ctrl+Alt+D", "snippet:two": "<Control><Alt>d"})

    def test_merge_preserves_newer_unedited_actions_and_rejects_stale_edits(self):
        previous = {**DEFAULT_KEYBINDINGS, "snippet:one": "Ctrl+Alt+D"}
        current = {**previous, "snippet:one": "Ctrl+Alt+E"}
        merged = merge_keybindings(current, {**previous, "copy": "Ctrl+Alt+C"}, previous)
        self.assertEqual(merged["snippet:one"], "Ctrl+Alt+E")
        self.assertEqual(merged["copy"], "Ctrl+Alt+C")
        with self.assertRaises(KeybindingError):
            merge_keybindings(current, {"snippet:one": "Ctrl+Alt+F"}, previous)

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

    def test_split_focus_defaults_use_control_and_arrow_keys(self) -> None:
        self.assertEqual(DEFAULT_KEYBINDINGS["focus_split_left"], "Ctrl+Left")
        self.assertEqual(DEFAULT_KEYBINDINGS["focus_split_right"], "Ctrl+Right")
        self.assertEqual(DEFAULT_KEYBINDINGS["focus_split_up"], "Ctrl+Up")
        self.assertEqual(DEFAULT_KEYBINDINGS["focus_split_down"], "Ctrl+Down")
