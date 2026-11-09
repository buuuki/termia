# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from termia.retron_profile import (
    MAX_PROFILE_BYTES,
    ROOT,
    build_profile_css,
    empty_profile,
    new_shadow,
    resolved,
    validate_profile,
)
from termia.retron_store import MAX_PRESETS, MAX_STORE_BYTES, RetronStore, preset_name


class RetronProfileTests(unittest.TestCase):
    def test_field_focus_overrides_preserve_scope_and_inherit_normal_values(self):
        profile = empty_profile()
        profile["components"]["fields"] = {
            "normal": {"background_color": "#112233"},
            "focus": {"border_color": "#ABCDEF", "shadows": [new_shadow()]},
            "disabled": {"border_opacity": 0.2},
        }
        self.assertEqual(validate_profile(profile), profile)
        self.assertEqual(resolved(profile, "fields", "focus")["background_color"], "#112233")
        css = build_profile_css(profile)
        focus = next(line for line in css.splitlines() if "entry:focus-within" in line)
        self.assertIn(ROOT + " spinbutton:focus-within", focus)
        self.assertIn("alpha(#ABCDEF, 1)", focus)
        self.assertIn("outline: none;", focus)
        self.assertIn("box-shadow:", focus)
        self.assertIn("entry:disabled", css)
        self.assertNotIn("textview", css)
        self.assertNotIn("button:", css.replace("spinbutton:", ""))

    def test_field_glow_alone_preserves_original_focus_outline(self):
        profile = empty_profile()
        profile["components"]["fields"] = {"focus": {"shadows": [new_shadow()]}}
        self.assertNotIn("outline:", build_profile_css(profile))
        profile["components"]["fields"]["focus"]["shadows"] = []
        css = build_profile_css(profile)
        self.assertIn("box-shadow: none", css)
        self.assertNotIn("outline:", css)

    def test_defaults_have_no_overrides_and_inheritance_is_per_property(self):
        profile = empty_profile()
        self.assertEqual(build_profile_css(profile), "")
        profile["common"] = {"normal": {"border_width": 2}, "focus": {"border_opacity": 0.8}}
        profile["components"] = {"notes": {"normal": {"border_color": "#ABCDEF"}, "focus": {"border_width": 3}}}
        result = resolved(profile, "notes", "focus")
        self.assertEqual((result["border_width"], result["border_opacity"], result["border_color"]), (3, 0.8, "#ABCDEF"))
        self.assertEqual(resolved(profile, "terminal", "focus")["border_width"], 2)
        snapshot = deepcopy(profile)
        result["shadows"].append(new_shadow())
        self.assertEqual(profile, snapshot)

    def test_every_custom_selector_excludes_alerts_and_editor(self):
        profile = empty_profile()
        profile["common"] = {"normal": {"border_style": "dotted", "background_opacity": 0.4, "shadows": [new_shadow()]}}
        css = build_profile_css(profile)
        for rule in css.splitlines():
            for selector in rule.split(" {")[0].split(", "):
                self.assertTrue(selector.startswith(ROOT), selector)
        self.assertNotIn("opacity:", css.replace("background-opacity:", ""))
        self.assertIn(".termia-terminal-pane:focus-within > scrolledwindow", css)

    def test_untrusted_profiles_cannot_inject_css_or_unbounded_effects(self):
        for key, value in (("border_color", "red; } * {color: red"), ("radius", -1),
                           ("radius", float("nan")), ("radius", float("inf")),
                           ("border_width", True), ("border_width", 100),
                           ("shadows", [new_shadow()] * 4), ("background_mode", "url(file:///test)")):
            with self.subTest(key=key, value=value):
                profile = empty_profile()
                profile["common"] = {"normal": {key: value}}
                with self.assertRaises((TypeError, ValueError)):
                    validate_profile(profile)
        for profile in ({}, {**empty_profile(), "schema_version": 2},
                        {**empty_profile(), "components": {"*": {}}}):
            with self.assertRaises(ValueError):
                validate_profile(profile)

    def test_gradients_do_not_stack_translucent_solid_and_terminal_stays_solid(self):
        profile = empty_profile()
        profile["common"] = {"normal": {"background_mode": "linear", "background_opacity": 0.5}}
        css = build_profile_css(profile)
        self.assertIn("background-color: transparent; background-image: linear-gradient", css)
        terminal_rule = next(line for line in css.splitlines() if ".termia-terminal-pane > scrolledwindow" in line)
        self.assertNotIn("gradient(", terminal_rule)
        self.assertIn("background-color: transparent", terminal_rule)
        profile["components"] = {"terminal": {"focus": {"background_opacity": 0.5}}}
        with self.assertRaises(ValueError):
            validate_profile(profile)


class RetronStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "themes" / "retron.json"
        self.writable = True
        self.store = RetronStore(self.path, lambda: self.writable)

    def test_roundtrip_is_independent_atomic_and_private(self):
        profile = self.store.load("#AABBCC")
        self.assertEqual(profile["accent"], "#AABBCC")
        self.assertFalse(self.path.exists())
        profile["components"] = {"window": {"normal": {"background_opacity": 0.75}}}
        self.store.save(profile)
        self.assertEqual(RetronStore(self.path, lambda: True).load(), profile)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_failed_replace_preserves_file_and_removes_temporary(self):
        profile = self.store.load()
        self.store.save(profile)
        original = self.path.read_bytes()
        profile["common"] = {"normal": {"radius": 15}}
        with patch("termia.retron_store.os.replace", side_effect=OSError("synthetic failure")), self.assertRaises(OSError):
            self.store.save(profile)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_legacy_load_is_read_only_and_named_save_preserves_appearance(self):
        legacy = empty_profile("#ABCDEF")
        legacy["common"] = {"normal": {"radius": 23}}
        self.path.parent.mkdir()
        raw = json.dumps(legacy).encode()
        self.path.write_bytes(raw)
        self.assertEqual(self.store.load(), legacy)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(self.store.presets, {})
        self.store.save(legacy, presets={"Soft": legacy}, active_name="Soft")
        document = json.loads(self.path.read_text())
        self.assertEqual(document["schema_version"], 2)
        reloaded = RetronStore(self.path, lambda: True)
        self.assertEqual(reloaded.load(), legacy)
        self.assertEqual(reloaded.presets, {"Soft": legacy})
        self.assertEqual(reloaded.active_name, "Soft")

    def test_invalid_libraries_preserve_bytes_and_disable_writes(self):
        self.path.parent.mkdir()
        profile = empty_profile()
        base = {"schema_version": 2, "current": profile, "presets": {"Soft": profile}, "active_name": "Soft"}
        variants = [
            {**base, "presets": {"Soft": profile, "soft": profile}},
            {**base, "presets": {" ": profile}},
            {**base, "presets": {"x" * 65: profile}},
            {**base, "presets": {"bad\nname": profile}},
            {**base, "presets": {str(i): profile for i in range(MAX_PRESETS + 1)}},
            {**base, "presets": {"Soft": {**profile, "schema_version": 99}}},
            {**base, "active_name": "Missing"},
            {**base, "active_name": []},
            {**base, "extra": True},
            {**base, "schema_version": 99},
        ]
        for document in variants:
            with self.subTest(document=document):
                raw = json.dumps(document).encode()
                self.path.write_bytes(raw)
                store = RetronStore(self.path, lambda: True)
                self.assertEqual(store.load(), profile)
                self.assertTrue(store.load_error)
                with self.assertRaises(PermissionError):
                    store.save(profile)
                self.assertEqual(self.path.read_bytes(), raw)
        self.path.write_bytes(b" " * (MAX_STORE_BYTES + 1))
        store = RetronStore(self.path, lambda: True)
        store.load()
        self.assertTrue(store.load_error)

    def test_failed_catalog_save_does_not_mutate_memory_or_disk(self):
        profile = self.store.load()
        self.store.save(profile, presets={"First": profile}, active_name="First")
        raw = self.path.read_bytes()
        with patch("termia.retron_store.os.replace", side_effect=OSError("synthetic failure")), self.assertRaises(OSError):
            self.store.save(profile, presets={"Second": profile}, active_name="Second")
        self.assertEqual(self.store.active_name, "First")
        self.assertEqual(set(self.store.presets), {"First"})
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(preset_name("  Cafe\u0301  "), "Café")

    def test_read_only_future_corrupt_and_external_edits_are_preserved(self):
        self.writable = False
        with self.assertRaises(PermissionError):
            self.store.save(empty_profile())
        self.assertFalse(self.path.parent.exists())
        self.path.parent.mkdir()
        for raw in (b"{broken", json.dumps({**empty_profile(), "schema_version": 99}).encode(), b" " * (MAX_PROFILE_BYTES + 1)):
            self.path.write_bytes(raw)
            store = RetronStore(self.path, lambda: True)
            self.assertEqual(store.load(), empty_profile())
            self.assertTrue(store.load_error)
            with self.assertRaises(PermissionError):
                store.save(empty_profile())
            self.assertEqual(self.path.read_bytes(), raw)
        self.path.write_text(json.dumps(empty_profile()), encoding="utf-8")
        store = RetronStore(self.path, lambda: True)
        store.load()
        self.path.write_bytes(b"external")
        with self.assertRaises(OSError):
            store.save(empty_profile())
        self.assertEqual(self.path.read_bytes(), b"external")


if __name__ == "__main__":
    unittest.main()
