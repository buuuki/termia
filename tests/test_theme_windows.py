# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise Retron provider replacement with real GTK secondary windows."""
import shutil
import subprocess
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gi.repository import GLib

from termia.app import Gdk, Gtk, TermiaWindow, WindowThemeScope
from termia.dialog_window import DialogWindow
from termia.theme_styles import build_dark_glow_css, build_interaction_css


class SecondaryThemeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("xdotool"), "Native pointer test requires xdotool")
    def test_real_title_pointer_press_and_release(self):
        window = Gtk.Window(title="Termia native title feedback test")
        window.set_default_size(420, 200)
        header = Gtk.HeaderBar()
        title = Gtk.Label(label="Synthetic title")
        header.set_title_widget(title)
        window.set_titlebar(header)
        window.set_child(Gtk.Label(label="Synthetic content"))
        scope = WindowThemeScope()

        def settle():
            deadline = time.monotonic() + 0.15
            while time.monotonic() < deadline:
                for _ in range(100):
                    if not GLib.MainContext.default().pending():
                        break
                    GLib.MainContext.default().iteration(False)
                time.sleep(0.005)

        try:
            scope.set_enabled(True)
            window.present()
            if not window.get_display().__gtype__.name.startswith("GdkX11"):
                self.skipTest("Native pointer test requires a private X11 display")
            settle()
            bounds = title.compute_bounds(window)[1]
            dx, dy = window.get_surface_transform()
            x = int(bounds.get_x() + bounds.get_width() / 2 + dx)
            y = int(bounds.get_y() + bounds.get_height() / 2 + dy)
            matches = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", "^Termia native title feedback test$"],
                check=True, capture_output=True, text=True, timeout=5,
            ).stdout.splitlines()
            self.assertEqual(len(matches), 1)
            subprocess.run(["xdotool", "mousemove", "--window", matches[0], str(x), str(y)],
                           check=True, timeout=5)
            settle()
            subprocess.run(["xdotool", "mousedown", "1"], check=True, timeout=5)
            settle()
            self.assertTrue(window.has_css_class("termia-title-held"))
            subprocess.run(["xdotool", "mouseup", "1"], check=True, timeout=5)
            settle()
            self.assertFalse(window.has_css_class("termia-title-held"))
            self.assertIsNone(scope._title_poll)
        finally:
            subprocess.run(["xdotool", "mouseup", "1"], check=False, timeout=5)
            scope.close()
            window.destroy()

    def test_title_feedback_observes_native_handles_and_releases_device_poll(self):
        scope = WindowThemeScope()
        window = Gtk.Window()
        handle = Gtk.WindowHandle()
        row = Gtk.Box()
        title = Gtk.Label(label="Synthetic title")
        button = Gtk.Button(label="Action")
        row.append(title)
        row.append(button)
        handle.set_child(row)
        window.set_child(handle)
        pointer = SimpleNamespace(state=Gdk.ModifierType.BUTTON1_MASK)
        gesture = SimpleNamespace(get_current_event_device=lambda: pointer)
        surface = SimpleNamespace(get_device_position=lambda _device: (True, 5, 5, pointer.state))
        surface_patch = patch.object(window, "get_surface", return_value=surface)

        def press(widget):
            with patch.object(window, "pick", return_value=widget):
                scope._on_title_pressed(gesture, 1, 5, 5, window.weak_ref())

        try:
            scope.set_enabled(True)
            window.present()
            surface_patch.start()
            self.assertTrue(scope._is_title_target(title))
            self.assertFalse(scope._is_title_target(button))
            press(button)
            self.assertFalse(window.has_css_class("termia-title-held"))
            for clear in ("release", "escape", "disable", "unmap", "device"):
                with self.subTest(clear=clear):
                    scope.set_enabled(True)
                    window.present()
                    pointer.state = Gdk.ModifierType.BUTTON1_MASK
                    press(title)
                    self.assertTrue(window.has_css_class("termia-title-held"))
                    if clear == "release":
                        scope._on_title_released(gesture, 1, 5, 5, window.weak_ref())
                    elif clear == "escape":
                        self.assertFalse(scope._on_title_key(None, Gdk.KEY_Escape, 0, 0, window.weak_ref()))
                    elif clear == "disable":
                        scope.set_enabled(False)
                    elif clear == "unmap":
                        window.set_visible(False)
                    else:
                        pointer.state = Gdk.ModifierType(0)
                        deadline = time.monotonic() + 0.5
                        while scope._title_poll is not None and time.monotonic() < deadline:
                            GLib.MainContext.default().iteration(False)
                            time.sleep(0.005)
                    self.assertFalse(window.has_css_class("termia-title-held"))
                    self.assertIsNone(scope._title_poll)
            scope.set_enabled(True)
            window.present()
            window.add_css_class("message")
            press(title)
            self.assertFalse(window.has_css_class("termia-title-held"))
            window.remove_css_class("message")
            press(title)
            scope.close()
            self.assertFalse(window.has_css_class("termia-title-held"))
            self.assertEqual(len(scope._title_controllers), 0)
        finally:
            surface_patch.stop()
            scope.close()
            window.destroy()

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
                _later, later_label = window()
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
