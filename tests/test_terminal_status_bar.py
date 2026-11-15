import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from termia.models import AppSettings, TerminalSettings
from termia.stores import ConnectionStore, SettingsStore
from termia.styles import build_application_css
from termia.terminal_sessions import GLib, Gtk, TerminalSessionsMixin, Vte


class StatusHost(TerminalSessionsMixin):
    def __init__(self, theme="dark"):
        self.store = SimpleNamespace(data=SimpleNamespace(
            app=AppSettings(theme=theme), terminal=TerminalSettings()))
        self.panes = {}
        session = SimpleNamespace(panes=self.panes, pane_for_terminal=lambda terminal: self.panes.get(id(terminal)))
        self.session_registry = SimpleNamespace(sessions=lambda: [session])

    def t(self, key):
        return key

    def make_pane(self):
        bar, _status, _timer, hide, close = self.build_session_status_bar()
        terminal = Vte.Terminal()
        container = self.build_terminal_pane(bar, terminal)
        pane = SimpleNamespace(container=container, status_bar=bar, terminal=terminal, retired=False)
        self.panes[id(terminal)] = pane
        return pane, hide, close


def settle():
    deadline = time.monotonic() + 0.15
    while time.monotonic() < deadline:
        for _ in range(100):
            if not GLib.MainContext.default().pending():
                break
            GLib.MainContext.default().iteration(False)
        time.sleep(0.002)


class TerminalStatusBarTests(unittest.TestCase):
    def test_reveal_tracks_visibility_preference_and_selected_pane(self):
        host = StatusHost()
        first, hide, close = host.make_pane()
        second, _, _ = host.make_pane()
        reveal_container = first.container.get_last_child().get_last_child()
        reveal = reveal_container.get_first_child()
        self.assertEqual(hide.get_icon_name(), "pan-up-symbolic")
        self.assertEqual(close.get_icon_name(), "window-close-symbolic")
        self.assertIs(first.status_bar.get_last_child(), hide)
        self.assertEqual(reveal.get_tooltip_text(), "show_session_status_bar")
        self.assertTrue(reveal.get_visible())
        self.assertTrue(reveal_container.get_visible())
        reveal.emit("clicked")
        self.assertTrue(first.status_bar.get_visible())
        self.assertFalse(second.status_bar.get_visible())
        self.assertFalse(reveal.get_visible())
        first.status_bar.set_visible(False)
        self.assertTrue(reveal.get_visible())
        host.store.data.terminal.show_status_bar_button = False
        host.apply_status_bar_button_visibility_to_open_tabs()
        self.assertFalse(reveal_container.get_visible())
        self.assertFalse(first.status_bar.get_visible())
        new, _, _ = host.make_pane()
        self.assertFalse(new.container.get_last_child().get_last_child().get_visible())
        host.store.data.terminal.show_status_bar_button = True
        host.apply_status_bar_button_visibility_to_open_tabs()
        self.assertTrue(reveal_container.get_visible())
        first.retired = True
        reveal.emit("clicked")
        self.assertFalse(first.status_bar.get_visible())

    def test_split_line_spacing_and_status_button_hit_areas(self):
        for theme in ("light", "dark", "dark_glow"):
            for orientation in (Gtk.Orientation.VERTICAL, Gtk.Orientation.HORIZONTAL):
                with self.subTest(theme=theme, orientation=orientation):
                    host = StatusHost(theme)
                    window = Gtk.Window(default_width=900, default_height=500)
                    if theme == "dark_glow":
                        window.add_css_class("termia-dark-glow")
                    provider = Gtk.CssProvider()
                    provider.load_from_data(build_application_css("#202430", "#008712", 1, theme))
                    display = window.get_display()
                    Gtk.StyleContext.add_provider_for_display(display, provider, 600)
                    try:
                        split = Gtk.Paned(orientation=orientation)
                        split.add_css_class("termia-split-pane")
                        first, _, _ = host.make_pane()
                        second, hide, close = host.make_pane()
                        first.status_bar.set_visible(True)
                        second.status_bar.set_visible(True)
                        first.container.add_css_class("in-split")
                        second.container.add_css_class("in-split")
                        split.set_start_child(first.container)
                        split.set_end_child(second.container)
                        window.set_child(split)
                        window.present()
                        split.set_position(250)
                        settle()
                        a = first.container.compute_bounds(window)[1]
                        b = second.container.compute_bounds(window)[1]
                        gap = (b.get_y() - a.get_y() - a.get_height()
                               if orientation == Gtk.Orientation.VERTICAL
                               else b.get_x() - a.get_x() - a.get_width())
                        self.assertEqual(gap, 8 if theme == "dark_glow" else 1)
                        for button in (hide, close):
                            bounds = button.compute_bounds(window)[1]
                            # The top pixels must belong to the button, never the split handle.
                            for dy in (0.5, 1.5, bounds.get_height() / 2):
                                picked = window.pick(bounds.get_x() + bounds.get_width() / 2,
                                                     bounds.get_y() + dy, Gtk.PickFlags.DEFAULT)
                                while picked is not None and picked is not button:
                                    picked = picked.get_parent()
                                self.assertIs(picked, button)
                    finally:
                        window.destroy()
                        Gtk.StyleContext.remove_provider_for_display(display, provider)


class StatusPreferencesStorageTests(unittest.TestCase):
    def test_legacy_default_and_roundtrip_preserve_status_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "settings.json"
            original = json.dumps({"app": {"show_session_status_bar": True}, "terminal": {}})
            path.write_text(original)
            settings = SettingsStore(path)
            self.assertTrue(settings.terminal.show_status_bar_button)
            self.assertTrue(settings.app.show_session_status_bar)
            self.assertEqual(path.read_text(), original)
            store = ConnectionStore(root / "connections.json", path,
                                    root / "statistics.json", root / "instance.lock")
            try:
                store.update_terminal_settings("Monospace", 13, "#eeeeee", "#222222",
                                               show_session_status_bar=False, show_status_bar_button=False)
                # Unrelated terminal and General saves must retain the new option.
                store.update_terminal_settings("Monospace", 14, "#eeeeee", "#222222")
                store.update_app_settings(AppSettings(show_session_status_bar=False))
                reloaded = SettingsStore(path)
                self.assertFalse(reloaded.app.show_session_status_bar)
                self.assertFalse(reloaded.terminal.show_status_bar_button)
                self.assertEqual(reloaded.terminal.font_size, 14)
            finally:
                store.close()
