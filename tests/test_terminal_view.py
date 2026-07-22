import unittest

from gi.repository import Pango
from termia.models import TerminalSettings
from termia.terminal_view import TerminalViewFactory


class FakeTerminal:
    def set_hexpand(self, value: bool) -> None:
        self.hexpand = value

    def set_vexpand(self, value: bool) -> None:
        self.vexpand = value

    def set_cursor_blink_mode(self, value: object) -> None:
        self.cursor_blink_mode = value

    def set_scrollback_lines(self, value: int) -> None:
        self.scrollback_lines = value

    def set_font(self, value: object) -> None:
        self.font = value

    def set_colors(self, foreground: object, background: object, palette: list[object]) -> None:
        self.foreground = foreground
        self.background = background
        self.palette = palette


class TerminalViewTests(unittest.TestCase):
    def test_apply_settings_resolves_font_and_applies_palette(self) -> None:
        terminal = FakeTerminal()
        settings = TerminalSettings(
            font_family="Preferred",
            font_size=15,
            foreground="#ffffff",
            background="#000000",
            ansi_palette=["#111111", "#222222"],
        )
        factory = TerminalViewFactory(lambda family: f"Resolved {family}")

        factory.apply_settings(terminal, settings)

        self.assertEqual(terminal.font.get_family(), "Resolved Preferred")
        self.assertEqual(terminal.font.get_size() // Pango.SCALE, 15)
        self.assertEqual(terminal.foreground.red, 1.0)
        self.assertEqual(terminal.background.blue, 0.0)
        self.assertEqual(len(terminal.palette), 2)
