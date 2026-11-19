import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class DiagnosticsTranslationsTests(unittest.TestCase):
    def setUp(self):
        source = (Path(__file__).resolve().parents[1]
                  / "tools/addon-lab/termia-plugins/diagnostics/src/termia_diagnostics/i18n.py")
        spec = importlib.util.spec_from_file_location("diagnostics_translation_test", source)
        self.translations = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.translations)
        temporary = tempfile.TemporaryDirectory(prefix="termia-plugin-translations-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.locales = root / "locales"
        self.locales.mkdir()
        self.write_catalog("en", {"title": "Diagnostics", "close": "Close"})
        location = patch.object(self.translations, "__file__", str(root / "i18n.py"))
        location.start()
        self.addCleanup(location.stop)

    def write_catalog(self, language, messages):
        (self.locales / f"{language}.json").write_text(json.dumps(messages), encoding="utf-8")

    def test_missing_optional_catalog_uses_english(self):
        for language in ("es", "ca"):
            with self.subTest(language=language):
                translate = self.translations.translator(language)
                self.assertEqual(translate("title"), "Diagnostics")
                self.assertEqual(translate("close"), "Close")

    def test_partial_catalog_preserves_translations_and_falls_back_per_key(self):
        self.write_catalog("es", {"title": "Diagnóstico"})
        translate = self.translations.translator("es")
        self.assertEqual(translate("title"), "Diagnóstico")
        self.assertEqual(translate("close"), "Close")
        self.assertEqual(translate("unknown_key"), "unknown_key")

    def test_unsupported_language_uses_english(self):
        self.assertEqual(self.translations.translator("fr")("title"), "Diagnostics")

    def test_missing_english_catalog_is_an_error(self):
        self.write_catalog("es", {"title": "Diagnóstico"})
        (self.locales / "en.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.translations.translator("es")

    def test_invalid_optional_catalog_is_not_silently_ignored(self):
        (self.locales / "es.json").write_text("invalid JSON", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.translations.translator("es")


if __name__ == "__main__":
    unittest.main()
