# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise Retron provider replacement with real GTK secondary windows."""
import time
import unittest
from types import SimpleNamespace

from gi.repository import GLib

from termia.app import Gdk, Gtk, TermiaWindow, WindowThemeScope
from termia.dialog_window import DialogWindow
from termia.theme_styles import build_dark_glow_css, build_interaction_css


class SecondaryThemeTests(unittest.TestCase):
    def test_every_retron_selector_is_scoped(self):
        css = build_dark_glow_css() + build_interaction_css("dark_glow", "#123456", "#abcdef")
        for block in css.split("}"):
            if "{" not in block:
                continue
            selectors = block.split("{", 1)[0]
            for selector in selectors.split(","):
                self.assertTrue(selector.strip().startswith("window.termia-dark-glow"), selector)

    def test_open_and_future_windows_restore_after_provider_replacement(self):
        scope = WindowThemeScope()
        host = SimpleNamespace(
            store=SimpleNamespace(data=SimpleNamespace(
                app=SimpleNamespace(theme="system", dark_glow_border_color="#55BAC9"),
                terminal=SimpleNamespace(background="#123456", foreground="#abcdef",
                                         split_separator_color="#008712", split_separator_thickness=1),
            )),
            get_application=lambda: SimpleNamespace(_window_theme_scope=scope),
        )
        windows = []

        def window():
            current = DialogWindow()
            label = Gtk.Label(label="Synthetic preview")
            listing = Gtk.ListBox()
            listing.append(label)
            current.get_content_area().append(listing)
            windows.append(current)
            current.present()
            return current, label

        def settle():
            deadline = time.monotonic() + 0.2
            while time.monotonic() < deadline:
                while GLib.MainContext.default().pending():
                    GLib.MainContext.default().iteration(False)
                time.sleep(0.005)

        first, label = window()
        try:
            TermiaWindow.install_tree_styles(host)
            settle()
            baseline = label.get_style_context().get_color().to_string()
            for target in ("light", "dark", "system"):
                host.store.data.app.theme = "dark_glow"
                TermiaWindow.install_tree_styles(host)
                future, future_label = window()
                settle()
                self.assertTrue(first.has_css_class("termia-dark-glow"))
                self.assertTrue(future.has_css_class("termia-dark-glow"))
                self.assertEqual(label.get_style_context().get_color().to_string(), "rgb(237,243,248)")
                self.assertEqual(future_label.get_style_context().get_color().to_string(), "rgb(237,243,248)")
                host.store.data.app.theme = target
                TermiaWindow.install_tree_styles(host)
                later, later_label = window()
                settle()
                for item in windows:
                    self.assertFalse(item.has_css_class("termia-dark-glow"))
                # Only the CSS provider changes here; the GTK variant stays
                # fixed, allowing an exact before/after comparison of removal.
                for item in (label, future_label, later_label):
                    self.assertEqual(item.get_style_context().get_color().to_string(), baseline)
        finally:
            for current in windows:
                current.destroy()
            scope.close()
            provider = getattr(host, "_application_css_provider", None)
            if provider is not None:
                Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(), provider)
