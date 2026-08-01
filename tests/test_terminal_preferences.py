import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.prompt_preferences import combined_terminal_preview_markup
from termia.terminal_preferences import TerminalPreferencesMixin


class FakeRgba:
    red = 0.2
    green = 0.4
    blue = 0.6

    def to_string(self) -> str:
        return "rgb(51,102,153)"


class TerminalPreferencesTests(unittest.TestCase):
    def test_shared_preview_combines_prompt_command_output_and_ansi_colors(self) -> None:
        markup = combined_terminal_preview_markup(
            prompt_enabled=True,
            prompt_template=r"custom \$ ",
            prompt_datetime_id="none",
            prompt_color="#abcdef",
            command_text='printf "<preview>"',
            output_text="preview output",
            ansi_palette=[f"#{index:06x}" for index in range(16)],
        )

        self.assertIn('foreground="#abcdef"', markup)
        self.assertIn("custom $", markup)
        self.assertIn("&lt;preview&gt;", markup)
        self.assertIn("preview output", markup)
        self.assertEqual(markup.count("●"), 8)

    def test_disabled_prompt_preview_uses_default_shell_prompt(self) -> None:
        markup = combined_terminal_preview_markup(
            prompt_enabled=False,
            prompt_template="custom prompt",
            prompt_datetime_id="both",
            prompt_color="#abcdef",
            command_text="command",
            output_text="output",
            ansi_palette=[],
        )

        self.assertIn("usuario@servidor", markup)
        self.assertNotIn("custom prompt", markup)

    def test_combined_save_persists_prompt_and_applies_only_appearance_live(self) -> None:
        host = SimpleNamespace(
            store=SimpleNamespace(update_terminal_settings=Mock()),
            selected_terminal_font_family=lambda _combo: "Monospace",
            apply_terminal_settings_to_open_tabs=Mock(),
            install_tree_styles=Mock(),
            toast_label=SimpleNamespace(set_label=Mock()),
            t=lambda key: key,
        )
        dialog = SimpleNamespace(destroy=Mock())
        rgba = FakeRgba()
        color_button = SimpleNamespace(get_rgba=lambda: rgba)

        TerminalPreferencesMixin.on_terminal_settings_response(
            host,
            dialog,
            Gtk.ResponseType.OK,
            object(),
            SimpleNamespace(get_value=lambda: 12),
            color_button,
            color_button,
            color_button,
            SimpleNamespace(get_value=lambda: 2),
            SimpleNamespace(get_active=lambda: True),
            SimpleNamespace(get_active_id=lambda: "time"),
            SimpleNamespace(get_text=lambda: r"\u@\h:\w\$ "),
            color_button,
        )

        saved = host.store.update_terminal_settings.call_args.kwargs
        self.assertTrue(saved["prompt_enabled"])
        self.assertIn(r"[\A]", saved["prompt_template"])
        self.assertEqual(saved["prompt_color"], "#336699")
        host.apply_terminal_settings_to_open_tabs.assert_called_once_with()
        host.install_tree_styles.assert_called_once_with()
        dialog.destroy.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
