import unittest
import warnings

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.styles import build_application_css


class SplitSeparatorStyleTests(unittest.TestCase):
    def test_visual_line_is_independent_from_the_drag_handle(self) -> None:
        css = build_application_css("#202020", "#008712", 1).decode()

        self.assertIn(".termia-split-pane.horizontal > separator", css)
        self.assertIn("min-width: 5px", css)
        self.assertIn("background: #202020; border-left: 1px solid #008712", css)
        self.assertIn("border-left: 1px solid #008712", css)
        self.assertIn(".termia-split-pane.vertical > separator", css)
        self.assertIn("min-height: 5px", css)
        self.assertIn("background: #202020; border-top: 1px solid #008712", css)
        self.assertIn("border-top: 1px solid #008712", css)
        self.assertIn(".termia-pane-status > label { min-width: 0; }", css)
        self.assertIn(
            ".termia-add-icon-badge { background: @theme_bg_color; border-radius: 999px; }",
            css,
        )

    def test_configured_thickness_expands_the_handle_when_needed(self) -> None:
        css = build_application_css("#202020", "#008712", 8).decode()

        self.assertIn("min-width: 8px", css)
        self.assertIn("min-height: 8px", css)
        self.assertIn("border-left: 8px solid #008712", css)
        self.assertIn("border-top: 8px solid #008712", css)

    def test_generated_css_is_accepted_by_gtk(self) -> None:
        provider = Gtk.CssProvider()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            provider.load_from_data(build_application_css("#202020", "#008712", 1))

    def test_notes_editor_has_dark_default_background_and_border(self) -> None:
        css = build_application_css("#202020", "#008712", 1).decode()

        self.assertIn(
            ".termia-notes-editor { border: 1px solid @borders; border-radius: 8px; "
            "background-color: #001b33; }",
            css,
        )
        self.assertIn(
            ".termia-notes-editor textview { color: #ffffff; "
            "background-color: #001b33; }",
            css,
        )
        self.assertIn(
            ".termia-notes-editor textview text { background-color: #001b33; }",
            css,
        )

    def test_application_modes_leave_menu_and_properties_surfaces_to_gtk(self) -> None:
        css = build_application_css("#202020", "#008712", 1).decode()

        self.assertNotIn("termia_menu_bg", css)
        self.assertNotIn("termia-menu-popover > contents", css)
        self.assertNotIn("termia-menu-panel {", css)
        self.assertNotIn("window.termia-note-properties", css)

    def test_required_marker_uses_theme_colors(self) -> None:
        css = build_application_css("#202020", "#008712", 1).decode()

        self.assertIn(
            ".termia-required-marker { font-size: 1.2em; font-weight: 700; }",
            css,
        )
        self.assertIn(
            ".termia-required-hint { color: alpha(@theme_fg_color, 0.8); }",
            css,
        )
        self.assertNotIn("@error_color", css)

    def test_fixed_theme_is_opt_in_and_preserves_terminal_colors(self):
        ordinary = build_application_css("#202020", "#008712", 1)
        for theme in ("system", "light", "dark"):
            self.assertEqual(build_application_css("#202020", "#008712", 1, theme), ordinary)
        self.assertNotIn(".termia-terminal-pane {", ordinary.decode())
        self.assertNotIn("headerbar.termia-main-header", ordinary.decode())
        self.assertNotIn(".termia-menu-popover modelbutton", ordinary.decode())
        css = build_application_css("#202020", "#008712", 1, "dark_glow").decode()
        self.assertIn("window.termia-dark-glow", css)
        self.assertIn("border-radius: 10px", css)
        self.assertIn("background-color: #182231", css)
        self.assertIn(
            "window.termia-dark-glow .termia-terminal-pane vte-terminal { padding: 6px 8px; }",
            css,
        )
        terminal_rules = [rule for rule in css.split("}") if "vte-terminal" in rule]
        self.assertTrue(all("color" not in rule for rule in terminal_rules))
        self.assertNotIn("backdrop-filter", css)

    def test_fixed_theme_css_parses_without_errors(self):
        provider = Gtk.CssProvider()
        errors = []
        provider.connect("parsing-error", lambda _provider, _section, error: errors.append(str(error)))
        provider.load_from_string(build_application_css("#202020", "#008712", 1, "dark_glow").decode())
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
