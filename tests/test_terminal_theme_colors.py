import json
import tempfile
import unittest
from pathlib import Path

from termia.constants import APP_THEMES, TERMINAL_PALETTES
from termia.models import AppSettings
from termia.stores import ConnectionStore, SettingsStore


class TerminalThemeColorTests(unittest.TestCase):
    def test_legacy_colors_seed_standard_themes_without_rewriting_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            original = json.dumps({
                "app": {"theme": "dark"},
                "terminal": {"foreground": "#abcdef", "background": "#123456"},
            })
            path.write_text(original, encoding="utf-8")
            store = SettingsStore(path)
            for theme in ("system", "light", "dark"):
                self.assertEqual(store.app.terminal_colors_by_theme[theme], {
                    "foreground": "#abcdef", "background": "#123456",
                })
            self.assertEqual(store.app.terminal_colors_by_theme["dark_glow"], {
                "foreground": "#839496", "background": "#182231",
            })
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_color_edits_survive_theme_switches_general_changes_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConnectionStore(root / "connections.json", root / "settings.json",
                                    root / "statistics.json", root / "instance.lock")
            try:
                expected = {}
                for index, theme in enumerate(APP_THEMES):
                    store.update_app_settings(AppSettings(theme=theme))
                    if theme == "dark_glow":
                        self.assertEqual((store.data.terminal.foreground, store.data.terminal.background),
                                         ("#839496", "#182231"))
                    foreground = f"#{index + 1:06x}"
                    background = f"#{index + 10:06x}"
                    store.update_terminal_settings("Monospace", 16, foreground, background)
                    expected[theme] = {"foreground": foreground, "background": background}
                store.update_app_settings(AppSettings(theme="dark_glow", language="es"))
                self.assertEqual(store.data.app.terminal_colors_by_theme, expected)
                for theme in APP_THEMES:
                    store.update_app_settings(AppSettings(theme=theme))
                    self.assertEqual(store.data.terminal.foreground, expected[theme]["foreground"])
                    self.assertEqual(store.data.terminal.background, expected[theme]["background"])
                    self.assertEqual(store.data.terminal.font_family, "Monospace")
                    self.assertEqual(store.data.terminal.font_size, 16)
                reloaded = SettingsStore(root / "settings.json")
                self.assertEqual(reloaded.app.terminal_colors_by_theme, expected)
                self.assertEqual(reloaded.terminal.background, expected["dark_glow"]["background"])
            finally:
                store.close()

    def test_invalid_entries_preserve_valid_profiles_and_read_only_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            original = json.dumps({"app": {
                "theme": "dark_glow",
                "terminal_colors_by_theme": {
                    "light": {"foreground": "#112233", "background": "#ddeeff"},
                    "dark_glow": {"foreground": [], "background": "invalid"},
                    "system": False,
                },
            }})
            path.write_text(original, encoding="utf-8")
            store = SettingsStore(path, read_only=True)
            self.assertEqual((store.terminal.foreground, store.terminal.background),
                             ("#839496", "#182231"))
            self.assertEqual(store.app.terminal_colors_by_theme["light"], {
                "foreground": "#112233", "background": "#ddeeff",
            })
            store.save()
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(store.recovery_messages, [])

    def test_explicit_solarized_profile_retains_selected_ubuntu_mono_font(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            foreground, background = TERMINAL_PALETTES["Solarized"]
            path.write_text(json.dumps({
                "app": {"theme": "dark_glow", "terminal_colors_by_theme": {
                    "dark_glow": {"foreground": foreground, "background": background},
                }},
                "terminal": {"font_family": "Ubuntu Mono", "font_size": 13,
                             "foreground": foreground, "background": background},
            }), encoding="utf-8")
            store = SettingsStore(path)
            self.assertEqual(store.terminal.font_family, "Ubuntu Mono")
            self.assertEqual((store.terminal.foreground, store.terminal.background),
                             TERMINAL_PALETTES["Solarized"])


if __name__ == "__main__":
    unittest.main()
