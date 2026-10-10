import unittest
import warnings

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from termia.styles import build_application_css


class SplitSeparatorStyleTests(unittest.TestCase):
    def test_visual_line_is_independent_from_the_drag_handle(self) -> None:
        css = build_application_css("#202020", "#202020", "#008712", 1).decode()

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
        css = build_application_css("#202020", "#202020", "#008712", 8).decode()

        self.assertIn("min-width: 8px", css)
        self.assertIn("min-height: 8px", css)
        self.assertIn("border-left: 8px solid #008712", css)
        self.assertIn("border-top: 8px solid #008712", css)

    def test_generated_css_is_accepted_by_gtk(self) -> None:
        provider = Gtk.CssProvider()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            provider.load_from_data(build_application_css("#202020", "#202020", "#008712", 1))

    def test_notes_tab_scrollbar_is_compact_and_translucent(self) -> None:
        css = build_application_css("#202020", "#202020", "#008712", 1).decode()

        self.assertIn(
            ".termia-notes-tab-scroller scrollbar.horizontal { min-height: 5px; margin: 0 2px; padding: 0; }",
            css,
        )
        self.assertIn(
            ".termia-notes-tab-scroller scrollbar.horizontal slider { min-height: 3px; min-width: 24px; "
            "background-color: alpha(@theme_fg_color, 0.35); }",
            css,
        )
        self.assertIn(
            ".termia-notes-tab-scroller scrollbar.horizontal slider:hover { "
            "background-color: alpha(@theme_fg_color, 0.6); }",
            css,
        )

    def test_notes_editor_has_theme_aware_background_and_border(self) -> None:
        css = build_application_css("#202020", "#202020", "#008712", 1).decode()

        self.assertIn(
            ".termia-notes-editor { border: 1px solid @borders; border-radius: 8px; "
            "background-color: @theme_base_color; }",
            css,
        )
        self.assertIn(
            ".termia-notes-editor textview, .termia-notes-editor textview text { "
            "background-color: @theme_base_color; }",
            css,
        )

    def test_note_properties_inverts_the_outer_and_inner_surfaces(self) -> None:
        css = build_application_css("#202020", "#202020", "#008712", 1).decode()

        self.assertIn(
            "window.termia-note-properties { background-color: @termia_menu_bg; }",
            css,
        )
        self.assertIn(
            "window.termia-note-properties headerbar { background: @termia_menu_bg; "
            "background-color: @termia_menu_bg; background-image: none; box-shadow: none; }",
            css,
        )
        self.assertIn(
            ".termia-note-properties-content { background-color: @theme_bg_color; "
            "background-image: none; border-radius: 8px; padding: 8px 12px; }",
            css,
        )

    def test_system_theme_leaves_menu_and_properties_surfaces_to_gtk(self) -> None:
        css = build_application_css(None, "#202020", "#008712", 1).decode()

        self.assertNotIn("termia_menu_bg", css)
        self.assertNotIn("termia-menu-popover > contents", css)
        self.assertNotIn("termia-menu-panel {", css)
        self.assertNotIn("window.termia-note-properties", css)

    def test_only_active_note_tab_gets_thin_full_width_blue_underline(self) -> None:
        css = build_application_css("#202020", "#202020", "#008712", 1).decode()

        self.assertIn(
            ".termia-note-tab { border-radius: 8px 8px 0 0; border-bottom: 2px solid transparent; }",
            css,
        )
        self.assertIn(
            ".termia-note-tab.active { border-bottom-color: #0066cc; }",
            css,
        )


if __name__ == "__main__":
    unittest.main()
