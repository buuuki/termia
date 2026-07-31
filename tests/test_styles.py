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
        self.assertIn("border-left: 1px solid #008712", css)
        self.assertIn(".termia-split-pane.vertical > separator", css)
        self.assertIn("min-height: 5px", css)
        self.assertIn("border-top: 1px solid #008712", css)
        self.assertIn(".termia-pane-status > label { min-width: 0; }", css)

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


if __name__ == "__main__":
    unittest.main()
