import json
import tempfile
import unittest
from pathlib import Path

from termia.constants import DEFAULT_DARK_GLOW_BORDER_COLOR
from termia.models import AppSettings
from termia.stores import ConnectionStore, SettingsStore, normalize_app_settings
from termia.styles import build_application_css


class BorderColorTests(unittest.TestCase):
    def test_missing_and_invalid_values_fall_back_without_replacing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for value in (None, 42, "red", "#123", "#ggff00", "#123456; color: red"):
                with self.subTest(value=value):
                    original = json.dumps({"app": {"dark_glow_border_color": value, "language": "es"}})
                    path.write_text(original, encoding="utf-8")
                    store = SettingsStore(path, read_only=True)
                    self.assertEqual(store.app.dark_glow_border_color, DEFAULT_DARK_GLOW_BORDER_COLOR)
                    self.assertEqual(store.app.language, "es")
                    store.save()
                    self.assertEqual(path.read_text(encoding="utf-8"), original)
                    self.assertEqual(store.recovery_messages, [])
        self.assertEqual(normalize_app_settings(AppSettings()).dark_glow_border_color,
                         DEFAULT_DARK_GLOW_BORDER_COLOR)

    def test_custom_choice_survives_other_preference_changes_and_restart_and_can_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "settings.json"
            store = ConnectionStore(root / "connections.json", path,
                                    root / "statistics.json", root / "instance.lock")
            try:
                store.update_app_settings(AppSettings(theme="dark_glow"), dark_glow_border_color="#aabbcc")
                store.update_app_settings(AppSettings(theme="light", language="es"))
                store.update_notes_editor({"size": 14})
                self.assertEqual(SettingsStore(path).app.dark_glow_border_color, "#AABBCC")
                store.update_app_settings(AppSettings(theme="dark_glow"))
                self.assertEqual(store.data.app.dark_glow_border_color, "#AABBCC")
                store.update_app_settings(AppSettings(theme="dark_glow"),
                                          dark_glow_border_color=DEFAULT_DARK_GLOW_BORDER_COLOR)
                self.assertEqual(SettingsStore(path).app.dark_glow_border_color,
                                 DEFAULT_DARK_GLOW_BORDER_COLOR)
            finally:
                store.close()

    def test_custom_border_changes_dark_glow_frames_but_preserves_semantic_roles(self):
        css = build_application_css("#182231", "#008712", 1, "dark_glow",
                                    dark_glow_border_color="#AABBCC").decode()
        self.assertIn("border: 1px solid alpha(#AABBCC, 0.50)", css)
        self.assertIn("border: 1px solid alpha(#AABBCC, 0.35); border-radius: 999px", css)
        self.assertIn("border-color: alpha(#AABBCC, 0.50); box-shadow: 0 0 3px alpha(#AABBCC, 0.05)", css)
        self.assertIn("inset 0 0 0 1px alpha(#AABBCC, 0.65)", css)
        self.assertIn("border-color: #78BD97", css)
        self.assertIn("border-color: #D8848D", css)

    def test_ordinary_theme_css_ignores_dark_glow_border_choice(self):
        for theme in ("system", "light", "dark"):
            with self.subTest(theme=theme):
                ordinary = build_application_css("#202020", "#008712", 1, theme)
                customized = build_application_css("#202020", "#008712", 1, theme,
                                                     dark_glow_border_color="#AABBCC")
                self.assertEqual(customized, ordinary)


if __name__ == "__main__":
    unittest.main()
