import unittest
from types import SimpleNamespace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

from termia.i18n import translate_key
from termia.keybindings import DEFAULT_KEYBINDINGS, KEYBINDING_ACTIONS
from termia.main_menu import MainMenuMixin


class HelpWindowTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check() or Gdk.Display.get_default() is None:
            self.skipTest("GTK widget integration requires a graphical display")

        class Host(MainMenuMixin, Gtk.Window):
            def t(self, key):
                return translate_key(key, self.language)

        self.host = Host()
        self.host.language = "en"
        self.host.store = SimpleNamespace(data=SimpleNamespace(app=SimpleNamespace(
            keybindings={**DEFAULT_KEYBINDINGS, "paste": "Ctrl+Alt+V", "copy": ""},
        )))
        self.addCleanup(self.host.destroy)

    def open_help(self):
        self.host.on_help(None)
        windows = Gtk.Window.get_toplevels()
        dialog = next(windows.get_item(i) for i in range(windows.get_n_items())
                      if windows.get_item(i).get_transient_for() is self.host)
        self.addCleanup(dialog.destroy)
        return dialog

    @staticmethod
    def labels(widget):
        result = [widget] if isinstance(widget, Gtk.Label) else []
        child = widget.get_first_child()
        while child is not None:
            result.extend(HelpWindowTests.labels(child))
            child = child.get_next_sibling()
        return result

    def test_sections_are_translated_and_shortcuts_reflect_saved_configuration(self):
        for language in ("en", "es", "ca"):
            with self.subTest(language=language):
                self.host.language = language
                dialog = self.open_help()
                labels = self.labels(dialog)
                headings = [label.get_text() for label in labels if label.has_css_class("heading")]
                self.assertEqual(len(headings), 9)
                for key in ("help_start", "help_terminals", "manage_notes", "manage_snippets",
                            "workspaces", "optional_tools", "security", "update_title", "help_shortcuts"):
                    self.assertIn(translate_key(key, language), headings)
                values = [label.get_text() for label in labels if label.has_css_class("monospace")]
                self.assertEqual(len(values), len(KEYBINDING_ACTIONS))
                self.assertIn("Ctrl+Alt+V", values)
                self.assertIn(translate_key("keybinding_disabled", language), values)
                texts = [label.get_text() for label in labels]
                self.assertIn(translate_key("help_security_body", language), texts)
                self.assertTrue(dialog.get_modal())
                dialog.response(Gtk.ResponseType.CLOSE)
                self.assertFalse(dialog.get_visible())

    def test_reopened_help_uses_latest_shortcuts(self):
        dialog = self.open_help()
        dialog.response(Gtk.ResponseType.CLOSE)
        self.host.store.data.app.keybindings["paste"] = "Super+V"
        labels = self.labels(self.open_help())
        self.assertIn("Super+V", [label.get_text() for label in labels])
